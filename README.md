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
backend/           # FastAPI server (main_fastapi.py, cape_router.py)
cape/              # CAPE 9-layer fraud scoring engine
config/            # Database and Spark configuration
docs/              # Architecture docs, methodology, diagrams
frontend/          # React dashboard (Vite + TypeScript + Tailwind)
ml/models/         # Production trained models (.pkl)
ml/training/       # Per-algorithm training scripts
pipeline/          # Kafka producer (Scala) + Spark jobs
scripts/           # Data pipeline steps (step1–step7)
tests/             # Unit, integration, and smoke tests
data/              # Raw CSV datasets (gitignored large files)
requirements.txt   # All Python dependencies (backend + CAPE)
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

## Quick Start (Manual E2E Testing)

### Prerequisites
- Python 3.10+
- Node.js 18+
- PostgreSQL 14+ with the **TimescaleDB** extension installed
- (Optional) Kafka + Zookeeper for live streaming

### 1 — Configure environment
```bash
# Copy the template and fill in your values
cp .env.example backend/.env
# Required: DB_PASSWORD, GEMINI_API_KEY, DB_READONLY_USER, DB_READONLY_PASSWORD
```

### 2 — Install Python dependencies
```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

### 3 — Install frontend dependencies
```bash
cd frontend && npm install && cd ..
```

### 4 — Initialise the database
```bash
# Apply schema (creates tables, hypertables, triggers)
psql -U postgres -f config/postgresql_schema.sql

# Seed today's sample transactions (so dashboards show real data immediately)
python scripts/seed_data.py
```

### 5 — Start everything (Windows one-command)
```bat
scripts\windows\start_all.bat
```
Or manually in two terminals:
```bash
# Terminal 1 — backend
cd backend && uvicorn main_fastapi:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2 — frontend
cd frontend && npm run dev
```

Open **http://localhost:3000** and log in with `admin` / `datapulse2024`.

### 6 — Enable the NLP Chatbot (optional)
The chatbot requires a Gemini API key and a one-time training step:
```bash
# 1. Add GEMINI_API_KEY, DB_READONLY_USER, DB_READONLY_PASSWORD to backend/.env
# 2. Create a read-only Postgres user:
#    CREATE USER dp_readonly WITH PASSWORD 'your-password';
#    GRANT SELECT ON ALL TABLES IN SCHEMA public TO dp_readonly;
# 3. Train the Vanna vector store (run once):
python backend/vanna_train.py
```
After training, click the **◈** button in the bottom-right of the dashboard.

---

## Setup & Usage (Model Training Only)
1. **Clone the repository:**
   ```bash
   git clone https://github.com/Sarthak-Salunke/DataPulse---Real-Time-Fraud-Detection-System.git
   cd DataPulse---Real-Time-Fraud-Detection-System
   ```
2. **Install dependencies:**
   - Python 3.8+
   - Install required packages:
     ```bash
     pip install -r requirements.txt
     ```
3. **Run model training:**
   ```bash
   python ml/training/logistic_regression/fraud_detection_lr.py
   ```
4. **Artifacts will be saved in the project root.**

## Real-Time Pipeline
- **Kafka Producer:** Streams transactions from `data/transactions_producer.csv`.
- **Spark Streaming:** Consumes, scores, and persists results.
- **FastAPI:** Serves predictions and analytics to the dashboard.
- **Frontend:** Visualizes fraud alerts and statistics in real time.

---

## Cloud Deployment — Option 1: Redpanda + Python Worker (Free Tier)

This deployment replaces Apache Spark with a lightweight Python consumer and uses fully-managed cloud services, achieving **$0/month** on free tiers.

### Architecture

```
Scala Producer → Redpanda Cloud (Kafka) → Python Worker → Supabase (PostgreSQL+pgvector)
                                                              ↑
                         Render (FastAPI backend) ────────────┘
                         Vercel (React frontend)
```

| Component | Service | Cost |
|-----------|---------|------|
| Message broker | Redpanda Cloud Serverless | Free |
| PostgreSQL + pgvector | Supabase | Free |
| FastAPI backend | Render Web Service | Free |
| Kafka consumer | Render Background Worker | Free |
| React frontend | Vercel | Free |

### Deploy Steps

#### 1 — Train the streaming model (run once locally)
```bash
python pipeline/train_streaming_model.py
# Produces: ml/models/streaming/sklearn_rf.pkl + label_encoders.pkl
git add ml/models/streaming/ && git commit -m "add streaming model artifacts"
```

#### 2 — Supabase database
1. Create a project at [supabase.com](https://supabase.com)
2. Open the SQL Editor and run `config/supabase_schema.sql`
3. Copy the connection string from **Settings → Database → URI**
4. Create the read-only user:
   ```sql
   CREATE USER dp_readonly WITH PASSWORD 'your-password';
   GRANT SELECT ON ALL TABLES IN SCHEMA public TO dp_readonly;
   ```

#### 3 — Redpanda Cloud
1. Create a Serverless cluster at [redpanda.com/redpanda-cloud](https://redpanda.com/redpanda-cloud)
2. Create a topic named `creditcardTransaction`
3. Create a user and note the bootstrap URL, username, and password
4. Update `pipeline/kafka-producer/src/main/resources/application.conf` with the bootstrap URL

#### 4 — Deploy to Render
1. Push this repository to GitHub
2. In Render: **New → Blueprint** → connect your repo (Render reads `render.yaml`)
3. Set all `sync: false` env vars in the Render dashboard:
   - `DATABASE_URL` — Supabase connection URI
   - `ALLOWED_ORIGINS` — your Vercel frontend URL (e.g. `https://datapulse.vercel.app`)
   - `ADMIN_PASSWORD`, `REDPANDA_USERNAME`, `REDPANDA_PASSWORD`

#### 5 — Deploy frontend to Vercel
```bash
cd frontend
# Set environment variable in Vercel dashboard:
#   VITE_API_BASE_URL = https://datapulse-api.onrender.com
#   VITE_WEBSOCKET_URL = wss://datapulse-api.onrender.com/ws
vercel --prod
```

#### 6 — Train Vanna (optional chatbot)
```bash
# Set DATABASE_URL, GEMINI_API_KEY, DB_READONLY_USER, DB_READONLY_PASSWORD in backend/.env
python backend/vanna_train.py
```

> **Note:** The Render free web service sleeps after 15 min of inactivity. Add a free [UptimeRobot](https://uptimerobot.com) monitor on `https://datapulse-api.onrender.com/api/health` to keep it awake.

---

## Contributing
Pull requests and issues are welcome! Please open an issue to discuss your ideas or report bugs.

## License
MIT License

---
For more details, see the code and documentation in each subfolder.
