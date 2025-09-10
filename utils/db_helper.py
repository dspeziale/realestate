# Copyright 2025 SILICONDEV SPA
# Filename: utils/db_helper.py
# Description: Database query helper functions for SQLite operations

import sqlite3
import logging
from contextlib import contextmanager
from typing import List, Dict, Any, Optional, Union
from flask import current_app

logger = logging.getLogger(__name__)


class DatabaseHelper:
    """Helper class for direct SQLite database operations"""

    @staticmethod
    def get_db_path() -> str:
        """Get database path from Flask app config"""
        try:
            db_uri = current_app.config.get('SQLALCHEMY_DATABASE_URI', '')
            if db_uri.startswith('sqlite:///'):
                return db_uri.replace('sqlite:///', '')
            elif db_uri.startswith('sqlite://'):
                return db_uri.replace('sqlite://', '')
            else:
                # Fallback to default
                return 'real_estate_auctions.db'
        except:
            # If no app context, use default
            return 'real_estate_auctions.db'

    @staticmethod
    @contextmanager
    def get_connection():
        """Context manager for database connections"""
        db_path = DatabaseHelper.get_db_path()
        conn = None
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row  # Enable dict-like access to rows
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Database connection error: {str(e)}")
            raise
        finally:
            if conn:
                conn.close()


def execute_query(
        query: str,
        params: Optional[Union[tuple, list, dict]] = None,
        fetch_one: bool = False,
        fetch_all: bool = False,
        commit: bool = False
) -> Optional[Union[List[Dict], Dict, int]]:
    """
    Execute a SQL query on the SQLite database

    Args:
        query (str): SQL query to execute
        params: Parameters for the query (tuple, list, or dict)
        fetch_one (bool): Return only the first row
        fetch_all (bool): Return all rows
        commit (bool): Commit the transaction (for INSERT/UPDATE/DELETE)

    Returns:
        - If fetch_one=True: Dict with row data or None
        - If fetch_all=True: List of Dict with rows data
        - If commit=True: Number of affected rows
        - Otherwise: None

    Examples:
        # SELECT query
        users = execute_query(
            "SELECT * FROM users WHERE is_admin = ?",
            (True,),
            fetch_all=True
        )

        # INSERT query
        rows_affected = execute_query(
            "INSERT INTO users (email, first_name, last_name) VALUES (?, ?, ?)",
            ('test@example.com', 'Test', 'User'),
            commit=True
        )

        # UPDATE query
        execute_query(
            "UPDATE users SET is_active = ? WHERE id = ?",
            (False, 1),
            commit=True
        )
    """
    try:
        with DatabaseHelper.get_connection() as conn:
            cursor = conn.cursor()

            # Execute query with parameters
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)

            # Handle different return types
            if fetch_one:
                row = cursor.fetchone()
                return dict(row) if row else None

            elif fetch_all:
                rows = cursor.fetchall()
                return [dict(row) for row in rows]

            elif commit:
                conn.commit()
                return cursor.rowcount

            return None

    except sqlite3.Error as e:
        logger.error(f"SQLite error in execute_query: {str(e)}")
        logger.error(f"Query: {query}")
        logger.error(f"Params: {params}")
        raise
    except Exception as e:
        logger.error(f"General error in execute_query: {str(e)}")
        raise


def execute_select(query: str, params: Optional[Union[tuple, list, dict]] = None) -> List[Dict[str, Any]]:
    """
    Execute a SELECT query and return all results

    Args:
        query (str): SELECT SQL query
        params: Query parameters

    Returns:
        List[Dict]: List of rows as dictionaries

    Example:
        users = execute_select("SELECT * FROM users WHERE city = ?", ("Roma",))
    """
    return execute_query(query, params, fetch_all=True) or []


def execute_select_one(query: str, params: Optional[Union[tuple, list, dict]] = None) -> Optional[Dict[str, Any]]:
    """
    Execute a SELECT query and return first result

    Args:
        query (str): SELECT SQL query
        params: Query parameters

    Returns:
        Dict or None: First row as dictionary or None if no results

    Example:
        user = execute_select_one("SELECT * FROM users WHERE email = ?", ("admin@example.com",))
    """
    return execute_query(query, params, fetch_one=True)


def execute_insert(query: str, params: Optional[Union[tuple, list, dict]] = None) -> int:
    """
    Execute an INSERT query

    Args:
        query (str): INSERT SQL query
        params: Query parameters

    Returns:
        int: Number of affected rows (usually 1 for single insert)

    Example:
        affected = execute_insert(
            "INSERT INTO properties (title, city, base_price, agent_id) VALUES (?, ?, ?, ?)",
            ("Test Property", "Roma", 150000, 1)
        )
    """
    return execute_query(query, params, commit=True) or 0


def execute_update(query: str, params: Optional[Union[tuple, list, dict]] = None) -> int:
    """
    Execute an UPDATE query

    Args:
        query (str): UPDATE SQL query
        params: Query parameters

    Returns:
        int: Number of affected rows

    Example:
        affected = execute_update(
            "UPDATE properties SET status = ? WHERE id = ?",
            ("sold", 1)
        )
    """
    return execute_query(query, params, commit=True) or 0


def execute_delete(query: str, params: Optional[Union[tuple, list, dict]] = None) -> int:
    """
    Execute a DELETE query

    Args:
        query (str): DELETE SQL query
        params: Query parameters

    Returns:
        int: Number of affected rows

    Example:
        affected = execute_delete("DELETE FROM bids WHERE auction_id = ?", (1,))
    """
    return execute_query(query, params, commit=True) or 0


def execute_script(script: str) -> None:
    """
    Execute a multi-statement SQL script

    Args:
        script (str): Multi-line SQL script

    Example:
        script = '''
        UPDATE users SET is_active = 1;
        INSERT INTO properties (title, city, base_price, agent_id)
        VALUES ('Test', 'Roma', 100000, 1);
        '''
        execute_script(script)
    """
    try:
        with DatabaseHelper.get_connection() as conn:
            cursor = conn.cursor()
            cursor.executescript(script)
            conn.commit()

    except sqlite3.Error as e:
        logger.error(f"SQLite error in execute_script: {str(e)}")
        logger.error(f"Script: {script}")
        raise
    except Exception as e:
        logger.error(f"General error in execute_script: {str(e)}")
        raise


def get_table_info(table_name: str) -> List[Dict[str, Any]]:
    """
    Get information about a table structure

    Args:
        table_name (str): Name of the table

    Returns:
        List[Dict]: Column information

    Example:
        columns = get_table_info('users')
        for col in columns:
            print(f"{col['name']}: {col['type']}")
    """
    query = f"PRAGMA table_info({table_name})"
    return execute_select(query)


def get_table_count(table_name: str, where_clause: str = None, params: Optional[tuple] = None) -> int:
    """
    Get count of rows in a table

    Args:
        table_name (str): Name of the table
        where_clause (str): Optional WHERE clause (without WHERE keyword)
        params (tuple): Parameters for WHERE clause

    Returns:
        int: Number of rows

    Examples:
        total_users = get_table_count('users')
        active_users = get_table_count('users', 'is_active = ?', (True,))
    """
    query = f"SELECT COUNT(*) as count FROM {table_name}"
    if where_clause:
        query += f" WHERE {where_clause}"

    result = execute_select_one(query, params)
    return result['count'] if result else 0


def table_exists(table_name: str) -> bool:
    """
    Check if a table exists in the database

    Args:
        table_name (str): Name of the table to check

    Returns:
        bool: True if table exists, False otherwise

    Example:
        if table_exists('users'):
            print("Users table exists")
    """
    query = "SELECT name FROM sqlite_master WHERE type='table' AND name=?"
    result = execute_select_one(query, (table_name,))
    return result is not None


def get_database_info() -> Dict[str, Any]:
    """
    Get general information about the database

    Returns:
        Dict: Database information including tables, sizes, etc.

    Example:
        info = get_database_info()
        print(f"Database has {len(info['tables'])} tables")
    """
    try:
        # Get all tables
        tables_query = "SELECT name FROM sqlite_master WHERE type='table'"
        tables = execute_select(tables_query)

        # Get database size
        import os
        db_path = DatabaseHelper.get_db_path()
        db_size = os.path.getsize(db_path) if os.path.exists(db_path) else 0

        # Count rows in main tables
        table_counts = {}
        main_tables = ['users', 'properties', 'auctions', 'bids']

        for table in main_tables:
            if table_exists(table):
                table_counts[table] = get_table_count(table)

        return {
            'database_path': db_path,
            'database_size_bytes': db_size,
            'database_size_mb': round(db_size / (1024 * 1024), 2),
            'tables': [t['name'] for t in tables],
            'table_count': len(tables),
            'row_counts': table_counts
        }

    except Exception as e:
        logger.error(f"Error getting database info: {str(e)}")
        return {
            'error': str(e),
            'database_path': DatabaseHelper.get_db_path(),
            'tables': [],
            'table_count': 0,
            'row_counts': {}
        }


# Convenience functions for common operations
def get_all_users() -> List[Dict[str, Any]]:
    """Get all users from database"""
    return execute_select("SELECT * FROM users ORDER BY created_at DESC")


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """Get user by email"""
    return execute_select_one("SELECT * FROM users WHERE email = ?", (email,))


def get_all_properties() -> List[Dict[str, Any]]:
    """Get all properties from database"""
    return execute_select("SELECT * FROM properties ORDER BY created_at DESC")


def get_properties_by_agent(agent_id: int) -> List[Dict[str, Any]]:
    """Get properties by agent ID"""
    return execute_select("SELECT * FROM properties WHERE agent_id = ? ORDER BY created_at DESC", (agent_id,))


def get_all_auctions() -> List[Dict[str, Any]]:
    """Get all auctions from database"""
    return execute_select("SELECT * FROM auctions ORDER BY start_date DESC")


def get_active_auctions() -> List[Dict[str, Any]]:
    """Get all active auctions"""
    return execute_select("SELECT * FROM auctions WHERE status = 'active' ORDER BY end_date ASC")


def get_user_bids(user_id: int) -> List[Dict[str, Any]]:
    """Get all bids by user"""
    return execute_select(
        "SELECT b.*, a.title as auction_title FROM bids b "
        "JOIN auctions a ON b.auction_id = a.id "
        "WHERE b.bidder_id = ? ORDER BY b.created_at DESC",
        (user_id,)
    )


# Example usage and testing function
def test_database_functions():
    """Test function to demonstrate usage"""
    try:
        print("=== Database Helper Test ===")

        # Get database info
        info = get_database_info()
        print(f"Database: {info['database_path']}")
        print(f"Size: {info['database_size_mb']} MB")
        print(f"Tables: {info['tables']}")
        print(f"Row counts: {info['row_counts']}")

        # Test user queries
        print("\n=== Users ===")
        users = get_all_users()
        print(f"Total users: {len(users)}")

        if users:
            admin_user = execute_select_one(
                "SELECT * FROM users WHERE is_admin = ? LIMIT 1",
                (True,)
            )
            if admin_user:
                print(f"Admin user: {admin_user['email']}")

        # Test properties
        print("\n=== Properties ===")
        properties = get_all_properties()
        print(f"Total properties: {len(properties)}")

        # Test auctions
        print("\n=== Auctions ===")
        auctions = get_all_auctions()
        print(f"Total auctions: {len(auctions)}")

        active_auctions = get_active_auctions()
        print(f"Active auctions: {len(active_auctions)}")

        print("\n=== Test completed successfully ===")

    except Exception as e:
        print(f"Test failed: {str(e)}")


if __name__ == "__main__":
    test_database_functions()