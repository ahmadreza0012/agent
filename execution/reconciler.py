"""
Portfolio Reconciler - Ensures local state matches exchange state.

This module compares local positions and balances with exchange state,
detects discrepancies, and triggers reconciliation when needed.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Any
import logging

from .exchange_adapter import ExchangeAdapter, Position, Balance
from .position_manager import PositionManager

logger = logging.getLogger(__name__)


@dataclass
class PositionMismatch:
    """Represents a position mismatch between local and exchange state."""
    symbol: str
    local_size: float
    exchange_size: float
    local_entry_price: float
    exchange_entry_price: float
    size_difference: float
    price_difference: float
    
    @property
    def is_significant(self) -> bool:
        """Check if mismatch is significant (>1% difference)."""
        if self.exchange_size == 0:
            return abs(self.local_size) > 0.000001
        return abs(self.size_difference / self.exchange_size) > 0.01


@dataclass
class BalanceMismatch:
    """Represents a balance mismatch between local and exchange state."""
    asset: str
    local_total: float
    exchange_total: float
    local_free: float
    exchange_free: float
    local_locked: float
    exchange_locked: float
    total_difference: float
    
    @property
    def is_significant(self) -> bool:
        """Check if mismatch is significant (>1% difference)."""
        if self.exchange_total == 0:
            return abs(self.local_total) > 0.000001
        return abs(self.total_difference / self.exchange_total) > 0.01


@dataclass
class ReconciliationResult:
    """Result of a portfolio reconciliation."""
    is_consistent: bool
    timestamp: datetime
    position_mismatches: List[PositionMismatch]
    balance_mismatches: List[BalanceMismatch]
    
    @property
    def has_critical_mismatch(self) -> bool:
        """Check if any mismatch is significant."""
        critical_positions = any(m.is_significant for m in self.position_mismatches)
        critical_balances = any(m.is_significant for m in self.balance_mismatches)
        return critical_positions or critical_balances


class PortfolioReconciler:
    """Reconciles local portfolio state with exchange state."""
    
    def __init__(
        self,
        exchange_adapter: ExchangeAdapter,
        position_manager: PositionManager,
        tolerance: float = 0.001,
    ):
        """
        Initialize the Portfolio Reconciler.
        
        Args:
            exchange_adapter: Exchange adapter for fetching remote state.
            position_manager: Position manager with local state.
            tolerance: Tolerance for floating point comparisons.
        """
        self.exchange = exchange_adapter
        self.position_manager = position_manager
        self.tolerance = tolerance
        self.last_reconciliation: Optional[ReconciliationResult] = None
        logger.info("PortfolioReconciler initialized")
    
    def reconcile(self) -> ReconciliationResult:
        """
        Perform full portfolio reconciliation.
        
        Returns:
            ReconciliationResult with all mismatches.
        """
        logger.info("Starting portfolio reconciliation...")
        
        # Get exchange state
        try:
            exchange_positions = self.exchange.get_positions()
            exchange_balances = self.exchange.get_balance()
        except Exception as e:
            logger.error(f"Failed to fetch exchange state: {e}")
            raise
        
        # Reconcile positions and balances
        position_mismatches = self._reconcile_positions(exchange_positions)
        balance_mismatches = self._reconcile_balances(exchange_balances)
        
        # Create result
        is_consistent = len(position_mismatches) == 0 and len(balance_mismatches) == 0
        
        result = ReconciliationResult(
            is_consistent=is_consistent,
            timestamp=datetime.now(),
            position_mismatches=position_mismatches,
            balance_mismatches=balance_mismatches,
        )
        
        self.last_reconciliation = result
        
        if is_consistent:
            logger.info("Portfolio reconciliation: CONSISTENT")
        else:
            logger.warning(
                f"Portfolio reconciliation: MISMATCH DETECTED | "
                f"positions={len(position_mismatches)}, balances={len(balance_mismatches)}"
            )
        
        return result
    
    def _reconcile_positions(
        self,
        exchange_positions: List[Position],
    ) -> List[PositionMismatch]:
        """
        Reconcile local positions with exchange positions.
        
        Args:
            exchange_positions: Positions from exchange.
        
        Returns:
            List of PositionMismatch objects.
        """
        mismatches = []
        
        # Build lookup dictionaries
        local_positions = {pos.symbol: pos for pos in self.position_manager.get_all_positions()}
        exchange_pos_dict = {pos.symbol: pos for pos in exchange_positions}
        
        # Check all local positions
        all_symbols = set(local_positions.keys()) | set(exchange_pos_dict.keys())
        
        for symbol in all_symbols:
            local_pos = local_positions.get(symbol)
            exchange_pos = exchange_pos_dict.get(symbol)
            
            # Skip if both don't exist
            if not local_pos and not exchange_pos:
                continue
            
            # Get values (default to 0 if missing)
            local_size = local_pos.size if local_pos else 0.0
            exchange_size = exchange_pos.size if exchange_pos else 0.0
            
            local_entry = local_pos.entry_price if local_pos else 0.0
            exchange_entry = exchange_pos.entry_price if exchange_pos else 0.0
            
            # Check for significant differences
            size_diff = abs(local_size - exchange_size)
            price_diff = abs(local_entry - exchange_entry) if local_entry > 0 or exchange_entry > 0 else 0.0
            
            if size_diff > self.tolerance or (price_diff > self.tolerance * local_entry and local_size != 0):
                mismatch = PositionMismatch(
                    symbol=symbol,
                    local_size=local_size,
                    exchange_size=exchange_size,
                    local_entry_price=local_entry,
                    exchange_entry_price=exchange_entry,
                    size_difference=local_size - exchange_size,
                    price_difference=local_entry - exchange_entry,
                )
                mismatches.append(mismatch)
                logger.warning(
                    f"Position mismatch: {symbol} | local={local_size}, exchange={exchange_size} | "
                    f"diff={size_diff}"
                )
        
        return mismatches
    
    def _reconcile_balances(
        self,
        exchange_balances: Dict[str, Balance],
    ) -> List[BalanceMismatch]:
        """
        Reconcile local balances with exchange balances.
        
        Note: This requires tracking local balances separately.
        For now, we only check if exchange balances are accessible.
        
        Args:
            exchange_balances: Balances from exchange.
        
        Returns:
            List of BalanceMismatch objects.
        """
        # TODO: Implement proper balance tracking
        # For now, return empty list as we don't track local balances
        return []
    
    def reconcile_positions(self) -> List[PositionMismatch]:
        """
        Reconcile only positions (not balances).
        
        Returns:
            List of PositionMismatch objects.
        """
        try:
            exchange_positions = self.exchange.get_positions()
            return self._reconcile_positions(exchange_positions)
        except Exception as e:
            logger.error(f"Failed to reconcile positions: {e}")
            raise
    
    def reconcile_balances(self) -> List[BalanceMismatch]:
        """
        Reconcile only balances (not positions).
        
        Returns:
            List of BalanceMismatch objects.
        """
        try:
            exchange_balances = self.exchange.get_balance()
            return self._reconcile_balances(exchange_balances)
        except Exception as e:
            logger.error(f"Failed to reconcile balances: {e}")
            raise
    
    def detect_mismatch(self) -> bool:
        """
        Quick check for any mismatch.
        
        Returns:
            True if any mismatch detected.
        """
        try:
            result = self.reconcile()
            return not result.is_consistent
        except Exception as e:
            logger.error(f"Mismatch detection failed: {e}")
            return True  # Assume mismatch on error for safety
    
    def get_reconciliation_status(self) -> Dict[str, Any]:
        """
        Get current reconciliation status.
        
        Returns:
            Dictionary with reconciliation information.
        """
        if self.last_reconciliation is None:
            return {
                'status': 'never_reconciled',
                'last_timestamp': None,
                'is_consistent': None,
            }
        
        return {
            'status': 'reconciled',
            'last_timestamp': self.last_reconciliation.timestamp.isoformat(),
            'is_consistent': self.last_reconciliation.is_consistent,
            'position_mismatches': len(self.last_reconciliation.position_mismatches),
            'balance_mismatches': len(self.last_reconciliation.balance_mismatches),
            'has_critical_mismatch': self.last_reconciliation.has_critical_mismatch,
        }