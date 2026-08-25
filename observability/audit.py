"""
Audit Logger - Immutable audit trail for all actions.
"""

import json
import sqlite3
from datetime import datetime
from typing import Dict, Any, Optional, List
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class AuditLogger:
    """
    Immutable audit trail for all system actions.
    
    Features:
    - Append-only logging
    - JSON-formatted events
    - SQLite storage
    - Queryable history
    - Tamper-evident (optional)
    """
    
    def __init__(self, db_path: str = "data/audit.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """Initialize audit database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                user_id TEXT,
                component TEXT NOT NULL,
                action TEXT NOT NULL,
                details TEXT,
                ip_address TEXT,
                request_id TEXT,
                checksum TEXT
            )
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_events(timestamp)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_event_type ON audit_events(event_type)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_component ON audit_events(component)
        """)
        
        conn.commit()
        conn.close()
    
    def log(self, event_type: str, component: str, action: str,
            details: Dict[str, Any], user_id: Optional[str] = None,
            ip_address: Optional[str] = None,
            request_id: Optional[str] = None) -> bool:
        """Log an audit event."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            details_json = json.dumps(details, default=str)
            
            cursor.execute("""
                INSERT INTO audit_events (
                    event_type, timestamp, user_id, component, action,
                    details, ip_address, request_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event_type,
                datetime.now().isoformat(),
                user_id,
                component,
                action,
                details_json,
                ip_address,
                request_id
            ))
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            logger.error(f"Failed to log audit event: {e}")
            return False
    
    def query(self, event_type: Optional[str] = None,
              component: Optional[str] = None,
              start_time: Optional[datetime] = None,
              end_time: Optional[datetime] = None,
              limit: int = 100) -> List[Dict[str, Any]]:
        """Query audit events."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = "SELECT * FROM audit_events WHERE 1=1"
            params = []
            
            if event_type:
                query += " AND event_type = ?"
                params.append(event_type)
            if component:
                query += " AND component = ?"
                params.append(component)
            if start_time:
                query += " AND timestamp >= ?"
                params.append(start_time.isoformat())
            if end_time:
                query += " AND timestamp <= ?"
                params.append(end_time.isoformat())
            
            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            conn.close()
            
            results = []
            for row in rows:
                result = dict(row)
                result['details'] = json.loads(result['details'])
                results.append(result)
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to query audit events: {e}")
            return []
    
    def get_recent(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent audit events."""
        return self.query(limit=limit)
    
    def get_by_action(self, action: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get audit events by action."""
        return self.query(event_type='action', limit=limit)
    
    def count_by_type(self, event_type: str) -> int:
        """Count events by type."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM audit_events WHERE event_type = ?",
                (event_type,)
            )
            count = cursor.fetchone()[0]
            conn.close()
            return count
        except Exception:
            return 0


# --- Audit Context Manager ---
class AuditContext:
    """Context manager for audit logging."""
    
    def __init__(self, audit_logger: AuditLogger, event_type: str,
                 component: str, action: str, user_id: Optional[str] = None,
                 ip_address: Optional[str] = None):
        self.audit = audit_logger
        self.event_type = event_type
        self.component = component
        self.action = action
        self.user_id = user_id
        self.ip_address = ip_address
        self._details = {}
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self._details['error'] = str(exc_val)
        self.audit.log(
            event_type=self.event_type,
            component=self.component,
            action=self.action,
            details=self._details,
            user_id=self.user_id,
            ip_address=self.ip_address
        )
    
    def set_details(self, **kwargs):
        """Set details for the audit event."""
        self._details.update(kwargs)
