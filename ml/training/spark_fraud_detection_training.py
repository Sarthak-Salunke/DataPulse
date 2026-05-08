"""
Spark Job: Fraud Detection Model Training
FIXED: Removed problematic UDF that caused Python worker crashes

This job:
1. Reads fraud and non-fraud transactions from PostgreSQL
2. Balances the dataset using K-means clustering
3. Creates ML feature pipeline (StringIndexer + OneHotEncoder + VectorAssembler)
4. Trains Random Forest classifier
5. Saves model and preprocessing pipeline
"""

import sys
import os
from pyspark.sql import SparkSession, Window
from pyspark.sql.functions import col, lit, when, isnan, hour, dayofweek, count, sum as spark_sum
from pyspark.sql.types import StringType
from pyspark.ml import Pipeline, PipelineModel
from pyspark.ml.feature import StringIndexer, OneHotEncoder, VectorAssembler
from pyspark.ml.classification import RandomForestClassifier
from pyspark.ml.clustering import KMeans
from pyspark.ml.evaluation import MulticlassClassificationEvaluator, BinaryClassificationEvaluator
from dotenv import load_dotenv

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spark_jobs.utils import create_spark_session, read_from_postgres, print_section

load_dotenv()


def balance_dataset(fraud_df, non_fraud_df, spark):
    """
    Balance non-fraud transactions using random undersampling
    
    K-means with 501 clusters causes Python worker crashes, so we use
    simple random undersampling instead - it's faster and more reliable.
    
    Args:
        fraud_df: DataFrame with fraud transactions
        non_fraud_df: DataFrame with non-fraud transactions
        spark: SparkSession
    
    Returns:
        Balanced DataFrame
    """
    print_section("DATA BALANCING")
    
    fraud_count = fraud_df.count()
    non_fraud_count = non_fraud_df.count()
    
    print(f"[INFO] Before balancing:")
    print(f"       Fraud transactions: {fraud_count}")
    print(f"       Non-fraud transactions: {non_fraud_count}")
    print(f"       Imbalance ratio: 1:{non_fraud_count/fraud_count:.1f}")
    
    if non_fraud_count <= fraud_count:
        print("[INFO] Dataset already balanced")
        balanced_non_fraud_df = non_fraud_df
    else:
        # Use random undersampling instead of K-means
        # Calculate sampling fraction
        sampling_fraction = fraud_count / non_fraud_count
        
        print(f"[INFO] Applying random undersampling")
        print(f"[INFO] Sampling {sampling_fraction*100:.2f}% of non-fraud transactions...")
        
        # Sample non-fraud data to match fraud count
        balanced_non_fraud_df = non_fraud_df.sample(
            withReplacement=False,
            fraction=sampling_fraction,
            seed=42
        )
        
        actual_count = balanced_non_fraud_df.count()
        print(f"[OK] Balanced non-fraud transactions: {actual_count}")
    
    # Combine fraud and balanced non-fraud
    balanced_df = fraud_df.union(balanced_non_fraud_df)
    
    total_count = balanced_df.count()
    print(f"[INFO] After balancing:")
    print(f"       Total transactions: {total_count}")
    print(f"       Balanced ratio: ~1:1")
    
    return balanced_df


def build_feature_pipeline(df, feature_columns):
    """
    Build ML feature pipeline
    
    Creates pipeline with:
    1. StringIndexer - Converts categorical strings to numeric indices
    2. OneHotEncoder - Converts indices to one-hot vectors
    3. VectorAssembler - Combines all features into single vector
    
    Args:
        df: Input DataFrame
        feature_columns: List of feature column names
    
    Returns:
        Array of PipelineStages
    """
    print_section("BUILDING FEATURE PIPELINE")
    
    stages = []
    feature_vector_cols = []
    
    # Get schema
    schema = df.schema
    
    for field in schema.fields:
        if field.name not in feature_columns:
            continue
        
        # Check data type
        if isinstance(field.dataType, StringType):
            print(f"[INFO] Processing categorical feature: {field.name}")
            
            # String Indexer
            indexer = StringIndexer(
                inputCol=field.name,
                outputCol=f"{field.name}_indexed",
                handleInvalid="keep"
            )
            stages.append(indexer)
            
            # One-Hot Encoder
            encoder = OneHotEncoder(
                inputCol=f"{field.name}_indexed",
                outputCol=f"{field.name}_encoded",
                dropLast=False
            )
            stages.append(encoder)
            
            feature_vector_cols.append(f"{field.name}_encoded")
            
        else:  # Numeric types
            print(f"[INFO] Processing numeric feature: {field.name}")
            feature_vector_cols.append(field.name)
    
    # Vector Assembler - combines all features
    assembler = VectorAssembler(
        inputCols=feature_vector_cols,
        outputCol="features",
        handleInvalid="keep"
    )
    stages.append(assembler)
    
    print(f"[INFO] Pipeline stages created: {len(stages)}")
    print(f"[INFO] Feature columns: {', '.join(feature_vector_cols)}")
    
    return stages


def train_random_forest_model(df, spark):
    """
    Train Random Forest classifier
    
    Args:
        df: Training DataFrame with 'features' and 'label' columns
        spark: SparkSession
    
    Returns:
        Trained RandomForestClassificationModel
    """
    print_section("TRAINING RANDOM FOREST MODEL")
    
    # Split data: 70% training, 30% test
    print("[INFO] Splitting data: 70% train, 30% test")
    train_df, test_df = df.randomSplit([0.7, 0.3], seed=42)
    
    train_count = train_df.count()
    test_count = test_df.count()
    
    print(f"[INFO] Training set size: {train_count}")
    print(f"[INFO] Test set size: {test_count}")
    
    # Compute inverse-frequency class weights to penalise the majority class
    total   = train_df.count()
    fraud_n = train_df.filter(col("label") == 1.0).count()
    legit_n = total - fraud_n
    w_fraud = total / (2.0 * fraud_n) if fraud_n > 0 else 1.0
    w_legit = total / (2.0 * legit_n) if legit_n > 0 else 1.0

    train_df = train_df.withColumn(
        "classWeight",
        when(col("label") == 1.0, w_fraud).otherwise(w_legit)
    )

    # Configure Random Forest
    print("[INFO] Configuring Random Forest classifier...")
    rf = RandomForestClassifier(
        labelCol="label",
        featuresCol="features",
        weightCol="classWeight",
        numTrees=100,
        maxBins=700,
        maxDepth=10,
        seed=42
    )

    # Train model
    print("[INFO] Training model (this may take a few minutes)...")
    model = rf.fit(train_df)
    
    # Make predictions
    print("[INFO] Making predictions on test set...")
    predictions = model.transform(test_df)
    
    # Evaluate model
    evaluator_accuracy = MulticlassClassificationEvaluator(
        labelCol="label",
        predictionCol="prediction",
        metricName="accuracy"
    )
    
    evaluator_f1 = MulticlassClassificationEvaluator(
        labelCol="label",
        predictionCol="prediction",
        metricName="f1"
    )
    
    accuracy = evaluator_accuracy.evaluate(predictions)
    f1_score = evaluator_f1.evaluate(predictions)

    # ROC-AUC
    evaluator_roc = BinaryClassificationEvaluator(
        labelCol="label",
        rawPredictionCol="rawPrediction",
        metricName="areaUnderROC"
    )
    roc_auc = evaluator_roc.evaluate(predictions)

    # PR-AUC
    evaluator_pr = BinaryClassificationEvaluator(
        labelCol="label",
        rawPredictionCol="rawPrediction",
        metricName="areaUnderPR"
    )
    pr_auc = evaluator_pr.evaluate(predictions)

    # Calculate fraud detection metrics
    fraud_predictions = predictions.filter(col("label") == 1.0)
    fraud_count = fraud_predictions.count()

    if fraud_count > 0:
        correct_fraud = fraud_predictions.filter(col("prediction") == col("label")).count()
        fraud_recall = correct_fraud / fraud_count
    else:
        fraud_recall = 0.0

    print_section("MODEL EVALUATION RESULTS")
    print(f"[RESULT] Overall Accuracy: {accuracy*100:.2f}%")
    print(f"[RESULT] F1-Score: {f1_score:.4f}")
    print(f"[RESULT] ROC-AUC: {roc_auc:.4f}")
    print(f"[RESULT] PR-AUC: {pr_auc:.4f}")
    print(f"[RESULT] Fraud Detection Recall: {fraud_recall*100:.2f}%")
    print(f"[INFO] Total test samples: {test_count}")
    print(f"[INFO] Correct predictions: {predictions.filter(col('prediction') == col('label')).count()}")
    
    # Feature importance
    print("\n[INFO] Top 10 Feature Importances:")
    feature_importances = model.featureImportances
    for i, importance in enumerate(feature_importances.toArray()[:10]):
        print(f"       Feature {i}: {importance:.4f}")
    
    return model


def main():
    """Main training function"""
    print_section("FRAUD DETECTION: MODEL TRAINING")
    
    # Create Spark session
    spark = create_spark_session("Fraud Detection Model Training")
    
    # Get model save paths
    project_home = os.path.join(os.path.expanduser("~"), "frauddetection")
    model_path = os.getenv('MODEL_PATH',
                          os.path.join(project_home, "ml", "models", "RandomForestModel"))
    preprocessing_path = os.getenv('PREPROCESSING_MODEL_PATH',
                                   os.path.join(project_home, "ml", "models", "PreprocessingModel"))
    
    # Create directories if they don't exist
    os.makedirs(os.path.dirname(model_path), exist_ok=True)
    
    try:
        # Step 1: Read data from PostgreSQL
        print_section("LOADING DATA FROM POSTGRESQL")
        
        # Base feature columns — temporal & velocity features added after enrichment
        base_feature_cols = ["cc_num", "category", "merchant", "distance", "amt", "age"]
        feature_cols = base_feature_cols + ["hour", "dayofweek", "is_weekend",
                                             "tx_count_1h", "tx_amt_1h"]
        read_cols = base_feature_cols + ["is_fraud", "trans_time", "trans_num"]

        print("[INFO] Reading fraud transactions...")
        fraud_df = read_from_postgres(spark, 'fraud_transaction', read_cols)

        print("[INFO] Reading non-fraud transactions...")
        non_fraud_df = read_from_postgres(spark, 'non_fraud_transaction', read_cols)
        
        # Rename is_fraud to label
        fraud_df = fraud_df.withColumnRenamed("is_fraud", "label")
        non_fraud_df = non_fraud_df.withColumnRenamed("is_fraud", "label")
        
        fraud_count = fraud_df.count()
        non_fraud_count = non_fraud_df.count()
        
        print(f"[OK] Loaded {fraud_count} fraud and {non_fraud_count} non-fraud transactions")
        
        # Step 2: Clean data - handle NaN/null values
        print_section("DATA CLEANING")
        
        # Check for null values before cleaning
        fraud_nulls = fraud_df.filter(
            col("distance").isNull() | col("amt").isNull() | col("age").isNull()
        ).count()
        non_fraud_nulls = non_fraud_df.filter(
            col("distance").isNull() | col("amt").isNull() | col("age").isNull()
        ).count()
        
        if fraud_nulls > 0 or non_fraud_nulls > 0:
            print(f"[WARN] Found null values: {fraud_nulls} in fraud, {non_fraud_nulls} in non-fraud")
            print("[INFO] Filling nulls with defaults...")
        else:
            print("[OK] No null values found in numeric columns")
        
        # Fill missing numeric values with defaults
        fraud_df = fraud_df.na.fill({
            'distance': 0.0,
            'amt': 50.0,
            'age': 40.0
        })
        
        non_fraud_df = non_fraud_df.na.fill({
            'distance': 0.0,
            'amt': 50.0,
            'age': 40.0
        })
        
        # Replace any NaN values
        for col_name in ['distance', 'amt', 'age']:
            fraud_df = fraud_df.withColumn(
                col_name,
                when(isnan(col(col_name)), 0.0).otherwise(col(col_name))
            )
            non_fraud_df = non_fraud_df.withColumn(
                col_name,
                when(isnan(col(col_name)), 0.0).otherwise(col(col_name))
            )
        
        print("[OK] Data cleaned successfully")
        
        # Step 3: Build feature pipeline
        print_section("FEATURE ENGINEERING")

        # Union both datasets for joint temporal & velocity enrichment
        all_data = non_fraud_df.union(fraud_df)

        # Temporal features from trans_time
        all_data = all_data \
            .withColumn("hour",       hour(col("trans_time"))) \
            .withColumn("dayofweek",  dayofweek(col("trans_time"))) \
            .withColumn("is_weekend", when(dayofweek(col("trans_time")).isin(1, 7), 1).otherwise(0))

        # Velocity features: 1-hour rolling window per card
        # Repartition by cc_num for efficient, OOM-safe window computation
        all_data = all_data.repartition(col("cc_num"))
        vel_window = (
            Window.partitionBy("cc_num")
                  .orderBy(col("trans_time").cast("long"))
                  .rangeBetween(-3600, 0)
        )
        all_data = all_data \
            .withColumn("tx_count_1h", count("trans_num").over(vel_window)) \
            .withColumn("tx_amt_1h",   spark_sum("amt").over(vel_window))

        # Split enriched data back to fraud / non-fraud
        fraud_enriched_df     = all_data.filter(col("label") == 1.0)
        non_fraud_enriched_df = all_data.filter(col("label") == 0.0)

        pipeline_stages = build_feature_pipeline(all_data, feature_cols)

        # Create and fit preprocessing pipeline
        print("\n[INFO] Fitting preprocessing pipeline...")
        preprocessing_pipeline = Pipeline(stages=pipeline_stages)
        preprocessing_model = preprocessing_pipeline.fit(all_data)

        # Transform data
        print("[INFO] Transforming fraud data...")
        fraud_features_df = preprocessing_model.transform(fraud_enriched_df).select("features", "label")

        print("[INFO] Transforming non-fraud data...")
        non_fraud_features_df = preprocessing_model.transform(non_fraud_enriched_df).select("features", "label")
        
        # Simple validation: just check counts
        print("\n[INFO] Validating transformed data...")
        fraud_features_count = fraud_features_df.count()
        non_fraud_features_count = non_fraud_features_df.count()
        
        print(f"[OK] Fraud features: {fraud_features_count}")
        print(f"[OK] Non-fraud features: {non_fraud_features_count}")
        
        if fraud_features_count == 0 or non_fraud_features_count == 0:
            raise ValueError("Feature transformation resulted in empty dataset!")
        
        # Step 4: Balance dataset
        balanced_df = balance_dataset(fraud_features_df, non_fraud_features_df, spark)
        
        # Step 5: Train Random Forest model
        rf_model = train_random_forest_model(balanced_df, spark)
        
        # Step 6: Save models
        print_section("SAVING MODELS")
        
        print(f"[INFO] Saving preprocessing model to: {preprocessing_path}")
        preprocessing_model.write().overwrite().save(preprocessing_path)
        print("[OK] Preprocessing model saved")
        
        print(f"[INFO] Saving Random Forest model to: {model_path}")
        rf_model.write().overwrite().save(model_path)
        print("[OK] Random Forest model saved")
        
        print_section("TRAINING COMPLETED SUCCESSFULLY")
        print("[OK] Models are ready for real-time fraud detection!")
        print(f"[INFO] Preprocessing model: {preprocessing_path}")
        print(f"[INFO] Random Forest model: {model_path}")
        print("\n[NEXT STEP] Run the streaming job to detect fraud in real-time")
        
    except Exception as e:
        print(f"\n[ERROR] Training failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        spark.stop()


if __name__ == "__main__":
    main()