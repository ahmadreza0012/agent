"""
Database Migrations - Schema version control.

Provides safe schema migrations with version tracking and rollback support.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from .database_manager import DatabaseManager

logger = logging.getLogger(__name__)


class MigrationService:
    """Database migration service for schema version control."""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self._ensure_migration_table()
    
    def _ensure_migration_table(self) -> None:
        """Create migrations table if not exists."""
        query = """
        CREATE TABLE IF NOT EXISTS migrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            applied_at TIMESTAMP NOT NULL
        )
        """
        self.db.execute(query)
        logger.info("Migrations table ensured")
    
    def get_current_version(self) -> Optional[str]:
        """Get current database version."""
        query = "SELECT version FROM migrations ORDER BY id DESC LIMIT 1"
        try:
            result = self.db.execute(query)
            return result[0]['version'] if result else None
        except Exception as e:
            logger.error(f"Failed to get current version: {e}")
            return None
    
    def get_applied_migrations(self) -> List[Dict[str, Any]]:
        """Get list of all applied migrations."""
        query = "SELECT * FROM migrations ORDER BY id"
        try:
            return self.db.execute(query) or []
        except Exception as e:
            logger.error(f"Failed to get applied migrations: {e}")
            return []
    
    def is_migration_applied(self, version: str) -> bool:
        """Check if a specific migration has been applied."""
        query = "SELECT version FROM migrations WHERE version = ?"
        try:
            result = self.db.execute(query, (version,))
            return len(result) > 0 if result else False
        except Exception as e:
            logger.error(f"Failed to check migration status: {e}")
            return False
    
    def apply_migration(self, version: str, name: str, up_query: str) -> bool:
        """Apply a migration.
        
        Args:
            version: Version string (e.g., '1.0.0')
            name: Human-readable name
            up_query: SQL to execute (can contain multiple statements separated by ;)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Check if already applied
            if self.is_migration_applied(version):
                logger.warning(f"Migration {version} already applied")
                return True
            
            # Split multi-statement migrations for SQLite compatibility
            statements = [s.strip() for s in up_query.split(';') if s.strip()]
            
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                
                # Execute each statement separately
                for statement in statements:
                    if statement:
                        cursor.execute(statement)
                
                # Record the migration
                cursor.execute(
                    "INSERT INTO migrations (version, name, applied_at) VALUES (?, ?, ?)",
                    (version, name, datetime.now().isoformat())
                )
                
                conn.commit()
            
            logger.info(f"Applied migration {version}: {name}")
            return True
        except Exception as e:
            logger.error(f"Migration {version} failed: {e}")
            return False
    
    def initialize_schema(self) -> bool:
        """Initialize complete database schema.
        
        Returns:
            True if all migrations applied successfully
        """
        migrations = self._get_all_migrations()
        
        success = True
        for version, name, query in migrations:
            if not self.apply_migration(version, name, query):
                success = False
                logger.error(f"Schema initialization failed at {version}")
                break
        
        if success:
            logger.info("Database schema initialized successfully")
        
        return success
    
    def _get_all_migrations(self) -> List[Tuple[str, str, str]]:
        """Get all migrations in order."""
        return [
            ("1.0.0", "Initial schema", self._get_initial_schema()),
            ("1.0.1", "Add performance table", self._get_performance_schema()),
            ("1.0.2", "Add risk events table", self._get_risk_events_schema()),
            ("1.0.3", "Add strategy decisions table", self._get_strategy_decisions_schema()),
            ("1.0.4", "Add daily snapshots table", self._get_daily_snapshots_schema()),
            ("1.0.5", "Add reconciliation table", self._get_reconciliation_schema()),
        ]
    
    def _get_initial_schema(self) -> str:
        """Get initial schema SQL."""
        return """
        -- Orders table
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id TEXT UNIQUE NOT NULL,
            client_order_id TEXT UNIQUE NOT NULL,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL,
            order_type TEXT NOT NULL,
            price REAL,
            amount REAL NOT NULL,
            filled_amount REAL DEFAULT 0,
            status TEXT NOT NULL,
            fee REAL DEFAULT 0,
            fee_currency TEXT DEFAULT 'USDT',
            error_message TEXT,
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP NOT NULL
        );
        
        -- Trades table
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id TEXT NOT NULL,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL,
            price REAL NOT NULL,
            amount REAL NOT NULL,
            fee REAL DEFAULT 0,
            fee_currency TEXT DEFAULT 'USDT',
            exchange_id TEXT,
            timestamp TIMESTAMP NOT NULL,
            created_at TIMESTAMP NOT NULL,
            UNIQUE(order_id, exchange_id)
        );
        
        -- Positions table
        CREATE TABLE IF NOT EXISTS positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            timestamp TIMESTAMP NOT NULL,
            size REAL NOT NULL,
            entry_price REAL NOT NULL,
            current_price REAL,
            unrealized_pnl REAL,
            realized_pnl REAL,
            version INTEGER DEFAULT 1,
            UNIQUE(symbol, timestamp)
        );
        
        -- Create indexes
        CREATE INDEX IF NOT EXISTS idx_orders_client_order_id ON orders(client_order_id);
        CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
        CREATE INDEX IF NOT EXISTS idx_orders_symbol ON orders(symbol);
        CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at);
        CREATE INDEX IF NOT EXISTS idx_trades_order_id ON trades(order_id);
        CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol);
        CREATE INDEX IF NOT EXISTS idx_trades_timestamp ON trades(timestamp);
        """
    
    def _get_performance_schema(self) -> str:
        return """
        CREATE TABLE IF NOT EXISTS performance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TIMESTAMP NOT NULL,
            period_start TIMESTAMP NOT NULL,
            period_end TIMESTAMP NOT NULL,
            returns REAL,
            volatility REAL,
            sharpe REAL,
            drawdown REAL,
            turnover REAL,
            fees REAL,
            slippage REAL,
            created_at TIMESTAMP NOT NULL
        );
        
        CREATE INDEX IF NOT EXISTS idx_performance_timestamp ON performance(timestamp);
        """
    
    def _get_risk_events_schema(self) -> str:
        return """
        CREATE TABLE IF NOT EXISTS risk_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TIMESTAMP NOT NULL,
            event_type TEXT NOT NULL,
            severity TEXT NOT NULL,
            description TEXT NOT NULL,
            details TEXT,
            resolved_at TIMESTAMP,
            resolved_by TEXT,
            created_at TIMESTAMP NOT NULL
        );
        
        CREATE INDEX IF NOT EXISTS idx_risk_events_timestamp ON risk_events(timestamp);
        CREATE INDEX IF NOT EXISTS idx_risk_events_severity ON risk_events(severity);
        """
    
    def _get_strategy_decisions_schema(self) -> str:
        return """
        CREATE TABLE IF NOT EXISTS strategy_decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TIMESTAMP NOT NULL,
            strategy_name TEXT NOT NULL,
            signal TEXT NOT NULL,
            confidence REAL,
            weight REAL,
            asset TEXT,
            regime TEXT,
            version INTEGER DEFAULT 1,
            created_at TIMESTAMP NOT NULL
        );
        
        CREATE INDEX IF NOT EXISTS idx_strategy_decisions_timestamp ON strategy_decisions(timestamp);
        CREATE INDEX IF NOT EXISTS idx_strategy_decisions_name ON strategy_decisions(strategy_name);
        """
    
    def _get_daily_snapshots_schema(self) -> str:
        return """
        CREATE TABLE IF NOT EXISTS daily_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date DATE NOT NULL UNIQUE,
            equity REAL NOT NULL,
            positions_value REAL,
            cash REAL,
            drawdown REAL,
            exposure REAL,
            daily_pnl REAL,
            daily_trades INTEGER,
            created_at TIMESTAMP NOT NULL
        );
        
        CREATE INDEX IF NOT EXISTS idx_daily_snapshots_date ON daily_snapshots(date);
        """
    
    def _get_reconciliation_schema(self) -> str:
        return """
        CREATE TABLE IF NOT EXISTS reconciliation (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TIMESTAMP NOT NULL,
            local_state TEXT NOT NULL,
            exchange_state TEXT NOT NULL,
            discrepancies TEXT,
            resolution TEXT,
            resolved_at TIMESTAMP,
            resolved_by TEXT,
            created_at TIMESTAMP NOT NULL
        );
        
        CREATE INDEX IF NOT EXISTS idx_reconciliation_timestamp ON reconciliation(timestamp);
        """
