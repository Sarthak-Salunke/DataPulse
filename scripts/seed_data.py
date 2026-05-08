"""
Seed the fraud_detection PostgreSQL database with sample data for manual E2E testing.

Reads data/transactions_producer.csv, re-timestamps every row to today's date
(preserving original times), then bulk-inserts into fraud_transaction,
non_fraud_transaction, and customer tables.

Usage (from project root):
    python scripts/seed_data.py

Requires backend/.env to be configured with valid DB credentials.
"""

import os
import sys
import csv
import random
from datetime import date, datetime, time
from pathlib import Path

# ── Locate project root and load .env ─────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

env_path = PROJECT_ROOT / "backend" / ".env"
if env_path.exists():
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=env_path)

import psycopg2
from psycopg2.extras import execute_values

DB_CONFIG = {
    "host":     os.getenv("DB_HOST", "localhost"),
    "port":     os.getenv("DB_PORT", "5432"),
    "database": os.getenv("DB_NAME", "fraud_detection"),
    "user":     os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "12345"),
}

CSV_PATH = PROJECT_ROOT / "data" / "transactions_producer.csv"
MAX_ROWS = 300  # rows to seed (split ~90% non-fraud / ~10% fraud)
TODAY = date.today()


def parse_time(t_str: str) -> time:
    """Parse HH:MM:SS string into a time object."""
    parts = t_str.strip().split(":")
    return time(int(parts[0]), int(parts[1]), int(parts[2]))


def make_timestamp(trans_time_str: str, offset_seconds: int = 0) -> datetime:
    """Combine today's date with the original transaction time."""
    t = parse_time(trans_time_str)
    dt = datetime.combine(TODAY, t)
    if offset_seconds:
        from datetime import timedelta
        dt += timedelta(seconds=offset_seconds)
    return dt


def seed():
    csv_path = CSV_PATH
    if not csv_path.exists():
        sys.exit(f"ERROR: CSV not found at {csv_path}")

    print(f"Reading {csv_path} ...")
    rows = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
            if len(rows) >= MAX_ROWS:
                break

    print(f"  Loaded {len(rows)} rows from CSV.")

    # ── Build customer dedup set ───────────────────────────────────────────────
    customers_seen: set = set()
    customer_rows = []
    for r in rows:
        cc = r["cc_num"].strip()
        if cc not in customers_seen:
            customers_seen.add(cc)
            customer_rows.append((
                cc,
                r.get("first", ""),
                r.get("last", ""),
                "M",            # gender placeholder (not in CSV)
                "123 Main St",  # street placeholder
                "Unknown",      # city placeholder
                "XX",           # state placeholder
                "00000",        # zip placeholder
                float(r["merch_lat"]) if r.get("merch_lat") else None,
                float(r["merch_long"]) if r.get("merch_long") else None,
                "Unknown",      # job placeholder
                datetime(1985, 1, 1),  # dob placeholder
            ))

    # ── Split into fraud / non-fraud ──────────────────────────────────────────
    fraud_rows = []
    non_fraud_rows = []

    # Track (cc_num, timestamp) to avoid PK collisions
    used_pks: set = set()

    for i, r in enumerate(rows):
        cc = r["cc_num"].strip()
        is_fraud = int(r.get("is_fraud", 0))

        # Build a unique timestamp — offset by 1s if collision
        base_ts = make_timestamp(r["trans_time"])
        ts = base_ts
        offset = 0
        while (cc, ts) in used_pks:
            offset += 1
            ts = make_timestamp(r["trans_time"], offset_seconds=offset)
        used_pks.add((cc, ts))

        amt = float(r.get("amt", 0))
        distance = round(random.uniform(0, 250), 2)
        age = random.randint(18, 80)

        row_tuple = (
            cc,
            ts,
            r.get("trans_num", f"SEED-{i}"),
            r.get("category", ""),
            r.get("merchant", ""),
            amt,
            float(r["merch_lat"]) if r.get("merch_lat") else None,
            float(r["merch_long"]) if r.get("merch_long") else None,
            distance,
            age,
            float(is_fraud),
        )

        if is_fraud == 1:
            fraud_rows.append(row_tuple)
        else:
            non_fraud_rows.append(row_tuple)

    # Ensure at least 10 fraud rows so the alerts panel has something to show
    if len(fraud_rows) < 10:
        print(f"  Only {len(fraud_rows)} fraud rows found — promoting 10 non-fraud rows to fraud.")
        promoted = non_fraud_rows[:10]
        non_fraud_rows = non_fraud_rows[10:]
        fraud_rows += [r[:10] + (1.0,) for r in promoted]

    print(f"  Customers : {len(customer_rows)}")
    print(f"  Fraud txns: {len(fraud_rows)}")
    print(f"  Normal txns: {len(non_fraud_rows)}")

    # ── Connect and insert ─────────────────────────────────────────────────────
    print(f"\nConnecting to {DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']} ...")
    try:
        conn = psycopg2.connect(**DB_CONFIG)
    except Exception as e:
        sys.exit(f"ERROR: Could not connect to database: {e}")

    conn.autocommit = False
    cur = conn.cursor()

    TX_COLS = "(cc_num, trans_time, trans_num, category, merchant, amt, merch_lat, merch_long, distance, age, is_fraud)"

    try:
        # Customers
        print("Inserting customers ...")
        execute_values(cur, f"""
            INSERT INTO customer (cc_num, first, last, gender, street, city, state, zip, lat, long, job, dob)
            VALUES %s ON CONFLICT (cc_num) DO NOTHING
        """, customer_rows)

        # Fraud transactions
        print(f"Inserting {len(fraud_rows)} fraud transactions ...")
        execute_values(cur, f"""
            INSERT INTO fraud_transaction {TX_COLS}
            VALUES %s ON CONFLICT DO NOTHING
        """, fraud_rows)

        # Non-fraud transactions
        print(f"Inserting {len(non_fraud_rows)} non-fraud transactions ...")
        execute_values(cur, f"""
            INSERT INTO non_fraud_transaction {TX_COLS}
            VALUES %s ON CONFLICT DO NOTHING
        """, non_fraud_rows)

        conn.commit()
        print("\nSeed complete.")
        print(f"  {len(fraud_rows)} fraud rows  |  {len(non_fraud_rows)} non-fraud rows  |  {len(customer_rows)} customers")
        print("  Dashboard metrics and alerts should now show live data.")

    except Exception as e:
        conn.rollback()
        sys.exit(f"ERROR during insert (rolled back): {e}")
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    seed()
