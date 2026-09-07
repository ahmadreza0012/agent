"""
Performance Repository - CRUD for performance metrics.

Stores periodic performance metrics for analysis and reporting.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import logging

from .base_repository import BaseRepository
from ..database_manager import DatabaseManager

logger = logging.getLogger(__name__)


class PerformanceRepository(BaseRepository):
    """Repository for performance metrics."""
    
    def __init__(self, db_manager: DatabaseManager):
        super().__init__(db_manager)
    
    def _ensure_table(self) -> None:
        """Create performance table if not exists."""
        query = """
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
        )
        """
        
        # Create indexes for efficient queries
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_performance_timestamp ON performance(timestamp)"
        ]
        
        self.db.execute(query)
        for index in indexes:
            self.db.execute(index)
        
        logger.info("Performance table ensured")
    
    def create_metrics(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create performance metrics."""
        if 'created_at' not in data:
            data['created_at'] = datetime.now().isoformat()
        return self.create(data)
    
    def get_daily_performance(self, days: int = 30) -> List[Dict[str, Any]]:
        """Get daily performance for the last N days."""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        query = f"""
            SELECT * FROM {self.table_name} 
            WHERE timestamp >= ? 
            ORDER BY timestamp DESC
        """
        try:
            return self.db.execute(query, (cutoff,)) or []
        except Exception as e:
            logger.error(f"Failed to get daily performance: {e}")
            return []
    
    def get_period_performance(self, start: datetime, end: datetime) -> List[Dict[str, Any]]:
        """Get performance for a specific period."""
        query = f"""
            SELECT * FROM {self.table_name} 
            WHERE timestamp >= ? AND timestamp <= ?
            ORDER BY timestamp
        """
        try:
            return self.db.execute(query, (start.isoformat(), end.isoformat())) or []
        except Exception as e:
            logger.error(f"Failed to get period performance: {e}")
            return []
    
    def get_latest_metrics(self) -> Optional[Dict[str, Any]]:
        """Get the most recent performance metrics."""
        query = f"SELECT * FROM {self.table_name} ORDER BY timestamp DESC LIMIT 1"
        try:
            result = self.db.execute(query)
            return result[0] if result else None
        except Exception as e:
            logger.error(f"Failed to get latest metrics: {e}")
            return None
    
    def get_average_sharpe(self, days: int = 30) -> float:
        """Get average Sharpe ratio over the last N days."""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        query = f"""
            SELECT AVG(sharpe) as avg_sharpe 
            FROM {self.table_name} 
            WHERE timestamp >= ? AND sharpe IS NOT NULL
        """
        try:
            result = self.db.execute(query, (cutoff,))
            return result[0]['avg_sharpe'] if result and result[0]['avg_sharpe'] else 0.0
        except Exception as e:
            logger.error(f"Failed to get average Sharpe: {e}")
            return 0.0
    
    def get_max_drawdown(self, days: int = 30) -> float:
        """Get maximum drawdown over the last N days."""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        query = f"""
            SELECT MIN(drawdown) as max_drawdown 
            FROM {self.table_name} 
            WHERE timestamp >= ? AND drawdown IS NOT NULL
        """
        try:
            result = self.db.execute(query, (cutoff,))
            return result[0]['max_drawdown'] if result and result[0]['max_drawdown'] else 0.0
        except Exception as e:
            logger.error(f"Failed to get max drawdown: {e}")
            return 0.0
    
    def get_total_fees(self, days: int = 30) -> float:
        """Get total fees over the last N days."""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        query = f"""
            SELECT SUM(fees) as total_fees 
            FROM {self.table_name} 
            WHERE timestamp >= ? AND fees IS NOT NULL
        """
        try:
            result = self.db.execute(query, (cutoff,))
            return result[0]['total_fees'] if result and result[0]['total_fees'] else 0.0
        except Exception as e:
            logger.error(f"Failed to get total fees: {e}")
            return 0.0
