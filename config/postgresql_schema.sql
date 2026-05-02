-- ============================================
-- PostgreSQL/TimescaleDB Schema
-- Fraud Detection Database
-- Matches original Cassandra schema structure
-- ============================================

-- Create database (run this first in psql)
-- CREATE DATABASE fraud_detection;

-- Connect to the database
\c fraud_detection;

-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- ============================================
-- Table 1: Customer Information
-- ============================================
CREATE TABLE IF NOT EXISTS customer (
    cc_num VARCHAR(50) PRIMARY KEY,
    first VARCHAR(100),
    last VARCHAR(100),
    gender VARCHAR(10),
    street VARCHAR(200),
    city VARCHAR(100),
    state VARCHAR(50),
    zip VARCHAR(20),
    lat DOUBLE PRECISION,
    long DOUBLE PRECISION,
    job VARCHAR(200),
    dob TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for faster lookups
CREATE INDEX IF NOT EXISTS idx_customer_name ON customer(first, last);
CREATE INDEX IF NOT EXISTS idx_customer_location ON customer(city, state);

COMMENT ON TABLE customer IS 'Customer master data';

-- ============================================
-- Table 2: Fraud Transactions
-- ============================================
CREATE TABLE IF NOT EXISTS fraud_transaction (
    cc_num VARCHAR(50) NOT NULL,
    trans_time TIMESTAMP NOT NULL,
    trans_num VARCHAR(100) NOT NULL,
    category VARCHAR(100),
    merchant VARCHAR(200),
    amt DOUBLE PRECISION,
    merch_lat DOUBLE PRECISION,
    merch_long DOUBLE PRECISION,
    distance DOUBLE PRECISION,
    age INTEGER,
    is_fraud DOUBLE PRECISION,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (cc_num, trans_time)
);

-- Convert to TimescaleDB hypertable for time-series optimization
SELECT create_hypertable('fraud_transaction', 'trans_time', 
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_fraud_trans_time ON fraud_transaction(trans_time DESC);
CREATE INDEX IF NOT EXISTS idx_fraud_cc_num ON fraud_transaction(cc_num);
CREATE INDEX IF NOT EXISTS idx_fraud_trans_num ON fraud_transaction(trans_num);
CREATE INDEX IF NOT EXISTS idx_fraud_merchant ON fraud_transaction(merchant);
CREATE INDEX IF NOT EXISTS idx_fraud_category ON fraud_transaction(category);

COMMENT ON TABLE fraud_transaction IS 'Transactions classified as fraudulent';

-- ============================================
-- Table 3: Non-Fraud Transactions
-- ============================================
CREATE TABLE IF NOT EXISTS non_fraud_transaction (
    cc_num VARCHAR(50) NOT NULL,
    trans_time TIMESTAMP NOT NULL,
    trans_num VARCHAR(100) NOT NULL,
    category VARCHAR(100),
    merchant VARCHAR(200),
    amt DOUBLE PRECISION,
    merch_lat DOUBLE PRECISION,
    merch_long DOUBLE PRECISION,
    distance DOUBLE PRECISION,
    age INTEGER,
    is_fraud DOUBLE PRECISION,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (cc_num, trans_time)
);

-- Convert to TimescaleDB hypertable
SELECT create_hypertable('non_fraud_transaction', 'trans_time',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_non_fraud_trans_time ON non_fraud_transaction(trans_time DESC);
CREATE INDEX IF NOT EXISTS idx_non_fraud_cc_num ON non_fraud_transaction(cc_num);
CREATE INDEX IF NOT EXISTS idx_non_fraud_trans_num ON non_fraud_transaction(trans_num);
CREATE INDEX IF NOT EXISTS idx_non_fraud_merchant ON non_fraud_transaction(merchant);
CREATE INDEX IF NOT EXISTS idx_non_fraud_category ON non_fraud_transaction(category);

COMMENT ON TABLE non_fraud_transaction IS 'Transactions classified as non-fraudulent';

-- ============================================
-- Table 4: Kafka Offset Tracking
-- ============================================
CREATE TABLE IF NOT EXISTS kafka_offset (
    partition INTEGER PRIMARY KEY,
    offset BIGINT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE kafka_offset IS 'Tracks Kafka consumer offset for each partition';

-- ============================================
-- View: All Transactions (Combined)
-- ============================================
CREATE OR REPLACE VIEW all_transactions AS
SELECT 
    cc_num, trans_time, trans_num, category, merchant, 
    amt, merch_lat, merch_long, distance, age, is_fraud,
    'fraud' as transaction_type,
    created_at
FROM fraud_transaction
UNION ALL
SELECT 
    cc_num, trans_time, trans_num, category, merchant,
    amt, merch_lat, merch_long, distance, age, is_fraud,
    'non_fraud' as transaction_type,
    created_at
FROM non_fraud_transaction
ORDER BY trans_time DESC;

-- ============================================
-- Continuous Aggregates (TimescaleDB Feature)
-- For real-time dashboard analytics
-- ============================================

-- Hourly fraud statistics
CREATE MATERIALIZED VIEW IF NOT EXISTS fraud_stats_hourly
WITH (timescaledb.continuous) AS
SELECT 
    time_bucket('1 hour', trans_time) AS hour,
    COUNT(*) as total_fraud_transactions,
    COUNT(DISTINCT cc_num) as unique_cards,
    AVG(amt) as avg_amount,
    SUM(amt) as total_amount,
    MIN(amt) as min_amount,
    MAX(amt) as max_amount,
    AVG(distance) as avg_distance
FROM fraud_transaction
GROUP BY hour
WITH NO DATA;

-- Refresh policy for continuous aggregate
SELECT add_continuous_aggregate_policy('fraud_stats_hourly',
    start_offset => INTERVAL '3 hours',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour',
    if_not_exists => TRUE
);

-- Daily transaction summary
CREATE MATERIALIZED VIEW IF NOT EXISTS daily_transaction_summary
WITH (timescaledb.continuous) AS
SELECT 
    time_bucket('1 day', trans_time) AS day,
    COUNT(*) FILTER (WHERE is_fraud > 0.5) as fraud_count,
    COUNT(*) FILTER (WHERE is_fraud <= 0.5) as non_fraud_count,
    COUNT(*) as total_count,
    SUM(amt) FILTER (WHERE is_fraud > 0.5) as fraud_amount,
    SUM(amt) FILTER (WHERE is_fraud <= 0.5) as non_fraud_amount,
    COUNT(DISTINCT cc_num) as unique_customers
FROM fraud_transaction
GROUP BY day
WITH NO DATA;

-- ============================================
-- Helper Functions
-- ============================================

-- Function to get customer with recent transactions
CREATE OR REPLACE FUNCTION get_customer_statement(customer_cc_num VARCHAR)
RETURNS TABLE (
    customer_info JSON,
    recent_transactions JSON
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        row_to_json(c.*) as customer_info,
        (SELECT json_agg(t.*)
         FROM (
             SELECT cc_num, trans_time, trans_num, category, merchant,
                    amt, distance, is_fraud
             FROM all_transactions 
             WHERE cc_num = customer_cc_num 
             ORDER BY trans_time DESC 
             LIMIT 50
         ) t) as recent_transactions
    FROM customer c
    WHERE c.cc_num = customer_cc_num;
END;
$$ LANGUAGE plpgsql;

-- Function to get fraud statistics for dashboard
CREATE OR REPLACE FUNCTION get_fraud_stats(hours_back INTEGER DEFAULT 24)
RETURNS TABLE (
    total_fraud INT,
    total_amount NUMERIC,
    avg_amount NUMERIC,
    unique_cards INT,
    fraud_rate NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        COUNT(*)::INT as total_fraud,
        ROUND(SUM(amt)::NUMERIC, 2) as total_amount,
        ROUND(AVG(amt)::NUMERIC, 2) as avg_amount,
        COUNT(DISTINCT cc_num)::INT as unique_cards,
        ROUND((COUNT(*)::NUMERIC / NULLIF(
            (SELECT COUNT(*) FROM all_transactions 
             WHERE trans_time >= NOW() - (hours_back || ' hours')::INTERVAL), 0
        ) * 100), 2) as fraud_rate
    FROM fraud_transaction
    WHERE trans_time >= NOW() - (hours_back || ' hours')::INTERVAL;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- Sample Data Insertion (Optional - for testing)
-- ============================================

-- Insert a test customer
INSERT INTO customer (cc_num, first, last, gender, street, city, state, zip, lat, long, job, dob)
VALUES (
    '1234567890123456',
    'John',
    'Doe',
    'M',
    '123 Main St',
    'New York',
    'NY',
    '10001',
    40.7128,
    -74.0060,
    'Software Engineer',
    '1990-01-01'
) ON CONFLICT (cc_num) DO NOTHING;

-- ============================================
-- Grant Permissions
-- ============================================
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO postgres;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO postgres;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO postgres;

-- ============================================
-- Data Retention Policy (Optional)
-- Uncomment to keep only last 90 days
-- ============================================
-- SELECT add_retention_policy('fraud_transaction', INTERVAL '90 days', if_not_exists => TRUE);
-- SELECT add_retention_policy('non_fraud_transaction', INTERVAL '90 days', if_not_exists => TRUE);

-- ============================================
-- Verification Queries
-- ============================================

-- Check tables created
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public' 
ORDER BY table_name;

-- Check hypertables
SELECT * FROM timescaledb_information.hypertables;

-- Display summary
\dt
\dv
\df

COMMENT ON DATABASE fraud_detection IS 'Real-time fraud detection system with TimescaleDB';

-- Done!
SELECT 'PostgreSQL schema created successfully!' as status;
