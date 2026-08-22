"""
Persistence Manager - Central state persistence system.

Provides atomic, versioned, and validated state persistence for all trading components.
Supports automatic backups, checksum validation, and graceful error handling.
"""

import json
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
import logging
import threading
import hashlib

logger = logging.getLogger(__name__)


class PersistenceManager:
    """Centralized persistence manager for all trading state."""
    
    STATE_DIR = "state"
    BACKUP_DIR = "backups"
    STATE_VERSION = "1.0.0"
    
    # File names
    TRADING_STATE = "trading_state.json"
    RISK_STATE = "risk_state.json"
    CIRCUIT_BREAKER_STATE = "circuit_breaker_state.json"
    KILL_SWITCH_STATE = "kill_switch_state.json"
    STRATEGY_STATE = "strategy_state.json"
    ML_STATE = "ml_state.json"
    SENTIMENT_STATE = "sentiment_state.json"
    RECONCILIATION_STATE = "reconciliation_state.json"
    
    def __init__(self, base_dir: str = "data"):
        self.base_dir = Path(base_dir)
        self.state_dir = self.base_dir / self.STATE_DIR
        self.backup_dir = self.base_dir / self.BACKUP_DIR
        
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        self._lock = threading.Lock()
        logger.info(f"PersistenceManager initialized (state: {self.state_dir})")
    
    def save_state(self, state_type: str, data: Dict[str, Any]) -> bool:
        """Save state atomically with backup and checksum."""
        with self._lock:
            try:
                filename = self._get_filename(state_type)
                filepath = self.state_dir / filename
                
                # Create backup if file exists
                if filepath.exists():
                    self._create_backup(state_type)
                
                # Prepare data with metadata
                data_with_meta = {
                    'version': self.STATE_VERSION,
                    'timestamp': datetime.now().isoformat(),
                    'state_type': state_type,
                    'data': data,
                    'checksum': self._calculate_checksum(data)
                }
                
                # Atomic write: write to temp file, then rename
                temp_fd, temp_path = tempfile.mkstemp(
                    suffix='.json', prefix=f'{state_type}_', dir=str(self.state_dir)
                )
                
                with os.fdopen(temp_fd, 'w') as f:
                    json.dump(data_with_meta, f, indent=2, default=str)
                
                os.replace(temp_path, filepath)
                logger.info(f"State saved: {state_type}")
                return True
                
            except Exception as e:
                logger.error(f"Failed to save state {state_type}: {e}")
                return False
    
    def load_state(self, state_type: str) -> Optional[Dict[str, Any]]:
        """Load state from disk with validation."""
        with self._lock:
            try:
                filename = self._get_filename(state_type)
                filepath = self.state_dir / filename
                
                if not filepath.exists():
                    logger.debug(f"State file not found: {state_type}")
                    return None
                
                with open(filepath, 'r') as f:
                    data = json.load(f)
                
                # Validate structure
                if not self._validate_state(data):
                    logger.error(f"State validation failed: {state_type}")
                    return None
                
                # Verify checksum
                if data.get('checksum') != self._calculate_checksum(data.get('data', {})):
                    logger.error(f"Checksum mismatch: {state_type}")
                    return None
                
                logger.info(f"State loaded: {state_type}")
                return data.get('data', {})
                
            except json.JSONDecodeError as e:
                logger.error(f"Corrupted state file {state_type}: {e}")
                return None
            except Exception as e:
                logger.error(f"Failed to load state {state_type}: {e}")
                return None
    
    def delete_state(self, state_type: str) -> bool:
        """Delete state file."""
        with self._lock:
            try:
                filename = self._get_filename(state_type)
                filepath = self.state_dir / filename
                if filepath.exists():
                    os.remove(filepath)
                    logger.info(f"State deleted: {state_type}")
                return True
            except Exception as e:
                logger.error(f"Failed to delete state {state_type}: {e}")
                return False
    
    def _get_filename(self, state_type: str) -> str:
        """Map state type to filename."""
        mapping = {
            'trading': self.TRADING_STATE,
            'risk': self.RISK_STATE,
            'circuit_breaker': self.CIRCUIT_BREAKER_STATE,
            'kill_switch': self.KILL_SWITCH_STATE,
            'strategy': self.STRATEGY_STATE,
            'ml': self.ML_STATE,
            'sentiment': self.SENTIMENT_STATE,
            'reconciliation': self.RECONCILIATION_STATE,
        }
        return mapping.get(state_type, f"{state_type}_state.json")
    
    def _create_backup(self, state_type: str) -> None:
        """Create timestamped backup before overwriting."""
        try:
            filename = self._get_filename(state_type)
            source = self.state_dir / filename
            if not source.exists():
                return
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_path = self.backup_dir / f"{state_type}_{timestamp}.json"
            shutil.copy2(source, backup_path)
            self._clean_backups(state_type, max_backups=10)
            logger.debug(f"Backup created: {backup_path}")
        except Exception as e:
            logger.warning(f"Failed to create backup: {e}")
    
    def _clean_backups(self, state_type: str, max_backups: int = 10) -> None:
        """Keep only recent backups."""
        try:
            backups = sorted(self.backup_dir.glob(f"{state_type}_*.json"))
            if len(backups) > max_backups:
                for backup in backups[:-max_backups]:
                    backup.unlink()
                logger.debug(f"Cleaned old backups for {state_type}")
        except Exception as e:
            logger.warning(f"Failed to clean backups: {e}")
    
    def _validate_state(self, data: Dict[str, Any]) -> bool:
        """Validate state structure."""
        required = ['version', 'timestamp', 'state_type', 'data', 'checksum']
        return all(field in data for field in required)
    
    def _calculate_checksum(self, data: Dict[str, Any]) -> str:
        """Calculate SHA256 checksum for data integrity."""
        sorted_data = json.dumps(data, sort_keys=True).encode()
        return hashlib.sha256(sorted_data).hexdigest()[:16]
    
    def get_all_state(self) -> Dict[str, Any]:
        """Get all persisted state."""
        state_types = ['trading', 'risk', 'circuit_breaker', 'kill_switch',
                       'strategy', 'ml', 'sentiment', 'reconciliation']
        result = {}
        for state_type in state_types:
            data = self.load_state(state_type)
            if data is not None:
                result[state_type] = data
        return result
    
    def clear_all_state(self) -> None:
        """Clear all persisted state (use with caution)."""
        state_types = ['trading', 'risk', 'circuit_breaker', 'kill_switch',
                       'strategy', 'ml', 'sentiment', 'reconciliation']
        for state_type in state_types:
            self.delete_state(state_type)
        logger.warning("All state cleared")
    
    def health_check(self) -> bool:
        """Check persistence system health."""
        try:
            test_data = {'health_check': True}
            result = self.save_state('_health', test_data)
            if result:
                loaded = self.load_state('_health')
                if loaded == test_data:
                    self.delete_state('_health')
                    return True
            return False
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
