"""
Phase 39: Post-Launch Monitoring & Optimization

Optimization journal for tracking all optimization decisions.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class OptimizationEntry:
    """Record of an optimization decision."""
    id: str
    timestamp: str
    version: int
    action: str
    category: str  # 'risk', 'strategy', 'model', 'execution', 'parameter'
    rationale: str
    expected_impact: Dict[str, Any]
    actual_impact: Optional[Dict[str, Any]] = None
    status: str = 'pending'  # 'pending', 'evaluated', 'reverted'
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'timestamp': self.timestamp,
            'version': self.version,
            'action': self.action,
            'category': self.category,
            'rationale': self.rationale,
            'expected_impact': self.expected_impact,
            'actual_impact': self.actual_impact,
            'status': self.status,
            'metadata': self.metadata
        }


class OptimizationJournal:
    """
    Track all optimization decisions and their outcomes.
    
    Provides audit trail for system changes and learnings.
    """
    
    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = storage_path or 'results/optimization_journal.json'
        self.entries: List[OptimizationEntry] = []
        self.current_version = 1
        
        # Load existing entries if available
        self._load_entries()
        
        logger.info(f"OptimizationJournal initialized - {len(self.entries)} entries loaded")
    
    def _load_entries(self):
        """Load entries from storage."""
        path = Path(self.storage_path)
        if path.exists():
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                    self.entries = [
                        OptimizationEntry(**entry) for entry in data.get('entries', [])
                    ]
                    self.current_version = data.get('current_version', 1)
                logger.info(f"Loaded {len(self.entries)} entries from {self.storage_path}")
            except Exception as e:
                logger.error(f"Failed to load journal: {e}")
    
    def _save_entries(self):
        """Save entries to storage."""
        data = {
            'entries': [e.to_dict() for e in self.entries],
            'current_version': self.current_version,
            'last_updated': datetime.utcnow().isoformat()
        }
        
        # Ensure directory exists
        Path(self.storage_path).parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.storage_path, 'w') as f:
            json.dump(data, f, indent=2, default=str)
    
    def record_decision(self, action: str, category: str, rationale: str,
                       expected_impact: Dict[str, Any], 
                       metadata: Optional[Dict] = None) -> str:
        """Record an optimization decision."""
        
        entry_id = f"opt_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{category}"
        
        entry = OptimizationEntry(
            id=entry_id,
            timestamp=datetime.utcnow().isoformat(),
            version=self.current_version,
            action=action,
            category=category,
            rationale=rationale,
            expected_impact=expected_impact,
            metadata=metadata or {}
        )
        
        self.entries.append(entry)
        self._save_entries()
        
        logger.info(f"Recorded optimization decision: {entry_id} - {action}")
        return entry_id
    
    def update_impact(self, entry_id: str, actual_impact: Dict[str, Any], 
                     status: str = 'evaluated'):
        """Update the actual impact of a decision."""
        
        for entry in self.entries:
            if entry.id == entry_id:
                entry.actual_impact = actual_impact
                entry.status = status
                self._save_entries()
                
                logger.info(f"Updated impact for {entry_id}: status={status}")
                return True
        
        logger.warning(f"Entry {entry_id} not found")
        return False
    
    def get_pending_decisions(self) -> List[OptimizationEntry]:
        """Get all pending decisions awaiting evaluation."""
        return [e for e in self.entries if e.status == 'pending']
    
    def get_evaluated_decisions(self, category: Optional[str] = None) -> List[OptimizationEntry]:
        """Get evaluated decisions, optionally filtered by category."""
        entries = [e for e in self.entries if e.status == 'evaluated']
        if category:
            entries = [e for e in entries if e.category == category]
        return entries
    
    def analyze_success_rate(self, category: Optional[str] = None) -> Dict[str, Any]:
        """Analyze success rate of optimization decisions."""
        evaluated = self.get_evaluated_decisions(category)
        
        if not evaluated:
            return {'success_rate': 0.0, 'total': 0}
        
        successes = 0
        for entry in evaluated:
            if entry.actual_impact and self._is_successful(entry):
                successes += 1
        
        success_rate = successes / len(evaluated)
        
        return {
            'success_rate': success_rate,
            'total_decisions': len(evaluated),
            'successful': successes,
            'unsuccessful': len(evaluated) - successes,
            'by_category': self._analyze_by_category(evaluated)
        }
    
    def _is_successful(self, entry: OptimizationEntry) -> bool:
        """Determine if an optimization was successful."""
        if not entry.actual_impact:
            return False
        
        expected = entry.expected_impact
        actual = entry.actual_impact
        
        # Check if actual impact meets expectations
        for key, expected_value in expected.items():
            if key in actual:
                actual_value = actual[key]
                
                # Handle different comparison types
                if isinstance(expected_value, (int, float)):
                    # Allow 20% tolerance
                    if abs(actual_value - expected_value) > abs(expected_value) * 0.2:
                        return False
        
        return True
    
    def _analyze_by_category(self, entries: List[OptimizationEntry]) -> Dict[str, Dict]:
        """Analyze success rate by category."""
        categories = set(e.category for e in entries)
        
        results = {}
        for category in categories:
            cat_entries = [e for e in entries if e.category == category]
            successes = sum(1 for e in cat_entries if self._is_successful(e))
            
            results[category] = {
                'total': len(cat_entries),
                'successful': successes,
                'success_rate': successes / len(cat_entries) if cat_entries else 0.0
            }
        
        return results
    
    def generate_report(self) -> str:
        """Generate optimization report."""
        report = "# OPTIMIZATION JOURNAL REPORT\n\n"
        report += f"Generated: {datetime.utcnow().isoformat()}\n"
        report += f"Total Entries: {len(self.entries)}\n"
        report += f"Current Version: {self.current_version}\n\n"
        
        # Summary statistics
        summary = self.analyze_success_rate()
        report += "## SUMMARY\n\n"
        report += f"- Overall Success Rate: {summary['success_rate']:.2%}\n"
        report += f"- Total Evaluated: {summary['total_decisions']}\n"
        report += f"- Successful: {summary['successful']}\n"
        report += f"- Unsuccessful: {summary['unsuccessful']}\n\n"
        
        # By category
        if summary.get('by_category'):
            report += "## BY CATEGORY\n\n"
            for category, stats in summary['by_category'].items():
                report += f"### {category.capitalize()}\n"
                report += f"- Success Rate: {stats['success_rate']:.2%}\n"
                report += f"- Total: {stats['total']}\n\n"
        
        # Recent decisions
        report += "## RECENT DECISIONS\n\n"
        for entry in reversed(self.entries[-10:]):
            report += f"### {entry.id}\n"
            report += f"- **Timestamp**: {entry.timestamp}\n"
            report += f"- **Category**: {entry.category}\n"
            report += f"- **Action**: {entry.action}\n"
            report += f"- **Rationale**: {entry.rationale}\n"
            report += f"- **Expected Impact**: {entry.expected_impact}\n"
            
            if entry.actual_impact:
                report += f"- **Actual Impact**: {entry.actual_impact}\n"
            
            report += f"- **Status**: {entry.status}\n\n"
        
        return report
    
    def increment_version(self):
        """Increment the version number."""
        self.current_version += 1
        self._save_entries()
        logger.info(f"Version incremented to {self.current_version}")
    
    def export_json(self, filepath: str):
        """Export journal to JSON file."""
        data = {
            'entries': [e.to_dict() for e in self.entries],
            'current_version': self.current_version,
            'export_timestamp': datetime.utcnow().isoformat()
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        
        logger.info(f"Journal exported to {filepath}")


def init_journal(storage_path: Optional[str] = None) -> OptimizationJournal:
    """Initialize optimization journal."""
    return OptimizationJournal(storage_path)


if __name__ == "__main__":
    # Demo usage
    journal = OptimizationJournal('results/demo_journal.json')
    
    # Record some sample decisions
    journal.record_decision(
        action="Increase max_drawdown threshold from 15% to 20%",
        category="risk",
        rationale="System showing stable performance with room for increased exposure",
        expected_impact={'sharpe': 0.8, 'max_dd': 0.18},
        metadata={'previous_value': 0.15, 'new_value': 0.20}
    )
    
    journal.record_decision(
        action="Reduce momentum strategy weight from 0.4 to 0.3",
        category="strategy",
        rationale="Momentum underperforming in current regime",
        expected_impact={'sharpe': 0.6, 'turnover': 0.8},
        metadata={'strategy': 'momentum', 'old_weight': 0.4, 'new_weight': 0.3}
    )
    
    # Update impact for first decision
    entries = journal.get_pending_decisions()
    if entries:
        journal.update_impact(
            entries[0].id,
            actual_impact={'sharpe': 0.75, 'max_dd': 0.17},
            status='evaluated'
        )
    
    # Generate report
    print(journal.generate_report())
    
    # Analyze success rate
    print("\n=== Success Rate Analysis ===")
    analysis = journal.analyze_success_rate()
    print(json.dumps(analysis, indent=2))
