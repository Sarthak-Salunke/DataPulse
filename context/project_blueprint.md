# Application Context & Blueprint

## 1. High-Level Overview
* **Name:** DataPulse
* **Purpose:** Real-time credit card fraud detection system. Streams financial transactions through Kafka and Spark, scores them with a trained Random Forest model, and surfaces live fraud alerts to analysts via a WebSocket-powered dashboard. Solves the gap between transaction occurrence and fraud visibility — reducing detection latency from days (batch) to under 30 seconds.
* **Current State:** Active Development / Final Year Major Project (MVP-complete; not production-hardened)

---

## 2. Technical Stack
* **Frontend:** React 19, TypeScript, Vite, TailwindCSS, Recharts, TanStack React Query v5, native WebSocket API
* **Backend:** Python 3.9, FastAPI, Uvicorn, psycopg2 (ThreadedConnectionPool, 2–10 connections), Pydantic v2, python-jose (JWT), passlib + bcrypt
* **Database/Storage:** PostgreSQL (`fraud_detection` DB) — tables: `customer`, `fraud_transaction`, `non_fraud_transaction`, `kafka_offset`
* **Integrations/AI:** Apache Spark 3.5 (Structured Streaming), Apache Kafka (`creditcardTransaction` topic), Spark ML (Random Forest Classifier + preprocessing pipeline — StringIndexer → OneHotEncoder → VectorAssembler). Kafka producer written in Scala.

---

## 3. Core Architecture & Folder Structure
* `backend/`: FastAPI server — single entry point `main_fastapi.py`, DB queries in `query_execute.py`, JWT auth baked in
* `frontend/src/`: React app — `components/`, `context/` (AuthContext, ThemeContext), `hooks/` (React Query wrappers), `services/` (ApiClient + WebSocketService), `types/`, `utils/`
* `pipeline/kafka-producer/`: Scala Kafka producer — reads CSV, emits JSON transaction events with 1–3s simulated delay
* `pipeline/spark_jobs/`: PySpark batch + streaming jobs — `streaming/` holds the live scoring pipeline; `batch/` holds DB import utilities
* `ml/models/`: Serialized production Spark ML artifacts — `PreprocessingModel/` (pipeline) and `RandomForestModel/` (classifier). Loaded at Spark job startup.
* `ml/training/`: Training scripts for all model variants (Random Forest, GBM, LR, SVM, Naive Bayes, Isolation Forest, Neural Network)
* `data/`: Raw CSV source data for Kafka producer and batch imports
* `scripts/windows/`: Batch files to launch Spark training (`run_spark_training.bat`) and streaming (`run_spark_streaming.bat`)
* `context/`: Project documentation, methodology, and training guides
* `config/`: Supplementary configuration files

---

## 4. Key Business Logic / Workflows

* **Transaction Ingestion & Scoring:**
  1. Scala producer reads `data/*.csv`, serializes each row as JSON, publishes to Kafka topic `creditcardTransaction` with 1–3s delay
  2. Spark Structured Streaming job consumes topic, parses JSON to DataFrame
  3. Broadcast-joins with `customer` table on `cc_num`; computes `age` (year diff from `dob`) and `distance` (Haversine UDF between customer lat/long and merchant lat/long)
  4. Applies `PreprocessingModel` pipeline (StringIndexer + OneHotEncoder + VectorAssembler) to produce feature vector
  5. Applies `RandomForestModel` to produce `is_fraud` probability (0.0–1.0); threshold 0.5
  6. Rows with `is_fraud > 0.5` written to `fraud_transaction`; remainder to `non_fraud_transaction` via `INSERT … ON CONFLICT DO NOTHING`

* **Live Dashboard Update:**
  1. FastAPI background task `monitor_fraud_transactions()` polls `fraud_transaction` every 5s for rows with `created_at > last_check_time`
  2. New rows broadcast to all connected WebSocket clients as `{type: "fraud_alert", data: {...}}`
  3. Browser `wsService` receives message, fires registered `fraud_alert` callbacks
  4. React Query independently polls `/api/fraud/alerts` (3s) and `/api/dashboard/metrics` (5s) for resilience
  5. Dashboard re-renders with updated feed and metrics cards

* **Analyst Authentication:**
  1. `POST /auth/login` with `{username, password}` — server validates against bcrypt hash of `.env` credentials
  2. On success, server sets `access_token` as `httpOnly, SameSite=Lax` cookie (8h TTL)
  3. All subsequent requests auto-attach cookie; backend `get_current_user()` dependency decodes JWT and gates every protected endpoint
  4. `GET /auth/me` on page load restores session without re-login; `POST /auth/logout` deletes cookie

* **Customer & Statement Lookup:**
  1. Analyst enters a card number in the dashboard search
  2. `GET /api/customer/{cc_num}` returns masked card number (`**** **** **** {last4}`), name, age, job, address
  3. `GET /api/statement/{cc_num}?limit=100` returns UNION of `fraud_transaction` + `non_fraud_transaction` for that card, ordered by `trans_time DESC`

---

## 5. Developer & AI Agent Onboarding

* **Environment Setup:**

  Required `.env` variables (create at `backend/.env`):
  ```
  DB_HOST=localhost
  DB_PORT=5432
  DB_NAME=fraud_detection
  DB_USER=postgres
  DB_PASSWORD=<your_password>
  POSTGRES_URL=jdbc:postgresql://localhost:5432/fraud_detection
  POSTGRES_JDBC_JAR=C:\Spark\spark\jars\postgresql-42.7.8.jar
  KAFKA_BOOTSTRAP_SERVERS=localhost:9092
  KAFKA_TOPIC=creditcardTransaction
  KAFKA_GROUP_ID=fraud-detection-consumer
  SPARK_MASTER=local[*]
  JWT_SECRET_KEY=<min-32-char-random-string>
  JWT_ALGORITHM=HS256
  JWT_EXPIRE_MINUTES=480
  ADMIN_USERNAME=admin
  ADMIN_PASSWORD=<your_password>
  ```

  Run order:
  ```bash
  # 1. Backend
  cd backend && pip install -r requirements.txt
  uvicorn main_fastapi:app --reload --port 8000

  # 2. Frontend
  cd frontend && npm install
  npm run dev   # http://localhost:5173

  # 3. Pipeline (requires Kafka + Spark running locally)
  scripts\windows\run_spark_training.bat    # one-time — trains and saves models to ml/models/
  scripts\windows\run_spark_streaming.bat   # continuous — starts real-time scoring
  ```

* **Strict Conventions:**
  * **Auth:** Never store JWT in `localStorage`/`sessionStorage`. Cookie is set server-side only. All fetch calls must pass `{ credentials: 'include' }`.
  * **DB access:** All PostgreSQL access goes through `query_execute.py` functions. Never open a raw `psycopg2` connection outside the `get_db()` context manager — connections must return to the `ThreadedConnectionPool`.
  * **Sync endpoints:** FastAPI endpoints that touch PostgreSQL must be `def` (not `async def`) — FastAPI runs them in a thread pool, which is correct for blocking psycopg2 I/O.
  * **Model paths:** ML model artifacts live at `ml/models/PreprocessingModel` and `ml/models/RandomForestModel` relative to `project_home` (`~/frauddetection`). Overridable via `MODEL_PATH` and `PREPROCESSING_MODEL_PATH` env vars.
  * **Duplicate prevention:** Spark streaming uses `INSERT … ON CONFLICT (cc_num, trans_time) DO NOTHING`. Do not change this to upsert — transaction records are immutable.
  * **React Query polling:** `staleTime` is 4s globally. Do not set polling intervals below 3s (alerts) or 5s (metrics) to avoid DB overload.
  * **Type safety:** All API response shapes are defined in `frontend/src/types/index.ts`. Backend Pydantic models must stay in sync with these frontend types.
  * **No Flask:** `backend/main.py` (Flask) has been removed. All routes live in `main_fastapi.py` on port 8000.
  * **Dependency versions:** `bcrypt` must stay on `4.x` — `passlib 1.7.4` is incompatible with `bcrypt 5.x`.
