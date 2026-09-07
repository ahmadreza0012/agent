"""
Auto Logger Module - Self-Improving Trading Bot
================================================
Records all trading events, errors, and performance metrics for automatic analysis.
"""

import logging
import json
import os
from datetime import datetime
from typing import Dict, Any, List
import sys

class AutoLogger:
    """Automatic logger that records structured data for self-analysis."""
    
    def __init__(self, log_file: str = "trading_log.jsonl", metrics_file: str = "performance_metrics.json"):
        self.log_file = log_file
        self.metrics_file = metrics_file
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.cycle_data = []
        self.errors = []
        self.performance_history = []
        
        # Setup file handler for detailed logs
        self.file_handler = logging.FileHandler("detailed_trading.log")
        self.file_handler.setLevel(logging.DEBUG)
        self.file_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        
        # Get root logger and add our handler
        self.logger = logging.getLogger()
        self.logger.addHandler(self.file_handler)
        self.logger.setLevel(logging.INFO)
        
        # Load existing metrics if available
        self.load_metrics()
    
    def log_event(self, event_type: str, data: Dict[str, Any]):
        """Log a structured event to JSONL file."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "session_id": self.session_id,
            "event_type": event_type,
            "data": data
        }
        
        # Append to JSONL file
        with open(self.log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")
        
        # Also log to standard logger
        self.logger.info(f"[{event_type}] {json.dumps(data)}")
    
    def log_cycle_start(self, cycle_number: int):
        """Log the start of a trading cycle."""
        self.log_event("cycle_start", {
            "cycle_number": cycle_number,
            "timestamp": datetime.now().isoformat()
        })
    
    def log_cycle_end(self, cycle_number: int, results: Dict[str, Any]):
        """Log the end of a trading cycle with results."""
        self.log_event("cycle_end", {
            "cycle_number": cycle_number,
            "results": results,
            "duration_seconds": results.get("duration_seconds", 0)
        })
        
        # Store in memory for analysis
        self.cycle_data.append({
            "cycle_number": cycle_number,
            "timestamp": datetime.now().isoformat(),
            "results": results
        })
        
        # Update performance history
        if "backtest_results" in results:
            self.performance_history.append(results["backtest_results"])
            self.save_metrics()
    
    def log_error(self, error_type: str, error_message: str, context: Dict[str, Any] = None):
        """Log an error with context."""
        error_entry = {
            "timestamp": datetime.now().isoformat(),
            "error_type": error_type,
            "error_message": error_message,
            "context": context or {}
        }
        self.errors.append(error_entry)
        self.log_event("error", error_entry)
    
    def log_decision(self, decision_type: str, reason: str, metrics: Dict[str, Any]):
        """Log a trading decision with reasoning."""
        self.log_event("decision", {
            "decision_type": decision_type,
            "reason": reason,
            "metrics": metrics
        })
    
    def log_strategy_performance(self, strategy_name: str, metrics: Dict[str, Any]):
        """Log performance metrics for a specific strategy."""
        self.log_event("strategy_performance", {
            "strategy_name": strategy_name,
            "metrics": metrics
        })
    
    def load_metrics(self):
        """Load existing performance metrics from file."""
        if os.path.exists(self.metrics_file):
            try:
                with open(self.metrics_file, "r") as f:
                    data = json.load(f)
                    self.performance_history = data.get("history", [])
                    self.errors = data.get("errors", [])
                    self.cycle_data = data.get("cycles", [])
            except Exception as e:
                self.logger.warning(f"Failed to load metrics: {e}")
    
    def save_metrics(self):
        """Save current metrics to file."""
        data = {
            "last_updated": datetime.now().isoformat(),
            "session_id": self.session_id,
            "total_cycles": len(self.cycle_data),
            "total_errors": len(self.errors),
            "history": self.performance_history,
            "errors": self.errors,
            "cycles": self.cycle_data
        }
        
        with open(self.metrics_file, "w") as f:
            json.dump(data, f, indent=2)
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of all logged data."""
        if not self.performance_history:
            return {"status": "no_data"}
        
        # Calculate aggregate statistics
        returns = [h.get("mean_monthly_return", 0) for h in self.performance_history]
        drawdowns = [h.get("worst_max_drawdown", 0) for h in self.performance_history]
        sharpes = [h.get("mean_sharpe", 0) for h in self.performance_history]
        
        return {
            "total_cycles": len(self.cycle_data),
            "total_errors": len(self.errors),
            "avg_monthly_return": sum(returns) / len(returns) if returns else 0,
            "avg_max_drawdown": sum(drawdowns) / len(drawdowns) if drawdowns else 0,
            "avg_sharpe": sum(sharpes) / len(sharpes) if sharpes else 0,
            "best_return": max(returns) if returns else 0,
            "worst_drawdown": min(drawdowns) if drawdowns else 0,
            "profitable_cycles": sum(1 for r in returns if r > 0),
            "loss_cycles": sum(1 for r in returns if r <= 0)
        }


# Global instance
auto_logger = AutoLogger()

def get_logger() -> AutoLogger:
    """Get the global auto logger instance."""
    return auto_logger
