# Application Context & Blueprint

## 1. High-Level Overview
* **Name:** DataPulse
* **Purpose:** Real-time credit card fraud detection system. Streams financial transactions through Kafka and Spark, scores them with a trained Random Forest model, passes results through a deterministic Rule Engine, and surfaces live fraud alerts to analysts via a WebSocket-powered dashboard driven by Postgres pub/sub. Reduces detection latency from days (batch) to **≤13 seconds** end-to-end.
* **Current State:** Active Development / Final Year Major Project (MVP-complete; CAPE architecture implemented and tested; not production-hardened)

---

## 2. Technical Stack
* **Frontend:** React 19, TypeScript, Vite, TailwindCSS, Recharts, TanStack React Query v5, native WebSocket API
* **Backend:** Python 3.9, FastAPI, Uvicorn, psycopg2 (`ThreadedConnectionPool` 2–10 connections; `ISOLATION_LEVEL_AUTOCOMMIT` connection for `LISTEN`), `import select` (async pub/sub wait), Pydantic v2, python-jose (JWT), passlib + bcrypt
* **Database/Storage:** PostgreSQL + **TimescaleDB extension** (`fraud_detection` DB)
  * Tables: `customer`, `fraud_transaction`, `non_fraud_transaction`, `kafka_offset`, **`customer_stats`** (hypertables + continuous aggregates for analytics)
  * `fraud_transaction` and `non_fraud_transaction` carry two rule engine columns: `rule_flags TEXT DEFAULT '[]'` and `rule_severity VARCHAR(10) DEFAULT 'NONE'`
  * Pub/Sub infrastructure: `notify_fraud_insert()` plpgsql function + `fraud_notify_trigger` (`AFTER INSERT ON fraud_transaction FOR EACH ROW`) emit `pg_notify('fraud_channel', row_to_json(NEW))`
* **Integrations/Streaming:** **Apache Spark 3.5.3** (PySpark Structured Streaming + optional DStreams), **Apache Kafka** (`creditcardTransaction` topic)
* **ML (Streaming inference):**
  * Spark ML artifacts (`PreprocessingModel` + `RandomForestModel`) loaded at Spark job startup
  * **11-feature inference vector:** `cc_num`, `category`, `merchant`, `distance`, `amt`, `age` (base 6) + `hour`, `dayofweek`, `is_weekend` (temporal 3) + `tx_count_1h`, `tx_amt_1h` (velocity 2)
  * **`tx_count_10min`** computed as a pass-through column (rule engine only — excluded from `VectorAssembler`)
  * Scoring: `preprocessed_df.cache()` → parallel `ThreadPoolExecutor` → `rf_model.transform` → `.unpersist()`
  * Classification: `probability[1]` (fraud class score) evaluated against per-category adaptive threshold map; final `is_fraud` overridden to `1.0` if any `CRITICAL` rule fires
* **Producer:** Scala + Maven Kafka producer (publishes **JSON** messages; Avro path commented out)
* **CAPE Architecture:** Pure-Python fraud scoring engine (`cape/`) — scikit-learn, LightGBM, MAPIE (conformal prediction), SHAP, ruptures. Redis-ready feature store (in-process dict fallback). No Spark dependency.

---

## 3. Core Architecture & Folder Structure
* `backend/`: FastAPI server — single entry point `main_fastapi.py`, JWT auth baked in
* `frontend/src/`: React app — `components/`, `context/` (AuthContext, ThemeContext), `hooks/` (React Query wrappers), `services/` (ApiClient + WebSocketService), `types/`, `utils/`
* `pipeline/kafka-producer/`: Scala Kafka producer — reads CSV, emits JSON transaction events with 1–3s simulated delay
* `pipeline/spark_jobs/`: PySpark batch + streaming jobs — `streaming/` holds the live scoring pipeline; `batch/` holds DB import utilities
* `ml/models/`: Serialized production Spark ML artifacts — `PreprocessingModel/` (pipeline) and `RandomForestModel/` (classifier). Loaded at Spark job startup.
* `ml/training/`: Training scripts for all model variants (Random Forest, GBM, LR, SVM, Naive Bayes, Isolation Forest, Neural Network)
* `data/`: Raw CSV source data for Kafka producer and batch imports
* `scripts/windows/`: Batch files to launch Spark training (`run_spark_training.bat`) and streaming (`run_spark_streaming.bat`)
* `docs/`: Project documentation, methodology, architecture guides, and reference diagrams (`docs/diagrams/`)
* `config/`: Supplementary configuration files (`postgresql_schema.sql` is the authoritative schema)
* `cape/`: **CAPE — Confidence-Aware Progressive Escalation** architecture (9-layer fraud scoring engine). Self-contained Python module.
* `tests/`: Unit and integration tests — `test_cape.py` (88 tests, all passing).

---

## 4. Key Business Logic / Workflows

### 4.1 Real-Time Transaction Ingestion & Scoring

1. **Kafka ingest:** Scala producer reads `data/transactions_producer.csv`, serializes each row as JSON, publishes to topic `creditcardTransaction` with 1–3s simulated delay per record
2. **Spark consumption:** Structured Streaming job reads from Kafka (5-second micro-batch trigger: `.trigger(processingTime='5 seconds')`), parses JSON to DataFrame via declared `StructType` schema
3. **Customer enrichment:** Broadcast-join with `customer` table on `cc_num`; compute `age` (year diff from `dob`) and `distance` (Haversine UDF between customer lat/long and merchant lat/long); `repartition(col("cc_num"))` applied before all window operations
4. **Temporal feature extraction:**
   ```python
   batch_df = batch_df
       .withColumn("hour",       hour(col("trans_time")))
       .withColumn("dayofweek",  dayofweek(col("trans_time")))
       .withColumn("is_weekend", when(dayofweek(...).isin(1, 7), 1).otherwise(0))
   ```
5. **Velocity feature extraction (ML + Rule Engine):**
   * 1-hour window (ML features): `Window.partitionBy("cc_num").orderBy(trans_time.cast("long")).rangeBetween(-3600, 0)` → `tx_count_1h`, `tx_amt_1h`
   * 10-minute window (rule engine only, not in `VectorAssembler`): `rangeBetween(-600, 0)` → `tx_count_10min`
6. **Feature selection:** `feature_df` assembles the 11 ML columns + pass-through columns (`trans_num`, `trans_time`, `merch_lat`, `merch_long`, `tx_count_10min`)
7. **Preprocessing pipeline:** `preprocessing_model.transform(feature_df).cache()` — `StringIndexer` → `OneHotEncoder` → `VectorAssembler` over the 11-feature vector
8. **Parallel ML scoring:**
   ```python
   with ThreadPoolExecutor() as ex:
       rf_future     = ex.submit(rf_model.transform, preprocessed_df)
       predictions_df = rf_future.result()
   preprocessed_df.unpersist()
   ```
9. **Adaptive threshold classification:** `fraud_score = probability[1]`; threshold looked up from `_threshold_map` (a Spark `create_map` Column) keyed by `category`, defaulting to `0.40`:

   | Category | Threshold |
   |---|---|
   | `online_gift_card` | 0.20 |
   | `misc_net`, `online_shopping` | 0.25 |
   | `travel` | 0.30 |
   | `grocery_pos`, `gas_transport` | 0.45 |
   | *(all others)* | 0.40 |

10. **Deterministic Rule Engine** (see §4.3) applied after ML classification
11. **DB write:** `fraud_transaction` / `non_fraud_transaction` via `INSERT … ON CONFLICT (cc_num, trans_time) DO NOTHING` (Structured Streaming: `psycopg2.extras.execute_values`; DStreams: Spark JDBC)

---

### 4.2 Live Dashboard Update (Postgres pub/sub — zero polling)

1. Every `INSERT` into `fraud_transaction` fires `fraud_notify_trigger` (`AFTER INSERT FOR EACH ROW`)
2. Trigger calls `notify_fraud_insert()` which executes `pg_notify('fraud_channel', row_to_json(NEW)::text)`
3. FastAPI background coroutine `monitor_fraud_transactions()` holds a dedicated `psycopg2` connection in `ISOLATION_LEVEL_AUTOCOMMIT` mode with `LISTEN fraud_channel` issued at startup
4. The coroutine blocks on `select.select([conn], [], [], 5)` offloaded to a thread executor — unblocks the asyncio event loop; the 5s timeout serves as a heartbeat only, **not** a poll interval
5. On wake: `conn.poll()` drains `conn.notifies`; each notification payload is `json.loads`-ed and immediately `manager.broadcast()`-ed to all connected WebSocket clients as `{type: "fraud_alert", data: {...}}`
6. Browser `wsService` receives message, fires registered `fraud_alert` callbacks; React Query independently polls `/api/fraud/alerts` (3s) and `/api/dashboard/metrics` (5s) for resilience

**Key distinction:** fraud alert delivery latency ≈ Postgres insert time (~0ms notification overhead), not 5s polling interval. The old `SELECT … WHERE created_at > last_check_time` loop has been fully removed.

---

### 4.3 Deterministic Rule Engine

Applied in `write_to_postgres_foreach_batch` (Structured Streaming) and `process_rdd` (DStreams) **after** adaptive ML threshold, **before** DB write. Implemented entirely with native PySpark `when()` chains — no Python UDFs, no `.map()`, fully Catalyst-optimized.

**State acquisition — `avg_amt_30d` broadcast join:**
* Per micro-batch, JDBC-reads `customer_stats(cc_num, avg_amt_30d)` table and joins with `broadcast()` hint
* `customer_stats` is maintained by a periodic external batch job (nightly/hourly refresh via `REFRESH MATERIALIZED VIEW` or equivalent); the streaming job itself does not write to it
* Wrapped in `try/except`: if table is empty or unreachable, `avg_amt_30d` defaults to `null` (the Amount Spike rule is skipped gracefully via `.isNotNull()` guard)
* This strategy was chosen over `flatMapGroupsWithState` to avoid holding 30 days of per-card transaction history in executor memory

**Rule definitions:**

| Rule | Condition | Severity | `rule_flags` value |
|---|---|---|---|
| Impossible Travel | `distance > 500 AND tx_count_10min > 1` | `CRITICAL` | `"IMPOSSIBLE_TRAVEL:CRITICAL"` |
| Amount Spike | `avg_amt_30d IS NOT NULL AND amt > avg_amt_30d * 5` | `HIGH` | `"AMOUNT_SPIKE:HIGH"` |
| High-Risk Merchant | `category IN HIGH_RISK_CATEGORIES AND amt > 1000` | `MEDIUM` | `"HIGH_RISK_MERCHANT:MEDIUM"` |

`HIGH_RISK_CATEGORIES = ["misc_net", "online_shopping", "online_gift_card", "shopping_net", "shopping_pos", "home"]`

**Severity precedence:** `CRITICAL` > `HIGH` > `MEDIUM` > `NONE` (resolved by chained `when()`)

**`rule_flags` serialization:** null-safe JSON array string built with `concat(lit("["), concat_ws(",", when(...), when(...), when(...)), lit("]"))` — `concat_ws` natively skips `null` columns, producing valid `[]` when no rules fire

**Final `is_fraud` override:**
```python
.withColumn("is_fraud",
    when((col("is_fraud") == 1.0) | (col("rule_severity") == "CRITICAL"), 1.0)
    .otherwise(0.0))
```
A transaction flagged `CRITICAL` by the Rule Engine is always written to `fraud_transaction`, even if the ML score is below threshold.

**Output columns added to `final_df`:** `rule_flags TEXT`, `rule_severity VARCHAR(10)`

---

### 4.4 ML Training: Feature Parity & Class Weights

Training script: `ml/training/spark_fraud_detection_training.py`

**Feature parity constraint:** the training feature vector must exactly match the inference feature vector. Violations cause silent model degradation at inference time.

* `read_cols = base_feature_cols + ["is_fraud", "trans_time", "trans_num"]` — `trans_time` and `trans_num` read from Postgres for temporal/velocity computation; dropped from `VectorAssembler` input
* Enrichment applied on **combined** fraud + non-fraud DataFrame before pipeline fitting:
  * Temporal: `hour`, `dayofweek`, `is_weekend` derived from `trans_time`
  * Velocity: `Window.partitionBy("cc_num").orderBy(trans_time.cast("long")).rangeBetween(-3600, 0)` → `tx_count_1h`, `tx_amt_1h`
  * `repartition(col("cc_num"))` precedes all window operations to prevent OOM on large training sets
* Final `feature_cols` (11 features — must match `feature_cols` in streaming scripts exactly):
  `["cc_num", "category", "merchant", "distance", "amt", "age", "hour", "dayofweek", "is_weekend", "tx_count_1h", "tx_amt_1h"]`
* **`tx_count_10min` is NOT included in training** — it is a rule-engine-only feature computed at inference time

**Class weights (inverse-frequency):**
```python
w_fraud = total / (2.0 * fraud_n)
w_legit = total / (2.0 * legit_n)
train_df = train_df.withColumn("classWeight",
    when(col("label") == 1.0, w_fraud).otherwise(w_legit))
```
Passed to classifier via `weightCol="classWeight"` — replaces the previous undersampling-only approach which suppressed recall on the minority (fraud) class.

**RandomForestClassifier config:** `numTrees=100`, `maxDepth=10`, `maxBins=700`, `weightCol="classWeight"`, `seed=42`

**Model retrain requirement:** whenever the feature vector changes (columns added/removed/reordered), both `PreprocessingModel` and `RandomForestModel` must be retrained and the serialized artifacts at `~/frauddetection/ml/models/` replaced before restarting the streaming job.

---

### 4.5 Analyst Authentication

1. `POST /auth/login` with `{username, password}` — server validates against bcrypt hash of `.env` credentials
2. On success, server sets `access_token` as `httpOnly, SameSite=Lax` cookie (8h TTL)
3. All subsequent requests auto-attach cookie; backend `get_current_user()` dependency decodes JWT and gates every protected endpoint
4. `GET /auth/me` on page load restores session without re-login; `POST /auth/logout` deletes cookie

---

### 4.6 Customer & Statement Lookup

1. Analyst enters a card number in the dashboard search
2. `GET /api/customer/{cc_num}` returns masked card number (`**** **** **** {last4}`), name, age, job, address
3. `GET /api/statement/{cc_num}?limit=100` returns UNION of `fraud_transaction` + `non_fraud_transaction` for that card, ordered by `trans_time DESC`

---

## 5. Datasets Used

This repository contains multiple datasets under `data/`. Only a subset is required for the **running application pipeline** (Kafka → Spark → Postgres → FastAPI → Dashboard). The rest are **training/research datasets** used by offline model training scripts.

### 5.1 Runtime / Application Pipeline Datasets (Required)

* **Customer master dataset:** `data/customer.csv`
  * **Used by**: initial DB import job (loads into Postgres table `customer`), and then Spark streaming joins `customer` on `cc_num`.
  * **Columns required (import schema)**: `cc_num, first, last, gender, street, city, state, zip, lat, long, job, dob`
  * **Code evidence**: `pipeline/spark_jobs/batch/spark_import_to_postgres.py` (customer schema + import), `pipeline/spark_jobs/streaming/spark_structured_streaming.py` (join columns `cc_num, lat, long, dob`).

* **Transaction history dataset:** `data/transactions.csv`
  * **Used by**: initial DB import job (splits into `fraud_transaction` and `non_fraud_transaction`), and also used by training scripts.
  * **Columns required (import schema)**:
    `cc_num, first, last, trans_num, trans_date, trans_time, unix_time, category, merchant, amt, merch_lat, merch_long, is_fraud`
  * **Code evidence**: `pipeline/spark_jobs/batch/spark_import_to_postgres.py` (`import_transactions()` schema + timestamp parsing), `ml/training/Random Forest/fraud_detection_rf.py`, `ml/training/cape/train_cape_models.py`.

* **Kafka producer input dataset (streaming demo):** `data/transactions_producer.csv`
  * **Used by**: Kafka producer "transaction replay" to publish events into topic `creditcardTransaction` for the Spark streaming job.
  * **Expected schema**: aligns with the Spark streaming Kafka JSON schema (`cc_num, first, last, trans_num, trans_date, trans_time, unix_time, category, merchant, amt, merch_lat, merch_long`) plus `is_fraud` if you reuse the merged dataset.
  * **Code evidence**: `scripts/step1_merge_sparkov.py` (overwrites `transactions_producer.csv` after merge), `pipeline/spark_jobs/streaming/spark_structured_streaming.py` (Kafka message schema), `pipeline/kafka-producer/src/main/resources/application-local.conf` (producer.file config—see note below).

  **Note:** The Scala producer's bundled config points to `src/main/resources/transactions.csv` inside the producer module. In this repo, the active "data folder" producer input is `data/transactions_producer.csv`, and you may need to copy/point the producer config to that file depending on how you run the producer.

### 5.2 Offline Training / Research Datasets (Optional)

These datasets exist under `data/` and are used by feature engineering experiments or training scripts; they are not required to run the live pipeline:

* **Sparkov synthetic credit card dataset**:
  `data/synthetic-credit-card-transactions-fraud-detection-dataset/fraudTrain.csv`, `fraudTest.csv`
  * Used by `scripts/step1_merge_sparkov.py` to build `transactions_merged.csv` and refresh `transactions_producer.csv`.

* **Credit Card Fraud Detection (classic)**: `data/credit-card-fraud-detection/creditcard.csv`
* **IEEE fraud detection**: `data/ieee-fraud-detection/*`
* **Synthetic financial datasets**: `data/synthetic-financial-datasets-for-fraud-detection/*`
* **E-commerce fraud datasets**: `data/fraud-ecommerce/*`

If you want a clean "minimal data pack" for running the app, the smallest set is:
`data/customer.csv` + `data/transactions.csv` + `data/transactions_producer.csv`.

---

## 6. Developer & AI Agent Onboarding

* **Environment Setup:**

  Required `.env` variables (create at `backend/.env`). These are consumed by the FastAPI server and Spark jobs via `python-dotenv`:
  ```
  DB_HOST=localhost
  DB_PORT=5432
  DB_NAME=fraud_detection
  DB_USER=postgres
  DB_PASSWORD=<your_password>
  # Spark ↔ Postgres JDBC
  POSTGRES_JDBC_JAR=C:\spark\jars\postgresql-42.7.1.jar
  KAFKA_BOOTSTRAP_SERVERS=localhost:9092
  KAFKA_TOPIC=creditcardTransaction
  SPARK_MASTER=local[*]
  JWT_SECRET_KEY=<min-32-char-random-string>
  JWT_ALGORITHM=HS256
  JWT_EXPIRE_MINUTES=480
  ADMIN_USERNAME=admin
  ADMIN_PASSWORD=<your_password>

  # Frontend (Vite) — optional overrides
  VITE_API_BASE_URL=http://localhost:8000
  VITE_WEBSOCKET_URL=ws://localhost:8000

  # Optional: referenced by Vite config (usage in app code may vary)
  GEMINI_API_KEY=<optional>
  ```

  Run order:
  ```bash
  # 1. Backend
  cd backend && pip install -r requirements.txt
  uvicorn main_fastapi:app --reload --port 8000

  # 2. Frontend
  cd frontend && npm install
  npm run dev   # http://localhost:3000 (Vite is configured to use port 3000)

  # 3. Pipeline (requires Kafka + Spark running locally)
  scripts\windows\run_spark_training.bat    # one-time — trains and saves models to ml/models/
  scripts\windows\run_spark_streaming.bat   # continuous — starts real-time scoring
  ```

  **Windows note (paths):** `scripts/windows/*.bat` currently contain hard-coded paths like `E:\Project\DataPulse\...`. Update `PROJECT_DIR` / venv path in those scripts to match your local repo location before running.

* **Strict Conventions:**
  * **Auth:** Never store JWT in `localStorage`/`sessionStorage`. Cookie is set server-side only. All fetch calls must pass `{ credentials: 'include' }`.
  * **DB access:** Never open a raw `psycopg2` connection outside the `get_db()` context manager in `main_fastapi.py` — connections must return to the `ThreadedConnectionPool`. The single exception is the dedicated `LISTEN` connection in `monitor_fraud_transactions()`, which must remain outside the pool and in `ISOLATION_LEVEL_AUTOCOMMIT` mode.
  * **Sync endpoints:** FastAPI endpoints that touch PostgreSQL must be `def` (not `async def`) — FastAPI runs them in a thread pool, which is correct for blocking psycopg2 I/O.
  * **Model paths:** ML model artifacts live at `ml/models/PreprocessingModel` and `ml/models/RandomForestModel` relative to `project_home` (`~/frauddetection`). Overridable via `MODEL_PATH` and `PREPROCESSING_MODEL_PATH` env vars.
  * **Feature vector contract:** The 11-column `feature_cols` list in `spark_structured_streaming.py` / `spark_dstream_fraud_detection.py` and in `spark_fraud_detection_training.py` must stay identical at all times. Changing one without retraining and updating the others causes silent inference errors.
  * **`tx_count_10min` is rule-engine-only:** It must never be added to `feature_cols` or passed to `VectorAssembler`. It is carried as a pass-through column in `feature_df.select()` exclusively for the Rule Engine `r_travel` condition.
  * **`customer_stats` maintenance:** The `avg_amt_30d` column is not updated by the streaming job. It must be refreshed by an external periodic process (scheduled batch job or materialized view refresh). If the table is empty, the Amount Spike rule degrades gracefully (condition skipped via `.isNotNull()` guard).
  * **Duplicate prevention:** Spark streaming uses `INSERT … ON CONFLICT (cc_num, trans_time) DO NOTHING`. Do not change this to upsert — transaction records are immutable.
  * **No polling in FastAPI monitor:** `monitor_fraud_transactions()` uses `LISTEN/NOTIFY` exclusively. Do not reintroduce `asyncio.sleep` polling or `SELECT … WHERE created_at > last_check_time` queries — the pub/sub path is the sole notification mechanism.
  * **React Query polling:** `staleTime` is 4s globally. Do not set polling intervals below 3s (alerts) or 5s (metrics) to avoid DB overload.
  * **Type safety:** All API response shapes are defined in `frontend/src/types/index.ts`. Backend Pydantic models must stay in sync with these frontend types.
  * **No Flask:** `backend/main.py` (Flask) has been removed. All routes live in `main_fastapi.py` on port 8000.
  * **Dependency versions:** `bcrypt` must stay on `4.x` — `passlib 1.7.4` is incompatible with `bcrypt 5.x`.

* **Deployment note (current repo state):**
  * There are no Docker/Kubernetes/CI pipeline manifests in this repository at present. The supported run path is host-based (direct `uvicorn`, `npm run dev`, and `spark-submit` via scripts).

---

## 7. CAPE — Confidence-Aware Progressive Escalation

A 9-layer fraud scoring engine that treats **model uncertainty as a primary signal**. Implemented in `cape/` as a pure-Python module decoupled from the Spark/Kafka pipeline. The two systems coexist: Spark pipeline does live ingestion and basic RF scoring; CAPE provides deeper probabilistic scoring and explainability.

### Layer Summary

| Layer | File | What it does |
|---|---|---|
| L0 — Feature Store | `layer0_feature_store.py` | Versioned pre-computed + on-the-fly features. Welford online baseline per user. Redis-ready (dict fallback). |
| L1 — Cold-Start Router | `layer1_cold_start_router.py` | New users (<20 txns) or new merchants (<7 days) bypass fast gate; get tighter thresholds (block=0.40, review=0.20). |
| L2 — Fast Gate | `layer2_fast_gate.py` | Welford N=2.5 stdev check + Count-Min Sketch velocity (1m/10m/1h) + invisible device signals. ~70–75% of traffic exits here as APPROVE. |
| L3 — Parallel Scorers | `layer3_parallel_scorers.py` | RF + GBT (LightGBM) + EWMA recency scorer; output is a probability vector, not a collapsed score. |
| L4 — Conformal Prediction | `layer4_conformal.py` | Online split conformal prediction wrapper. Produces interval `[lower, upper]` at 95% confidence. Wide interval = novel fraud signal. Rolling calibration window (N=1000) recalibrates continuously. |
| L5 — Drift Detection | `layer5_drift_detection.py` | CUSUM (fast, ~50 txns) + PSI (slow, 1k–5k txns). Threshold formula: `adjusted = base − (magnitude × 0.15)`, floored at 0.10. PSI alert triggers automated retrain request. |
| L6 — Routing | `layer6_routing.py` | BLOCK / APPROVE / NOVEL-FLAG. Channel-aware action map for NOVEL-FLAG (Web→OTP, POS→soft decline, ATM→hard hold, Recurring→manual review, B2B→analyst queue). |
| L7 — Explainability | `layer7_explainability.py` | SHAP TreeExplainer on GBT scorer. Top-3 features → human-readable reason codes. Zero overhead on fast-gate-approved transactions. |
| L8 — Feedback Loop | `layer8_feedback.py` | Chargeback→fraud label, step-up cleared→legit label. Analyst queue (4h/24h SLA). Uncertain analyst labels excluded from retrain data. Shadow scoring + blue-green rollout (10%→25%→50%→100%). |
| Orchestrator | `pipeline.py` | `CAPEPipeline.evaluate(txn)` wires all layers in correct order. |

### Key Design Decisions
* **Feature array:** 19 features (including `graph_distinct_accounts_1hr`) — order defined in `layer3_parallel_scorers.FEATURE_ORDER`. Must stay consistent across training and inference.
* **Graph bootstrap:** Graph features zero'd for `deployment_day < 30`. Enable via `pipeline.enable_graph_features()`.
* **Conformal warm-up:** Initial quantile = 0.25 → all non-fast-pass decisions are NOVEL_FLAG until ≥10 calibration samples arrive. This is intentional conservative behavior.
* **Welford baseline:** zscore=0 when std=0 (uniform baseline). The gate escalates at N=2.5 stdev — a perfectly uniform baseline passes any amount. Use varied training data.

### Running CAPE
```bash
# Install dependencies (all requirements consolidated at project root)
pip install -r requirements.txt

# Smoke test (no external deps)
python tests/smoke_test.py

# Unit tests
python -m pytest tests/test_cape.py -v    # 88 tests
```

### Integrating CAPE into the FastAPI backend
```python
from cape import CAPEPipeline, Transaction, Channel

pipeline = CAPEPipeline(deployment_day=0)

# In a FastAPI endpoint or Spark streaming foreachBatch:
decision = pipeline.evaluate(Transaction(
    trans_num=row["trans_num"],
    cc_num=str(row["cc_num"]),
    amt=float(row["amt"]),
    merchant=row["merchant"],
    category=row["category"],
    channel=Channel.WEB,
))
# decision.decision → RoutingDecision.BLOCK / APPROVE / NOVEL_FLAG
# decision.reason_codes → ["Transaction amount...", ...]
# decision.channel_action → "step_up_auth_otp"
```

---

## 8. Real-Time Fraud Pipeline — End-to-End Flow

### 8.1 Pipeline Sequence

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  STAGE                        │  COMPONENT                  │  LATENCY     │
├─────────────────────────────────────────────────────────────────────────────┤
│  1. Transaction published      │  Scala Kafka producer        │  1–3s        │
│  2. Spark micro-batch fires    │  .trigger(processingTime=   │  0–5s        │
│                                │    '5 seconds')             │              │
│  3. JSON parse + enrichment    │  from_json / broadcast join  │  <1s         │
│  4. Temporal feature extract   │  hour / dayofweek /          │  <1s         │
│                                │  is_weekend                 │              │
│  5. Velocity feature extract   │  Window.rangeBetween        │  <1s         │
│                                │  (-3600,0) and (-600,0)     │              │
│  6. ML preprocessing           │  PreprocessingModel.cache() │  <1s         │
│  7. Parallel RF scoring        │  ThreadPoolExecutor +        │  <1s         │
│                                │  rf_model.transform()       │              │
│  8. Adaptive threshold         │  probability[1] vs          │  <1s         │
│                                │  per-category map           │              │
│  9. Deterministic Rule Engine  │  when() chains + broadcast  │  <1s         │
│                                │  join customer_stats        │              │
│  10. Postgres INSERT           │  execute_values / JDBC       │  <1s         │
│  11. AFTER INSERT trigger      │  fraud_notify_trigger →     │  ~0ms        │
│                                │  pg_notify('fraud_channel') │              │
│  12. FastAPI LISTEN wakes      │  select.select + conn.poll  │  ~0ms        │
│  13. WebSocket broadcast       │  manager.broadcast()        │  ~0ms        │
│  14. Browser alert rendered    │  React wsService callback   │  ~0ms        │
├─────────────────────────────────────────────────────────────────────────────┤
│  TOTAL END-TO-END                                             │  ≤13s        │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 8.2 Database Schema — Rule Engine Additions

| Object | Type | Purpose |
|---|---|---|
| `customer_stats` | Table | `cc_num PK`, `avg_amt_30d NUMERIC(10,2)`, `updated_at TIMESTAMP` — source for Amount Spike rule; refreshed externally |
| `fraud_transaction.rule_flags` | `TEXT DEFAULT '[]'` | JSON array string of fired rule identifiers e.g. `["IMPOSSIBLE_TRAVEL:CRITICAL"]` |
| `fraud_transaction.rule_severity` | `VARCHAR(10) DEFAULT 'NONE'` | Highest severity among fired rules: `CRITICAL` / `HIGH` / `MEDIUM` / `NONE` |
| `non_fraud_transaction.rule_flags` | `TEXT DEFAULT '[]'` | Same — non-fraud rows carry rule output for auditability |
| `non_fraud_transaction.rule_severity` | `VARCHAR(10) DEFAULT 'NONE'` | Same |
| `notify_fraud_insert()` | plpgsql function | Fires `pg_notify('fraud_channel', row_to_json(NEW)::text)` on every fraud insert |
| `fraud_notify_trigger` | `AFTER INSERT ON fraud_transaction FOR EACH ROW` | Invokes `notify_fraud_insert()` |

### 8.3 ML Feature Vector Contract

Both training and inference must use this exact 11-column ordered set as `feature_cols`. Any change requires full model retrain.

| # | Column | Source | Type | Used by |
|---|---|---|---|---|
| 1 | `cc_num` | Kafka JSON | String → StringIndexer + OHE | ML |
| 2 | `category` | Kafka JSON | String → StringIndexer + OHE | ML + Rule Engine |
| 3 | `merchant` | Kafka JSON | String → StringIndexer + OHE | ML |
| 4 | `distance` | Haversine UDF | Double | ML + Rule Engine |
| 5 | `amt` | Kafka JSON | Double | ML + Rule Engine |
| 6 | `age` | Customer join | Integer | ML |
| 7 | `hour` | `hour(trans_time)` | Integer | ML |
| 8 | `dayofweek` | `dayofweek(trans_time)` | Integer | ML |
| 9 | `is_weekend` | `dayofweek.isin(1,7)` | Integer (0/1) | ML |
| 10 | `tx_count_1h` | Window(-3600,0) | Long | ML |
| 11 | `tx_amt_1h` | Window(-3600,0) | Double | ML |
| — | `tx_count_10min` | Window(-600,0) | Long | **Rule Engine only** |
