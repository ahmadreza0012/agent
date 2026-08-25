"""
Kill Switch Models - Data models for the kill switch mechanism.

This module defines the core data structures used by the kill switch system.
These models are the API contract for all kill switch operations.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional, Any, Dict


class KillSwitchLevel(Enum):
    """
    Kill switch severity levels.
    
    Each level has specific actions and recovery requirements.
    """
    NORMAL = "normal"           # All systems operational, trading allowed
    PAUSE = "pause"             # Stop new orders, keep open orders, can auto-resume
    DERISK = "derisk"           # Stop new orders, reduce exposure, manual review to resume
    HALT = "halt"               # Stop new orders, cancel all orders, close positions, manual review
    EMERGENCY = "emergency"     # Emergency close via market orders, kill processes, full review required


class KillSwitchTrigger(Enum):
    """
    Kill switch trigger reasons.
    
    These enumerate all possible conditions that can activate the kill switch.
    """
    MANUAL = "manual"                       # Manual trigger by operator
    DRAWDOWN = "drawdown"                   # Maximum drawdown breach
    DAILY_LOSS = "daily_loss"               # Daily loss limit breach
    POSITION_LIMIT = "position_limit"       # Position size limit breach
    EXCHANGE_ERROR = "exchange_error"       # Exchange connection/API failure
    DATA_ERROR = "data_error"               # Corrupted or missing market data
    SYSTEM_ERROR = "system_error"           # Critical system error
    NETWORK_ERROR = "network_error"         # Network connectivity failure
    SEQUENCE_ERROR = "sequence_error"       # Order sequence/ID mismatch
    TIMEOUT = "timeout"                     # Operation timeout
    CIRCUIT_BREAKER = "circuit_breaker"     # Circuit breaker triggered
    RSI_OVERSOLD = "rsi_oversold"           # Extreme RSI oversold condition
    RSI_OVERBOUGHT = "rsi_overbought"       # Extreme RSI overbought condition
    RECONCILIATION = "reconciliation"       # Reconciliation failure


@dataclass
class KillSwitchEvent:
    """
    Represents a kill switch activation event.
    
    Attributes:
        id: Unique event identifier
        level: Kill switch level triggered
        trigger: What triggered the event
        timestamp: When the event occurred
        reason: Human-readable reason for the trigger
        details: Additional context/metrics at time of trigger
        triggered_by: Who/what triggered the event (user, system, etc.)
        resolved_at: When the event was resolved (None if active)
        resolution: How the event was resolved
    """
    id: str
    level: KillSwitchLevel
    trigger: KillSwitchTrigger
    timestamp: datetime
    reason: str
    details: Dict[str, Any]
    triggered_by: str
    resolved_at: Optional[datetime] = None
    resolution: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for serialization."""
        return {
            "id": self.id,
            "level": self.level.value,
            "trigger": self.trigger.value,
            "timestamp": self.timestamp.isoformat(),
            "reason": self.reason,
            "details": self.details,
            "triggered_by": self.triggered_by,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "resolution": self.resolution
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KillSwitchEvent":
        """Create event from dictionary."""
        return cls(
            id=data["id"],
            level=KillSwitchLevel(data["level"]),
            trigger=KillSwitchTrigger(data["trigger"]),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            reason=data["reason"],
            details=data.get("details", {}),
            triggered_by=data["triggered_by"],
            resolved_at=datetime.fromisoformat(data["resolved_at"]) if data.get("resolved_at") else None,
            resolution=data.get("resolution")
        )


@dataclass
class KillSwitchState:
    """
    Current state of the kill switch system.
    
    Attributes:
        level: Current kill switch level
        is_triggered: Whether kill switch is currently active
        last_trigger: The most recent trigger event (if any)
        history: List of all historical events
        timestamp: Last state update timestamp
    """
    level: KillSwitchLevel
    is_triggered: bool
    last_trigger: Optional[KillSwitchEvent]
    history: List[KillSwitchEvent]
    timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert state to dictionary for serialization."""
        return {
            "level": self.level.value,
            "is_triggered": self.is_triggered,
            "last_trigger": self.last_trigger.to_dict() if self.last_trigger else None,
            "history": [e.to_dict() for e in self.history],
            "timestamp": self.timestamp.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KillSwitchState":
        """Create state from dictionary."""
        history = [KillSwitchEvent.from_dict(e) for e in data.get("history", [])]
        last_trigger = KillSwitchEvent.from_dict(data["last_trigger"]) if data.get("last_trigger") else None
        return cls(
            level=KillSwitchLevel(data["level"]),
            is_triggered=data["is_triggered"],
            last_trigger=last_trigger,
            history=history,
            timestamp=datetime.fromisoformat(data["timestamp"])
        )


@dataclass
class KillSwitchResponse:
    """
    Response from kill switch operations.
    
    Attributes:
        success: Whether the operation succeeded
        level: Current kill switch level after operation
        message: Human-readable status message
        timestamp: Response timestamp
        actions_taken: List of actions executed as part of the operation
        requires_review: Whether manual review is required before resuming
    """
    success: bool
    level: KillSwitchLevel
    message: str
    timestamp: datetime
    actions_taken: List[str]
    requires_review: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert response to dictionary for serialization."""
        return {
            "success": self.success,
            "level": self.level.value,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "actions_taken": self.actions_taken,
            "requires_review": self.requires_review
        }
