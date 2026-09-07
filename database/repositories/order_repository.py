"""
Order Repository - CRUD for orders.

Stores complete order history with status tracking and error information.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
import logging

from .base_repository import BaseRepository
from ..database_manager import DatabaseManager

logger = logging.getLogger(__name__)


class OrderRepository(BaseRepository):
    """Repository for order records."""
    
    def __init__(self, db_manager: DatabaseManager):
        super().__init__(db_manager)
    
    def _ensure_table(self) -> None:
        """Create orders table if not exists."""
        query = """
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
        )
        """
        
        # Create indexes for efficient queries
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_orders_client_order_id ON orders(client_order_id)",
            "CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status)",
            "CREATE INDEX IF NOT EXISTS idx_orders_symbol ON orders(symbol)",
            "CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at)"
        ]
        
        self.db.execute(query)
        for index in indexes:
            self.db.execute(index)
        
        logger.info("Orders table ensured")
    
    def create_order(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create an order record."""
        return self.create(data)
    
    def get_by_order_id(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Get order by exchange order ID."""
        query = f"SELECT * FROM {self.table_name} WHERE order_id = ?"
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (order_id,))
                row = cursor.fetchone()
                
                if not row:
                    return None
                
                columns = [d[0] for d in cursor.description]
                return dict(zip(columns, row))
        except Exception as e:
            logger.error(f"Failed to get order by order_id {order_id}: {e}")
            return None
    
    def get_by_client_id(self, client_order_id: str) -> Optional[Dict[str, Any]]:
        """Get order by client order ID."""
        query = f"SELECT * FROM {self.table_name} WHERE client_order_id = ?"
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (client_order_id,))
                row = cursor.fetchone()
                
                if not row:
                    return None
                
                columns = [d[0] for d in cursor.description]
                return dict(zip(columns, row))
        except Exception as e:
            logger.error(f"Failed to get order by client_order_id {client_order_id}: {e}")
            return None
    
    def get_open_orders(self) -> List[Dict[str, Any]]:
        """Get all open orders."""
        query = f"""
            SELECT * FROM {self.table_name} 
            WHERE status IN ('open', 'partially_filled') 
            ORDER BY created_at DESC
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query)
                rows = cursor.fetchall()
                
                if not rows:
                    return []
                
                columns = [d[0] for d in cursor.description]
                return [dict(zip(columns, row)) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get open orders: {e}")
            return []
    
    def update_status(self, order_id: str, status: str, error_message: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Update order status."""
        data = {
            'status': status,
            'updated_at': datetime.now().isoformat()
        }
        if error_message:
            data['error_message'] = error_message
        
        set_clause = ', '.join([f"{k} = ?" for k in data.keys()])
        query = f"UPDATE {self.table_name} SET {set_clause} WHERE order_id = ?"
        
        params = tuple(list(data.values()) + [order_id])
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                
                # Fetch updated record
                cursor.execute(f"SELECT * FROM {self.table_name} WHERE order_id = ?", (order_id,))
                row = cursor.fetchone()
                
                if not row:
                    return None
                
                columns = [d[0] for d in cursor.description]
                return dict(zip(columns, row))
        except Exception as e:
            logger.error(f"Failed to update order status {order_id}: {e}")
            return None
    
    def get_by_symbol(self, symbol: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get orders by symbol."""
        query = f"""
            SELECT * FROM {self.table_name} 
            WHERE symbol = ? 
            ORDER BY created_at DESC 
            LIMIT ?
        """
        try:
            return self.db.execute(query, (symbol, limit)) or []
        except Exception as e:
            logger.error(f"Failed to get orders by symbol {symbol}: {e}")
            return []
    
    def get_recent_orders(self, hours: int = 24, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent orders within specified hours."""
        cutoff = (datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)).isoformat()
        query = f"""
            SELECT * FROM {self.table_name} 
            WHERE created_at >= ? 
            ORDER BY created_at DESC 
            LIMIT ?
        """
        try:
            return self.db.execute(query, (cutoff, limit)) or []
        except Exception as e:
            logger.error(f"Failed to get recent orders: {e}")
            return []
