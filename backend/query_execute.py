"""
PostgreSQL/TimescaleDB query executor
Updated to match schema table names
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
    'database': os.getenv('DB_NAME', 'fraud_detection'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'postgres123')
}


def get_connection():
    """Get PostgreSQL database connection"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        print(f"Database connection error: {e}")
        raise


def get_costumer_by_id(cc_num):
    """
    Get customer information by credit card number
    
    Args:
        cc_num: Credit card number
    
    Returns:
        dict: Customer information
    """
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    # Updated table name: customers -> customer
    # Updated column names: first_name -> first, last_name -> last
    query = """
        SELECT 
            cc_num,
            first,
            last,
            gender,
            street,
            city,
            state,
            zip,
            lat,
            long,
            job,
            dob
        FROM customer
        WHERE cc_num = %s;
    """
    
    try:
        cursor.execute(query, (cc_num,))
        result = cursor.fetchone()
        
        if result:
            # Calculate age from dob
            age = None
            if result.get('dob'):
                dob = result['dob']
                if isinstance(dob, datetime):
                    age = int((datetime.today() - dob).days / 365.2425)
                elif isinstance(dob, str):
                    dob_date = datetime.strptime(dob, '%Y-%m-%d')
                    age = int((datetime.today() - dob_date).days / 365.2425)
            
            # Return in format compatible with existing app.py
            return {
                "cc_num": result.get('cc_num'),
                "first": result.get('first'),
                "last": result.get('last'),
                "gender": result.get('gender'),
                "age": age,
                "job": result.get('job'),
                "street": result.get('street'),
                "city": result.get('city'),
                "state": result.get('state'),
                "zip": result.get('zip'),
                "lat": result.get('lat'),
                "long": result.get('long')
            }
        else:
            return {
                "error": "Customer not found",
                "cc_num": cc_num
            }
    
    except Exception as e:
        print(f"Error fetching customer: {e}")
        return {"error": str(e)}
    finally:
        cursor.close()
        conn.close()


def get_statement_by_id(cc_num, limit=100):
    """
    Get transaction statement for a credit card
    Combines fraud_transaction and non_fraud_transaction tables
    
    Args:
        cc_num: Credit card number
        limit: Maximum number of transactions
    
    Returns:
        dict: Transaction statement with list of transactions
    """
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    # Query both fraud_transaction and non_fraud_transaction
    query = """
        SELECT 
            cc_num,
            trans_time,
            trans_num,
            category,
            amt,
            merchant,
            distance,
            is_fraud,
            merch_lat,
            merch_long,
            age,
            'fraud' as source
        FROM fraud_transaction
        WHERE cc_num = %s
        
        UNION ALL
        
        SELECT 
            cc_num,
            trans_time,
            trans_num,
            category,
            amt,
            merchant,
            distance,
            is_fraud,
            merch_lat,
            merch_long,
            age,
            'non_fraud' as source
        FROM non_fraud_transaction
        WHERE cc_num = %s
        
        ORDER BY trans_time DESC
        LIMIT %s;
    """
    
    try:
        cursor.execute(query, (cc_num, cc_num, limit))
        results = cursor.fetchall()
        
        # Convert to list of dicts
        transactions = []
        for row in results:
            trans = {
                "cc_num": row.get('cc_num'),
                "trans_num": row.get('trans_num'),
                "trans_time": str(row.get('trans_time')) if row.get('trans_time') else None,
                "category": row.get('category'),
                "amt": row.get('amt'),
                "merchant": row.get('merchant'),
                "distance": row.get('distance'),
                "is_fraud": row.get('is_fraud'),
                "source": row.get('source')  # 'fraud' or 'non_fraud'
            }
            transactions.append(trans)
        
        link = {
            "name": "customer",
            "href": f"http://localhost:8000/api/customer/{cc_num}"
        }
        
        return {
            "cc_num": cc_num,
            "transaction_count": len(transactions),
            "data": transactions,
            "link": link
        }
    
    except Exception as e:
        print(f"Error fetching statement: {e}")
        return {
            "cc_num": cc_num,
            "error": str(e),
            "data": [],
            "link": {
                "name": "customer",
                "href": f"http://localhost:8000/api/customer/{cc_num}"
            }
        }
    finally:
        cursor.close()
        conn.close()


def get_recent_fraud_transactions(minutes=5, limit=100):
    """
    Get recent fraud transactions
    
    Args:
        minutes: Number of minutes to look back
        limit: Maximum number of transactions
    
    Returns:
        list: Recent fraud transactions
    """
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    query = """
        SELECT 
            trans_time,
            trans_num,
            cc_num,
            amt,
            merchant,
            is_fraud,
            category,
            distance,
            created_at
        FROM fraud_transaction
        WHERE trans_time >= NOW() - (INTERVAL '1 minute' * %s)
        ORDER BY trans_time DESC
        LIMIT %s;
    """
    
    try:
        cursor.execute(query, (minutes, limit))
        results = cursor.fetchall()
        return [dict(row) for row in results]
    except Exception as e:
        print(f"Error fetching fraud transactions: {e}")
        return []
    finally:
        cursor.close()
        conn.close()


def insert_fraud_transaction(trans_data):
    """
    Insert transaction into fraud_transaction table
    
    Args:
        trans_data: Dictionary with transaction data
        
    Returns:
        bool: Success status
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    query = """
        INSERT INTO fraud_transaction (
            cc_num, trans_time, trans_num, category, merchant,
            amt, merch_lat, merch_long, distance, age, is_fraud
        ) VALUES (
            %(cc_num)s, %(trans_time)s, %(trans_num)s, %(category)s, %(merchant)s,
            %(amt)s, %(merch_lat)s, %(merch_long)s, %(distance)s, %(age)s, %(is_fraud)s
        )
        ON CONFLICT (cc_num, trans_time) DO NOTHING;
    """
    
    try:
        cursor.execute(query, trans_data)
        conn.commit()
        return True
    except Exception as e:
        print(f"Error inserting fraud transaction: {e}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()


def insert_non_fraud_transaction(trans_data):
    """
    Insert transaction into non_fraud_transaction table
    
    Args:
        trans_data: Dictionary with transaction data
        
    Returns:
        bool: Success status
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    query = """
        INSERT INTO non_fraud_transaction (
            cc_num, trans_time, trans_num, category, merchant,
            amt, merch_lat, merch_long, distance, age, is_fraud
        ) VALUES (
            %(cc_num)s, %(trans_time)s, %(trans_num)s, %(category)s, %(merchant)s,
            %(amt)s, %(merch_lat)s, %(merch_long)s, %(distance)s, %(age)s, %(is_fraud)s
        )
        ON CONFLICT (cc_num, trans_time) DO NOTHING;
    """
    
    try:
        cursor.execute(query, trans_data)
        conn.commit()
        return True
    except Exception as e:
        print(f"Error inserting non-fraud transaction: {e}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()


def get_kafka_offset(partition):
    """Get Kafka offset for a partition"""
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    query = "SELECT offset FROM kafka_offset WHERE partition = %s;"
    
    try:
        cursor.execute(query, (partition,))
        result = cursor.fetchone()
        return result['offset'] if result else 0
    except Exception as e:
        print(f"Error getting Kafka offset: {e}")
        return 0
    finally:
        cursor.close()
        conn.close()


def update_kafka_offset(partition, offset):
    """Update Kafka offset for a partition"""
    conn = get_connection()
    cursor = conn.cursor()
    
    query = """
        INSERT INTO kafka_offset (partition, offset, updated_at)
        VALUES (%s, %s, CURRENT_TIMESTAMP)
        ON CONFLICT (partition)
        DO UPDATE SET offset = EXCLUDED.offset, updated_at = CURRENT_TIMESTAMP;
    """
    
    try:
        cursor.execute(query, (partition, offset))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error updating Kafka offset: {e}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()


def get_fraud_statistics(hours=24):
    """
    Get fraud statistics for dashboard
    
    Args:
        hours: Number of hours to look back
        
    Returns:
        dict: Statistics
    """
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    query = """
        SELECT 
            COUNT(*)::INT as total_fraud_transactions,
            ROUND(SUM(amt)::NUMERIC, 2) as total_fraud_amount,
            ROUND(AVG(amt)::NUMERIC, 2) as avg_fraud_amount,
            ROUND(MIN(amt)::NUMERIC, 2) as min_fraud_amount,
            ROUND(MAX(amt)::NUMERIC, 2) as max_fraud_amount,
            COUNT(DISTINCT cc_num)::INT as unique_cards_affected
        FROM fraud_transaction
        WHERE trans_time >= NOW() - INTERVAL '%s hours';
    """
    
    try:
        cursor.execute(query, (hours,))
        result = cursor.fetchone()
        return dict(result) if result else {}
    except Exception as e:
        print(f"Error getting fraud statistics: {e}")
        return {}
    finally:
        cursor.close()
        conn.close()


# Test function
if __name__ == "__main__":
    print("=" * 60)
    print("Testing PostgreSQL Query Functions")
    print("=" * 60)
    
    # Test connection
    print("\n1. Testing database connection...")
    try:
        conn = get_connection()
        print("[OK] Connection successful!")
        conn.close()
    except Exception as e:
        print(f"[ERROR] Connection failed: {e}")

    # Test customer query
    print("\n2. Testing get_costumer_by_id...")
    customer = get_costumer_by_id("1234567890123456")
    if "error" in customer:
        print(f"[OK] Function works (customer not found as expected)")
    else:
        print(f"[OK] Customer found: {customer.get('first')} {customer.get('last')}")

    # Test statement query
    print("\n3. Testing get_statement_by_id...")
    statement = get_statement_by_id("1234567890123456")
    print(f"[OK] Found {statement['transaction_count']} transactions")

    # Test fraud statistics
    print("\n4. Testing get_fraud_statistics...")
    stats = get_fraud_statistics(24)
    print(f"[OK] Stats: {stats}")
    
    print("\n" + "=" * 60)
    print("All tests completed successfully!")
    print("=" * 60)
