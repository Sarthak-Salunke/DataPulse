"""
Utility functions for Spark fraud detection jobs
Helper functions used across multiple Spark jobs
"""

import math
from pyspark.sql.functions import udf, col
from pyspark.sql.types import DoubleType


def calculate_distance(lat1, lon1, lat2, lon2):
    """
    Calculate distance between two coordinates using Haversine formula
    
    Args:
        lat1, lon1: First coordinate (customer location)
        lat2, lon2: Second coordinate (merchant location)
    
    Returns:
        Distance in kilometers
    """
    if None in [lat1, lon1, lat2, lon2]:
        return 0.0
    
    # Convert to radians
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    
    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    
    # Radius of Earth in kilometers
    r = 6371
    return c * r


# Register as Spark UDF
distance_udf = udf(calculate_distance, DoubleType())


def get_postgres_properties():
    """Get PostgreSQL connection properties"""
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    return {
        'url': f"jdbc:postgresql://{os.getenv('DB_HOST', 'localhost')}:{os.getenv('DB_PORT', '5432')}/{os.getenv('DB_NAME', 'fraud_detection')}",
        'user': os.getenv('DB_USER', 'postgres'),
        'password': os.getenv('DB_PASSWORD', 'postgres123'),
        'driver': 'org.postgresql.Driver'
    }


def read_from_postgres(spark, table_name, columns=None):
    """
    Read data from PostgreSQL table
    
    Args:
        spark: SparkSession
        table_name: Name of the table
        columns: List of columns to select (optional)
    
    Returns:
        DataFrame
    """
    props = get_postgres_properties()
    
    df = spark.read \
        .jdbc(
            url=props['url'],
            table=table_name,
            properties={
                'user': props['user'],
                'password': props['password'],
                'driver': props['driver']
            }
        )
    
    if columns:
        df = df.select(*columns)
    
    return df


def write_to_postgres(df, table_name, mode='append'):
    """
    Write DataFrame to PostgreSQL table
    
    Args:
        df: Spark DataFrame
        table_name: Target table name
        mode: Write mode ('append', 'overwrite', 'ignore', 'error')
    """
    props = get_postgres_properties()
    
    df.write \
        .jdbc(
            url=props['url'],
            table=table_name,
            mode=mode,
            properties={
                'user': props['user'],
                'password': props['password'],
                'driver': props['driver']
            }
        )


def create_spark_session(app_name):
    """
    Create SparkSession with PostgreSQL and Kafka support
    
    Args:
        app_name: Name of the Spark application
    
    Returns:
        SparkSession
    """
    import os
    from pyspark.sql import SparkSession
    from dotenv import load_dotenv
    
    load_dotenv()
    
    spark = SparkSession.builder \
        .appName(app_name) \
        .master(os.getenv('SPARK_MASTER', 'local[*]')) \
        .config("spark.jars.packages",
                "org.postgresql:postgresql:42.7.1,"
                "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.3") \
        .config("spark.driver.extraClassPath",
                os.getenv('POSTGRES_JDBC_JAR', 'file:///C:/spark/jars/postgresql-42.7.1.jar')) \
        .config("spark.executor.extraClassPath",
                os.getenv('POSTGRES_JDBC_JAR', 'file:///C:/spark/jars/postgresql-42.7.1.jar')) \
        .config("spark.sql.streaming.checkpointLocation",
                os.path.join(os.path.expanduser("~"), "frauddetection", "checkpoints")) \
        .config("spark.hadoop.fs.file.impl", "org.apache.hadoop.fs.LocalFileSystem") \
        .config("spark.hadoop.fs.AbstractFileSystem.file.impl", "org.apache.hadoop.fs.local.LocalFs") \
        .config("spark.hadoop.hadoop.home.dir", "C:/hadoop") \
        .getOrCreate()
    
    # Set log level
    spark.sparkContext.setLogLevel("WARN")
    
    return spark


def print_section(title):
    """Print formatted section header"""
    print("\n" + "=" * 70)
    print(f" {title}")
    print("=" * 70)
