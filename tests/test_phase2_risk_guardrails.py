"""
Test suite for Risk Policy Module (Phase 2 - Risk Guardrails)
=============================================================

Tests cover:
- Trading mode detection
- Threshold enforcement by mode
- Circuit breaker triggering
- Manual reset protection in LIVE mode
- State transitions
"""

import os
import pytest
from unittest.mock import patch
import time

import risk_policy
from risk_policy import (
    RiskPolicy,
    TradingMode,
    RiskState,
    RiskThresholds,
    RESEARCH_THRESHOLDS,
    PAPER_THRESHOLDS,
    LIVE_THRESHOLDS,
)


class TestTradingModeDetection:
    """Test trading mode detection from environment."""
    
    def test_default_mode_is_research(self):
        """Default mode should be research (safe default)."""
        # Ensure env is not set
        old_env = os.environ.pop('TRADING_MODE', None)
        try:
            p = RiskPolicy()
            assert p.mode == TradingMode.RESEARCH
            assert not p.can_issue_real_orders()
        finally:
            if old_env:
                os.environ['TRADING_MODE'] = old_env
    
    def test_live_mode_from_env(self):
        """LIVE mode detected from environment variable."""
        with patch.dict(os.environ, {'TRADING_MODE': 'live'}):
            p = RiskPolicy()
            assert p.mode == TradingMode.LIVE
            assert p.is_live_mode()
    
    def test_paper_mode_from_env(self):
        """Paper mode detected from environment variable."""
        with patch.dict(os.environ, {'TRADING_MODE': 'paper'}):
            p = RiskPolicy()
            assert p.mode == TradingMode.PAPER
    
    def test_unknown_mode_defaults_to_research(self, caplog):
        """Unknown mode string defaults to research with warning."""
        with patch.dict(os.environ, {'TRADING_MODE': 'invalid_mode'}):
            p = RiskPolicy()
            assert p.mode == TradingMode.RESEARCH
            assert 'defaulting to research' in caplog.text.lower()


class TestThresholdConfiguration:
    """Test threshold configuration by mode."""
    
    def test_research_thresholds(self):
        """Research mode has relaxed thresholds."""
        p = RiskPolicy(mode=TradingMode.RESEARCH)
        assert p.thresholds.max_drawdown == 0.25  # 25% tolerance
        assert p.thresholds.min_sharpe == -1.0     # Allow negative
        assert p.thresholds.target_return == -0.05  # Allow losses
    
    def test_live_thresholds(self):
        """LIVE mode has strict thresholds."""
        p = RiskPolicy(mode=TradingMode.LIVE)
        assert p.thresholds.max_drawdown == 0.12  # 12% circuit breaker
        assert p.thresholds.min_sharpe == 0.0      # Must be non-negative
        assert p.thresholds.target_return == 0.0   # Must be profitable
    
    def test_paper_thresholds(self):
        """Paper mode uses live thresholds."""
        p = RiskPolicy(mode=TradingMode.PAPER)
        assert p.thresholds.max_drawdown == 0.15
        assert p.thresholds.min_sharpe == -0.5
    
    def test_custom_thresholds_override(self):
        """Custom thresholds override defaults."""
        custom = RiskThresholds(
            target_return=0.05,
            max_drawdown=0.10,
            min_sharpe=0.5,
            max_position_single_asset=0.25,
            max_gross_exposure=0.8,
        )
        p = RiskPolicy(mode=TradingMode.LIVE, custom_thresholds=custom)
        assert p.thresholds.max_drawdown == 0.10
        assert p.thresholds.min_sharpe == 0.5


class TestCircuitBreaker:
    """Test circuit breaker functionality."""
    
    def test_circuit_breaker_triggers_on_dd_breach(self):
        """Circuit breaker triggers when drawdown exceeds limit."""
        p = RiskPolicy(mode=TradingMode.RESEARCH)
        
        # 26% DD exceeds 25% research threshold
        new_state = p.update_state(
            current_dd=-0.26,
            current_sharpe=-0.5,
            current_return=-0.10
        )
        
        assert new_state == RiskState.CIRCUIT_BREAKER
        assert p.state == RiskState.CIRCUIT_BREAKER
    
    def test_circuit_breaker_prevents_trading(self):
        """Circuit breaker state prevents real order issuance."""
        p = RiskPolicy(mode=TradingMode.LIVE)
        
        # Trigger circuit breaker
        p.update_state(current_dd=-0.13, current_sharpe=-0.2, current_return=-0.05)
        
        assert p.state == RiskState.CIRCUIT_BREAKER
        assert not p.can_issue_real_orders()
    
    def test_no_circuit_breaker_in_research_for_moderate_dd(self):
        """Moderate DD doesn't trigger circuit breaker in research."""
        p = RiskPolicy(mode=TradingMode.RESEARCH)
        
        # 15% DD is within 25% research threshold
        new_state = p.update_state(
            current_dd=-0.15,
            current_sharpe=-0.5,
            current_return=-0.03
        )
        
        assert new_state == RiskState.ACTIVE
        assert p.state == RiskState.ACTIVE
    
    def test_warning_state_approaching_limits(self):
        """Warning state triggered when approaching limits."""
        p = RiskPolicy(mode=TradingMode.LIVE)
        
        # 10% DD is 83% of 12% limit (above 80% warning threshold)
        new_state = p.update_state(
            current_dd=-0.10,
            current_sharpe=0.5,
            current_return=0.02
        )
        
        assert new_state == RiskState.WARNING


class TestManualResetProtection:
    """Test manual reset protection in LIVE mode."""
    
    def test_reset_allowed_in_research_mode(self):
        """Reset allowed in research mode."""
        p = RiskPolicy(mode=TradingMode.RESEARCH)
        
        # Trigger circuit breaker
        p.update_state(current_dd=-0.26, current_sharpe=-1.0, current_return=-0.10)
        assert p.state == RiskState.CIRCUIT_BREAKER
        
        # Reset should work
        p.reset_to_active()
        assert p.state == RiskState.ACTIVE
    
    def test_reset_blocked_in_live_mode(self):
        """Reset blocked in LIVE mode without manual confirmation."""
        p = RiskPolicy(mode=TradingMode.LIVE)
        
        # Trigger circuit breaker
        p.update_state(current_dd=-0.13, current_sharpe=-0.2, current_return=-0.05)
        assert p.state == RiskState.CIRCUIT_BREAKER
        
        # Reset should raise RuntimeError
        with pytest.raises(RuntimeError, match="Manual confirmation required"):
            p.reset_to_active()
        
        # State should remain circuit breaker
        assert p.state == RiskState.CIRCUIT_BREAKER


class TestTradeAllowedChecks:
    """Test trade allowance logic."""
    
    def test_trade_allowed_within_limits(self):
        """Trade allowed when all metrics within limits."""
        p = RiskPolicy(mode=TradingMode.LIVE)
        
        allowed, reason = p.check_trade_allowed({
            'drawdown': -0.05,
            'sharpe': 0.5,
            'annualized_return': 0.03
        })
        
        assert allowed is True
        assert 'allowed' in reason.lower()
    
    def test_trade_blocked_by_drawdown(self):
        """Trade blocked when drawdown exceeds limit."""
        p = RiskPolicy(mode=TradingMode.LIVE)
        
        allowed, reason = p.check_trade_allowed({
            'drawdown': -0.15,  # Exceeds 12% limit
            'sharpe': 0.5,
            'annualized_return': 0.03
        })
        
        assert allowed is False
        assert 'drawdown' in reason.lower()
    
    def test_trade_blocked_by_sharpe_in_live_mode(self):
        """Trade blocked when Sharpe below minimum in LIVE mode."""
        p = RiskPolicy(mode=TradingMode.LIVE)
        
        allowed, reason = p.check_trade_allowed({
            'drawdown': -0.05,
            'sharpe': -0.2,  # Below 0.0 minimum
            'annualized_return': 0.03
        })
        
        assert allowed is False
        assert 'sharpe' in reason.lower()
    
    def test_trade_allowed_negative_sharpe_in_research(self):
        """Negative Sharpe allowed in research mode."""
        p = RiskPolicy(mode=TradingMode.RESEARCH)
        
        allowed, reason = p.check_trade_allowed({
            'drawdown': -0.10,
            'sharpe': -0.5,  # Below LIVE minimum but OK for research
            'annualized_return': -0.02
        })
        
        assert allowed is True


class TestStatusReport:
    """Test status report generation."""
    
    def test_status_report_contains_all_fields(self):
        """Status report includes all required fields."""
        p = RiskPolicy(mode=TradingMode.LIVE)
        report = p.get_status_report()
        
        assert 'mode' in report
        assert 'state' in report
        assert 'can_trade_real' in report
        assert 'thresholds' in report
        assert 'circuit_breaker_active' in report
        
        assert report['mode'] == 'live'
        assert report['state'] == 'active'
        assert report['can_trade_real'] is True
        assert report['circuit_breaker_active'] is False


class TestConfigValidation:
    """Test configuration sanity validation."""
    
    def test_config_module_validates_on_import(self):
        """Config module validates on import."""
        import config
        
        assert config.RISK_FREE_RATE == 0.0
        assert config.DEFAULT_TRADING_MODE == 'research'
        assert config.MAX_POSITION_PCT_OF_ADV == 0.10
        assert config.MIN_LIQUIDITY_USD == 1_000_000
    
    def test_live_thresholds_stricter_than_research(self):
        """LIVE thresholds must be stricter than research."""
        assert LIVE_THRESHOLDS.max_drawdown <= RESEARCH_THRESHOLDS.max_drawdown
        assert LIVE_THRESHOLDS.min_sharpe >= RESEARCH_THRESHOLDS.min_sharpe


class TestIntegrationWithMainSystem:
    """Integration tests with main system components."""
    
    def test_risk_policy_importable_from_config(self):
        """Risk policy can use config constants."""
        import config
        
        # Verify config exports are usable
        assert hasattr(config, 'RISK_FREE_RATE')
        assert hasattr(config, 'LIVE_THRESHOLDS')
        assert hasattr(config, 'RESEARCH_THRESHOLDS')
    
    def test_backward_compatibility_with_existing_code(self):
        """Existing code using hardcoded values still works."""
        # Old code might use risk_free_rate=0.0 directly
        from portfolio_optimizer import PortfolioOptimizer
        
        optimizer = PortfolioOptimizer(n_assets=3, asset_names=['A', 'B', 'C'])
        # Should work with explicit risk_free_rate=0.0
        weights = optimizer.mean_variance_optimization(
            expected_returns=[0.01, 0.02, 0.03],
            cov_matrix=[[0.01, 0, 0], [0, 0.01, 0], [0, 0, 0.01]],
            risk_free_rate=0.0
        )
        assert len(weights) == 3
        assert abs(sum(weights) - 1.0) < 0.01  # Weights sum to ~1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
