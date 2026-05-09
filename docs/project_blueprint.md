# Application Context & Blueprint

## 1. High-Level Overview
* **Name:** DataPulse
* **Purpose:** Real-time credit card fraud detection system. Transactions are ingested from Kafka/Redpanda, scored by a sklearn RandomForest (cloud) or Spark RF (local), passed through a deterministic Rule Engine, persisted to PostgreSQL, and surfaced to analysts via a WebSocket-powered dashboard and an NL-to-SQL chatbot.
* **Current State:** Deployed on Render (FastAPI backend + Kafka consumer worker). Frontend deployed on Vercel. Database: Supabase PostgreSQL. Streaming broker: Redpanda Cloud. End-to-end latency ≤13 seconds.

---

## 2. Technical Stack

### Backend
* Python 3.11, FastAPI 2.0, Uvicorn
* `psycopg2` `ThreadedConnectionPool` (min=1, max=10)
* Pydantic v2, python-jose (JWT), passlib + bcrypt 4.x
* **Chatbot:** Vanna + pgvector (`FraudVanna` mixin) + Gemini Flash (`gemini-1.5-flash`) — NL-to-SQL two-pass architecture
* **Google Auth:** `google-auth` package (optional; gracefully disabled if absent)
* `confluent-kafka` ≥ 2.3.0 (Kafka consumer worker)
* scikit-learn (streaming model inference in `kafka_consumer_worker.py`)

### Frontend
* React 19, TypeScript, Vite, **TailwindCSS** (`tailwind.config.js` present)
* TanStack React Query v5 (`@tanstack/react-query`)
* Native WebSocket API (no socket.io)
* React Router v6 (`BrowserRouter`)
* Recharts (charts inside Dashboard)
* Deployed on Vercel (`vercel.json` present)

### Database / Storage
* PostgreSQL via **Supabase** (cloud) or local Postgres (`fraud_detection` DB)
* Tables: `customer`, `fraud_transaction`, `non_fraud_transaction`, `kafka_offset`, `customer_stats`
* `fraud_transaction` and `non_fraud_transaction` carry: `rule_flags TEXT DEFAULT '[]'`, `rule_severity VARCHAR(10) DEFAULT 'NONE'`
* Schema files: `config/postgresql_schema.sql` (local/TimescaleDB), `config/supabase_schema.sql` (cloud)

### Streaming / ML
* **Cloud path:** Python `kafka_consumer_worker.py` (confluent-kafka) → sklearn RF (`ml/models/streaming/sklearn_rf.pkl` + `label_encoders.pkl`)
* **Local/research path:** Apache Spark 3.5.3 Structured Streaming (`pipeline/spark_jobs/streaming/spark_structured_streaming.py`) → Spark ML artifacts (`ml/models/PreprocessingModel/` + `ml/models/RandomForestModel/`)
* Kafka producer: Scala + Maven (`pipeline/kafka-producer/`) — publishes JSON to topic `creditcardTransaction`
* Redpanda Cloud used as Kafka-compatible broker in production (SASL/SCRAM-SHA-256)

### CAPE
* Pure-Python 9-layer fraud scoring engine in `cape/`
* Dependencies: scikit-learn, LightGBM, MAPIE, SHAP, ruptures
* Loaded at FastAPI startup via `cape_router.py`; exposes `/api/cape/*` endpoints

---

## 3. Core Architecture & Folder Structure

```
DataPulse/
├── backend/
│   ├── main_fastapi.py       # FastAPI entry point (REST + WebSocket + auth)
│   ├── cape_router.py        # CAPE scoring API (/api/cape/*)
│   ├── chatbot.py            # NL-to-SQL chatbot (/api/chat)
│   └── vanna_train.py        # Vanna training helper
├── frontend/src/
│   ├── App.tsx               # Router: / (Landing), /login, /dashboard, /cases/:id
│   ├── components/
│   │   ├── Auth/LoginPage.tsx
│   │   ├── Cases/CaseDetail.tsx
│   │   ├── Chat/FraudChatPanel.tsx   # Sliding chat panel (NL queries)
│   │   ├── Chat/ChartRenderer.tsx    # Recharts renderer for query results
│   │   ├── Chat/DataTable.tsx
│   │   ├── Common/AppShell.tsx       # Sidebar + nav shell
│   │   ├── Dashboard/Dashboard.tsx
│   │   ├── Dashboard/MetricsCard.tsx
│   │   ├── Dashboard/RealTimeFeed.tsx
│   │   ├── LandingPage.tsx
│   │   └── Pipeline/ArchitectureDiagram.tsx
│   ├── context/AuthContext.tsx
│   ├── hooks/useApiData.ts    # React Query hooks (metrics/alerts/transactions/ws)
│   ├── services/api.ts        # ApiClient class + apiService + mockApi
│   ├── lib/queryClient.ts
│   └── types/index.ts
├── pipeline/
│   ├── kafka_consumer_worker.py   # PRIMARY cloud streaming worker (sklearn RF)
│   ├── train_streaming_model.py   # Trains sklearn_rf.pkl + label_encoders.pkl
│   ├── kafka-producer/            # Scala Kafka producer
│   └── spark_jobs/
│       ├── streaming/spark_structured_streaming.py  # Local Spark path
│       ├── streaming/spark_dstream_fraud_detection.py
│       └── batch/                 # DB import utilities
├── ml/
│   ├── models/
│   │   ├── streaming/             # sklearn_rf.pkl + label_encoders.pkl (cloud)
│   │   ├── PreprocessingModel/    # Spark ML preprocessing (local only)
│   │   ├── RandomForestModel/     # Spark ML RF (local only)
│   │   ├── lgbm_model.pkl         # LightGBM (CAPE)
│   │   └── rf_model.pkl           # sklearn RF (CAPE)
│   └── training/                  # Offline training scripts (RF, GBM, SVM, etc.)
├── cape/                          # 9-layer CAPE engine (L0–L8 + pipeline.py)
├── config/
│   ├── postgresql_schema.sql      # Authoritative local schema
│   └── supabase_schema.sql        # Cloud / Supabase schema
├── scripts/                       # Data pipeline scripts (step1–step8) + bat files
├── data/                          # CSV datasets
├── docs/                          # Documentation
├── tests/                         # test_cape.py (88 tests), smoke_test.py
├── render.yaml                    # Render deployment manifest
└── requirements.txt               # Root-level deps (backend + pipeline + CAPE)
```

---

## 4. Key Business Logic / Workflows

### 4.1 Cloud Real-Time Pipeline (Primary — `kafka_consumer_worker.py`)

1. **Kafka ingest:** Scala producer publishes JSON to `creditcardTransaction`; Redpanda Cloud (SASL/SCRAM-SHA-256) brokers the topic
2. **Consumer:** `kafka_consumer_worker.py` polls with `confluent-kafka`, decodes JSON
3. **Feature engineering (pure Python):**
   * Customer lat/long/dob fetched from Postgres via `CustomerCache` (5-min TTL)
   * `distance` via Haversine UDF
   * `age` from dob
   * Temporal: `hour`, `dayofweek` (Spark convention: Sun=1…Sat=7), `is_weekend`
   * Velocity: `VelocityTracker` sliding deque — `tx_count_1h`, `tx_amt_1h`, `tx_count_10min`
   * Categorical encoding: `LabelEncoder` loaded from `label_encoders.pkl`
4. **ML scoring:** `sklearn_rf.pkl.predict_proba(feat_vec)[0,1]` → `fraud_prob`
5. **Adaptive threshold:** same per-category map as Spark path (see §4.3)
6. **Rule Engine:** same 3-rule logic as Spark path (see §4.3)
7. **DB write:** `execute_values` → `fraud_transaction` or `non_fraud_transaction`, `ON CONFLICT (cc_num, trans_time) DO NOTHING`
8. **WebSocket broadcast:** FastAPI `poll_new_fraud_transactions()` polls `fraud_transaction WHERE created_at > last_seen` every **3 seconds**, broadcasts `{type: "fraud_alert", data: {...}}` to all connected clients

**Note:** The `LISTEN/NOTIFY` (pg_notify) mechanism described in older docs has been replaced by a **3-second polling loop** (`poll_new_fraud_transactions`) to support Supabase's Supavisor connection pooler, which blocks `LISTEN`.

### 4.2 Local Spark Pipeline (Research / Development)

Same conceptual flow as §4.1 but uses:
* PySpark Structured Streaming with `.trigger(processingTime='5 seconds')`
* `PreprocessingModel` (StringIndexer → OHE → VectorAssembler) + `RandomForestModel`
* `ThreadPoolExecutor` for parallel RF scoring
* `foreachBatch` → `psycopg2.extras.execute_values`

### 4.3 Deterministic Rule Engine

Applied **after** ML scoring, **before** DB write. Same logic in both cloud worker and Spark job.

| Rule | Condition | Severity |
|---|---|---|
| Impossible Travel | `distance > 500 AND tx_count_10min > 1` | `CRITICAL` |
| Amount Spike | `avg_amt_30d IS NOT NULL AND amt > avg_amt_30d * 5` | `HIGH` |
| High-Risk Merchant | `category IN HIGH_RISK_CATEGORIES AND amt > 1000` | `MEDIUM` |

`HIGH_RISK_CATEGORIES = {"misc_net", "online_shopping", "online_gift_card", "shopping_net", "shopping_pos", "home"}`

**Severity precedence:** `CRITICAL > HIGH > MEDIUM > NONE`

**CRITICAL override:** `is_fraud = 1.0` whenever `rule_severity == "CRITICAL"`, regardless of ML score.

**Adaptive threshold map:**

| Category | Threshold |
|---|---|
| `online_gift_card` | 0.20 |
| `misc_net`, `online_shopping` | 0.25 |
| `travel` | 0.30 |
| `grocery_pos`, `gas_transport` | 0.45 |
| *(all others)* | 0.40 |

### 4.4 ML Feature Vector Contract

Both training (`pipeline/train_streaming_model.py`) and inference (`kafka_consumer_worker.py`) use this exact 11-feature ordered set. Any change requires retraining and replacing both `.pkl` files.

| # | Column | Source | Used by |
|---|---|---|---|
| 1 | `cc_num_enc` | `LabelEncoder(cc_num)` | ML |
| 2 | `category_enc` | `LabelEncoder(category)` | ML |
| 3 | `merchant_enc` | `LabelEncoder(merchant)` | ML |
| 4 | `distance` | Haversine UDF | ML + Rule Engine |
| 5 | `amt` | Kafka JSON | ML + Rule Engine |
| 6 | `age` | Customer join / dob | ML |
| 7 | `hour` | `trans_time.hour` | ML |
| 8 | `dayofweek` | Spark convention (Sun=1) | ML |
| 9 | `is_weekend` | `dayofweek in (1,7)` | ML |
| 10 | `tx_count_1h` | VelocityTracker window(-3600) | ML |
| 11 | `tx_amt_1h` | VelocityTracker window(-3600) | ML |
| — | `tx_count_10min` | VelocityTracker window(-600) | **Rule Engine only** |

### 4.5 Sklearn RF Training (`pipeline/train_streaming_model.py`)

* Reads `data/transactions.csv` + `data/customer.csv`
* Computes distance, age, temporal, velocity features (O(n) deque per card)
* Fits `RandomForestClassifier(n_estimators=100, max_depth=15, class_weight="balanced")`
* Saves `ml/models/streaming/sklearn_rf.pkl` + `ml/models/streaming/label_encoders.pkl`
* Must be run before starting `kafka_consumer_worker.py`

### 4.6 Analyst Authentication

1. `POST /auth/login` → bcrypt verify → issues JWT; also supports Google OAuth (`POST /auth/google` via `google-auth`)
2. Cookie: `httpOnly=True, samesite="none", secure=True` (cross-origin safe for Vercel ↔ Render)
3. Auth also accepted via `Authorization: Bearer <token>` header (fallback for cross-origin cookie blocking)
4. Token stored in `sessionStorage` as `dp_token` on the frontend (`setAuthToken()` in `useApiData.ts`)
5. `GET /auth/me` restores session on page load; `POST /auth/logout` clears cookie

### 4.7 NL-to-SQL Chatbot (`backend/chatbot.py` → `POST /api/chat`)

Two-pass architecture:
1. **Pass 1 — Vanna (NL → SQL → DataFrame):** `FraudVanna` (PG_VectorStore + GoogleGeminiChat mixin) uses `gemini-1.5-flash` to generate a `SELECT` query and runs it against the DB via a read-only user
2. **Pass 2 — Gemini (DataFrame → insight):** `gemini-1.5-flash` generates a 1–2 sentence analyst-friendly summary of the result
3. **Visualization hint:** inferred from SQL structure (`GROUP BY` + date cols → `line_chart`; `GROUP BY` → `bar_chart`; single row → `stat_card`; else → `table`)
4. Requires `GEMINI_API_KEY`, `DB_READONLY_USER`, `DB_READONLY_PASSWORD` in `.env`
5. Frontend: `FraudChatPanel.tsx` (sliding side panel, always rendered inside `DashboardPage`)

### 4.8 Transaction Ingest Endpoint (`POST /api/transactions/ingest`)

Accepts a raw transaction JSON, scores it (CAPE pipeline first; heuristic fallback if models absent), and writes directly to `fraud_transaction` or `non_fraud_transaction`. Used for manual/demo ingestion without Kafka.

### 4.9 Customer & Statement Lookup

* `GET /api/customer/{cc_num}` → masked card number, name, age, job, address
* `GET /api/statement/{cc_num}?limit=100` → UNION of `fraud_transaction` + `non_fraud_transaction` for that card, ordered by `trans_time DESC`
* Frontend: `CaseDetail.tsx` at route `/cases/:id`

---

## 5. Frontend Routes & Components

| Route | Component | Access |
|---|---|---|
| `/` | `LandingPage.tsx` (Hero, HowItWorks, Features, CTA, Footer) | Public |
| `/login` | `Auth/LoginPage.tsx` | Public |
| `/dashboard` | `Dashboard/Dashboard.tsx` inside `AppShell` + `FraudChatPanel` | Protected |
| `/cases/:id` | `Cases/CaseDetail.tsx` | Protected |

**Context:** `AuthContext` (user + isLoading), `ThemeContext` (dark/light toggle — dark default)

**Data hooks (`hooks/useApiData.ts`):**
* `useDashboardMetrics(5000ms)` — polls `/api/dashboard/metrics`
* `useRecentAlerts(limit, 3000ms)` — polls `/api/fraud/alerts`
* `useTransactions(limit, 5000ms)` — polls `/api/transactions`
* `useHealthCheck(30000ms)` — polls `/api/health`
* `useWebSocket(onMessage)` — native WS to `/ws`, exponential backoff reconnect (max 5 attempts, 30s cap)

**Services (`services/api.ts`):** `ApiClient` class + `apiService` object for typed REST calls; `mockApi` for dev without backend.

---

## 6. API Endpoints Reference

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/` | No | Root info |
| GET | `/api/health` | No | DB connectivity check |
| GET | `/api/dashboard/metrics` | Yes | `totalTransactions`, `fraudDetected`, `fraudRate`, `accuracy` |
| GET | `/api/fraud/alerts?limit=N` | Yes | Recent fraud transactions |
| GET | `/api/transactions?limit=N` | Yes | Combined fraud + normal transactions |
| GET | `/api/customer/{cc_num}` | Yes | Customer profile |
| GET | `/api/statement/{cc_num}?limit=N` | Yes | Card transaction history |
| POST | `/api/transactions/ingest` | No | Manual transaction ingest + CAPE scoring |
| POST | `/api/chat` | Yes | NL-to-SQL chatbot |
| POST | `/api/cape/score` | Yes | CAPE pipeline score |
| POST | `/api/cape/feedback/chargeback` | Yes | CAPE feedback (fraud label) |
| POST | `/api/cape/feedback/step_up_cleared` | Yes | CAPE feedback (legit label) |
| GET | `/api/cape/status` | Yes | CAPE calibration health |
| POST | `/auth/login` | No | Username/password login |
| POST | `/auth/google` | No | Google OAuth login |
| POST | `/auth/logout` | No | Clear auth cookie |
| GET | `/auth/me` | Yes | Current user from cookie |
| WS | `/ws` | No (token via WS or cookie) | Real-time fraud alert stream |

---

## 7. Datasets

### Runtime / Pipeline Required
* `data/customer.csv` — loaded into `customer` table; Kafka worker joins on `cc_num`
* `data/transactions.csv` — loaded into `fraud_transaction` / `non_fraud_transaction`; used by `train_streaming_model.py`
* `data/transactions_producer.csv` — Scala Kafka producer input

### Offline Training / Research
* `data/synthetic-credit-card-transactions-fraud-detection-dataset/` (Sparkov)
* `data/credit-card-fraud-detection/creditcard.csv`
* `data/ieee-fraud-detection/`
* `data/synthetic-financial-datasets-for-fraud-detection/`
* `data/fraud-ecommerce/`

**Minimal data pack to run the app:** `customer.csv` + `transactions.csv` + `transactions_producer.csv`

---

## 8. CAPE — Confidence-Aware Progressive Escalation

9-layer pure-Python fraud scoring engine in `cape/`. Decoupled from Kafka/Spark. Loaded into FastAPI at startup via `cape_router.py`.

| Layer | File | Role |
|---|---|---|
| L0 — Feature Store | `layer0_feature_store.py` | Versioned features, Welford online baseline, Redis-ready (dict fallback) |
| L1 — Cold-Start Router | `layer1_cold_start_router.py` | Tighter thresholds for new users (<20 txns) / new merchants (<7 days) |
| L2 — Fast Gate | `layer2_fast_gate.py` | Welford z-score (N=2.5σ) + Count-Min Sketch velocity. ~70–75% traffic exits as APPROVE |
| L3 — Parallel Scorers | `layer3_parallel_scorers.py` | RF + LightGBM + EWMA recency scorer → probability vector |
| L4 — Conformal Prediction | `layer4_conformal.py` | Online split conformal, 95% CI, rolling calibration window N=1000 |
| L5 — Drift Detection | `layer5_drift_detection.py` | CUSUM (fast) + PSI (slow). Auto-adjusts threshold; triggers retrain request |
| L6 — Routing | `layer6_routing.py` | BLOCK / APPROVE / NOVEL-FLAG with channel-aware action map |
| L7 — Explainability | `layer7_explainability.py` | SHAP TreeExplainer → top-3 feature reason codes |
| L8 — Feedback Loop | `layer8_feedback.py` | Chargeback→fraud / step-up→legit labels; analyst queue; shadow scoring |
| Orchestrator | `pipeline.py` | `CAPEPipeline.evaluate(txn)` wires all layers |

**Model artifacts used by CAPE:** `ml/models/rf_model.pkl`, `ml/models/lgbm_model.pkl`, `ml/models/cape/`

**CAPE feature vector:** 19 features (including `graph_distinct_accounts_1hr`). Order defined in `layer3_parallel_scorers.FEATURE_ORDER`. Separate from the 11-feature streaming vector.

---

## 9. Deployment

### Production (Render + Vercel + Supabase + Redpanda)

| Service | Platform | Config |
|---|---|---|
| FastAPI backend | Render Web Service (free) | `render.yaml` → `cd backend && uvicorn main_fastapi:app` |
| Kafka worker | Render Background Worker (free) | `render.yaml` → `python pipeline/kafka_consumer_worker.py` |
| Frontend | Vercel | `frontend/vercel.json` (SPA redirect) |
| Database | Supabase PostgreSQL | `DATABASE_URL` env var; schema from `config/supabase_schema.sql` |
| Kafka broker | Redpanda Cloud Serverless | SASL/SCRAM-SHA-256; `REDPANDA_USERNAME` / `REDPANDA_PASSWORD` |

**Pre-deploy checklist:**
1. Create Supabase project → run `config/supabase_schema.sql`
2. Create Redpanda Cloud cluster + topic `creditcardtransaction`
3. Run `python pipeline/train_streaming_model.py` → commit `ml/models/streaming/` to Git
4. Set all `sync: false` vars in Render dashboard

### Local Development

```bash
# Backend
cd backend && pip install -r ../requirements.txt
uvicorn main_fastapi:app --reload --port 8000

# Frontend
cd frontend && npm install
npm run dev   # http://localhost:5173

# Streaming worker (requires trained model + Kafka running)
python pipeline/kafka_consumer_worker.py

# Train streaming model (one-time)
python pipeline/train_streaming_model.py

# Spark path (optional — requires Kafka + Spark installed)
scripts\windows\run_spark_streaming.bat
```

---

## 10. Environment Variables

### `backend/.env`

```
# Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=fraud_detection
DB_USER=postgres
DB_PASSWORD=<password>
DATABASE_URL=<full-postgres-url>          # preferred for cloud (Supabase)

# Auth
JWT_SECRET_KEY=<min-32-char-random-string>
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=480
ADMIN_USERNAME=admin
ADMIN_PASSWORD=<password>
GOOGLE_CLIENT_ID=<optional>              # enables Google OAuth

# CORS
ALLOWED_ORIGINS=http://localhost:5173,https://your-frontend.vercel.app

# Chatbot (optional)
GEMINI_API_KEY=<optional>
DB_READONLY_USER=dp_readonly
DB_READONLY_PASSWORD=<optional>

# Spark (local only)
POSTGRES_JDBC_JAR=C:\spark\jars\postgresql-42.7.1.jar
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_TOPIC=creditcardTransaction
SPARK_MASTER=local[*]
```

### `frontend/.env`

```
VITE_API_BASE_URL=http://localhost:8000
VITE_WEBSOCKET_URL=ws://localhost:8000/ws
```

---

## 11. Strict Conventions

* **Auth cookies:** `httpOnly`, `samesite="none"`, `secure=True`. Frontend also caches JWT in `sessionStorage` as `dp_token` and sends `Authorization: Bearer` header to handle cross-origin cookie blocking.
* **DB access:** All DB calls go through `get_db()` context manager (pool borrow/return). Exception: chatbot uses its own Vanna connection via `DB_READONLY_USER`.
* **Sync endpoints:** FastAPI DB-touching endpoints are plain `def`, not `async def`.
* **WebSocket monitor:** `poll_new_fraud_transactions()` polls every 3s — do NOT revert to `LISTEN/NOTIFY` (blocked by Supabase Supavisor).
* **No Flask:** `main.py` (Flask) removed. All routes on port 8000 in `main_fastapi.py`.
* **bcrypt version:** must stay on `4.x` — passlib 1.7.4 is incompatible with bcrypt 5.x.
* **Feature vector contract:** `FEATURE_COLS` in `train_streaming_model.py` and `kafka_consumer_worker.py` must stay identical. Any change requires retraining both `.pkl` files.
* **`tx_count_10min` is rule-engine-only:** never add to `FEATURE_COLS` or model input.
* **Duplicate prevention:** `INSERT … ON CONFLICT (cc_num, trans_time) DO NOTHING` — immutable records, do not upsert.
* **React Query polling:** minimum intervals: 3s (alerts), 5s (metrics). `staleTime` set globally on `queryClient`.
* **Type safety:** API response shapes defined in `frontend/src/types/index.ts` must stay in sync with backend Pydantic models.
* **CAPE startup:** `init_cape_pipeline(deployment_day=0)` called at FastAPI startup; non-fatal if model files absent (falls back to heuristic in `/api/transactions/ingest`).

---

## 12. Data Pipeline Scripts (`scripts/`)

| Script | Purpose |
|---|---|
| `step1_merge_sparkov.py` | Merges Sparkov synthetic datasets → `transactions_merged.csv` → `transactions_producer.csv` |
| `step2_smote_balance.py` | SMOTE oversampling for class balance |
| `step3_ieee_features.py` | IEEE fraud feature engineering |
| `step4_cape_calibration.py` | CAPE conformal calibration data prep |
| `step5_graph_features.py` | Graph-based velocity features |
| `step6_ecommerce_features.py` | E-commerce fraud features |
| `step7_final_dataset.py` | Assembles final training dataset |
| `step8_retrain_models.py` | Retrains models after dataset update |
| `seed_data.py` | Seeds Postgres with initial data |
| `simulate_transactions.py` | Simulates real-time transaction stream for testing |

---

## 13. End-to-End Pipeline Latency

```
Stage                         Component                      Latency
─────────────────────────────────────────────────────────────────────
1. Transaction published       Scala Kafka producer           1–3s
2. Consumer poll               kafka_consumer_worker.py       <1s
3. Feature engineering         CustomerCache + Velocity        <1s
4. ML scoring                  sklearn RF predict_proba       <1s
5. Rule Engine                 apply_rules()                  <1s
6. DB write                    execute_values / psycopg2      <1s
7. FastAPI poll wakes          poll_new_fraud (3s interval)   0–3s
8. WebSocket broadcast         manager.broadcast()            ~0ms
9. Browser alert rendered      React WS callback              ~0ms
─────────────────────────────────────────────────────────────────────
TOTAL END-TO-END                                              ≤13s
```
