"""
Python Kafka consumer worker — replaces Apache Spark Structured Streaming.
Reads from Redpanda/Kafka, scores transactions with a sklearn RF, writes
fraud/non-fraud rows to PostgreSQL, and triggers WebSocket broadcasts via
the FastAPI polling mechanism.

Environment variables:
    KAFKA_BOOTSTRAP_SERVERS   Kafka/Redpanda broker URL (default: localhost:9092)
    KAFKA_TOPIC               Topic to consume (default: creditcardTransaction)
    KAFKA_GROUP_ID            Consumer group (default: fraud-detection-worker)
    REDPANDA_USERNAME         SASL username for Redpanda Cloud (optional)
    REDPANDA_PASSWORD         SASL password for Redpanda Cloud (optional)
    DATABASE_URL              Full Postgres connection URL (preferred for cloud)
    DB_HOST/PORT/NAME/USER/PASSWORD  Fallback individual vars for local dev
    MODEL_PATH                Path to sklearn_rf.pkl
    ENCODERS_PATH             Path to label_encoders.pkl

Usage:
    python pipeline/kafka_consumer_worker.py
"""

import json
import math
import os
import pickle
import signal
import sys
import threading
import time
import urllib.parse
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Optional

import numpy as np
import psycopg2
from psycopg2 import pool as pg_pool
from psycopg2.extras import execute_values

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(_ROOT, "backend", ".env"))

# ── Config ────────────────────────────────────────────────────────────────────

BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC       = os.getenv("KAFKA_TOPIC", "creditcardTransaction")
KAFKA_GROUP_ID    = os.getenv("KAFKA_GROUP_ID", "fraud-detection-worker")
REDPANDA_USER     = os.getenv("REDPANDA_USERNAME", "")
REDPANDA_PASS     = os.getenv("REDPANDA_PASSWORD", "")

_DEFAULT_MODEL_PATH    = os.path.join(_ROOT, "ml", "models", "streaming", "sklearn_rf.pkl")
_DEFAULT_ENCODERS_PATH = os.path.join(_ROOT, "ml", "models", "streaming", "label_encoders.pkl")
MODEL_PATH    = os.getenv("MODEL_PATH",    _DEFAULT_MODEL_PATH)
ENCODERS_PATH = os.getenv("ENCODERS_PATH", _DEFAULT_ENCODERS_PATH)

FEATURE_COLS = [
    "cc_num_enc", "category_enc", "merchant_enc",
    "distance", "amt", "age",
    "hour", "dayofweek", "is_weekend",
    "tx_count_1h", "tx_amt_1h",
]

CATEGORY_THRESHOLDS = {
    "misc_net": 0.25, "online_shopping": 0.25, "online_gift_card": 0.20,
    "travel": 0.30, "grocery_pos": 0.45, "gas_transport": 0.45,
}
DEFAULT_THRESHOLD = 0.40

HIGH_RISK_CATEGORIES = {
    "misc_net", "online_shopping", "online_gift_card",
    "shopping_net", "shopping_pos", "home",
}

CUSTOMER_CACHE_TTL   = 300   # seconds
VELOCITY_WINDOW_1H   = 3600
VELOCITY_WINDOW_10M  = 600

_running = True  # set to False by SIGTERM handler


# ── DB helpers ────────────────────────────────────────────────────────────────

def _build_dsn() -> str:
    url = os.getenv("DATABASE_URL")
    if url:
        return url
    user = os.getenv("DB_USER", "postgres")
    pwd  = urllib.parse.quote(os.getenv("DB_PASSWORD", ""), safe="")
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    name = os.getenv("DB_NAME", "fraud_detection")
    return f"postgresql://{user}:{pwd}@{host}:{port}/{name}"


def _make_pool() -> pg_pool.ThreadedConnectionPool:
    dsn = _build_dsn()
    return pg_pool.ThreadedConnectionPool(minconn=1, maxconn=5, dsn=dsn)


# ── Customer cache ────────────────────────────────────────────────────────────

class CustomerCache:
    """
    Per-card cache of customer lat/long/dob/avg_amt_30d with 5-min TTL.
    Prevents a DB round-trip on every message for cards seen recently.
    """

    def __init__(self, pool: pg_pool.ThreadedConnectionPool):
        self._pool = pool
        self._cache: dict = {}
        self._lock  = threading.Lock()

    def get(self, cc_num: str) -> dict:
        with self._lock:
            entry = self._cache.get(cc_num)
            if entry and time.monotonic() - entry["_ts"] < CUSTOMER_CACHE_TTL:
                return entry

        conn = self._pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT lat, long, dob FROM customer WHERE cc_num = %s",
                    (cc_num,),
                )
                cust_row = cur.fetchone()
                cur.execute(
                    "SELECT avg_amt_30d FROM customer_stats WHERE cc_num = %s",
                    (cc_num,),
                )
                stats_row = cur.fetchone()
        finally:
            self._pool.putconn(conn)

        record: dict = {"_ts": time.monotonic()}
        if cust_row:
            dob = cust_row[2]
            record.update({
                "lat":          float(cust_row[0]) if cust_row[0] else 0.0,
                "long":         float(cust_row[1]) if cust_row[1] else 0.0,
                "dob":          dob,
                "avg_amt_30d":  float(stats_row[0]) if stats_row and stats_row[0] else None,
            })
        else:
            record.update({"lat": 0.0, "long": 0.0, "dob": None, "avg_amt_30d": None})

        with self._lock:
            self._cache[cc_num] = record
        return record


# ── Velocity tracker ──────────────────────────────────────────────────────────

class VelocityTracker:
    """
    Per-card sliding-window counters.  Transaction is added to the window
    BEFORE computing velocity to match Spark rangeBetween(-3600, 0).
    """

    def __init__(self):
        self._lock    = threading.Lock()
        self._windows: dict[str, deque] = defaultdict(deque)

    def record(self, cc_num: str, unix_ts: float, amt: float) -> tuple:
        """Returns (tx_count_1h, tx_amt_1h, tx_count_10min)."""
        with self._lock:
            dq = self._windows[cc_num]
            dq.append((unix_ts, amt))

            cutoff_1h = unix_ts - VELOCITY_WINDOW_1H
            while dq and dq[0][0] < cutoff_1h:
                dq.popleft()

            cutoff_10m = unix_ts - VELOCITY_WINDOW_10M
            tx_count_1h  = len(dq)
            tx_amt_1h    = sum(a for _, a in dq)
            tx_count_10m = sum(1 for t, _ in dq if t >= cutoff_10m)
        return tx_count_1h, tx_amt_1h, tx_count_10m


# ── Feature engineering ───────────────────────────────────────────────────────

def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    rlat1, rlon1, rlat2, rlon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat, dlon = rlat2 - rlat1, rlon2 - rlon1
    a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
    return R * 2 * math.asin(math.sqrt(max(0.0, a)))


def _encode(le, value: str) -> int:
    """Encode a label; return 0 for values unseen during training."""
    classes = le.classes_
    idx = np.searchsorted(classes, value)
    if idx < len(classes) and classes[idx] == value:
        return int(idx)
    return 0


def build_features(
    msg: dict,
    customer: dict,
    velocity: tuple,
    encoders: dict,
) -> tuple[np.ndarray, datetime, float]:
    """
    Extract the 11-feature vector.
    Returns (feature_vector, trans_datetime, unix_ts).
    """
    trans_time_str: str = msg["trans_time"]
    dt = datetime.strptime(trans_time_str, "%Y-%m-%d %H:%M:%S")
    unix_ts = dt.replace(tzinfo=timezone.utc).timestamp()

    hour      = dt.hour
    dow       = (dt.isoweekday() % 7) + 1   # Spark: Sun=1 … Sat=7
    is_weekend = 1 if dow in (1, 7) else 0

    cust_lat   = customer.get("lat", 0.0)
    cust_long  = customer.get("long", 0.0)
    merch_lat  = float(msg.get("merch_lat", 0))
    merch_long = float(msg.get("merch_long", 0))
    distance   = _haversine(cust_lat, cust_long, merch_lat, merch_long)

    dob = customer.get("dob")
    if dob:
        if isinstance(dob, str):
            try:
                dob = datetime.strptime(dob[:10], "%Y-%m-%d")
            except ValueError:
                dob = None
    age = int((dt - dob.replace(tzinfo=None)).days / 365.2425) if dob else 30

    tx_count_1h, tx_amt_1h, _ = velocity

    features = np.array([
        _encode(encoders["cc_num"],    str(msg["cc_num"])),
        _encode(encoders["category"],  str(msg.get("category", ""))),
        _encode(encoders["merchant"],  str(msg.get("merchant", ""))),
        distance,
        float(msg["amt"]),
        float(age),
        float(hour),
        float(dow),
        float(is_weekend),
        float(tx_count_1h),
        float(tx_amt_1h),
    ], dtype=np.float64)

    return features, dt, unix_ts


# ── Rule engine ───────────────────────────────────────────────────────────────

def apply_rules(
    msg: dict,
    distance: float,
    tx_count_10m: int,
    avg_amt_30d: Optional[float],
) -> tuple[list, str]:
    """Returns (rule_flags, rule_severity). CRITICAL overrides is_fraud to 1.0."""
    flags: list[str] = []
    severity = "NONE"

    # IMPOSSIBLE_TRAVEL
    if distance > 500 and tx_count_10m > 1:
        flags.append("IMPOSSIBLE_TRAVEL")
        severity = "CRITICAL"

    # AMOUNT_SPIKE
    if avg_amt_30d is not None and float(msg["amt"]) > avg_amt_30d * 5:
        flags.append("AMOUNT_SPIKE")
        if severity not in ("CRITICAL",):
            severity = "HIGH"

    # HIGH_RISK_MERCHANT
    category = str(msg.get("category", ""))
    if category in HIGH_RISK_CATEGORIES and float(msg["amt"]) > 1000:
        flags.append("HIGH_RISK_MERCHANT")
        if severity == "NONE":
            severity = "MEDIUM"

    return flags, severity


# ── DB write ──────────────────────────────────────────────────────────────────

_INSERT_SQL = """
    INSERT INTO {table} (
        cc_num, trans_time, trans_num, category, merchant,
        amt, merch_lat, merch_long, distance, age, is_fraud,
        rule_flags, rule_severity, created_at
    ) VALUES %s
    ON CONFLICT (cc_num, trans_time) DO NOTHING
"""


def write_transaction(pool: pg_pool.ThreadedConnectionPool, row: tuple, table: str) -> None:
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            execute_values(cur, _INSERT_SQL.format(table=table), [row])
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


# ── Kafka consumer ────────────────────────────────────────────────────────────

def _build_consumer_config() -> dict:
    cfg = {
        "bootstrap.servers": BOOTSTRAP_SERVERS,
        "group.id":           KAFKA_GROUP_ID,
        "auto.offset.reset":  "latest",
        "enable.auto.commit": True,
    }
    if REDPANDA_USER and REDPANDA_PASS:
        cfg.update({
            "security.protocol":        "SASL_SSL",
            "sasl.mechanism":           "SCRAM-SHA-256",
            "sasl.username":            REDPANDA_USER,
            "sasl.password":            REDPANDA_PASS,
        })
    return cfg


def _signal_handler(sig, frame):  # noqa: ANN001
    global _running
    print(f"\n[worker] Received signal {sig}. Shutting down gracefully...")
    _running = False


def run() -> None:
    try:
        from confluent_kafka import Consumer, KafkaError
    except ImportError:
        sys.exit(
            "confluent-kafka is not installed. Run: pip install confluent-kafka>=2.3.0"
        )

    if not os.path.exists(MODEL_PATH):
        sys.exit(
            f"Model not found at {MODEL_PATH}.\n"
            "Run: python pipeline/train_streaming_model.py"
        )

    print("[worker] Loading model and encoders...")
    with open(MODEL_PATH, "rb") as f:
        model = pickle.load(f)
    with open(ENCODERS_PATH, "rb") as f:
        encoders = pickle.load(f)

    print("[worker] Connecting to database...")
    pool = _make_pool()

    cache    = CustomerCache(pool)
    velocity = VelocityTracker()

    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT,  _signal_handler)

    consumer = Consumer(_build_consumer_config())
    consumer.subscribe([KAFKA_TOPIC])

    print(f"[worker] Subscribed to '{KAFKA_TOPIC}' on {BOOTSTRAP_SERVERS}")
    print("[worker] Press Ctrl+C to stop.\n")

    backoff = 1

    while _running:
        msg = consumer.poll(timeout=1.0)
        if msg is None:
            continue
        if msg.error():
            from confluent_kafka import KafkaError as _KE
            if msg.error().code() == _KE.PARTITION_EOF:
                continue
            print(f"[worker] Kafka error: {msg.error()}")
            time.sleep(min(backoff, 30))
            backoff = min(backoff * 2, 30)
            continue

        backoff = 1
        raw = msg.value()
        if raw is None:
            continue

        try:
            payload = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            print(f"[worker] Malformed message skipped: {e}")
            continue

        try:
            cc_num = str(payload.get("cc_num", ""))
            customer = cache.get(cc_num)

            feat_vec, trans_dt, unix_ts = build_features(
                payload, customer, (0, 0.0, 0), encoders
            )
            vel = velocity.record(cc_num, unix_ts, float(payload["amt"]))
            # Re-build with actual velocity
            feat_vec, trans_dt, unix_ts = build_features(payload, customer, vel, encoders)

            fraud_prob = float(model.predict_proba(feat_vec.reshape(1, -1))[0, 1])
            category   = str(payload.get("category", ""))
            threshold  = CATEGORY_THRESHOLDS.get(category, DEFAULT_THRESHOLD)

            # Extract for rule engine
            distance = float(feat_vec[3])
            _, tx_count_10m = vel[0], vel[2]
            flags, severity = apply_rules(
                payload, distance, tx_count_10m, customer.get("avg_amt_30d")
            )

            is_fraud = 1.0 if (severity == "CRITICAL" or fraud_prob >= threshold) else 0.0
            table    = "fraud_transaction" if is_fraud == 1.0 else "non_fraud_transaction"

            age = int(feat_vec[5])
            row = (
                cc_num,
                trans_dt,
                str(payload.get("trans_num", "")),
                category,
                str(payload.get("merchant", "")),
                float(payload["amt"]),
                float(payload.get("merch_lat", 0)),
                float(payload.get("merch_long", 0)),
                distance,
                age,
                is_fraud,
                json.dumps(flags),
                severity,
                datetime.utcnow(),
            )

            write_transaction(pool, row, table)
            print(
                f"[worker] {table[:5].upper()} | cc=…{cc_num[-4:]} "
                f"amt={payload['amt']:.2f} prob={fraud_prob:.3f} "
                f"sev={severity}"
            )

        except Exception as e:
            print(f"[worker] Processing error for message: {e}")
            time.sleep(0.5)

    consumer.close()
    pool.closeall()
    print("[worker] Shutdown complete.")


if __name__ == "__main__":
    run()
