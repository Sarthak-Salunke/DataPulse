"""
Diagnostic script to test model loading
Run this first to identify the exact issue
"""

import os
import sys
from pyspark.sql import SparkSession
from pyspark.ml import PipelineModel
from pyspark.ml.classification import RandomForestClassificationModel

def test_model_loading():
    print("="*70)
    print("MODEL LOADING DIAGNOSTIC TEST")
    print("="*70)
    
    # Create minimal Spark session
    spark = SparkSession.builder \
        .appName("Model Loading Test") \
        .master("local[1]") \
        .config("spark.driver.memory", "2g") \
        .getOrCreate()
    
    print(f"\n[INFO] Spark version: {spark.version}")
    print(f"[INFO] Python version: {sys.version}")
    print(f"[INFO] PySpark location: {spark.sparkContext.pythonExec}")
    
    # Define paths
    project_home = os.path.join(os.path.expanduser("~"), "frauddetection")
    preprocessing_path = os.path.join(project_home, "ml", "models", "PreprocessingModel")
    model_path = os.path.join(project_home, "ml", "models", "RandomForestModel")
    
    print(f"\n[INFO] Checking preprocessing model path...")
    print(f"  Path: {preprocessing_path}")
    print(f"  Exists: {os.path.exists(preprocessing_path)}")
    
    if os.path.exists(preprocessing_path):
        print(f"  Contents: {os.listdir(preprocessing_path)}")
        
        # Check for metadata
        metadata_path = os.path.join(preprocessing_path, "metadata")
        if os.path.exists(metadata_path):
            print(f"  Metadata exists: Yes")
            print(f"  Metadata contents: {os.listdir(metadata_path)}")
        else:
            print(f"  Metadata exists: No [ERROR]")
    
    print(f"\n[INFO] Checking Random Forest model path...")
    print(f"  Path: {model_path}")
    print(f"  Exists: {os.path.exists(model_path)}")
    
    if os.path.exists(model_path):
        print(f"  Contents: {os.listdir(model_path)}")
    
    # Try loading preprocessing model
    print(f"\n[TEST 1] Loading preprocessing model...")
    try:
        preprocessing_model = PipelineModel.load(preprocessing_path)
        print(f"  [SUCCESS]")
        print(f"  Stages: {[stage.__class__.__name__ for stage in preprocessing_model.stages]}")
        
        # Test transform on dummy data
        print(f"\n[TEST 2] Testing preprocessing model transform...")
        from pyspark.sql.types import StructType, StructField, StringType, DoubleType, IntegerType
        
        schema = StructType([
            StructField("cc_num", StringType(), True),
            StructField("category", StringType(), True),
            StructField("merchant", StringType(), True),
            StructField("distance", DoubleType(), True),
            StructField("amt", DoubleType(), True),
            StructField("age", IntegerType(), True)
        ])
        
        test_data = [("1234567890123456", "grocery_pos", "Test Merchant", 5.0, 100.0, 35)]
        test_df = spark.createDataFrame(test_data, schema)
        
        result_df = preprocessing_model.transform(test_df)
        print(f"  [SUCCESS]")
        print(f"  Result columns: {result_df.columns}")
        
    except Exception as e:
        print(f"  [FAILED]: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Try loading Random Forest model
    print(f"\n[TEST 3] Loading Random Forest model...")
    try:
        rf_model = RandomForestClassificationModel.load(model_path)
        print(f"  [SUCCESS]")
        print(f"  Number of trees: {rf_model.getNumTrees}")
        print(f"  Feature importance: {len(rf_model.featureImportances)}")
        
    except Exception as e:
        print(f"  [FAILED]: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n" + "="*70)
    print("ALL TESTS PASSED ")
    print("="*70)
    
    spark.stop()
    return True


if __name__ == "__main__":
    success = test_model_loading()
    sys.exit(0 if success else 1)