-- ============================================================
-- Supabase / Plain PostgreSQL Schema
-- Fraud Detection Database
--
-- Differences from config/postgresql_schema.sql:
--   - TimescaleDB extension and hypertables removed
--   - Continuous aggregates removed (TimescaleDB-only feature)
--   - pgvector extension added (for Vanna NLP chatbot)
--   - LISTEN/NOTIFY trigger kept (works on Supabase direct connections)
--
-- Apply via Supabase SQL Editor or:
--   psql "$DATABASE_URL" -f config/supabase_schema.sql
-- ============================================================

-- pgvector for Vanna's vector store (NLP chatbot training data)
CREATE EXTENSION IF NOT EXISTS vector;

-- ── Customer ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS customer (
    cc_num     VARCHAR(50) PRIMARY KEY,
    first      VARCHAR(100),
    last       VARCHAR(100),
    gender     VARCHAR(10),
    street     VARCHAR(200),
    city       VARCHAR(100),
    state      VARCHAR(50),
    zip        VARCHAR(20),
    lat        DOUBLE PRECISION,
    long       DOUBLE PRECISION,
    job        VARCHAR(200),
    dob        TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_customer_name     ON customer(first, last);
CREATE INDEX IF NOT EXISTS idx_customer_location ON customer(city, state);

-- ── Fraud Transactions ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS fraud_transaction (
    cc_num        VARCHAR(50)  NOT NULL,
    trans_time    TIMESTAMP    NOT NULL,
    trans_num     VARCHAR(100) NOT NULL,
    category      VARCHAR(100),
    merchant      VARCHAR(200),
    amt           DOUBLE PRECISION,
    merch_lat     DOUBLE PRECISION,
    merch_long    DOUBLE PRECISION,
    distance      DOUBLE PRECISION,
    age           INTEGER,
    is_fraud      DOUBLE PRECISION,
    rule_flags    TEXT         DEFAULT '[]',
    rule_severity VARCHAR(10)  DEFAULT 'NONE',
    created_at    TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (cc_num, trans_time)
);

CREATE INDEX IF NOT EXISTS idx_fraud_trans_time ON fraud_transaction(trans_time DESC);
CREATE INDEX IF NOT EXISTS idx_fraud_cc_num     ON fraud_transaction(cc_num);
CREATE INDEX IF NOT EXISTS idx_fraud_trans_num  ON fraud_transaction(trans_num);
CREATE INDEX IF NOT EXISTS idx_fraud_merchant   ON fraud_transaction(merchant);
CREATE INDEX IF NOT EXISTS idx_fraud_category   ON fraud_transaction(category);
CREATE INDEX IF NOT EXISTS idx_fraud_created_at ON fraud_transaction(created_at DESC);

-- ── Non-Fraud Transactions ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS non_fraud_transaction (
    cc_num        VARCHAR(50)  NOT NULL,
    trans_time    TIMESTAMP    NOT NULL,
    trans_num     VARCHAR(100) NOT NULL,
    category      VARCHAR(100),
    merchant      VARCHAR(200),
    amt           DOUBLE PRECISION,
    merch_lat     DOUBLE PRECISION,
    merch_long    DOUBLE PRECISION,
    distance      DOUBLE PRECISION,
    age           INTEGER,
    is_fraud      DOUBLE PRECISION,
    rule_flags    TEXT         DEFAULT '[]',
    rule_severity VARCHAR(10)  DEFAULT 'NONE',
    created_at    TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (cc_num, trans_time)
);

CREATE INDEX IF NOT EXISTS idx_non_fraud_trans_time ON non_fraud_transaction(trans_time DESC);
CREATE INDEX IF NOT EXISTS idx_non_fraud_cc_num     ON non_fraud_transaction(cc_num);
CREATE INDEX IF NOT EXISTS idx_non_fraud_trans_num  ON non_fraud_transaction(trans_num);
CREATE INDEX IF NOT EXISTS idx_non_fraud_merchant   ON non_fraud_transaction(merchant);
CREATE INDEX IF NOT EXISTS idx_non_fraud_category   ON non_fraud_transaction(category);
CREATE INDEX IF NOT EXISTS idx_non_fraud_created_at ON non_fraud_transaction(created_at DESC);

-- ── Kafka Offset Tracking ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS kafka_offset (
    partition    INTEGER PRIMARY KEY,
    offset_value BIGINT    NOT NULL,
    updated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ── Customer Stats (for rule engine AMOUNT_SPIKE) ─────────────────────────────
CREATE TABLE IF NOT EXISTS customer_stats (
    cc_num      VARCHAR(50) PRIMARY KEY,
    avg_amt_30d NUMERIC(10, 2),
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ── Combined View ─────────────────────────────────────────────────────────────
CREATE OR REPLACE VIEW all_transactions AS
SELECT
    cc_num, trans_time, trans_num, category, merchant,
    amt, merch_lat, merch_long, distance, age, is_fraud,
    'fraud' AS transaction_type, created_at
FROM fraud_transaction
UNION ALL
SELECT
    cc_num, trans_time, trans_num, category, merchant,
    amt, merch_lat, merch_long, distance, age, is_fraud,
    'non_fraud' AS transaction_type, created_at
FROM non_fraud_transaction
ORDER BY trans_time DESC;

-- ── Helper Functions ──────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION get_customer_statement(customer_cc_num VARCHAR)
RETURNS TABLE (customer_info JSON, recent_transactions JSON) AS $$
BEGIN
    RETURN QUERY
    SELECT
        row_to_json(c.*) AS customer_info,
        (SELECT json_agg(t.*)
         FROM (
             SELECT cc_num, trans_time, trans_num, category, merchant,
                    amt, distance, is_fraud
             FROM all_transactions
             WHERE cc_num = customer_cc_num
             ORDER BY trans_time DESC
             LIMIT 50
         ) t) AS recent_transactions
    FROM customer c
    WHERE c.cc_num = customer_cc_num;
END;
$$ LANGUAGE plpgsql;


CREATE OR REPLACE FUNCTION get_fraud_stats(hours_back INTEGER DEFAULT 24)
RETURNS TABLE (
    total_fraud  INT,
    total_amount NUMERIC,
    avg_amount   NUMERIC,
    unique_cards INT,
    fraud_rate   NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        COUNT(*)::INT AS total_fraud,
        ROUND(SUM(amt)::NUMERIC, 2) AS total_amount,
        ROUND(AVG(amt)::NUMERIC, 2) AS avg_amount,
        COUNT(DISTINCT cc_num)::INT AS unique_cards,
        ROUND((COUNT(*)::NUMERIC / NULLIF(
            (SELECT COUNT(*) FROM all_transactions
             WHERE trans_time >= NOW() - (hours_back || ' hours')::INTERVAL), 0
        ) * 100), 2) AS fraud_rate
    FROM fraud_transaction
    WHERE trans_time >= NOW() - (hours_back || ' hours')::INTERVAL;
END;
$$ LANGUAGE plpgsql;

-- ── LISTEN/NOTIFY (for direct Postgres connections; bypassed on Supabase
--    connection pooler — FastAPI falls back to 3-second polling instead) ──────

CREATE OR REPLACE FUNCTION notify_fraud_insert()
RETURNS TRIGGER AS $$
BEGIN
    PERFORM pg_notify('fraud_channel', row_to_json(NEW)::text);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS fraud_notify_trigger ON fraud_transaction;
CREATE TRIGGER fraud_notify_trigger
    AFTER INSERT ON fraud_transaction
    FOR EACH ROW EXECUTE FUNCTION notify_fraud_insert();

-- ── Permissions ───────────────────────────────────────────────────────────────
GRANT ALL PRIVILEGES ON ALL TABLES    IN SCHEMA public TO postgres;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO postgres;
GRANT EXECUTE ON ALL FUNCTIONS        IN SCHEMA public TO postgres;

-- Read-only user (for Vanna NLP chatbot)
-- Create first: CREATE USER dp_readonly WITH PASSWORD 'your-password';
DO $$
BEGIN
    IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'dp_readonly') THEN
        GRANT SELECT ON ALL TABLES IN SCHEMA public TO dp_readonly;
    END IF;
END $$;

-- ── Sample test customer ──────────────────────────────────────────────────────
INSERT INTO customer (cc_num, first, last, gender, street, city, state, zip, lat, long, job, dob)
VALUES (
    '1234567890123456', 'John', 'Doe', 'M', '123 Main St',
    'New York', 'NY', '10001', 40.7128, -74.0060, 'Software Engineer', '1990-01-01'
) ON CONFLICT (cc_num) DO NOTHING;

-- Done
SELECT 'Supabase schema created successfully!' AS status;
