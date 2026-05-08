"""
Spark Job: Real-time Fraud Detection - DStreams
Replaces DstreamFraudDetection.scala

This job:
1. Reads transactions from Kafka using DStreams
2. Enriches with customer data from PostgreSQL
3. Predicts fraud using trained ML model
4. Writes results to PostgreSQL
5. Tracks Kafka offsets in PostgreSQL
"""

import sys
import os
from pyspark import SparkContext
from pyspark.sql import SparkSession, Window
from pyspark.streaming import StreamingContext
from pyspark.sql.functions import (
    col, to_timestamp, concat_ws, current_timestamp,
    year, broadcast, when, lit, hour, dayofweek, count, sum as spark_sum,
    create_map, coalesce, vector_to_array, concat
)
from pyspark.ml import PipelineModel
from pyspark.ml.classification import RandomForestClassificationModel
from dotenv import load_dotenv
import json
import psycopg2
from concurrent.futures import ThreadPoolExecutor

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spark_jobs.utils import (
    create_spark_session, read_from_postgres,
    get_postgres_properties, distance_udf, print_section
)

load_dotenv()

# Per-category fraud probability thresholds (tuned from offline model analysis)
DEFAULT_THRESHOLD = 0.40

_threshold_map = create_map([
    lit("misc_net"),         lit(0.25),
    lit("online_shopping"),  lit(0.25),
    lit("online_gift_card"), lit(0.20),
    lit("travel"),           lit(0.30),
    lit("grocery_pos"),      lit(0.45),
    lit("gas_transport"),    lit(0.45),
])

HIGH_RISK_CATEGORIES = [
    "misc_net", "online_shopping", "online_gift_card",
    "shopping_net", "shopping_pos", "home",
]


def get_kafka_offset(partition):
    """
    Get last processed Kafka offset from PostgreSQL
    
    Args:
        partition: Kafka partition number
    
    Returns:
        Offset value
    """
    try:
        conn = psycopg2.connect(**{
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': os.getenv('DB_PORT', '5432'),
            'database': os.getenv('DB_NAME', 'fraud_detection'),
            'user': os.getenv('DB_USER', 'postgres'),
            'password': os.getenv('DB_PASSWORD', 'postgres123')
        })
        cursor = conn.cursor()
        cursor.execute("SELECT offset FROM kafka_offset WHERE partition = %s;", (partition,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        return result[0] if result else 0
    except Exception as e:
        print(f"[WARNING] Could not get Kafka offset: {e}")
        return 0


def update_kafka_offset(partition, offset):
    """
    Update Kafka offset in PostgreSQL
    
    Args:
        partition: Kafka partition number
        offset: New offset value
    """
    try:
        conn = psycopg2.connect(**{
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': os.getenv('DB_PORT', '5432'),
            'database': os.getenv('DB_NAME', 'fraud_detection'),
            'user': os.getenv('DB_USER', 'postgres'),
            'password': os.getenv('DB_PASSWORD', 'postgres123')
        })
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO kafka_offset (partition, offset, updated_at)
            VALUES (%s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (partition)
            DO UPDATE SET offset = EXCLUDED.offset, updated_at = CURRENT_TIMESTAMP;
        """, (partition, offset))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"[ERROR] Could not update Kafka offset: {e}")


def load_models(spark):
    """Load trained ML models"""
    project_home = os.path.join(os.path.expanduser("~"), "frauddetection")
    model_path = os.getenv('MODEL_PATH',
                          os.path.join(project_home, "ml", "models", "RandomForestModel"))
    preprocessing_path = os.getenv('PREPROCESSING_MODEL_PATH',
                                   os.path.join(project_home, "ml", "models", "PreprocessingModel"))
    
    print(f"[INFO] Loading preprocessing model: {preprocessing_path}")
    preprocessing_model = PipelineModel.load(preprocessing_path)
    
    print(f"[INFO] Loading Random Forest model: {model_path}")
    rf_model = RandomForestClassificationModel.load(model_path)
    
    return preprocessing_model, rf_model


def process_rdd(rdd, spark, customer_df_broadcast, preprocessing_model, rf_model):
    """
    Process each RDD batch
    
    Args:
        rdd: RDD containing Kafka messages
        spark: SparkSession
        customer_df_broadcast: Broadcast customer data
        preprocessing_model: Trained preprocessing pipeline
        rf_model: Trained Random Forest model
    """
    if rdd.isEmpty():
        return
    
    try:
        # Convert RDD to DataFrame
        json_rdd = rdd.map(lambda x: json.loads(x[1]))
        
        if json_rdd.isEmpty():
            return
        
        # Create DataFrame
        transactions_df = spark.read.json(json_rdd)
        
        count = transactions_df.count()
        print(f"\n[BATCH] Processing {count} transactions...")
        
        # Process timestamp
        transactions_df = transactions_df.withColumn(
            "trans_time",
            to_timestamp(
                concat_ws(" ", col("trans_date"), col("trans_time")),
                "yyyy-MM-dd HH:mm:ss"
            )
        )
        
        # Join with customer data
        customer_df = customer_df_broadcast.value
        
        enriched_df = transactions_df.join(
            customer_df,
            transactions_df.cc_num == customer_df.cust_cc_num,
            "left"
        )
        
        # Calculate distance
        enriched_df = enriched_df.withColumn(
            "distance",
            distance_udf(
                col("cust_lat"),
                col("cust_long"),
                col("merch_lat"),
                col("merch_long")
            )
        )
        
        # Temporal features from transaction timestamp
        enriched_df = enriched_df \
            .withColumn("hour",       hour(col("trans_time"))) \
            .withColumn("dayofweek",  dayofweek(col("trans_time"))) \
            .withColumn("is_weekend", when(dayofweek(col("trans_time")).isin(1, 7), 1).otherwise(0))

        # Velocity features: 1-hour rolling window per card
        # Repartition by cc_num for efficient, OOM-safe window computation
        enriched_df = enriched_df.repartition(col("cc_num"))
        vel_window = (
            Window.partitionBy("cc_num")
                  .orderBy(col("trans_time").cast("long"))
                  .rangeBetween(-3600, 0)
        )
        enriched_df = enriched_df \
            .withColumn("tx_count_1h", count("trans_num").over(vel_window)) \
            .withColumn("tx_amt_1h",   spark_sum("amt").over(vel_window))

        # Rule engine: 10-minute window (rule use only — NOT in ML feature vector)
        win_10min = (
            Window.partitionBy("cc_num")
                  .orderBy(col("trans_time").cast("long"))
                  .rangeBetween(-600, 0)
        )
        enriched_df = enriched_df.withColumn("tx_count_10min", count("trans_num").over(win_10min))

        # Select features (extended with temporal & velocity)
        feature_cols = ["cc_num", "category", "merchant", "distance", "amt", "age",
                        "hour", "dayofweek", "is_weekend", "tx_count_1h", "tx_amt_1h"]
        feature_df = enriched_df.select(
            *[col(c) for c in feature_cols],
            col("trans_num"),
            col("trans_time"),
            col("merch_lat"),
            col("merch_long"),
            col("tx_count_10min")     # carried for rule engine, excluded from ML features
        )

        # Apply preprocessing pipeline; cache to avoid recomputing DAG per model
        preprocessed_df = preprocessing_model.transform(feature_df).cache()

        # Score models in parallel threads
        with ThreadPoolExecutor() as ex:
            rf_future = ex.submit(rf_model.transform, preprocessed_df)
            predictions_df = rf_future.result()

        preprocessed_df.unpersist()
        
        # Adaptive threshold: evaluate probability[1] against per-category threshold
        predictions_df = predictions_df \
            .withColumn("fraud_score", vector_to_array(col("probability"))[1]) \
            .withColumn("threshold",   coalesce(_threshold_map[col("category")], lit(DEFAULT_THRESHOLD))) \
            .withColumn("is_fraud",    when(col("fraud_score") >= col("threshold"), 1.0).otherwise(0.0))

        # ── Rule Engine ───────────────────────────────────────────────────────────
        # Broadcast join avg_amt_30d from customer_stats (graceful on empty/missing table)
        try:
            props = get_postgres_properties()
            stats_df = spark.read.jdbc(
                url=props['url'],
                table='customer_stats',
                properties={'user': props['user'], 'password': props['password'], 'driver': props['driver']}
            ).select("cc_num", "avg_amt_30d")
            predictions_df = predictions_df.join(broadcast(stats_df), on="cc_num", how="left")
        except Exception:
            predictions_df = predictions_df.withColumn("avg_amt_30d", lit(None).cast("double"))

        # Boolean rule conditions (native Spark — no UDFs, no row iteration)
        r_travel   = (col("distance") > 500) & (col("tx_count_10min") > 1)
        r_spike    = col("avg_amt_30d").isNotNull() & (col("amt") > col("avg_amt_30d") * 5)
        r_highrisk = col("category").isin(HIGH_RISK_CATEGORIES) & (col("amt") > 1000)

        predictions_df = predictions_df \
            .withColumn("rule_severity",
                        when(r_travel,    lit("CRITICAL"))
                        .when(r_spike,    lit("HIGH"))
                        .when(r_highrisk, lit("MEDIUM"))
                        .otherwise(lit("NONE"))) \
            .withColumn("rule_flags",
                        concat(
                            lit("["),
                            concat_ws(",",
                                when(r_travel,    lit('"IMPOSSIBLE_TRAVEL:CRITICAL"')),
                                when(r_spike,     lit('"AMOUNT_SPIKE:HIGH"')),
                                when(r_highrisk,  lit('"HIGH_RISK_MERCHANT:MEDIUM"'))
                            ),
                            lit("]")
                        )) \
            .withColumn("is_fraud",
                        when((col("is_fraud") == 1.0) | (col("rule_severity") == "CRITICAL"), 1.0)
                        .otherwise(0.0))
        # ── End Rule Engine ───────────────────────────────────────────────────────

        predictions_df = predictions_df.withColumn("created_at", current_timestamp())

        # Select final columns
        final_df = predictions_df.select(
            "cc_num", "trans_time", "trans_num", "category", "merchant",
            "amt", "merch_lat", "merch_long", "distance", "age", "is_fraud",
            "rule_flags", "rule_severity", "created_at"
        )

        # Split fraud and non-fraud
        fraud_df     = final_df.filter(col("is_fraud") == 1.0)
        non_fraud_df = final_df.filter(col("is_fraud") == 0.0)
        
        fraud_count = fraud_df.count()
        non_fraud_count = non_fraud_df.count()
        
        # Get PostgreSQL properties
        props = get_postgres_properties()
        
        # Write to PostgreSQL
        if fraud_count > 0:
            print(f"[ALERT] [WARNING] FRAUD DETECTED: {fraud_count} transactions")
            fraud_df.write.jdbc(
                url=props['url'],
                table='fraud_transaction',
                mode='append',
                properties={'user': props['user'], 'password': props['password'], 'driver': props['driver']}
            )
        
        if non_fraud_count > 0:
            print(f"[INFO] [OK] Normal: {non_fraud_count} transactions")
            non_fraud_df.write.jdbc(
                url=props['url'],
                table='non_fraud_transaction',
                mode='append',
                properties={'user': props['user'], 'password': props['password'], 'driver': props['driver']}
            )
        
        print(f"[BATCH] [OK] Completed ({fraud_count} fraud, {non_fraud_count} normal)")
        
    except Exception as e:
        print(f"[ERROR] Batch processing failed: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Main DStreams function"""
    print_section("FRAUD DETECTION: DSTREAMS")
    
    # Create Spark session and context
    spark = create_spark_session("Real-time Fraud Detection - DStreams")
    sc = spark.sparkContext
    
    # Create Streaming Context
    batch_interval = int(os.getenv('BATCH_INTERVAL', '5'))  # seconds
    ssc = StreamingContext(sc, batch_interval)
    
    print(f"[INFO] Batch interval: {batch_interval} seconds")
    
    # Load models
    preprocessing_model, rf_model = load_models(spark)
    
    # Load customer data and broadcast
    print("[INFO] Loading customer data...")
    customer_df = read_from_postgres(spark, 'customer', ['cc_num', 'lat', 'long', 'dob'])
    customer_df = customer_df.withColumn("age", year(current_timestamp()) - year(col("dob")))
    customer_df = customer_df.select(
        col("cc_num").alias("cust_cc_num"),
        col("lat").alias("cust_lat"),
        col("long").alias("cust_long"),
        col("age")
    )
    
    customer_df_broadcast = sc.broadcast(customer_df)
    print(f"[OK] Customer data broadcasted ({customer_df.count()} records)")
    
    # Kafka configuration
    kafka_bootstrap_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
    kafka_topic = os.getenv('KAFKA_TOPIC', 'creditcardTransaction')
    
    print_section("KAFKA CONFIGURATION")
    print(f"[INFO] Bootstrap servers: {kafka_bootstrap_servers}")
    print(f"[INFO] Topic: {kafka_topic}")
    
    # Kafka parameters
    kafka_params = {
        "bootstrap.servers": kafka_bootstrap_servers,
        "auto.offset.reset": "latest",
        "enable.auto.commit": False,
        "group.id": "fraud-detection-dstream"
    }
    
    try:
        from kafka import KafkaConsumer
        
        print_section("STARTING DSTREAM")
        print("[INFO] Creating Kafka DStream...")
        print("[INFO] Monitoring for fraudulent transactions...")
        print("[INFO] Press Ctrl+C to stop\n")
        
        # Create Kafka DStream (simplified for Python)
        # Note: Full Kafka-Spark integration requires kafka-python package
        from pyspark.streaming.kafka import KafkaUtils
        
        kafka_stream = KafkaUtils.createDirectStream(
            ssc,
            [kafka_topic],
            kafka_params
        )
        
        # Process each RDD
        kafka_stream.foreachRDD(
            lambda rdd: process_rdd(
                rdd, spark, customer_df_broadcast,
                preprocessing_model, rf_model
            )
        )
        
        # Start streaming
        ssc.start()
        ssc.awaitTermination()
        
    except KeyboardInterrupt:
        print("\n\n[INFO] Stopping DStream (Ctrl+C detected)...")
        ssc.stop(stopSparkContext=True, stopGraceFully=True)
        print("[OK] DStream stopped gracefully")
    except Exception as e:
        print(f"\n[ERROR] DStream failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
