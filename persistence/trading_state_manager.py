"""
Trading State Manager - Persistence for trading component state.

Manages portfolio, positions, orders, fills, and balances persistence.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

from .state_manager import StateManager
from .persistence_manager import PersistenceManager

logger = logging.getLogger(__name__)


@dataclass
class TradingState:
    """Trading system state."""
    portfolio: Dict[str, float] = field(default_factory=dict)
    positions: List[Dict[str, Any]] = field(default_factory=list)
    orders: List[Dict[str, Any]] = field(default_factory=list)
    fills: List[Dict[str, Any]] = field(default_factory=list)
    balances: Dict[str, float] = field(default_factory=dict)
    last_update: Optional[datetime] = None
    version: int = 1


class TradingStateManager(StateManager[TradingState]):
    """State manager for trading component."""
    
    def __init__(self, persistence_manager: PersistenceManager):
        super().__init__(persistence_manager, 'trading')
    
    def serialize(self, state: TradingState) -> Dict[str, Any]:
        return {
            'portfolio': state.portfolio,
            'positions': state.positions,
            'orders': state.orders,
            'fills': state.fills,
            'balances': state.balances,
            'last_update': state.last_update.isoformat() if state.last_update else None,
            'version': state.version
        }
    
    def deserialize(self, data: Dict[str, Any]) -> TradingState:
        state = TradingState()
        state.portfolio = data.get('portfolio', {})
        state.positions = data.get('positions', [])
        state.orders = data.get('orders', [])
        state.fills = data.get('fills', [])
        state.balances = data.get('balances', {})
        last_update = data.get('last_update')
        state.last_update = datetime.fromisoformat(last_update) if last_update else None
        state.version = data.get('version', 1)
        return state
    
    def get_default_state(self) -> TradingState:
        return TradingState()
    
    def add_position(self, position: Dict[str, Any]) -> None:
        """Add a position to state."""
        state = self.get_current()
        state.positions.append(position)
        state.last_update = datetime.now()
        self.set_current(state)
        self.save_current()
    
    def update_position(self, symbol: str, updates: Dict[str, Any]) -> None:
        """Update an existing position."""
        state = self.get_current()
        for i, pos in enumerate(state.positions):
            if pos.get('symbol') == symbol:
                state.positions[i].update(updates)
                state.last_update = datetime.now()
                break
        self.set_current(state)
        self.save_current()
    
    def remove_position(self, symbol: str) -> None:
        """Remove a closed position."""
        state = self.get_current()
        state.positions = [p for p in state.positions if p.get('symbol') != symbol]
        state.last_update = datetime.now()
        self.set_current(state)
        self.save_current()
    
    def add_order(self, order: Dict[str, Any]) -> None:
        """Add an order to state."""
        state = self.get_current()
        state.orders.append(order)
        state.last_update = datetime.now()
        self.set_current(state)
        self.save_current()
    
    def update_order_status(self, order_id: str, status: str) -> None:
        """Update order status."""
        state = self.get_current()
        for i, order in enumerate(state.orders):
            if order.get('id') == order_id or order.get('client_order_id') == order_id:
                state.orders[i]['status'] = status
                state.orders[i]['updated_at'] = datetime.now().isoformat()
                state.last_update = datetime.now()
                break
        self.set_current(state)
        self.save_current()
    
    def add_fill(self, fill: Dict[str, Any]) -> None:
        """Add a fill to state."""
        state = self.get_current()
        state.fills.append(fill)
        state.last_update = datetime.now()
        self.set_current(state)
        self.save_current()
    
    def update_balances(self, balances: Dict[str, float]) -> None:
        """Update account balances."""
        state = self.get_current()
        state.balances.update(balances)
        state.last_update = datetime.now()
        self.set_current(state)
        self.save_current()
