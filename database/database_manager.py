"""
Database Manager - Central database connection and management.

Supports both SQLite (development) and PostgreSQL (production).
Provides transactional consistency, retry logic, and connection pooling.
"""

import os
import time
import logging
from typing import Dict, Any, Optional, List, ContextManager
from contextlib import contextmanager
from datetime import datetime
import sqlite3

logger = logging.getLogger(__name__)

# Try to import psycopg2 for PostgreSQL support
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    from psycopg2.pool import SimpleConnectionPool
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False
    logger.warning("psycopg2 not available - PostgreSQL support disabled")


class DatabaseManager:
    """
    Central database manager supporting SQLite and PostgreSQL.
    
    Features:
    - Connection pooling for PostgreSQL
    - Transaction support
    - Retry logic
    - Connection health checks
    - Migration management
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.db_type = config.get('type', 'sqlite')
        self._pool = None
        self._is_initialized = False
        
        logger.info(f"DatabaseManager initialized with {self.db_type}")
        
        if self.db_type == 'postgresql':
            if not PSYCOPG2_AVAILABLE:
                raise ImportError("PostgreSQL support requires psycopg2. Install with: pip install psycopg2-binary")
            self._init_pool()
        else:
            self._init_sqlite()
    
    def _init_sqlite(self) -> None:
        """Initialize SQLite database."""
        db_path = self.config.get('path', 'data/trading.db')
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._db_path = db_path
        
        # Create connection to initialize
        conn = self._get_sqlite_connection()
        conn.close()
        
        self._is_initialized = True
        logger.info(f"SQLite database initialized: {db_path}")
    
    def _init_pool(self) -> None:
        """Initialize PostgreSQL connection pool."""
        try:
            self._pool = SimpleConnectionPool(
                minconn=1,
                maxconn=self.config.get('max_connections', 10),
                host=self.config.get('host', 'localhost'),
                port=self.config.get('port', 5432),
                database=self.config.get('database', 'trading'),
                user=self.config.get('user', 'trading'),
                password=self.config.get('password', ''),
                sslmode=self.config.get('sslmode', 'require')
            )
            self._is_initialized = True
            logger.info("PostgreSQL connection pool initialized")
        except Exception as e:
            logger.error(f"Failed to initialize PostgreSQL pool: {e}")
            raise
    
    def _get_sqlite_connection(self) -> sqlite3.Connection:
        """Get SQLite connection with retry."""
        max_retries = 5
        for attempt in range(max_retries):
            try:
                conn = sqlite3.connect(self._db_path, timeout=30.0)
                conn.execute("PRAGMA foreign_keys = ON")
                conn.execute("PRAGMA journal_mode = WAL")
                conn.execute("PRAGMA synchronous = NORMAL")
                return conn
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    time.sleep(0.1 * (attempt + 1))
                    continue
                raise
    
    @contextmanager
    def get_connection(self) -> ContextManager:
        """Get database connection (context manager)."""
        if self.db_type == 'postgresql':
            conn = self._pool.getconn()
            try:
                yield conn
            finally:
                self._pool.putconn(conn)
        else:
            conn = self._get_sqlite_connection()
            try:
                yield conn
            finally:
                pass  # Don't close, let caller manage commit/close
            conn.commit()
            conn.close()
    
    @contextmanager
    def get_cursor(self, cursor_type: str = 'dict'):
        """Get database cursor (context manager)."""
        with self.get_connection() as conn:
            if self.db_type == 'postgresql':
                cursor = conn.cursor(cursor_factory=RealDictCursor)
            else:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
            try:
                yield cursor
            finally:
                conn.commit()
                cursor.close()
    
    def execute(self, query: str, params: tuple = ()) -> Optional[List[Dict]]:
        """Execute a query and return results."""
        try:
            with self.get_cursor() as cursor:
                cursor.execute(query, params)
                if query.strip().upper().startswith('SELECT'):
                    if self.db_type == 'postgresql':
                        return [dict(row) for row in cursor.fetchall()]
                    else:
                        return [dict(row) for row in cursor.fetchall()]
                return None
        except Exception as e:
            logger.error(f"Query execution failed: {e}\nQuery: {query}")
            raise
    
    def execute_many(self, query: str, params_list: List[tuple]) -> int:
        """Execute a query with multiple parameter sets."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.executemany(query, params_list)
                conn.commit()
                return cursor.rowcount
        except Exception as e:
            logger.error(f"Batch execution failed: {e}")
            raise
    
    def execute_transaction(self, operations: List[tuple]) -> bool:
        """Execute multiple operations in a transaction.
        
        Args:
            operations: List of (query, params) tuples
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                for query, params in operations:
                    cursor.execute(query, params)
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Transaction failed: {e}")
            try:
                with self.get_connection() as conn:
                    conn.rollback()
            except:
                pass
            return False
    
    def health_check(self) -> bool:
        """Check database health."""
        try:
            with self.get_cursor() as cursor:
                if self.db_type == 'postgresql':
                    cursor.execute("SELECT 1")
                else:
                    cursor.execute("SELECT 1")
                return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False
    
    def close(self) -> None:
        """Close database connections."""
        if self._pool:
            self._pool.closeall()
            logger.info("Database connection pool closed")
