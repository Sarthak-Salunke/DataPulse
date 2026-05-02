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
from pyspark.sql import SparkSession
from pyspark.streaming import StreamingContext
from pyspark.sql.functions import (
    col, to_timestamp, concat_ws, current_timestamp,
    year, broadcast
)
from pyspark.ml import PipelineModel
from pyspark.ml.classification import RandomForestClassificationModel
from dotenv import load_dotenv
import json
import psycopg2

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spark_jobs.utils import (
    create_spark_session, read_from_postgres,
    get_postgres_properties, distance_udf, print_section
)

load_dotenv()


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
        
        # Select features
        feature_cols = ["cc_num", "category", "merchant", "distance", "amt", "age"]
        feature_df = enriched_df.select(
            *[col(c) for c in feature_cols],
            col("trans_num"),
            col("trans_time"),
            col("merch_lat"),
            col("merch_long")
        )
        
        # Apply preprocessing and prediction
        preprocessed_df = preprocessing_model.transform(feature_df)
        predictions_df = rf_model.transform(preprocessed_df)
        
        # Add is_fraud and created_at
        predictions_df = predictions_df.withColumn("is_fraud", col("prediction"))
        predictions_df = predictions_df.withColumn("created_at", current_timestamp())
        
        # Select final columns
        final_df = predictions_df.select(
            "cc_num", "trans_time", "trans_num", "category", "merchant",
            "amt", "merch_lat", "merch_long", "distance", "age", "is_fraud",
            "created_at"
        )
        
        # Split fraud and non-fraud
        fraud_df = final_df.filter(col("is_fraud") > 0.5)
        non_fraud_df = final_df.filter(col("is_fraud") <= 0.5)
        
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
    batch_interval = int(os.getenv('BATCH_INTERVAL', '10'))  # seconds
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
