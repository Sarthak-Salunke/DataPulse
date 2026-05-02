"""
Database utility functions for PostgreSQL/TimescaleDB
Helper functions for database operations
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor, execute_values
from psycopg2.pool import SimpleConnectionPool
from dotenv import load_dotenv
from contextlib import contextmanager

load_dotenv()

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
    'database': os.getenv('DB_NAME', 'fraud_detection'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'postgres123')
}

# Connection pool (optional, for better performance)
_connection_pool = None


def get_connection_pool(minconn=1, maxconn=10):
    """Get or create a connection pool"""
    global _connection_pool
    if _connection_pool is None:
        _connection_pool = SimpleConnectionPool(
            minconn=minconn,
            maxconn=maxconn,
            **DB_CONFIG
        )
    return _connection_pool


@contextmanager
def get_db_connection():
    """Context manager for database connections"""
    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        yield conn
        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        raise e
    finally:
        if conn:
            conn.close()


def get_connection():
    """Get a single database connection"""
    return psycopg2.connect(**DB_CONFIG)


def execute_query(query, params=None, fetch_one=False, fetch_all=True):
    """
    Execute a SQL query
    
    Args:
        query: SQL query string
        params: Query parameters (tuple or dict)
        fetch_one: If True, fetch one row
        fetch_all: If True, fetch all rows
        
    Returns:
        Query results
    """
    with get_db_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cursor.execute(query, params)
            if fetch_one:
                return cursor.fetchone()
            elif fetch_all:
                return cursor.fetchall()
            else:
                return None
        finally:
            cursor.close()


def execute_update(query, params=None):
    """
    Execute an UPDATE/INSERT/DELETE query
    
    Args:
        query: SQL query string
        params: Query parameters (tuple or dict)
        
    Returns:
        Number of affected rows
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(query, params)
            return cursor.rowcount
        finally:
            cursor.close()


def bulk_insert(table_name, columns, data, on_conflict=None):
    """
    Bulk insert data into a table
    
    Args:
        table_name: Name of the table
        columns: List of column names
        data: List of tuples with data
        on_conflict: Optional ON CONFLICT clause (e.g., "DO NOTHING")
        
    Returns:
        Number of inserted rows
    """
    if not data:
        return 0
    
    columns_str = ', '.join(columns)
    placeholders = ', '.join(['%s'] * len(columns))
    
    query = f"INSERT INTO {table_name} ({columns_str}) VALUES %s"
    if on_conflict:
        query += f" ON CONFLICT {on_conflict}"
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            execute_values(cursor, query, data, page_size=1000)
            return cursor.rowcount
        finally:
            cursor.close()


def table_exists(table_name):
    """Check if a table exists"""
    query = """
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = %s
        );
    """
    result = execute_query(query, (table_name,), fetch_one=True, fetch_all=False)
    return result[0] if result else False


def get_table_columns(table_name):
    """Get column information for a table"""
    query = """
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_schema = 'public' 
        AND table_name = %s
        ORDER BY ordinal_position;
    """
    return execute_query(query, (table_name,))


def get_table_row_count(table_name):
    """Get the number of rows in a table"""
    query = f"SELECT COUNT(*) as count FROM {table_name};"
    result = execute_query(query, fetch_one=True, fetch_all=False)
    return result['count'] if result else 0


def truncate_table(table_name):
    """Truncate a table"""
    query = f"TRUNCATE TABLE {table_name} CASCADE;"
    execute_update(query)
    print(f"[OK] Table {table_name} truncated successfully")


def create_index_if_not_exists(table_name, column_name, index_name=None, unique=False):
    """Create an index if it doesn't exist"""
    if index_name is None:
        index_name = f"idx_{table_name}_{column_name}"
    
    unique_str = "UNIQUE" if unique else ""
    query = f"""
        CREATE {unique_str} INDEX IF NOT EXISTS {index_name}
        ON {table_name} ({column_name});
    """
    try:
        execute_update(query)
        print(f"[OK] Index {index_name} created (or already exists)")
    except Exception as e:
        print(f"[ERROR] Error creating index: {e}")


def get_database_info():
    """Get database information"""
    info = {
        'host': DB_CONFIG['host'],
        'port': DB_CONFIG['port'],
        'database': DB_CONFIG['database'],
        'user': DB_CONFIG['user'],
        'tables': []
    }
    
    query = """
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public'
        ORDER BY table_name;
    """
    tables = execute_query(query)
    info['tables'] = [table['table_name'] for table in tables]
    
    return info


# Test function
if __name__ == "__main__":
    print("Testing database helper functions...")
    
    # Test connection
    try:
        conn = get_connection()
        print("[OK] Connection successful")
        conn.close()
    except Exception as e:
        print(f"[ERROR] Connection failed: {e}")
        exit(1)
    
    # Get database info
    info = get_database_info()
    print(f"\nDatabase: {info['database']}")
    print(f"Host: {info['host']}:{info['port']}")
    print(f"User: {info['user']}")
    print(f"Tables: {len(info['tables'])}")
    for table in info['tables']:
        count = get_table_row_count(table)
        print(f"  - {table}: {count} rows")

