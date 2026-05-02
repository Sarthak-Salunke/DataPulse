"""
Spark configuration for PostgreSQL/TimescaleDB
"""

import os
from dotenv import load_dotenv

load_dotenv()

# PostgreSQL JDBC driver path
POSTGRES_JDBC_JAR = os.getenv('POSTGRES_JDBC_JAR', 'C:/spark/jars/postgresql-42.7.1.jar')

SPARK_CONFIG = {
    'spark.jars': POSTGRES_JDBC_JAR,
    'spark.driver.extraClassPath': POSTGRES_JDBC_JAR,
    'spark.executor.extraClassPath': POSTGRES_JDBC_JAR,
}

POSTGRES_PROPERTIES = {
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'postgres123'),
    'driver': 'org.postgresql.Driver'
}

POSTGRES_URL = f"jdbc:postgresql://{os.getenv('DB_HOST', 'localhost')}:{os.getenv('DB_PORT', '5432')}/{os.getenv('DB_NAME', 'fraud_detection')}"


def get_spark_session():
    """Create Spark session with PostgreSQL support"""
    from pyspark.sql import SparkSession
    
    spark = SparkSession.builder \
        .appName(os.getenv('SPARK_APP_NAME', 'FraudDetection')) \
        .master(os.getenv('SPARK_MASTER', 'local[*]')) \
        .config("spark.jars", SPARK_CONFIG['spark.jars']) \
        .config("spark.driver.extraClassPath", SPARK_CONFIG['spark.driver.extraClassPath']) \
        .config("spark.executor.extraClassPath", SPARK_CONFIG['spark.executor.extraClassPath']) \
        .config("spark.hadoop.fs.file.impl", "org.apache.hadoop.fs.LocalFileSystem") \
        .config("spark.hadoop.fs.AbstractFileSystem.file.impl", "org.apache.hadoop.fs.local.LocalFs") \
        .config("spark.hadoop.hadoop.home.dir", "C:/hadoop") \
        .getOrCreate()
    
    return spark


def read_from_postgres(spark, table_name):
    """Read data from PostgreSQL table"""
    df = spark.read \
        .jdbc(
            url=POSTGRES_URL,
            table=table_name,
            properties=POSTGRES_PROPERTIES
        )
    
    return df


def write_to_postgres(df, table_name, mode='append'):
    """Write DataFrame to PostgreSQL"""
    df.write \
        .jdbc(
            url=POSTGRES_URL,
            table=table_name,
            mode=mode,
            properties=POSTGRES_PROPERTIES
        )
