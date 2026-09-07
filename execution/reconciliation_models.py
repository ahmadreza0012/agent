"""
Reconciliation Data Models - Core data structures for position reconciliation.

This module defines the data models used for reconciling local state with exchange state.
Exchange state is the SOLE source of truth. Local state must adapt to it.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional


class DiscrepancySeverity(Enum):
    """Severity levels for reconciliation discrepancies."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class DiscrepancyType(Enum):
    """Types of reconciliation discrepancies."""
    POSITION_SIZE_MISMATCH = "position_size_mismatch"
    POSITION_ENTRY_PRICE_MISMATCH = "position_entry_price_mismatch"
    POSITION_MISSING_LOCAL = "position_missing_local"
    POSITION_MISSING_EXCHANGE = "position_missing_exchange"
    BALANCE_TOTAL_MISMATCH = "balance_total_mismatch"
    BALANCE_FREE_MISMATCH = "balance_free_mismatch"
    BALANCE_MISSING_LOCAL = "balance_missing_local"
    BALANCE_MISSING_EXCHANGE = "balance_missing_exchange"
    ORDER_STATUS_MISMATCH = "order_status_mismatch"
    ORDER_FILLED_AMOUNT_MISMATCH = "order_filled_amount_mismatch"
    ORDER_MISSING_LOCAL = "order_missing_local"
    ORDER_MISSING_EXCHANGE = "order_missing_exchange"


@dataclass
class Discrepancy:
    """Represents a single discrepancy between local and exchange state."""
    id: str
    type: DiscrepancyType
    severity: DiscrepancySeverity
    local_data: dict
    exchange_data: Optional[dict]
    description: str
    suggested_action: str
    timestamp: datetime = field(default_factory=datetime.now)
    resolved: bool = False
    resolution: Optional[str] = None


@dataclass
class ReconciliationResult:
    """Result of a reconciliation operation."""
    timestamp: datetime = field(default_factory=datetime.now)
    is_consistent: bool = True
    discrepancies: List[Discrepancy] = field(default_factory=list)
    critical_count: int = 0
    warning_count: int = 0
    
    def add_discrepancy(self, d: Discrepancy):
        """Add a discrepancy and update counts."""
        self.discrepancies.append(d)
        if d.severity == DiscrepancySeverity.CRITICAL:
            self.critical_count += 1
            self.is_consistent = False
        elif d.severity == DiscrepancySeverity.WARNING:
            self.warning_count += 1

    @property
    def has_critical(self) -> bool:
        """Check if there are any critical discrepancies."""
        return self.critical_count > 0

    def summary(self) -> str:
        """Get a human-readable summary of the reconciliation result."""
        status = '✅ CONSISTENT' if self.is_consistent else '❌ INCONSISTENT'
        return f"Reconciliation: {status} | Critical: {self.critical_count}, Warning: {self.warning_count}"
