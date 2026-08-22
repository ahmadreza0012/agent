"""
Test Phase 19: Kill Switch

Comprehensive tests for the kill switch mechanism covering all levels,
triggers, persistence, and integration scenarios.
"""

import json
import os
import tempfile
import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

# Import kill switch components
from execution.kill_switch_models import (
    KillSwitchLevel,
    KillSwitchTrigger,
    KillSwitchEvent,
    KillSwitchState,
    KillSwitchResponse,
)
from execution.kill_switch import KillSwitch
from execution.kill_switch_manager import KillSwitchManager


class MockExchangeAdapter:
    """Mock exchange adapter for testing."""
    
    def __init__(self):
        self.orders_cancelled = 0
        self.positions_closed = 0
    
    def create_order(self, symbol, side, order_type, amount, **kwargs):
        """Mock order creation."""
        return Mock(
            id=f"mock_order_{symbol}_{datetime.now().timestamp()}",
            symbol=symbol,
            side=side,
            type=order_type,
            amount=amount,
            filled_amount=0,
            status="open"
        )
    
    def cancel_order(self, order_id, symbol=None):
        """Mock order cancellation."""
        self.orders_cancelled += 1
        return True


class MockOrderManager:
    """Mock order manager for testing."""
    
    def __init__(self):
        self._paused = False
        self.orders = {}
        self.client_order_ids = set()
    
    def cancel_order_safe(self, order_id):
        """Mock safe order cancellation."""
        if order_id in self.orders:
            self.orders[order_id].status = "cancelled"
            return True
        return False


class MockPositionManager:
    """Mock position manager for testing."""
    
    def __init__(self, positions=None):
        self._positions = positions or []
    
    def get_all_positions(self):
        """Return all mock positions."""
        return self._positions


def create_mock_position(symbol, size, current_price):
    """Helper to create a mock position."""
    return Mock(
        symbol=symbol,
        size=size,
        current_price=current_price
    )


class TestKillSwitchModels:
    """Test data models."""
    
    def test_kill_switch_level_enum(self):
        """Test KillSwitchLevel enum values."""
        assert KillSwitchLevel.NORMAL.value == "normal"
        assert KillSwitchLevel.PAUSE.value == "pause"
        assert KillSwitchLevel.DERISK.value == "derisk"
        assert KillSwitchLevel.HALT.value == "halt"
        assert KillSwitchLevel.EMERGENCY.value == "emergency"
    
    def test_kill_switch_trigger_enum(self):
        """Test KillSwitchTrigger enum values."""
        assert KillSwitchTrigger.MANUAL.value == "manual"
        assert KillSwitchTrigger.DRAWDOWN.value == "drawdown"
        assert KillSwitchTrigger.EXCHANGE_ERROR.value == "exchange_error"
    
    def test_kill_switch_event_serialization(self):
        """Test KillSwitchEvent to_dict and from_dict."""
        event = KillSwitchEvent(
            id="test-123",
            level=KillSwitchLevel.PAUSE,
            trigger=KillSwitchTrigger.MANUAL,
            timestamp=datetime.utcnow(),
            reason="Test pause",
            details={"test": True},
            triggered_by="tester"
        )
        
        # Serialize
        data = event.to_dict()
        assert data["id"] == "test-123"
        assert data["level"] == "pause"
        assert data["trigger"] == "manual"
        
        # Deserialize
        restored = KillSwitchEvent.from_dict(data)
        assert restored.id == event.id
        assert restored.level == event.level
        assert restored.trigger == event.trigger


class TestKillSwitchCore:
    """Test core kill switch functionality."""
    
    @pytest.fixture
    def temp_state_file(self):
        """Create temporary state file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
        yield temp_path
        # Cleanup
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    
    @pytest.fixture
    def kill_switch(self, temp_state_file):
        """Create fresh kill switch instance."""
        return KillSwitch(state_file=temp_state_file)
    
    def test_initial_state(self, kill_switch):
        """TEST 1: Initial state should be NORMAL and not triggered."""
        state = kill_switch.get_state()
        assert state.level == KillSwitchLevel.NORMAL
        assert state.is_triggered is False
        assert state.last_trigger is None
        assert len(state.history) == 0
    
    def test_trigger_pause(self, kill_switch):
        """TEST 2: Trigger PAUSE and verify state change."""
        response = kill_switch.trigger(
            level=KillSwitchLevel.PAUSE,
            trigger=KillSwitchTrigger.MANUAL,
            reason="Test pause",
            details={},
            triggered_by="test_user"
        )
        
        assert response.success is True
        assert response.level == KillSwitchLevel.PAUSE
        
        state = kill_switch.get_state()
        assert state.level == KillSwitchLevel.PAUSE
        assert state.is_triggered is True
        assert state.last_trigger is not None
        assert state.last_trigger.level == KillSwitchLevel.PAUSE
    
    def test_trigger_halt(self, kill_switch):
        """TEST 3: Trigger HALT and verify requires_review flag."""
        response = kill_switch.trigger(
            level=KillSwitchLevel.HALT,
            trigger=KillSwitchTrigger.MANUAL,
            reason="Test halt",
            details={},
            triggered_by="test_user"
        )
        
        assert response.success is True
        assert response.level == KillSwitchLevel.HALT
        assert response.requires_review is True
        
        state = kill_switch.get_state()
        assert state.level == KillSwitchLevel.HALT
        assert state.is_triggered is True
    
    def test_cannot_override_higher_level(self, kill_switch):
        """TEST 4: Cannot downgrade severity once triggered at higher level."""
        # Trigger HALT first
        kill_switch.trigger(
            level=KillSwitchLevel.HALT,
            trigger=KillSwitchTrigger.MANUAL,
            reason="Initial halt",
            details={},
            triggered_by="test"
        )
        
        # Try to trigger PAUSE (lower level)
        response = kill_switch.trigger(
            level=KillSwitchLevel.PAUSE,
            trigger=KillSwitchTrigger.MANUAL,
            reason="Try pause",
            details={},
            triggered_by="test"
        )
        
        # Should fail or stay at HALT
        assert response.success is False or response.level == KillSwitchLevel.HALT
    
    def test_resume_from_pause(self, kill_switch):
        """TEST 5: Resume from PAUSE successfully."""
        # Trigger PAUSE
        kill_switch.trigger(
            level=KillSwitchLevel.PAUSE,
            trigger=KillSwitchTrigger.MANUAL,
            reason="Test pause",
            details={},
            triggered_by="test"
        )
        
        # Resume
        response = kill_switch.resume(
            reason="Test resume",
            resolved_by="test_user"
        )
        
        assert response.success is True
        assert response.level == KillSwitchLevel.NORMAL
        
        state = kill_switch.get_state()
        assert state.level == KillSwitchLevel.NORMAL
        assert state.is_triggered is False
    
    def test_resume_from_halt_requires_manual(self, kill_switch):
        """TEST 6: Cannot auto-resume from HALT via system."""
        # Trigger HALT
        kill_switch.trigger(
            level=KillSwitchLevel.HALT,
            trigger=KillSwitchTrigger.MANUAL,
            reason="Test halt",
            details={},
            triggered_by="test"
        )
        
        # Try to resume via "system" (not manual)
        response = kill_switch.resume(
            reason="Auto resume",
            resolved_by="system"
        )
        
        assert response.success is False
        assert response.requires_review is True
    
    def test_persistence(self, temp_state_file):
        """TEST 7: State persists across restarts."""
        # Create kill switch and trigger PAUSE
        ks1 = KillSwitch(state_file=temp_state_file)
        ks1.trigger(
            level=KillSwitchLevel.PAUSE,
            trigger=KillSwitchTrigger.MANUAL,
            reason="Persist test",
            details={},
            triggered_by="test"
        )
        
        # Create new instance - should load from disk
        ks2 = KillSwitch(state_file=temp_state_file)
        state = ks2.get_state()
        
        assert state.level == KillSwitchLevel.PAUSE
        assert state.is_triggered is True
    
    def test_event_history(self, kill_switch):
        """TEST 8: Event history tracks all triggers and resumes."""
        # Trigger 3 times
        kill_switch.trigger(KillSwitchLevel.PAUSE, KillSwitchTrigger.MANUAL, "Pause 1", {}, "test")
        kill_switch.resume("Resume 1", "test")
        
        kill_switch.trigger(KillSwitchLevel.PAUSE, KillSwitchTrigger.MANUAL, "Pause 2", {}, "test")
        kill_switch.resume("Resume 2", "test")
        
        kill_switch.trigger(KillSwitchLevel.PAUSE, KillSwitchTrigger.MANUAL, "Pause 3", {}, "test")
        kill_switch.resume("Resume 3", "test")
        
        state = kill_switch.get_state()
        # 3 triggers + 3 resumes = 6 events
        assert len(state.history) == 6
    
    def test_trading_allowed_flag(self, kill_switch):
        """TEST 9: is_trading_allowed returns correct values."""
        # Initially allowed
        assert kill_switch.is_trading_allowed() is True
        
        # After PAUSE - NOT allowed (only NORMAL allows trading)
        kill_switch.trigger(
            level=KillSwitchLevel.PAUSE,
            trigger=KillSwitchTrigger.MANUAL,
            reason="Test",
            details={},
            triggered_by="test"
        )
        assert kill_switch.is_trading_allowed() is False
        
        # After resume - allowed again
        kill_switch.resume("Resume", "test")
        assert kill_switch.is_trading_allowed() is True


class TestKillSwitchManager:
    """Test kill switch manager integration."""
    
    @pytest.fixture
    def temp_state_file(self):
        """Create temporary state file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
        yield temp_path
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    
    @pytest.fixture
    def mock_components(self):
        """Create mock trading components."""
        order_manager = MockOrderManager()
        position_manager = MockPositionManager([
            create_mock_position("BTC/USDT", 0.5, 50000),
            create_mock_position("ETH/USDT", 5.0, 3000),
        ])
        exchange_adapter = MockExchangeAdapter()
        
        return {
            'order_manager': order_manager,
            'position_manager': position_manager,
            'exchange_adapter': exchange_adapter
        }
    
    @pytest.fixture
    def kill_switch_manager(self, temp_state_file, mock_components):
        """Create kill switch manager with mock components."""
        kill_switch = KillSwitch(state_file=temp_state_file)
        return KillSwitchManager(
            kill_switch=kill_switch,
            order_manager=mock_components['order_manager'],
            position_manager=mock_components['position_manager'],
            exchange_adapter=mock_components['exchange_adapter']
        )
    
    def test_emergency_stop(self, kill_switch_manager):
        """TEST 10a: Emergency stop triggers EMERGENCY level."""
        response = kill_switch_manager.emergency_stop(
            reason="Test emergency",
            triggered_by="test"
        )
        
        assert response.success is True
        assert response.level == KillSwitchLevel.EMERGENCY
        assert response.requires_review is True
    
    def test_halt_trading(self, kill_switch_manager, mock_components):
        """TEST 10b: Halt trading cancels orders and closes positions."""
        # Add some mock open orders
        kill_switch_manager.order_manager.orders['order1'] = Mock(
            id='order1',
            is_complete=False,
            status='open'
        )
        
        response = kill_switch_manager.halt_trading(
            reason="Test halt",
            triggered_by="test"
        )
        
        assert response.success is True
        assert response.level == KillSwitchLevel.HALT
        
        # Verify order manager was paused
        assert kill_switch_manager.order_manager._paused is True
    
    def test_pause_trading(self, kill_switch_manager):
        """TEST 10c: Pause trading stops new orders."""
        response = kill_switch_manager.pause_trading(
            reason="Test pause",
            triggered_by="test"
        )
        
        assert response.success is True
        assert response.level == KillSwitchLevel.PAUSE
        assert kill_switch_manager.order_manager._paused is True
    
    def test_resume_trading(self, kill_switch_manager):
        """TEST 10d: Resume trading re-enables order manager."""
        # Pause first
        kill_switch_manager.pause_trading("Test", "test")
        assert kill_switch_manager.order_manager._paused is True
        
        # Resume
        response = kill_switch_manager.resume_trading(
            reason="Test resume",
            resolved_by="test_user"
        )
        
        assert response.success is True
        assert kill_switch_manager.order_manager._paused is False
    
    def test_check_conditions_drawdown(self, kill_switch_manager):
        """TEST 10e: Drawdown breach triggers DERISK."""
        metrics = {
            'current_drawdown': 0.20,  # 20% drawdown (exceeds 15% default)
            'daily_pnl': 0,
            'equity': 100000,
            'positions': [],
            'total_exposure': 0
        }
        
        # Call check_conditions directly on the core kill switch
        kill_switch_manager.kill_switch._check_conditions(metrics)
        
        state = kill_switch_manager.kill_switch.get_state()
        assert state.level == KillSwitchLevel.DERISK
        assert state.last_trigger.trigger == KillSwitchTrigger.DRAWDOWN
    
    def test_get_status(self, kill_switch_manager):
        """TEST 10f: Get status returns correct structure."""
        status = kill_switch_manager.get_status()
        
        assert 'level' in status
        assert 'is_triggered' in status
        assert 'history_count' in status
        assert 'trading_allowed' in status
        assert 'timestamp' in status
        
        assert status['level'] == 'normal'
        assert status['is_triggered'] is False
        assert status['trading_allowed'] is True


class TestKillSwitchIntegration:
    """Integration tests for kill switch with full system."""
    
    @pytest.fixture
    def temp_state_file(self):
        """Create temporary state file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
        yield temp_path
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    
    def test_full_lifecycle(self, temp_state_file):
        """Test complete kill switch lifecycle."""
        # Initialize
        ks = KillSwitch(state_file=temp_state_file)
        
        # Normal operation
        assert ks.is_trading_allowed() is True
        
        # Pause
        ks.trigger(KillSwitchLevel.PAUSE, KillSwitchTrigger.MANUAL, "Pause", {}, "user")
        assert ks.is_trading_allowed() is False
        
        # Resume
        ks.resume("Resume", "user")
        assert ks.is_trading_allowed() is True
        
        # Derisk
        ks.trigger(KillSwitchLevel.DERISK, KillSwitchTrigger.DRAWDOWN, "Drawdown", {}, "system")
        assert ks.is_trading_allowed() is False
        
        # Halt
        ks.trigger(KillSwitchLevel.HALT, KillSwitchTrigger.MANUAL, "Halt", {}, "user")
        state = ks.get_state()
        assert state.level == KillSwitchLevel.HALT
        
        # Try auto-resume (should fail)
        response = ks.resume("Auto", "system")
        assert response.success is False
        
        # Manual resume
        response = ks.resume("Manual review done", "admin")
        assert response.success is True
        assert ks.is_trading_allowed() is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
