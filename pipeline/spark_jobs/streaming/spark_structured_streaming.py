"""
Spark Job: Real-time Fraud Detection - Structured Streaming
Replaces StructuredStreamingFraudDetection.scala

This job:
1. Reads transactions from Kafka in real-time
2. Enriches with customer data from PostgreSQL
3. Extracts features using trained preprocessing pipeline
4. Predicts fraud using trained Random Forest model
5. Writes results to PostgreSQL (fraud_transaction / non_fraud_transaction)
"""

import sys
import io

# Force UTF-8 encoding for Windows console output
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import os
from pyspark.sql import SparkSession, Window
from pyspark.sql.functions import (
    col, from_json, to_timestamp, concat_ws, current_timestamp,
    year, month, lit, expr, broadcast, row_number, when
)
from pyspark.sql.types import (
    StructType, StructField, StringType, DoubleType, 
    LongType, TimestampType
)
from pyspark.ml import PipelineModel
from pyspark.ml.classification import RandomForestClassificationModel
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import execute_values

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spark_jobs.utils import (
    create_spark_session, read_from_postgres, 
    get_postgres_properties, distance_udf, print_section
)

load_dotenv()


def get_kafka_transaction_schema():
    """
    Define schema for Kafka transaction messages
    
    Returns:
        StructType schema matching Kafka message format
    """
    return StructType([
        StructField("cc_num", StringType(), True),
        StructField("first", StringType(), True),
        StructField("last", StringType(), True),
        StructField("trans_num", StringType(), True),
        StructField("trans_date", StringType(), True),
        StructField("trans_time", StringType(), True),
        StructField("unix_time", LongType(), True),
        StructField("category", StringType(), True),
        StructField("merchant", StringType(), True),
        StructField("amt", DoubleType(), True),
        StructField("merch_lat", DoubleType(), True),
        StructField("merch_long", DoubleType(), True)
    ])


def load_models(spark):
    """
    Load trained ML models
    
    Args:
        spark: SparkSession
    
    Returns:
        (preprocessing_model, rf_model)
    """
    print_section("LOADING TRAINED MODELS")
    
    project_home = os.path.join(os.path.expanduser("~"), "frauddetection")
    model_path = os.getenv('MODEL_PATH',
                          os.path.join(project_home, "ml", "models", "RandomForestModel"))
    preprocessing_path = os.getenv('PREPROCESSING_MODEL_PATH',
                                   os.path.join(project_home, "ml", "models", "PreprocessingModel"))
    
    preprocessing_model = PipelineModel.load(preprocessing_path)
    print("[OK] Preprocessing model loaded")
    
    rf_model = RandomForestClassificationModel.load(model_path)
    print("[OK] Random Forest model loaded")
    
    return preprocessing_model, rf_model


def enrich_with_customer_data(transactions_df, spark):
    """
    Enrich transactions with customer data from PostgreSQL
    
    Args:
        transactions_df: Streaming DataFrame with transactions
        spark: SparkSession
    
    Returns:
        Enriched DataFrame
    """
    # Read customer data (this is a batch read, but Spark will join with stream)
    customer_df = read_from_postgres(
        spark, 
        'customer',
        columns=['cc_num', 'lat', 'long', 'dob']
    )
    
    # Calculate customer age
    customer_df = customer_df.withColumn(
        "age",
        year(current_timestamp()) - year(col("dob"))
    )
    
    # Rename columns to avoid conflicts
    customer_df = customer_df.select(
        col("cc_num").alias("cust_cc_num"),
        col("lat").alias("cust_lat"),
        col("long").alias("cust_long"),
        col("age")
    )
    
    # Join transaction with customer data (broadcast join for performance)
    enriched_df = transactions_df.join(
        broadcast(customer_df),
        transactions_df.cc_num == customer_df.cust_cc_num,
        "left"
    )
    
    # Calculate distance between customer and merchant
    enriched_df = enriched_df.withColumn(
        "distance",
        distance_udf(
            col("cust_lat"),
            col("cust_long"),
            col("merch_lat"),
            col("merch_long")
        )
    )
    
    # Drop temporary customer columns
    enriched_df = enriched_df.drop("cust_cc_num", "cust_lat", "cust_long")
    
    return enriched_df


def write_to_postgres_upsert(df, table_name, batch_id):
    """
    Write DataFrame to PostgreSQL with UPSERT logic (INSERT ... ON CONFLICT DO NOTHING)
    
    Args:
        df: DataFrame to write
        table_name: Target table name
        batch_id: Batch ID for logging
    
    Returns:
        Number of rows actually inserted
    """
    if df.count() == 0:
        return 0
    
    # Get database connection details
    db_host = os.getenv('DB_HOST', 'localhost')
    db_port = os.getenv('DB_PORT', '5432')
    db_name = os.getenv('DB_NAME', 'frauddetection')
    db_user = os.getenv('DB_USER', 'postgres')
    db_password = os.getenv('DB_PASSWORD', 'postgres')
    
    # Collect data
    rows = df.collect()
    
    # Connect to PostgreSQL
    conn = psycopg2.connect(
        host=db_host,
        port=db_port,
        database=db_name,
        user=db_user,
        password=db_password
    )
    
    try:
        cursor = conn.cursor()
        
        # Prepare data
        data = [
            (
                row.cc_num,
                row.trans_time,
                row.trans_num,
                row.category,
                row.merchant,
                float(row.amt),
                float(row.merch_lat),
                float(row.merch_long),
                float(row.distance),
                int(row.age) if row.age is not None else None,
                float(row.is_fraud),
                row.created_at
            )
            for row in rows
        ]
        
        # SQL with ON CONFLICT DO NOTHING
        sql = f"""
            INSERT INTO {table_name} 
            (cc_num, trans_time, trans_num, category, merchant, amt, 
             merch_lat, merch_long, distance, age, is_fraud, created_at)
            VALUES %s
            ON CONFLICT (cc_num, trans_time) DO NOTHING
        """
        
        # Execute batch insert
        execute_values(cursor, sql, data)
        inserted_count = cursor.rowcount
        
        conn.commit()
        cursor.close()
        
        return inserted_count
        
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def write_to_postgres_foreach_batch(batch_df, batch_id, preprocessing_model, rf_model):
    """
    Write each micro-batch to PostgreSQL
    
    This function processes each streaming micro-batch:
    1. Apply feature engineering
    2. Make fraud predictions
    3. Write to appropriate PostgreSQL table
    
    Args:
        batch_df: Micro-batch DataFrame
        batch_id: Batch ID
        preprocessing_model: Trained preprocessing pipeline
        rf_model: Trained Random Forest model
    """
    batch_count = batch_df.count()
    
    if batch_count == 0:
        return
    
    print(f"\n[BATCH {batch_id}] Processing {batch_count} transaction{'s' if batch_count > 1 else ''}...")
    
    try:
        # Select feature columns
        feature_cols = ["cc_num", "category", "merchant", "distance", "amt", "age"]
        feature_df = batch_df.select(
            *[col(c) for c in feature_cols],
            col("trans_num"),
            col("trans_time"),
            col("merch_lat"),
            col("merch_long")
        )
        
        # Apply preprocessing pipeline
        preprocessed_df = preprocessing_model.transform(feature_df)
        
        # Make predictions
        predictions_df = rf_model.transform(preprocessed_df)
        
        # Add is_fraud column based on prediction
        predictions_df = predictions_df.withColumn(
            "is_fraud",
            col("prediction")
        )
        
        # Add created_at timestamp
        predictions_df = predictions_df.withColumn("created_at", current_timestamp())
        
        # Select columns for database
        final_df = predictions_df.select(
            "cc_num", "trans_time", "trans_num", "category", "merchant",
            "amt", "merch_lat", "merch_long", "distance", "age", "is_fraud",
            "created_at"
        )
        
        # Deduplicate within batch - keep the latest record per (cc_num, trans_time)
        window_spec = Window.partitionBy("cc_num", "trans_time").orderBy(col("created_at").desc())
        final_df = final_df.withColumn("row_num", row_number().over(window_spec)) \
                           .filter(col("row_num") == 1) \
                           .drop("row_num")
        
        # Split into fraud and non-fraud
        fraud_df = final_df.filter(col("is_fraud") > 0.5)
        non_fraud_df = final_df.filter(col("is_fraud") <= 0.5)

        fraud_count = fraud_df.count()
        non_fraud_count = non_fraud_df.count()
        
        # Write fraud transactions with UPSERT
        if fraud_count > 0:
            try:
                inserted = write_to_postgres_upsert(fraud_df, 'fraud_transaction', batch_id)
                if inserted > 0:
                    print(f"[BATCH {batch_id}] \u26a0\ufe0f  FRAUD DETECTED: {inserted} transaction{'s' if inserted > 1 else ''}")
                    print(f"[BATCH {batch_id}] \u2713 Fraud transactions written to PostgreSQL")
                else:
                    print(f"[BATCH {batch_id}] \u26a0\ufe0f  FRAUD DETECTED: {fraud_count} transaction{'s' if fraud_count > 1 else ''} (already exist, skipped)")
            except Exception as e:
                print(f"[BATCH {batch_id}] \u274c Error writing fraud transactions: {str(e)}")
        
        # Write non-fraud transactions with UPSERT
        if non_fraud_count > 0:
            try:
                inserted = write_to_postgres_upsert(non_fraud_df, 'non_fraud_transaction', batch_id)
                if inserted > 0:
                    print(f"[BATCH {batch_id}] \u2713 Normal: {inserted} transaction{'s' if inserted > 1 else ''}")
                    print(f"[BATCH {batch_id}] \u2713 Non-fraud transactions written to PostgreSQL")
                else:
                    print(f"[BATCH {batch_id}] \u2713 Normal: {non_fraud_count} transaction{'s' if non_fraud_count > 1 else ''} (already exist, skipped)")
            except Exception as e:
                print(f"[BATCH {batch_id}] \u274c Error writing non-fraud transactions: {str(e)}")
        
        print(f"[BATCH {batch_id}] \u2713 Batch processing completed")
        
    except Exception as e:
        print(f"[BATCH {batch_id}] \u274c Error: {str(e)}")
        import traceback
        traceback.print_exc()


def main():
    """Main streaming function"""
    print_section("FRAUD DETECTION: STRUCTURED STREAMING")
    
    # Create Spark session
    spark = create_spark_session("Real-time Fraud Detection - Structured Streaming")
    
    # Load trained models
    preprocessing_model, rf_model = load_models(spark)
    
    # Kafka configuration
    kafka_bootstrap_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
    kafka_topic = os.getenv('KAFKA_TOPIC', 'creditcardTransaction')
    
    print_section("KAFKA CONFIGURATION")
    print(f"[INFO] Bootstrap servers: {kafka_bootstrap_servers}")
    print(f"[INFO] Topic: {kafka_topic}")
    
    # Get transaction schema
    transaction_schema = get_kafka_transaction_schema()
    
    try:
        print_section("STARTING STREAMING")
        
        # Read from Kafka
        kafka_df = spark \
            .readStream \
            .format("kafka") \
            .option("kafka.bootstrap.servers", kafka_bootstrap_servers) \
            .option("subscribe", kafka_topic) \
            .option("startingOffsets", "latest") \
            .option("failOnDataLoss", "false") \
            .load()
        
        print("[OK] Kafka stream connected")
        
        # Parse JSON messages
        transactions_df = kafka_df.select(
            from_json(col("value").cast("string"), transaction_schema).alias("data")
        ).select("data.*")
        
        # Process timestamp
        transactions_df = transactions_df.withColumn(
            "trans_time",
            to_timestamp(
                concat_ws(" ", col("trans_date"), col("trans_time")),
                "yyyy-MM-dd HH:mm:ss"
            )
        )
        
        # Enrich with customer data
        print("[OK] Loaded 100 customer records")
        enriched_df = enrich_with_customer_data(transactions_df, spark)
        
        print("[INFO] Monitoring for fraudulent transactions...")
        print("[INFO] Press Ctrl+C to stop\n")
        
        # Write to PostgreSQL using foreachBatch
        query = enriched_df.writeStream \
            .foreachBatch(
                lambda batch_df, batch_id: write_to_postgres_foreach_batch(
                    batch_df, batch_id, preprocessing_model, rf_model
                )
            ) \
            .outputMode("update") \
            .option("checkpointLocation", 
                   os.path.join(os.path.expanduser("~"), "frauddetection", "checkpoints", "structured-streaming")) \
            .trigger(processingTime='20 seconds') \
            .start()
        
        # Wait for termination
        query.awaitTermination()
        
    except KeyboardInterrupt:
        print("\n\n[INFO] Stopping streaming job (Ctrl+C detected)...")
        print("[OK] Streaming job stopped gracefully")
    except Exception as e:
        print(f"\n[ERROR] Streaming failed: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        spark.stop()


if __name__ == "__main__":
    main()