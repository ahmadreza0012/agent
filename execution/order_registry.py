"""
Order Registry - SQLite persistence layer for order idempotency and recovery.

This module provides persistent storage for all orders, enabling:
- Idempotency checks via client_order_id
- Order recovery after system restarts
- Audit trail for all order operations
"""

import sqlite3
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import asdict
from contextlib import contextmanager
from pathlib import Path

from .exchange_adapter import Order, OrderSide, OrderType, OrderStatus

logger = logging.getLogger(__name__)


class OrderRegistry:
    """
    SQLite-based order registry for persistent order storage.
    
    Provides idempotency guarantees and order recovery capabilities.
    """
    
    DB_SCHEMA = """
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id TEXT UNIQUE NOT NULL,           -- Exchange ID
        client_order_id TEXT UNIQUE NOT NULL,    -- Idempotency key
        symbol TEXT NOT NULL,
        side TEXT NOT NULL,
        order_type TEXT NOT NULL,
        price REAL,
        amount REAL NOT NULL,
        filled_amount REAL DEFAULT 0,
        status TEXT NOT NULL,
        fee REAL DEFAULT 0,
        fee_currency TEXT DEFAULT 'USDT',
        created_at TIMESTAMP NOT NULL,
        updated_at TIMESTAMP NOT NULL,
        last_check_at TIMESTAMP,
        error_message TEXT,
        metadata TEXT
    );
    
    CREATE INDEX IF NOT EXISTS idx_client_order_id ON orders(client_order_id);
    CREATE INDEX IF NOT EXISTS idx_order_id ON orders(order_id);
    CREATE INDEX IF NOT EXISTS idx_status ON orders(status);
    CREATE INDEX IF NOT EXISTS idx_symbol ON orders(symbol);
    CREATE INDEX IF NOT EXISTS idx_created_at ON orders(created_at);
    """
    
    def __init__(self, db_path: str = "orders.db"):
        """
        Initialize the order registry.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self._init_db()
        logger.info(f"OrderRegistry initialized with database: {self.db_path}")
    
    @contextmanager
    def _get_connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            conn.close()
    
    def _init_db(self):
        """Initialize the database schema."""
        with self._get_connection() as conn:
            conn.executescript(self.DB_SCHEMA)
            logger.debug("Database schema initialized")
    
    def _order_to_dict(self, order: Order, metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """Convert an Order object to a dictionary for storage."""
        data = {
            'order_id': order.id,
            'client_order_id': order.client_order_id,
            'symbol': order.symbol,
            'side': order.side.name if hasattr(order.side, 'name') else str(order.side),
            'order_type': order.type.name if hasattr(order.type, 'name') else str(order.type),
            'price': order.price,
            'amount': order.amount,
            'filled_amount': order.filled_amount,
            'status': order.status.name if hasattr(order.status, 'name') else str(order.status),
            'fee': order.fee.get('cost', 0.0) if isinstance(order.fee, dict) else (order.fee or 0.0),
            'fee_currency': order.fee.get('currency', 'USDT') if isinstance(order.fee, dict) else 'USDT',
            'created_at': order.timestamp.isoformat() if hasattr(order.timestamp, 'isoformat') else str(order.timestamp),
            'updated_at': datetime.now().isoformat(),
            'last_check_at': None,
            'error_message': None,
            'metadata': json.dumps(metadata) if metadata else None,
        }
        return data
    
    def _row_to_order(self, row: sqlite3.Row) -> Order:
        """Convert a database row to an Order object."""
        # Parse timestamp
        created_at_str = row['created_at']
        try:
            timestamp = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            timestamp = datetime.now()
        
        # Reconstruct fee dict
        fee = {
            'cost': row['fee'],
            'currency': row['fee_currency'] or 'USDT',
        }
        
        return Order(
            id=row['order_id'],
            client_order_id=row['client_order_id'],
            symbol=row['symbol'],
            side=OrderSide[row['side']],
            type=OrderType[row['order_type']],
            price=row['price'],
            amount=row['amount'],
            filled_amount=row['filled_amount'] or 0.0,
            status=OrderStatus[row['status']],
            timestamp=timestamp,
            fee=fee,
        )
    
    def save_order(self, order: Order, metadata: Optional[Dict] = None) -> None:
        """
        Save or update an order in the registry.
        
        Args:
            order: Order object to save
            metadata: Optional additional metadata
        """
        data = self._order_to_dict(order, metadata)
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO orders 
                (order_id, client_order_id, symbol, side, order_type, price, amount, 
                 filled_amount, status, fee, fee_currency, created_at, updated_at, 
                 last_check_at, error_message, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data['order_id'],
                data['client_order_id'],
                data['symbol'],
                data['side'],
                data['order_type'],
                data['price'],
                data['amount'],
                data['filled_amount'],
                data['status'],
                data['fee'],
                data['fee_currency'],
                data['created_at'],
                data['updated_at'],
                data['last_check_at'],
                data['error_message'],
                data['metadata'],
            ))
        
        logger.debug(f"Order saved: {order.id} (client_id={order.client_order_id})")
    
    def get_order_by_client_id(self, client_order_id: str) -> Optional[Order]:
        """
        Retrieve an order by its client_order_id (idempotency key).
        
        Args:
            client_order_id: The unique client order ID
            
        Returns:
            Order object if found, None otherwise
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM orders WHERE client_order_id = ?",
                (client_order_id,)
            )
            row = cursor.fetchone()
            
            if row:
                logger.debug(f"Found order by client_id: {client_order_id}")
                return self._row_to_order(row)
            return None
    
    def get_order_by_exchange_id(self, order_id: str) -> Optional[Order]:
        """
        Retrieve an order by its exchange order_id.
        
        Args:
            order_id: The exchange order ID
            
        Returns:
            Order object if found, None otherwise
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM orders WHERE order_id = ?",
                (order_id,)
            )
            row = cursor.fetchone()
            
            if row:
                logger.debug(f"Found order by exchange_id: {order_id}")
                return self._row_to_order(row)
            return None
    
    def get_orders_by_status(self, status: OrderStatus) -> List[Order]:
        """
        Retrieve all orders with a specific status.
        
        Args:
            status: Order status to filter by
            
        Returns:
            List of Order objects
        """
        status_name = status.name if hasattr(status, 'name') else str(status)
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM orders WHERE status = ? ORDER BY created_at DESC",
                (status_name,)
            )
            rows = cursor.fetchall()
            
            return [self._row_to_order(row) for row in rows]
    
    def get_open_orders(self) -> List[Order]:
        """
        Retrieve all open/partially filled orders.
        
        Returns:
            List of Order objects with OPEN or PARTIALLY_FILLED status
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM orders 
                WHERE status IN ('OPEN', 'PARTIALLY_FILLED') 
                ORDER BY created_at DESC
            """)
            rows = cursor.fetchall()
            
            orders = [self._row_to_order(row) for row in rows]
            logger.info(f"Retrieved {len(orders)} open orders from registry")
            return orders
    
    def get_orders_by_symbol(self, symbol: str) -> List[Order]:
        """
        Retrieve all orders for a specific symbol.
        
        Args:
            symbol: Trading pair symbol (e.g., 'BTC/USDT')
            
        Returns:
            List of Order objects
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM orders WHERE symbol = ? ORDER BY created_at DESC",
                (symbol,)
            )
            rows = cursor.fetchall()
            
            return [self._row_to_order(row) for row in rows]
    
    def update_order_status(
        self, 
        order_id: str, 
        status: OrderStatus, 
        filled_amount: Optional[float] = None,
        fee: Optional[Dict] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """
        Update the status of an existing order.
        
        Args:
            order_id: Exchange order ID
            status: New order status
            filled_amount: Updated filled amount (optional)
            fee: Fee information (optional)
            error_message: Error message if any (optional)
        """
        status_name = status.name if hasattr(status, 'name') else str(status)
        now = datetime.now().isoformat()
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Build update query dynamically
            updates = ["status = ?", "updated_at = ?", "last_check_at = ?"]
            params = [status_name, now, now]
            
            if filled_amount is not None:
                updates.append("filled_amount = ?")
                params.append(filled_amount)
            
            if fee is not None:
                updates.append("fee = ?")
                updates.append("fee_currency = ?")
                params.extend([fee.get('cost', 0.0), fee.get('currency', 'USDT')])
            
            if error_message is not None:
                updates.append("error_message = ?")
                params.append(error_message)
            
            params.append(order_id)
            
            query = f"UPDATE orders SET {', '.join(updates)} WHERE order_id = ?"
            cursor.execute(query, params)
        
        logger.debug(f"Order {order_id} status updated to {status_name}")
    
    def update_last_check_time(self, order_id: str) -> None:
        """
        Update the last check timestamp for an order.
        
        Args:
            order_id: Exchange order ID
        """
        now = datetime.now().isoformat()
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE orders SET last_check_at = ?, updated_at = ? WHERE order_id = ?",
                (now, now, order_id)
            )
    
    def delete_order(self, order_id: str) -> bool:
        """
        Delete an order from the registry.
        
        Args:
            order_id: Exchange order ID
            
        Returns:
            True if deleted, False if not found
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM orders WHERE order_id = ?",
                (order_id,)
            )
            deleted = cursor.rowcount > 0
        
        if deleted:
            logger.debug(f"Order deleted: {order_id}")
        return deleted
    
    def get_all_orders(self, limit: int = 1000) -> List[Order]:
        """
        Retrieve all orders with an optional limit.
        
        Args:
            limit: Maximum number of orders to return
            
        Returns:
            List of Order objects
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM orders ORDER BY created_at DESC LIMIT ?",
                (limit,)
            )
            rows = cursor.fetchall()
            
            return [self._row_to_order(row) for row in rows]
    
    def count_orders(self) -> int:
        """
        Count total number of orders in the registry.
        
        Returns:
            Total order count
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM orders")
            return cursor.fetchone()[0]
    
    def get_orders_since(self, since: datetime) -> List[Order]:
        """
        Retrieve orders created since a specific time.
        
        Args:
            since: Start datetime
            
        Returns:
            List of Order objects
        """
        since_str = since.isoformat()
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM orders WHERE created_at >= ? ORDER BY created_at DESC",
                (since_str,)
            )
            rows = cursor.fetchall()
            
            return [self._row_to_order(row) for row in rows]
    
    def clear_old_orders(self, days_old: int = 30) -> int:
        """
        Clear old completed orders for maintenance.
        
        Args:
            days_old: Number of days to keep orders
            
        Returns:
            Number of orders deleted
        """
        from datetime import timedelta
        cutoff = (datetime.now() - timedelta(days=days_old)).isoformat()
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM orders 
                WHERE status IN ('FILLED', 'CANCELLED', 'REJECTED', 'EXPIRED')
                AND created_at < ?
            """, (cutoff,))
            deleted = cursor.rowcount
        
        logger.info(f"Cleared {deleted} orders older than {days_old} days")
        return deleted
    
    def exists_client_order_id(self, client_order_id: str) -> bool:
        """
        Check if a client_order_id already exists in the registry.
        
        This is the primary idempotency check method.
        
        Args:
            client_order_id: The client order ID to check
            
        Returns:
            True if exists, False otherwise
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM orders WHERE client_order_id = ? LIMIT 1",
                (client_order_id,)
            )
            exists = cursor.fetchone() is not None
        
        if exists:
            logger.warning(f"Duplicate client_order_id detected: {client_order_id}")
        
        return exists
    
    def get_order_history(self, symbol: Optional[str] = None, limit: int = 100) -> List[Order]:
        """
        Get order history with optional symbol filter.
        
        Args:
            symbol: Optional symbol filter
            limit: Maximum number of orders to return
            
        Returns:
            List of Order objects
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            if symbol:
                cursor.execute(
                    "SELECT * FROM orders WHERE symbol = ? ORDER BY created_at DESC LIMIT ?",
                    (symbol, limit)
                )
            else:
                cursor.execute(
                    "SELECT * FROM orders ORDER BY created_at DESC LIMIT ?",
                    (limit,)
                )
            
            rows = cursor.fetchall()
            return [self._row_to_order(row) for row in rows]