# DataPulse - Fraud Detection System Methodology

## Table of Contents
1. [Project Overview](#project-overview)
2. [Research & Development Methodology](#research--development-methodology)
3. [Data Processing Methodology](#data-processing-methodology)
4. [Machine Learning Methodology](#machine-learning-methodology)
5. [Software Development Methodology](#software-development-methodology)
6. [Real-Time Processing Methodology](#real-time-processing-methodology)
7. [Evaluation & Validation Methodology](#evaluation--validation-methodology)
8. [Deployment Methodology](#deployment-methodology)

---

## 1. Project Overview

**Project Name:** DataPulse - Real-Time Credit Card Fraud Detection System

**Objective:** Develop an end-to-end real-time fraud detection system that processes credit card transactions, identifies fraudulent activities using machine learning, and provides real-time alerts through a modern web dashboard.

**Approach:** Hybrid architecture combining batch processing (for model training) and stream processing (for real-time fraud detection).

---

## 2. Research & Development Methodology

### 2.1 Problem Definition Phase
- **Identification:** Credit card fraud is a growing concern requiring immediate detection
- **Requirements Gathering:**
  - Real-time transaction processing
  - Low-latency fraud detection (< 20 seconds)
  - High accuracy (> 94%)
  - Scalable architecture
  - User-friendly dashboard

### 2.2 Technology Selection
- **Big Data Processing:** Apache Spark (distributed computing, ML capabilities)
- **Message Queue:** Apache Kafka (high-throughput event streaming)
- **Database:** PostgreSQL with TimescaleDB (time-series optimization)
- **Backend:** FastAPI (async REST + WebSocket), Flask (legacy support)
- **Frontend:** React + TypeScript (modern, type-safe UI)
- **ML Framework:** PySpark MLlib (Random Forest Classifier)

### 2.3 Architecture Design
- **Pattern:** Lambda Architecture (batch + streaming)
- **Design Principles:**
  - Separation of concerns
  - Microservices architecture
  - Fault tolerance
  - Scalability
  - Real-time processing

---

## 3. Data Processing Methodology

### 3.1 Data Ingestion Methodology

**Source:** CSV files containing credit card transactions

**Process:**
1. **Kafka Producer (Scala)**
   - Reads transaction CSV files
   - Serializes using Avro schema (`creditTransaction.avsc`)
   - Publishes to Kafka topic: `creditcardTransaction`
   - Handles schema evolution
   - Supports both local and cluster configurations

**Data Schema:**
```json
{
  "cc_num": "string",
  "first": "string",
  "last": "string",
  "trans_num": "string",
  "trans_date": "string",
  "trans_time": "string",
  "unix_time": "long",
  "category": "string",
  "merchant": "string",
  "amt": "double",
  "merch_lat": "double",
  "merch_long": "double"
}
```

### 3.2 Data Enrichment Methodology

**Real-Time Enrichment (Spark Streaming):**
1. **Customer Data Lookup**
   - Broadcast join with PostgreSQL `customer` table
   - Retrieves: customer location (lat/long), DOB
   - Calculates: customer age

2. **Feature Calculation**
   - **Distance Feature:** Haversine formula to calculate distance between customer and merchant
   ```
   distance = Haversine(customer_lat, customer_long, merchant_lat, merchant_long)
   ```
   - Formula:
     ```
     a = sin²(Δlat/2) + cos(lat1) × cos(lat2) × sin²(Δlon/2)
     c = 2 × atan2(√a, √(1−a))
     distance = R × c (R = 6371 km)
     ```

### 3.3 Data Storage Methodology

**Database Design:**
- **TimescaleDB Hypertables:** Optimized for time-series data
- **Table Separation:** 
  - `fraud_transaction` - Fraudulent transactions
  - `non_fraud_transaction` - Normal transactions
  - Benefits: Faster queries, easier maintenance

**Indexing Strategy:**
- Primary keys: Composite (`cc_num`, `trans_time`)
- Secondary indexes: `trans_time DESC`, `trans_num`, `merchant`, `category`
- Clustering order: Time-based for temporal queries

**Data Retention:**
- Configurable retention policies (default: 90 days)
- Continuous aggregates for historical analysis

---

## 4. Machine Learning Methodology

### 4.1 Feature Engineering Methodology

**Feature Selection:**
Selected features based on domain knowledge and fraud detection best practices:
- `cc_num` - Credit card identifier (categorical)
- `category` - Transaction category (categorical)
- `merchant` - Merchant name (categorical)
- `distance` - Calculated distance from customer to merchant (numerical)
- `amt` - Transaction amount (numerical)
- `age` - Customer age (numerical)

**Feature Transformation Pipeline:**

1. **Categorical Features (StringIndexer)**
   - Converts categorical strings to numeric indices
   - Handles unknown values with "keep" strategy
   - Example: `category: "grocery"` → `category_indexed: 0.0`

2. **One-Hot Encoding**
   - Converts indexed categories to sparse binary vectors
   - Prevents ordinal bias in categorical features
   - Example: `category_indexed: 0.0` → `[1.0, 0.0, 0.0, ...]`

3. **Vector Assembler**
   - Combines all features into single feature vector
   - Required for MLlib algorithms
   - Output: `features` column (DenseVector or SparseVector)

**Preprocessing Pipeline Stages:**
```
Input Data
  ↓
[StringIndexer] → [OneHotEncoder] (for each categorical)
  ↓
[Numeric Features] (distance, amt, age)
  ↓
[VectorAssembler] → Combined Feature Vector
```

### 4.2 Data Balancing Methodology

**Problem:** Imbalanced dataset (fraud cases << normal cases)

**Approach:** Random Undersampling
- **Rationale:** K-means clustering caused Python worker crashes; simpler method more reliable
- **Method:**
  1. Count fraud transactions: `N_fraud`
  2. Count non-fraud transactions: `N_non_fraud`
  3. Calculate sampling fraction: `fraction = N_fraud / N_non_fraud`
  4. Randomly sample non-fraud data to match fraud count
  5. Seed: 42 (for reproducibility)

**Result:** Balanced dataset with ~1:1 ratio

### 4.3 Model Training Methodology

**Algorithm:** Random Forest Classifier

**Hyperparameters:**
- `numTrees`: 100 (ensemble size)
- `maxDepth`: 10 (tree depth limit)
- `maxBins`: 700 (categorical feature binning)
- `seed`: 42 (reproducibility)

**Training Process:**
1. **Data Split:** 70% training, 30% testing
   - Random split with seed=42
   - Stratified approach (maintains class distribution)

2. **Training:**
   - Fit Random Forest on training set
   - Ensemble of 100 decision trees
   - Bootstrap sampling for each tree

3. **Prediction:**
   - Majority voting across trees
   - Binary classification: 0 = Normal, 1 = Fraud

### 4.4 Model Evaluation Methodology

**Evaluation Metrics:**
1. **Overall Accuracy**
   - Formula: `(TP + TN) / (TP + TN + FP + FN)`
   - Measures: General model performance

2. **F1-Score**
   - Formula: `2 × (Precision × Recall) / (Precision + Recall)`
   - Measures: Balance between precision and recall

3. **Fraud Detection Recall (Primary Metric)**
   - Formula: `TP / (TP + FN)`
   - Measures: Ability to catch fraud cases
   - **Critical:** High recall reduces missed frauds

4. **Feature Importance**
   - Extracted from Random Forest model
   - Identifies most predictive features
   - Used for feature selection optimization

**Validation Approach:**
- **Holdout Method:** 70/30 train-test split
- **No Cross-Validation:** Due to streaming nature, temporal split more appropriate

### 4.5 Model Persistence Methodology

**Saved Components:**
1. **Preprocessing Pipeline Model**
   - Path: `~/frauddetection/models/PreprocessingModel/`
   - Format: Spark PipelineModel (Parquet)
   - Contains: StringIndexer, OneHotEncoder, VectorAssembler transformers

2. **Random Forest Model**
   - Path: `~/frauddetection/models/RandomForestModel/`
   - Format: RandomForestClassificationModel (Parquet)
   - Contains: Trained trees, metadata, feature importance

**Versioning:**
- Models can be overwritten for updates
- Checkpointing in streaming job for fault tolerance

---

## 5. Software Development Methodology

### 5.1 Development Approach

**Methodology:** Agile-inspired, iterative development
- Incremental feature additions
- Modular component design
- Continuous integration ready

### 5.2 Code Organization

**Project Structure:**
```
DataPulse/
├── backend/          # Backend APIs (Flask + FastAPI)
├── frontend/         # React frontend
├── spark_jobs/       # Spark processing jobs
│   ├── batch/        # Batch processing
│   ├── streaming/    # Real-time streaming
│   └── training/     # ML model training
├── kafka-producer/   # Kafka producer (Scala)
├── config/           # Configuration files
└── scripts/          # Deployment scripts
```

**Code Quality:**
- Type hints in Python (type safety)
- TypeScript for frontend (compile-time checks)
- Modular functions (single responsibility)
- Comprehensive error handling
- Logging at key stages

### 5.3 Configuration Management

**Environment Variables (.env):**
- Database credentials
- Kafka broker addresses
- Spark master configuration
- Model paths
- Port numbers

**Separation of Concerns:**
- Configuration vs. implementation
- Local vs. cluster configs
- Development vs. production settings

---

## 6. Real-Time Processing Methodology

### 6.1 Stream Processing Architecture

**Technology:** Apache Spark Structured Streaming

**Processing Model:**
- **Micro-batch Processing:** Fixed interval (20 seconds)
- **Trigger:** `processingTime='20 seconds'`
- **Output Mode:** Update (incremental processing)

### 6.2 Stream Processing Workflow

**Step-by-Step Process:**

1. **Kafka Consumption**
   - Source: Kafka topic `creditcardTransaction`
   - Starting offset: Latest (configurable)
   - Schema: JSON message parsing

2. **Data Parsing**
   - Parse JSON messages from Kafka
   - Extract transaction fields
   - Convert timestamps to Spark TimestampType

3. **Customer Enrichment**
   - Broadcast join with customer table (cached)
   - Calculate customer age from DOB
   - Calculate distance (Haversine formula)

4. **Feature Engineering**
   - Apply preprocessing pipeline model
   - Transform features to ML format
   - Create feature vector

5. **Fraud Prediction**
   - Apply Random Forest model
   - Generate predictions (0 or 1)
   - Extract confidence scores

6. **Result Storage**
   - Split predictions: fraud vs. non-fraud
   - Write to PostgreSQL with UPSERT logic
   - Handle duplicates: `ON CONFLICT DO NOTHING`

### 6.3 Fault Tolerance Methodology

**Checkpointing:**
- Location: `~/frauddetection/checkpoints/structured-streaming`
- Purpose: Recover from failures, maintain state
- Mechanism: Spark writes checkpoint metadata

**Offset Tracking:**
- Table: `kafka_offset` in PostgreSQL
- Stores: Partition ID, Offset
- Ensures: No data loss on restart

**Idempotency:**
- UPSERT operations prevent duplicates
- Composite key: (`cc_num`, `trans_time`)
- Deduplication within batches

### 6.4 Real-Time Alerting Methodology

**FastAPI WebSocket Implementation:**
1. **Polling Mechanism:**
   - Background task checks PostgreSQL every 5 seconds
   - Query: `SELECT * FROM fraud_transaction WHERE created_at > last_check_time`
   - Tracks last checked timestamp

2. **Broadcasting:**
   - New fraud transactions → WebSocket broadcast
   - Format: JSON message with fraud alert data
   - All connected clients receive updates

3. **Connection Management:**
   - Connection pool tracking
   - Automatic cleanup on disconnect
   - Reconnection support

---

## 7. Evaluation & Validation Methodology

### 7.1 Model Validation

**Training Validation:**
- **Split Ratio:** 70% train, 30% test
- **Metrics Tracked:**
  - Overall Accuracy
  - F1-Score
  - Fraud Detection Recall (critical)
  - Feature Importance

**Expected Performance:**
- Accuracy: > 94%
- Fraud Recall: > 90%
- F1-Score: > 0.90

### 7.2 Production Monitoring

**Real-Time Metrics:**
- Transaction processing rate
- Fraud detection rate
- Model prediction latency
- System health (PostgreSQL, Kafka, Spark)

**Dashboard KPIs:**
- Total transactions today
- Fraud detected count
- Fraud rate percentage
- Model accuracy (static)

### 7.3 Error Handling & Validation

**Data Validation:**
- Null value handling (defaults: distance=0, amt=50, age=40)
- NaN replacement
- Schema validation

**Process Validation:**
- Empty batch detection
- Model loading verification
- Database connection health checks
- Transform validation (non-empty results)

---

## 8. Deployment Methodology

### 8.1 Deployment Architecture

**Components:**
1. **Kafka Producer** - Standalone application
2. **Spark Streaming Job** - Long-running Spark application
3. **FastAPI Backend** - Web server (port 8000)
4. **Flask Backend** - Legacy API (port 5050)
5. **React Frontend** - Vite dev server (port 5173)
6. **PostgreSQL Database** - Persistent storage

### 8.2 Deployment Steps

**1. Database Setup:**
```bash
# Create database
psql -U postgres -c "CREATE DATABASE fraud_detection;"

# Run schema script
psql -U postgres -d fraud_detection -f config/postgresql_schema.sql
```

**2. Model Training:**
```bash
# Train ML models
python spark_jobs/training/spark_fraud_detection_training.py
```

**3. Start Services:**
```bash
# Start Kafka producer (if needed)
# Start Spark streaming
python spark_jobs/streaming/spark_structured_streaming.py

# Start FastAPI backend
python backend/main_fastapi.py

# Start frontend
cd frontend && npm run dev
```

### 8.3 Deployment Scripts

**Windows Scripts:**
- `scripts/windows/run_spark_training.bat` - Train models
- `scripts/windows/run_spark_streaming.bat` - Start streaming
- `scripts/windows/start_fastapi_server.bat` - Start API
- `scripts/windows/start_backend.bat` - Start Flask API

### 8.4 Scaling Methodology

**Horizontal Scaling:**
- **Kafka:** Add partitions for parallel processing
- **Spark:** Increase executor instances
- **Database:** Read replicas for queries

**Vertical Scaling:**
- **Spark:** Increase executor memory/cores
- **Database:** Increase instance size
- **API:** Increase worker processes

**Future Enhancements:**
- Containerization (Docker)
- Orchestration (Kubernetes)
- Load balancing for APIs

---

## 9. Methodology Summary

### 9.1 Key Methodological Principles

1. **End-to-End Pipeline:** Complete workflow from ingestion to visualization
2. **Real-Time Processing:** Low-latency fraud detection (< 20 seconds)
3. **Scalable Architecture:** Distributed computing with Spark
4. **Fault Tolerance:** Checkpointing, idempotency, offset tracking
5. **Production-Ready:** Error handling, logging, monitoring

### 9.2 Methodology Advantages

✅ **High Performance:** Distributed processing with Spark
✅ **Real-Time:** Micro-batch processing with 20-second latency
✅ **Accurate:** Random Forest ensemble with >94% accuracy
✅ **Scalable:** Horizontal scaling capabilities
✅ **Fault Tolerant:** Recovery mechanisms in place
✅ **Maintainable:** Clean code structure, modular design

### 9.3 Limitations & Future Work

**Current Limitations:**
- Model retraining requires manual execution
- No A/B testing framework
- Limited feature engineering (could add more features)
- Single model approach (could use ensemble of different algorithms)

**Future Improvements:**
- Automated model retraining pipeline
- Real-time model updates
- Feature store implementation
- Online learning capabilities
- Multi-model ensemble
- Explainable AI (model interpretability)

---

## 10. References

### Technologies Used
- Apache Spark 3.5.0
- Apache Kafka
- PostgreSQL 14+ with TimescaleDB
- FastAPI 0.104+
- React 19.2.0
- PySpark MLlib

### Algorithms & Techniques
- Random Forest Classification
- Haversine Distance Calculation
- String Indexing & One-Hot Encoding
- Random Undersampling
- Micro-batch Stream Processing
- Broadcast Joins

---

**Document Version:** 1.0  
**Last Updated:** 2024  
**Author:** DataPulse Development Team








