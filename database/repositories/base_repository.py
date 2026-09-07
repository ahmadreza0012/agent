"""
Base Repository - Base class for all repositories.

Provides common CRUD operations with proper error handling and logging.
"""

from typing import Dict, Any, Optional, List, TypeVar, Generic
from datetime import datetime
import logging

from ..database_manager import DatabaseManager

logger = logging.getLogger(__name__)

T = TypeVar('T')


class BaseRepository(Generic[T]):
    """Base repository with common CRUD operations."""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self.table_name = self._get_table_name()
        self._ensure_table()
    
    def _get_table_name(self) -> str:
        """Get table name for this repository."""
        return self.__class__.__name__.replace('Repository', '').lower() + 's'
    
    def _ensure_table(self) -> None:
        """Ensure table exists (implemented by subclasses)."""
        pass
    
    def create(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create a new record."""
        if not data:
            logger.error("Cannot create record with empty data")
            return None
        
        columns = ', '.join(data.keys())
        placeholders = ', '.join(['?' for _ in data])
        query = f"INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})"
        
        try:
            # Execute insert and fetch in same connection context
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, tuple(data.values()))
                
                # Get the last inserted ID
                last_id = cursor.lastrowid
                
                # Fetch the created record
                cursor.execute(f"SELECT * FROM {self.table_name} WHERE id = ?", (last_id,))
                row = cursor.fetchone()
                
                if row:
                    if self.db.db_type == 'postgresql':
                        return dict(row)
                    else:
                        return dict(zip([d[0] for d in cursor.description], row))
                return None
        except Exception as e:
            logger.error(f"Failed to create record in {self.table_name}: {e}")
            return None
    
    def get_by_id(self, id: int) -> Optional[Dict[str, Any]]:
        """Get record by ID."""
        query = f"SELECT * FROM {self.table_name} WHERE id = ?"
        try:
            result = self.db.execute(query, (id,))
            return result[0] if result else None
        except Exception as e:
            logger.error(f"Failed to get record by ID {id}: {e}")
            return None
    
    def get_all(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Get all records with pagination."""
        query = f"SELECT * FROM {self.table_name} ORDER BY created_at DESC LIMIT ? OFFSET ?"
        try:
            return self.db.execute(query, (limit, offset)) or []
        except Exception as e:
            logger.error(f"Failed to get all records: {e}")
            return []
    
    def update(self, id: int, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update a record."""
        if not data:
            logger.warning("Cannot update record with empty data")
            return None
        
        set_clause = ', '.join([f"{k} = ?" for k in data.keys()])
        query = f"UPDATE {self.table_name} SET {set_clause}, updated_at = ? WHERE id = ? RETURNING *"
        
        params = tuple(list(data.values()) + [datetime.now().isoformat(), id])
        try:
            result = self.db.execute(query, params)
            return result[0] if result else None
        except Exception as e:
            logger.error(f"Failed to update record {id}: {e}")
            return None
    
    def delete(self, id: int) -> bool:
        """Delete a record."""
        query = f"DELETE FROM {self.table_name} WHERE id = ?"
        try:
            self.db.execute(query, (id,))
            return True
        except Exception as e:
            logger.error(f"Failed to delete record {id}: {e}")
            return False
    
    def count(self) -> int:
        """Get total record count."""
        query = f"SELECT COUNT(*) as total FROM {self.table_name}"
        try:
            result = self.db.execute(query)
            return result[0]['total'] if result else 0
        except Exception as e:
            logger.error(f"Failed to count records: {e}")
            return 0
    
    def find_by_field(self, field: str, value: Any) -> List[Dict[str, Any]]:
        """Find records by a specific field value."""
        query = f"SELECT * FROM {self.table_name} WHERE {field} = ? ORDER BY created_at DESC"
        try:
            return self.db.execute(query, (value,)) or []
        except Exception as e:
            logger.error(f"Failed to find records by {field}={value}: {e}")
            return []
