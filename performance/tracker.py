"""
Performance Tracker Module for Phase 32.

Track performance against targets over time with rolling metrics and trend analysis.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class PerformanceTracker:
    """
    Track performance against targets over time.
    
    This class provides functionality to record performance metrics,
    calculate rolling statistics, check trends, and generate tracking reports.
    """
    
    def __init__(self):
        self.history: Dict[str, List[Dict]] = {}
        
    def record_performance(
        self,
        date: str,
        metrics: Dict[str, float],
        market_regime: str,
        notes: Optional[str] = None
    ):
        """Record performance metrics for a specific date."""
        record = {
            'date': date,
            'metrics': metrics,
            'market_regime': market_regime,
            'notes': notes or '',
        }
        
        self.history.setdefault('records', []).append(record)
        logger.info(f"Performance recorded for {date}")
    
    def calculate_rolling_metrics(self, metric: str, window: int = 60) -> pd.Series:
        """Calculate rolling metrics over time."""
        records = self.history.get('records', [])
        if not records:
            return pd.Series()
        
        dates = [r['date'] for r in records]
        values = [r['metrics'].get(metric, np.nan) for r in records]
        
        return pd.Series(values, index=pd.to_datetime(dates)).rolling(window).mean()
    
    def check_trend(self, metric: str, window: int = 30) -> str:
        """Check if performance trend is improving or worsening."""
        series = self.calculate_rolling_metrics(metric, window)
        if len(series) < 10:
            return "insufficient_data"
        
        # Check recent vs earlier
        recent = series.iloc[-5:].mean()
        earlier = series.iloc[-20:-5].mean()
        
        if recent > earlier * 1.1:
            return "improving"
        elif recent < earlier * 0.9:
            return "worsening"
        else:
            return "stable"
    
    def compare_to_target(
        self,
        metric: str,
        target_value: float,
        current_metrics: Dict[str, float]
    ) -> Dict:
        """Compare current metrics to target."""
        if metric not in current_metrics:
            return {'status': 'unknown'}
        
        current = current_metrics[metric]
        gap = current - target_value
        percentage = current / target_value if target_value != 0 else 0
        
        return {
            'metric': metric,
            'current': current,
            'target': target_value,
            'gap': gap,
            'percentage_achieved': percentage,
            'status': 'exceeded' if gap > 0 else 'below' if gap < 0 else 'on_target',
        }
    
    def get_latest_metrics(self) -> Dict[str, float]:
        """Get the most recent recorded metrics."""
        records = self.history.get('records', [])
        if not records:
            return {}
        return records[-1]['metrics']
    
    def get_metrics_history(self, metric: str) -> pd.Series:
        """Get historical values for a specific metric."""
        records = self.history.get('records', [])
        if not records:
            return pd.Series()
        
        dates = [r['date'] for r in records]
        values = [r['metrics'].get(metric, np.nan) for r in records]
        
        return pd.Series(values, index=pd.to_datetime(dates))
    
    def calculate_statistics(self, metric: str) -> Dict:
        """Calculate statistics for a metric over recorded history."""
        series = self.get_metrics_history(metric)
        if len(series) == 0:
            return {'error': 'No data available'}
        
        return {
            'mean': series.mean(),
            'std': series.std(),
            'min': series.min(),
            'max': series.max(),
            'median': series.median(),
            'count': len(series),
        }
    
    def generate_tracking_report(self) -> str:
        """Generate a performance tracking report."""
        records = self.history.get('records', [])
        if not records:
            return "No performance data recorded"
        
        lines = [
            "=" * 80,
            "PERFORMANCE TRACKING REPORT",
            "=" * 80,
            "",
            f"Total Records: {len(records)}",
            f"Date Range: {records[0]['date']} to {records[-1]['date']}",
            "",
            "RECENT PERFORMANCE:",
            "-" * 40,
        ]
        
        # Last 5 records
        for record in records[-5:]:
            metrics_str = ", ".join([f"{k}: {v:.2f}" for k, v in record['metrics'].items() if isinstance(v, (int, float))])
            lines.append(f"{record['date']} ({record['market_regime']}): {metrics_str}")
        
        lines.extend([
            "",
            "TRENDS:",
            "-" * 40,
        ])
        
        # Check trends for key metrics
        key_metrics = ['sharpe_ratio', 'max_drawdown', 'win_rate']
        for metric in key_metrics:
            trend = self.check_trend(metric)
            lines.append(f"{metric}: {trend}")
        
        lines.extend([
            "",
            "STATISTICS:",
            "-" * 40,
        ])
        
        # Statistics for key metrics
        for metric in key_metrics:
            stats = self.calculate_statistics(metric)
            if 'error' not in stats:
                lines.append(f"{metric}:")
                lines.append(f"  Mean: {stats['mean']:.3f}, Std: {stats['std']:.3f}")
                lines.append(f"  Min: {stats['min']:.3f}, Max: {stats['max']:.3f}")
        
        lines.extend([
            "",
            "=" * 80,
        ])
        
        return "\n".join(lines)
    
    def export_to_csv(self, filepath: str):
        """Export performance history to CSV."""
        records = self.history.get('records', [])
        if not records:
            logger.warning("No records to export")
            return False
        
        # Flatten records into DataFrame
        rows = []
        for record in records:
            row = {
                'date': record['date'],
                'market_regime': record['market_regime'],
                'notes': record['notes'],
            }
            row.update(record['metrics'])
            rows.append(row)
        
        df = pd.DataFrame(rows)
        df.to_csv(filepath, index=False)
        logger.info(f"Exported {len(rows)} records to {filepath}")
        return True
    
    def import_from_csv(self, filepath: str):
        """Import performance history from CSV."""
        try:
            df = pd.read_csv(filepath)
            
            for _, row in df.iterrows():
                date = str(row['date'])
                market_regime = row.get('market_regime', 'unknown')
                notes = row.get('notes', '')
                
                # Extract metrics (all columns except date, market_regime, notes)
                metrics = {}
                for col in df.columns:
                    if col not in ['date', 'market_regime', 'notes']:
                        metrics[col] = row[col]
                
                self.record_performance(date, metrics, market_regime, notes)
            
            logger.info(f"Imported {len(df)} records from {filepath}")
            return True
        except Exception as e:
            logger.error(f"Failed to import from {filepath}: {e}")
            return False
