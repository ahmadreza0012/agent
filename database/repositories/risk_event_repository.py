"""
Risk Event Repository - CRUD for risk events.

Stores all risk-related events for audit, analysis, and compliance.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
import logging

from .base_repository import BaseRepository
from ..database_manager import DatabaseManager

logger = logging.getLogger(__name__)


class RiskEventRepository(BaseRepository):
    """Repository for risk events."""
    
    def __init__(self, db_manager: DatabaseManager):
        super().__init__(db_manager)
    
    def _ensure_table(self) -> None:
        """Create risk_events table if not exists."""
        query = """
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
        )
        """
        
        # Create indexes for efficient queries
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_risk_events_timestamp ON risk_events(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_risk_events_severity ON risk_events(severity)"
        ]
        
        self.db.execute(query)
        for index in indexes:
            self.db.execute(index)
        
        logger.info("Risk events table ensured")
    
    def create_event(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create a risk event."""
        if 'created_at' not in data:
            data['created_at'] = datetime.now().isoformat()
        return self.create(data)
    
    def get_by_severity(self, severity: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get events by severity."""
        query = f"""
            SELECT * FROM {self.table_name} 
            WHERE severity = ? 
            ORDER BY timestamp DESC 
            LIMIT ?
        """
        try:
            return self.db.execute(query, (severity, limit)) or []
        except Exception as e:
            logger.error(f"Failed to get events by severity {severity}: {e}")
            return []
    
    def get_unresolved(self) -> List[Dict[str, Any]]:
        """Get unresolved events."""
        query = f"""
            SELECT * FROM {self.table_name} 
            WHERE resolved_at IS NULL 
            ORDER BY timestamp DESC
        """
        try:
            return self.db.execute(query) or []
        except Exception as e:
            logger.error(f"Failed to get unresolved events: {e}")
            return []
    
    def resolve_event(self, event_id: int, resolved_by: str) -> Optional[Dict[str, Any]]:
        """Resolve a risk event."""
        data = {
            'resolved_at': datetime.now().isoformat(),
            'resolved_by': resolved_by
        }
        return self.update(event_id, data)
    
    def get_recent_events(self, hours: int = 24, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent events within specified hours."""
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
            logger.error(f"Failed to get recent events: {e}")
            return []
    
    def get_events_by_type(self, event_type: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get events by type."""
        query = f"""
            SELECT * FROM {self.table_name} 
            WHERE event_type = ? 
            ORDER BY timestamp DESC 
            LIMIT ?
        """
        try:
            return self.db.execute(query, (event_type, limit)) or []
        except Exception as e:
            logger.error(f"Failed to get events by type {event_type}: {e}")
            return []
    
    def count_unresolved_by_severity(self, severity: str) -> int:
        """Count unresolved events by severity."""
        query = f"""
            SELECT COUNT(*) as total 
            FROM {self.table_name} 
            WHERE severity = ? AND resolved_at IS NULL
        """
        try:
            result = self.db.execute(query, (severity,))
            return result[0]['total'] if result else 0
        except Exception as e:
            logger.error(f"Failed to count unresolved events: {e}")
            return 0
    
    def get_critical_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get critical severity events."""
        return self.get_by_severity('critical', limit)
    
    def get_warning_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get warning severity events."""
        return self.get_by_severity('warning', limit)
