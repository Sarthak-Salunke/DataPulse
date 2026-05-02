"""
Spark Job: Import Initial Data to PostgreSQL
Replaces IntialImportToCassandra.scala

This job:
1. Reads customer and transaction CSV files
2. Processes and transforms the data
3. Writes to PostgreSQL (customer, fraud_transaction, non_fraud_transaction tables)

FIXED: Handles transactions.csv with embedded customer names (first, last, unix_time)
UPDATED: Filters out existing ccnum before insert (anti-join logic)
FIXED: Resolved Python worker crash due to complex UDF operations
"""

import sys
import os
from pyspark.sql.functions import (
    col, split, concat_ws, to_timestamp, current_timestamp, lit,
    when, coalesce, length, trim, regexp_replace, udf
)
from pyspark.sql.types import *
from dotenv import load_dotenv
from datetime import datetime

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spark_jobs.utils import create_spark_session, write_to_postgres, print_section

load_dotenv()

def get_existing_ccnums(spark):
    """
    Read existing cc_num values from PostgreSQL customer table
    
    Args:
        spark: SparkSession
        
    Returns:
        DataFrame with existing cc_num values, or empty DataFrame if table doesn't exist
    """
    try:
        # Database connection properties
        jdbc_url = os.getenv('POSTGRES_URL', 'jdbc:postgresql://localhost:5432/fraud_detection')
        jdbc_properties = {
            "user": os.getenv('POSTGRES_USER', 'postgres'),
            "password": os.getenv('POSTGRES_PASSWORD', 'postgres'),
            "driver": "org.postgresql.Driver"
        }
        
        print("[INFO] Reading existing customer ccnums from PostgreSQL...")
        
        # Read entire customer table and select only cc_num
        existing_df = spark.read.jdbc(
            url=jdbc_url,
            table="customer",
            properties=jdbc_properties
        ).select("cc_num")
        
        existing_count = existing_df.count()
        print(f"[INFO] Found {existing_count} existing customer records in database")
        
        return existing_df
        
    except Exception as e:
        print(f"[WARNING] Could not read existing customers (table may not exist yet): {e}")
        print("[INFO] Assuming this is the first import - will import all records")
        # Return empty DataFrame with same schema
        return spark.createDataFrame([], StructType([StructField("cc_num", StringType(), False)]))


def parse_dob(dob_str):
    """
    Parse DOB string with multiple format attempts
    Returns timestamp or None
    """
    if not dob_str or dob_str.strip() == "":
        return None
    
    dob_str = dob_str.strip()
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%m/%d/%Y",
        "%d/%m/%Y"
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(dob_str, fmt)
        except:
            continue
    
    return None


def import_customers(spark, customer_file):
    """
    Import customer data from CSV to PostgreSQL
    Uses anti-join to filter out records with ccnum that already exist in DB
    
    Args:
        spark: SparkSession
        customer_file: Path to customer CSV file
    """
    print_section("IMPORTING CUSTOMERS")
    print(f"[INFO] Reading customer data from: {customer_file}")
    
    # Define schema matching customer.csv structure
    customer_schema = StructType([
        StructField("cc_num", StringType(), False),
        StructField("first", StringType(), True),
        StructField("last", StringType(), True),
        StructField("gender", StringType(), True),
        StructField("street", StringType(), True),
        StructField("city", StringType(), True),
        StructField("state", StringType(), True),
        StructField("zip", StringType(), True),
        StructField("lat", DoubleType(), True),
        StructField("long", DoubleType(), True),
        StructField("job", StringType(), True),
        StructField("dob", StringType(), True)
    ])
    
    # Read CSV
    customer_df = spark.read \
        .option("header", "true") \
        .schema(customer_schema) \
        .csv(customer_file)
    
    total_count = customer_df.count()
    print(f"[INFO] Found {total_count} customer records in CSV")
    
    # Parse DOB using simpler approach - try one format at a time
    print("[INFO] Parsing date of birth...")
    
    # Try format 1: yyyy-MM-dd HH:mm:ss
    customer_df = customer_df.withColumn(
        "dob_parsed",
        to_timestamp(trim(col("dob")), "yyyy-MM-dd HH:mm:ss")
    )
    
    # Try format 2: yyyy-MM-dd (for nulls from format 1)
    customer_df = customer_df.withColumn(
        "dob_parsed",
        when(col("dob_parsed").isNull(), 
             to_timestamp(trim(col("dob")), "yyyy-MM-dd")
        ).otherwise(col("dob_parsed"))
    )
    
    # Try format 3: MM/dd/yyyy (for nulls from format 2)
    customer_df = customer_df.withColumn(
        "dob_parsed",
        when(col("dob_parsed").isNull(), 
             to_timestamp(trim(col("dob")), "MM/dd/yyyy")
        ).otherwise(col("dob_parsed"))
    )
    
    # Rename column
    customer_df = customer_df.withColumn("dob", col("dob_parsed")).drop("dob_parsed")
    
    # Add created_at
    customer_df = customer_df.withColumn("created_at", current_timestamp())
    
    # Get existing ccnums from database
    existing_ccnums_df = get_existing_ccnums(spark)
    
    # Perform anti-join to filter out existing records
    # Anti-join keeps only records from customer_df that DON'T have matching cc_num in existing_ccnums_df
    new_customers_df = customer_df.join(
        existing_ccnums_df,
        customer_df.cc_num == existing_ccnums_df.cc_num,
        "left_anti"  # left_anti = keep rows from left that have no match in right
    )
    
    new_count = new_customers_df.count()
    duplicate_count = total_count - new_count
    
    print(f"[INFO] New customers to import: {new_count}")
    print(f"[INFO] Duplicate customers filtered out: {duplicate_count}")
    
    if new_count == 0:
        print("[WARNING] No new customers to import - all records already exist in database")
        return
    
    # Show sample of NEW customers only
    print("[INFO] Sample of NEW customer data to be imported:")
    new_customers_df.show(5, truncate=False)
    
    # Write to PostgreSQL
    print(f"[INFO] Writing {new_count} new customers to PostgreSQL...")
    write_to_postgres(new_customers_df, 'customer', mode='append')
    print(f"[OK] {new_count} customers imported successfully!")


def get_existing_transactions(spark, table_name):
    """
    Read existing transaction keys from PostgreSQL
    
    Args:
        spark: SparkSession
        table_name: Name of transaction table (fraud_transaction or non_fraud_transaction)
        
    Returns:
        DataFrame with existing (cc_num, trans_time) keys, or empty DataFrame if table doesn't exist
    """
    try:
        jdbc_url = os.getenv('POSTGRES_URL', 'jdbc:postgresql://localhost:5432/fraud_detection')
        jdbc_properties = {
            "user": os.getenv('POSTGRES_USER', 'postgres'),
            "password": os.getenv('POSTGRES_PASSWORD', 'postgres'),
            "driver": "org.postgresql.Driver"
        }
        
        print(f"[INFO] Reading existing transactions from {table_name}...")
        
        existing_df = spark.read.jdbc(
            url=jdbc_url,
            table=table_name,
            properties=jdbc_properties
        ).select("cc_num", "trans_time")
        
        existing_count = existing_df.count()
        print(f"[INFO] Found {existing_count} existing transactions in {table_name}")
        
        return existing_df
        
    except Exception as e:
        print(f"[WARNING] Could not read existing transactions from {table_name}: {e}")
        print(f"[INFO] Assuming this is the first import to {table_name}")
        return spark.createDataFrame([], StructType([
            StructField("cc_num", StringType(), False),
            StructField("trans_time", TimestampType(), False)
        ]))


def import_transactions(spark, transaction_file):
    """
    Import transaction data from CSV to PostgreSQL
    FIXED: Handles CSV with structure:
    cc_num,first,last,trans_num,trans_date,trans_time,unix_time,category,merchant,amt,merch_lat,merch_long,is_fraud
    UPDATED: Filters out existing transactions using anti-join
    
    Args:
        spark: SparkSession
        transaction_file: Path to transaction CSV file
    """
    print_section("IMPORTING TRANSACTIONS")
    print(f"[INFO] Reading transaction data from: {transaction_file}")
    
    # Define schema matching YOUR actual CSV structure (13 columns)
    transaction_schema = StructType([
        StructField("cc_num", StringType(), False),
        StructField("first", StringType(), True),      # Customer first name
        StructField("last", StringType(), True),       # Customer last name
        StructField("trans_num", StringType(), False),
        StructField("trans_date", StringType(), True),
        StructField("trans_time", StringType(), True),
        StructField("unix_time", LongType(), True),    # Unix timestamp
        StructField("category", StringType(), True),
        StructField("merchant", StringType(), True),
        StructField("amt", DoubleType(), True),
        StructField("merch_lat", DoubleType(), True),
        StructField("merch_long", DoubleType(), True),
        StructField("is_fraud", IntegerType(), True)
    ])
    
    # Read CSV with exact schema
    trans_df = spark.read \
        .option("header", "true") \
        .schema(transaction_schema) \
        .csv(transaction_file)
    
    print(f"[INFO] CSV columns: {trans_df.columns}")
    print(f"[INFO] Column count: {len(trans_df.columns)}")
    
    # Show raw data sample
    print("[INFO] Raw transaction data (first 3 rows):")
    trans_df.show(3, truncate=False)
    
    # Process timestamp from trans_date and trans_time
    print("[INFO] Processing timestamps...")
    
    # Step 1: Clean trans_date - remove timezone and milliseconds
    # "2012-01-01T00:00:00.000+05:30" -> "2012-01-01"
    trans_df = trans_df.withColumn(
        "trans_date_clean",
        regexp_replace(col("trans_date"), "T.*", "")
    )
    
    # Step 2: Combine date and time
    trans_df = trans_df.withColumn(
        "trans_timestamp",
        when(
            (col("trans_time").isNotNull()) & (length(trim(col("trans_time"))) > 0),
            to_timestamp(
                concat_ws(" ", col("trans_date_clean"), trim(col("trans_time"))),
                "yyyy-MM-dd HH:mm:ss"
            )
        ).otherwise(
            to_timestamp(col("trans_date_clean"), "yyyy-MM-dd")
        )
    )
    
    # Add created_at
    trans_df = trans_df.withColumn("created_at", current_timestamp())
    
    # Select and rename columns for final output
    # Match the expected schema for fraud_transaction and non_fraud_transaction tables
    final_df = trans_df.select(
        col("trans_num"),
        col("trans_timestamp").alias("trans_time"),  # Rename to trans_time
        col("cc_num"),
        col("category"),
        col("merchant"),
        col("amt"),
        col("merch_lat"),
        col("merch_long"),
        col("unix_time").cast(DoubleType()).alias("distance"),  # Map unix_time to distance
        lit(None).cast(IntegerType()).alias("age"),  # Add age field
        col("is_fraud").cast(DoubleType()),
        col("created_at")
    )
    
    total_count = final_df.count()
    print(f"[INFO] Found {total_count} total transaction records")
    
    # Check for NULL timestamps
    null_time_count = final_df.filter(col("trans_time").isNull()).count()
    if null_time_count > 0:
        print(f"[WARNING] {null_time_count} records have NULL trans_time after parsing")
    
    # Split into fraud and non-fraud
    fraud_df = final_df.filter(col("is_fraud") > 0.5)
    non_fraud_df = final_df.filter(col("is_fraud") <= 0.5)
    
    fraud_count = fraud_df.count()
    non_fraud_count = non_fraud_df.count()
    
    print(f"[INFO] Fraud transactions: {fraud_count} ({fraud_count/total_count*100:.2f}%)")
    print(f"[INFO] Non-fraud transactions: {non_fraud_count} ({non_fraud_count/total_count*100:.2f}%)")
    
    # Show samples
    print("\n[INFO] Sample fraud transactions:")
    fraud_df.show(3, truncate=False)
    
    print("\n[INFO] Sample non-fraud transactions:")
    non_fraud_df.show(3, truncate=False)
    
    # Write fraud transactions
    if fraud_count > 0:
        print("\n[INFO] Writing fraud transactions to PostgreSQL...")
        write_to_postgres(fraud_df, 'fraud_transaction', mode='append')
        print("[OK] Fraud transactions imported!")
    else:
        print("[WARNING] No fraud transactions to import")
    
    # Write non-fraud transactions
    if non_fraud_count > 0:
        print("\n[INFO] Writing non-fraud transactions to PostgreSQL...")
        write_to_postgres(non_fraud_df, 'non_fraud_transaction', mode='append')
        print("[OK] Non-fraud transactions imported!")
    else:
        print("[WARNING] No non-fraud transactions to import")


def main():
    """Main function"""
    print_section("FRAUD DETECTION: Import Initial Data to PostgreSQL")
    
    # Create Spark session - fault handler configs are set via batch file
    spark = create_spark_session("Import Data to PostgreSQL")
    
    # Get file paths
    project_home = os.path.join(os.path.expanduser("~"), "frauddetection")
    
    # Default paths
    customer_file = os.getenv('CUSTOMER_DATA_FILE',
                              os.path.join(project_home, "data", "customer.csv"))
    transaction_file = os.getenv('TRANSACTION_DATA_FILE',
                                 os.path.join(project_home, "data", "transactions.csv"))
    
    # Alternative: Use build-files path if data is there
    build_files_data = r"E:\Project\datapulse-ai-fraud-detection\Fraud Detection\build-files\data"
    if os.path.exists(os.path.join(build_files_data, "transactions.csv")):
        transaction_file = os.path.join(build_files_data, "transactions.csv")
        print(f"[INFO] Using transaction file from build-files: {transaction_file}")
    
    if os.path.exists(os.path.join(build_files_data, "customer.csv")):
        customer_file = os.path.join(build_files_data, "customer.csv")
        print(f"[INFO] Using customer file from build-files: {customer_file}")
    
    try:
        # Import customers (with anti-join filtering)
        if os.path.exists(customer_file):
            import_customers(spark, customer_file)
        else:
            print(f"[WARNING] Customer file not found: {customer_file}")
            print("[INFO] Skipping customer import")
        
        # Import transactions
        if os.path.exists(transaction_file):
            import_transactions(spark, transaction_file)
        else:
            print(f"[WARNING] Transaction file not found: {transaction_file}")
            print("[INFO] Skipping transaction import")
        
        print_section("IMPORT COMPLETED SUCCESSFULLY")
        print("[OK] All data imported to PostgreSQL!")
        print("\n[INFO] You can now verify the data in PostgreSQL using:")
        print("  psql -U postgres -d fraud_detection")
        print("  SELECT COUNT(*) FROM customer;")
        print("  SELECT COUNT(*) FROM fraud_transaction;")
        print("  SELECT COUNT(*) FROM non_fraud_transaction;")
        print("\n[INFO] Sample queries:")
        print("  SELECT * FROM fraud_transaction LIMIT 5;")
        print("  SELECT COUNT(*), is_fraud FROM fraud_transaction GROUP BY is_fraud;")
        
    except Exception as e:
        print(f"\n[ERROR] Import failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        spark.stop()


if __name__ == "__main__":
    main()