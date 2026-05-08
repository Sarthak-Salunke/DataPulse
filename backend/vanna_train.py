"""
One-time Vanna training script.

Run ONCE before starting the FastAPI server, and re-run whenever the schema
or business rules change. Training data is stored in Postgres via pgvector.

Usage (from the backend/ directory):
    python vanna_train.py
"""

import os
import sys

from dotenv import load_dotenv

# Allow running from the backend/ directory or the project root.
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

from chatbot import FraudVanna  # noqa: E402  (import after load_dotenv)


def main() -> None:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        sys.exit("Error: GEMINI_API_KEY is not set. Add it to backend/.env first.")

    readonly_user = os.getenv("DB_READONLY_USER")
    readonly_password = os.getenv("DB_READONLY_PASSWORD")
    if not readonly_user or not readonly_password:
        sys.exit(
            "Error: DB_READONLY_USER and DB_READONLY_PASSWORD must be set in backend/.env."
        )

    import urllib.parse
    db_url = os.getenv("DATABASE_URL") or (
        f"postgresql://{urllib.parse.quote(readonly_user, safe='')}:"
        f"{urllib.parse.quote(readonly_password, safe='')}@"
        f"{os.getenv('DB_HOST', 'localhost')}:{os.getenv('DB_PORT', '5432')}/"
        f"{os.getenv('DB_NAME', 'fraud_detection')}"
    )

    vn = FraudVanna(config={
        "api_key":           api_key,
        "model":             "gemini-1.5-flash",
        "connection_string": db_url,
    })
    vn.connect_to_postgres(
        host=os.getenv("DB_HOST", "localhost"),
        dbname=os.getenv("DB_NAME", "fraud_detection"),
        user=readonly_user,
        password=readonly_password,
    )

    # ── DDL ───────────────────────────────────────────────────────────────────
    print("Training: DDL...")
    vn.train(ddl="""
        CREATE TABLE fraud_transaction (
            cc_num      VARCHAR,
            trans_num   VARCHAR,
            trans_time  TIMESTAMP,
            amt         FLOAT,
            merchant    VARCHAR,
            category    VARCHAR,
            distance    FLOAT,
            is_fraud    DOUBLE PRECISION,
            created_at  TIMESTAMP
        );
        CREATE TABLE non_fraud_transaction (
            cc_num      VARCHAR,
            trans_num   VARCHAR,
            trans_time  TIMESTAMP,
            amt         FLOAT,
            merchant    VARCHAR,
            category    VARCHAR,
            distance    FLOAT,
            is_fraud    DOUBLE PRECISION,
            created_at  TIMESTAMP
        );
        CREATE TABLE customer (
            cc_num  VARCHAR,
            first   VARCHAR,
            last    VARCHAR,
            dob     DATE,
            job     VARCHAR,
            city    VARCHAR,
            state   VARCHAR,
            lat     FLOAT,
            long    FLOAT
        );
    """)

    # ── Business rules ────────────────────────────────────────────────────────
    print("Training: documentation...")
    vn.train(documentation="""
        - To query ALL transactions (fraud + non-fraud), always UNION
          fraud_transaction and non_fraud_transaction tables.
        - is_fraud = 1.0 means the transaction was flagged as fraudulent.
        - is_fraud = 0.0 means the transaction was classified as normal.
        - For real-time queries use the created_at column.
          For historical queries use the trans_time column.
        - Fraud rate = COUNT(fraud rows) / COUNT(all rows) * 100
        - Always use descriptive column aliases in SELECT.
        - Today's date is available in PostgreSQL via CURRENT_DATE.
    """)

    # ── Few-shot Q&A pairs ────────────────────────────────────────────────────
    print("Training: example Q&A pairs...")

    vn.train(
        question="Which merchant has the highest fraud rate today?",
        sql="""
            SELECT merchant,
                   COUNT(*) AS fraud_count,
                   ROUND(AVG(is_fraud)::numeric, 2) AS avg_is_fraud
            FROM fraud_transaction
            WHERE DATE(created_at) = CURRENT_DATE
            GROUP BY merchant
            ORDER BY fraud_count DESC
            LIMIT 10
        """,
    )

    vn.train(
        question="Compare fraud volume this week vs last week",
        sql="""
            SELECT
                CASE
                    WHEN created_at >= DATE_TRUNC('week', CURRENT_DATE)
                    THEN 'This Week'
                    ELSE 'Last Week'
                END AS period,
                COUNT(*) AS fraud_count,
                ROUND(SUM(amt)::numeric, 2) AS total_amount
            FROM fraud_transaction
            WHERE created_at >= DATE_TRUNC('week', CURRENT_DATE) - INTERVAL '7 days'
            GROUP BY period
            ORDER BY period
        """,
    )

    vn.train(
        question="Show high value fraud transactions above $500 in the last hour",
        sql="""
            SELECT trans_num, merchant, category, amt, is_fraud, created_at
            FROM fraud_transaction
            WHERE amt > 500
              AND created_at >= NOW() - INTERVAL '1 hour'
            ORDER BY amt DESC
        """,
    )

    vn.train(
        question="What is the overall fraud rate by category?",
        sql="""
            SELECT category,
                   COUNT(*) AS total_transactions,
                   ROUND(AVG(is_fraud)::numeric, 2) AS avg_is_fraud
            FROM (
                SELECT category, is_fraud FROM fraud_transaction
                UNION ALL
                SELECT category, is_fraud FROM non_fraud_transaction
            ) all_txns
            GROUP BY category
            ORDER BY avg_is_fraud DESC
        """,
    )

    print("Vanna training complete. Training data stored in Postgres via pgvector.")


if __name__ == "__main__":
    main()
