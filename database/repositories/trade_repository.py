"""
Trade Repository - CRUD for trades.

Stores all trade executions with complete metadata for audit and analysis.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
import logging

from .base_repository import BaseRepository
from ..database_manager import DatabaseManager

logger = logging.getLogger(__name__)


class TradeRepository(BaseRepository):
    """Repository for trade records."""
    
    def __init__(self, db_manager: DatabaseManager):
        super().__init__(db_manager)
    
    def _ensure_table(self) -> None:
        """Create trades table if not exists."""
        query = """
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
        )
        """
        
        # Create indexes for efficient queries
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_trades_order_id ON trades(order_id)",
            "CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol)",
            "CREATE INDEX IF NOT EXISTS idx_trades_timestamp ON trades(timestamp)"
        ]
        
        self.db.execute(query)
        for index in indexes:
            self.db.execute(index)
        
        logger.info("Trades table ensured")
    
    def create_trade(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create a trade record."""
        if 'created_at' not in data:
            data['created_at'] = datetime.now().isoformat()
        return self.create(data)
    
    def get_by_order_id(self, order_id: str) -> List[Dict[str, Any]]:
        """Get trades by order ID."""
        query = f"SELECT * FROM {self.table_name} WHERE order_id = ? ORDER BY timestamp"
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (order_id,))
                rows = cursor.fetchall()
                
                if not rows:
                    return []
                
                # Convert to dict
                columns = [d[0] for d in cursor.description]
                return [dict(zip(columns, row)) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get trades by order_id {order_id}: {e}")
            return []
    
    def get_by_symbol(self, symbol: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get trades by symbol."""
        query = f"""
            SELECT * FROM {self.table_name} 
            WHERE symbol = ? 
            ORDER BY timestamp DESC 
            LIMIT ?
        """
        try:
            return self.db.execute(query, (symbol, limit)) or []
        except Exception as e:
            logger.error(f"Failed to get trades by symbol {symbol}: {e}")
            return []
    
    def get_recent_trades(self, hours: int = 24, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent trades within specified hours."""
        cutoff = (datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)).isoformat()
        query = f"""
            SELECT * FROM {self.table_name} 
            WHERE timestamp >= ? 
            ORDER BY timestamp DESC 
            LIMIT ?
        """
        try:
            return self.db.execute(query, (cutoff, limit)) or []
        except Exception as e:
            logger.error(f"Failed to get recent trades: {e}")
            return []
    
    def get_trades_by_date_range(self, start: datetime, end: datetime) -> List[Dict[str, Any]]:
        """Get trades within a date range."""
        query = f"""
            SELECT * FROM {self.table_name} 
            WHERE timestamp >= ? AND timestamp <= ?
            ORDER BY timestamp
        """
        try:
            return self.db.execute(query, (start.isoformat(), end.isoformat())) or []
        except Exception as e:
            logger.error(f"Failed to get trades by date range: {e}")
            return []
    
    def get_total_volume_by_symbol(self, symbol: str, days: int = 30) -> float:
        """Get total trading volume for a symbol over the last N days."""
        cutoff = (datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)).isoformat()
        query = f"""
            SELECT SUM(amount * price) as total_volume 
            FROM {self.table_name} 
            WHERE symbol = ? AND timestamp >= ?
        """
        try:
            result = self.db.execute(query, (symbol, cutoff))
            return result[0]['total_volume'] if result and result[0]['total_volume'] else 0.0
        except Exception as e:
            logger.error(f"Failed to get total volume for {symbol}: {e}")
            return 0.0
    
    def get_total_fees(self, days: int = 30) -> float:
        """Get total fees paid over the last N days."""
        cutoff = (datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)).isoformat()
        query = f"""
            SELECT SUM(fee) as total_fees 
            FROM {self.table_name} 
            WHERE timestamp >= ?
        """
        try:
            result = self.db.execute(query, (cutoff,))
            return result[0]['total_fees'] if result and result[0]['total_fees'] else 0.0
        except Exception as e:
            logger.error(f"Failed to get total fees: {e}")
            return 0.0
