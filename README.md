# DataPulse: Real-Time Fraud Detection System

## Overview
DataPulse is a real-time fraud detection platform that streams credit card activity through Kafka, Spark ML, FastAPI, and a React dashboard for instant anomaly detection. This repository contains the complete pipeline, including data ingestion, feature engineering, model training (Logistic Regression and Random Forest), and real-time scoring.

## Key Features
- **Streaming Architecture:** Kafka for ingesting real-time transactions.
- **Machine Learning:** Spark ML and scikit-learn for fraud detection.
- **APIs:** FastAPI REST and WebSocket APIs for serving predictions.
- **Dashboard:** React + Tailwind for live monitoring and analytics.
- **Persistence:** PostgreSQL/TimescaleDB for storing results and historical data.

## Directory Structure
```
backend/           # FastAPI backend and API logic
config/            # Database and Spark configuration
frontend/          # React dashboard
kafka-producer/    # Scala-based Kafka producer for transaction data
models/            # Trained ML models and metadata
scripts/           # Utility scripts for running jobs
spark_jobs/        # Spark and Python ML jobs (batch, streaming, training)
data/              # Sample datasets (customers, transactions)
```

## Model Training Pipeline (Logistic Regression)
- **Location:** `spark_jobs/training/fraud_detection_lr.py`
- **Steps:**
  1. Data loading and EDA
  2. Feature engineering (temporal, geospatial, behavioral, etc.)
  3. Feature selection and scaling
  4. Handling class imbalance (SMOTE + undersampling)
  5. Model training (Logistic Regression)
  6. Hyperparameter tuning (GridSearchCV)
  7. Evaluation (ROC, PR curves, threshold optimization)
  8. Saving model, scaler, feature names, and results

### Output Artifacts
- `logistic_regression_fraud_model.pkl` — Trained model
- `feature_scaler.pkl` — Scaler for preprocessing
- `feature_names.pkl` — List of features used
- `model_results_summary.pkl` — Training summary and metrics
- `feature_importance_lr.csv` — Feature importance
- `lr_performance_curves.png` — ROC and PR curves

## Setup & Usage
1. **Clone the repository:**
   ```bash
   git clone https://github.com/Sarthak-Salunke/DataPulse---Real-Time-Fraud-Detection-System.git
   cd DataPulse---Real-Time-Fraud-Detection-System
   ```
2. **Install dependencies:**
   - Python 3.8+
   - Install required packages:
     ```bash
     pip install -r backend/requirements.txt
     pip install scikit-learn imbalanced-learn matplotlib seaborn pandas numpy
     ```
3. **Run model training:**
   ```bash
   cd spark_jobs/training
   python fraud_detection_lr.py
   ```
4. **Artifacts will be saved in the project root.**

## Real-Time Pipeline
- **Kafka Producer:** Streams transactions from `data/transactions_producer.csv`.
- **Spark Streaming:** Consumes, scores, and persists results.
- **FastAPI:** Serves predictions and analytics to the dashboard.
- **Frontend:** Visualizes fraud alerts and statistics in real time.

## Contributing
Pull requests and issues are welcome! Please open an issue to discuss your ideas or report bugs.

## License
MIT License

---
For more details, see the code and documentation in each subfolder.
