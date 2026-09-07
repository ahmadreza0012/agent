"""
Database Manager for Agent Trading System
Handles persistent storage of cycle results, strategy track records, and metrics using SQLite.
"""

import sqlite3
import json
import os
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = os.environ.get("AGENT_DB_PATH", "/app/data/agent_history.db")

class AgentDB:
    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        self._ensure_dir_exists()
        self._init_tables()
    
    def _ensure_dir_exists(self):
        """Create the directory for the database file if it doesn't exist."""
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            try:
                os.makedirs(db_dir, exist_ok=True)
                logger.info(f"Created database directory: {db_dir}")
            except Exception as e:
                logger.warning(f"Failed to create database directory {db_dir}: {e}")
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection with row factory enabled."""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _init_tables(self):
        """Create tables if they don't exist."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Cycle results table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS cycle_results (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        cycle_number INTEGER UNIQUE NOT NULL,
                        timestamp TEXT NOT NULL,
                        regime TEXT,
                        sentiment_score REAL,
                        decision TEXT,
                        sleep_hours REAL,
                        duration_seconds REAL,
                        mean_monthly_return REAL,
                        max_drawdown REAL,
                        sharpe_ratio REAL,
                        pct_positive_months REAL,
                        n_folds INTEGER,
                        fold_total_returns TEXT,
                        fold_monthly_returns TEXT,
                        final_blend_weights TEXT,
                        final_asset_weights TEXT,
                        black_litterman_views TEXT,
                        asset_sentiment_scores TEXT,
                        warnings TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Strategy track records table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS strategy_records (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        cycle_number INTEGER NOT NULL,
                        strategy_name TEXT NOT NULL,
                        return_pct REAL,
                        volatility REAL,
                        sharpe REAL,
                        track_record_size INTEGER,
                        FOREIGN KEY (cycle_number) REFERENCES cycle_results(cycle_number)
                    )
                """)
                
                # Create indexes for faster lookups
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_cycle_number ON cycle_results(cycle_number)
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_strategy_cycle ON strategy_records(cycle_number, strategy_name)
                """)
                
                conn.commit()
                logger.info("Database tables initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize database tables: {e}")
            raise
    
    def save_cycle_result(self, cycle_data: Dict[str, Any]):
        """
        Save a complete cycle result including metrics, strategy records, and weights.
        
        Args:
            cycle_data: Dictionary containing all cycle information
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Extract cycle metadata and metrics
                cycle_number = cycle_data.get('cycle_number')
                timestamp = cycle_data.get('timestamp', datetime.now().isoformat())
                regime = cycle_data.get('regime')
                sentiment_score = cycle_data.get('sentiment_score')
                decision = cycle_data.get('decision')
                sleep_hours = cycle_data.get('sleep_hours')
                duration_seconds = cycle_data.get('duration_seconds')
                
                # Extract performance metrics
                metrics = cycle_data.get('metrics', {})
                mean_monthly_return = metrics.get('mean_monthly_return')
                max_drawdown = metrics.get('max_drawdown')
                sharpe_ratio = metrics.get('sharpe_ratio')
                pct_positive_months = metrics.get('pct_positive_months')
                n_folds = metrics.get('n_folds')
                
                # Convert lists to JSON strings
                fold_total_returns = json.dumps(metrics.get('_fold_total_returns', []))
                fold_monthly_returns = json.dumps(metrics.get('_fold_monthly_returns', []))
                
                # Extract weights and other data
                final_blend_weights = json.dumps(cycle_data.get('final_blend_weights', {}))
                final_asset_weights = json.dumps(cycle_data.get('final_asset_weights', {}))
                black_litterman_views = json.dumps(cycle_data.get('black_litterman_views', {}))
                asset_sentiment_scores = json.dumps(cycle_data.get('asset_sentiment_scores', {}))
                warnings = json.dumps(cycle_data.get('warnings', []))
                
                # Insert or replace cycle result
                cursor.execute("""
                    INSERT OR REPLACE INTO cycle_results (
                        cycle_number, timestamp, regime, sentiment_score, decision,
                        sleep_hours, duration_seconds, mean_monthly_return, max_drawdown,
                        sharpe_ratio, pct_positive_months, n_folds, fold_total_returns,
                        fold_monthly_returns, final_blend_weights, final_asset_weights,
                        black_litterman_views, asset_sentiment_scores, warnings
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    cycle_number, timestamp, regime, sentiment_score, decision,
                    sleep_hours, duration_seconds, mean_monthly_return, max_drawdown,
                    sharpe_ratio, pct_positive_months, n_folds, fold_total_returns,
                    fold_monthly_returns, final_blend_weights, final_asset_weights,
                    black_litterman_views, asset_sentiment_scores, warnings
                ))
                
                # Insert strategy records
                strategy_records = cycle_data.get('strategy_records', [])
                for record in strategy_records:
                    cursor.execute("""
                        INSERT INTO strategy_records (
                            cycle_number, strategy_name, return_pct, volatility, sharpe, track_record_size
                        ) VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        cycle_number,
                        record.get('strategy_name'),
                        record.get('return_pct'),
                        record.get('volatility'),
                        record.get('sharpe'),
                        record.get('track_record_size')
                    ))
                
                conn.commit()
                logger.info(f"Saved cycle {cycle_number} to database (decision: {decision})")
                
        except Exception as e:
            logger.error(f"Failed to save cycle result to database: {e}")
            raise
    
    def load_strategy_history(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Load historical strategy performance data grouped by strategy name.
        
        Returns:
            Dictionary mapping strategy names to lists of historical records
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT strategy_name, return_pct, volatility, sharpe, track_record_size, cycle_number
                    FROM strategy_records
                    ORDER BY cycle_number ASC
                """)
                
                history = {}
                for row in cursor.fetchall():
                    strategy_name = row['strategy_name']
                    if strategy_name not in history:
                        history[strategy_name] = []
                    
                    history[strategy_name].append({
                        'cycle_number': row['cycle_number'],
                        'return_pct': row['return_pct'],
                        'volatility': row['volatility'],
                        'sharpe': row['sharpe'],
                        'track_record_size': row['track_record_size']
                    })
                
                logger.info(f"Loaded strategy history for {len(history)} strategies from database")
                return history
                
        except Exception as e:
            logger.error(f"Failed to load strategy history from database: {e}")
            return {}
    
    def get_recent_cycles(self, n: int = 10) -> List[Dict[str, Any]]:
        """
        Get the most recent N cycle results.
        
        Args:
            n: Number of recent cycles to retrieve
            
        Returns:
            List of cycle result dictionaries
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM cycle_results
                    ORDER BY cycle_number DESC
                    LIMIT ?
                """, (n,))
                
                cycles = []
                for row in cursor.fetchall():
                    cycle = dict(row)
                    # Parse JSON fields
                    for json_field in ['fold_total_returns', 'fold_monthly_returns', 
                                     'final_blend_weights', 'final_asset_weights',
                                     'black_litterman_views', 'asset_sentiment_scores', 'warnings']:
                        if cycle.get(json_field):
                            try:
                                cycle[json_field] = json.loads(cycle[json_field])
                            except:
                                cycle[json_field] = {}
                    
                    cycles.append(cycle)
                
                logger.info(f"Retrieved {len(cycles)} recent cycles from database")
                return cycles
                
        except Exception as e:
            logger.error(f"Failed to get recent cycles from database: {e}")
            return []
    
    def get_cycle_count(self) -> int:
        """Get total number of cycles stored in database."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) as count FROM cycle_results")
                result = cursor.fetchone()
                return result['count'] if result else 0
        except Exception as e:
            logger.error(f"Failed to get cycle count: {e}")
            return 0
    
    def get_strategy_summary(self) -> Dict[str, Dict[str, Any]]:
        """
        Get summary statistics for each strategy across all recorded cycles.
        
        Returns:
            Dictionary with strategy names as keys and summary stats as values
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT strategy_name, 
                           COUNT(*) as record_count,
                           AVG(return_pct) as avg_return,
                           AVG(volatility) as avg_volatility,
                           AVG(sharpe) as avg_sharpe,
                           MAX(track_record_size) as max_track_size
                    FROM strategy_records
                    GROUP BY strategy_name
                """)
                
                summary = {}
                for row in cursor.fetchall():
                    summary[row['strategy_name']] = {
                        'record_count': row['record_count'],
                        'avg_return': row['avg_return'],
                        'avg_volatility': row['avg_volatility'],
                        'avg_sharpe': row['avg_sharpe'],
                        'max_track_size': row['max_track_size']
                    }
                
                logger.info(f"Generated strategy summary for {len(summary)} strategies")
                return summary
                
        except Exception as e:
            logger.error(f"Failed to get strategy summary: {e}")
            return {}
