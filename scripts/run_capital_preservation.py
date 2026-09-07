#!/usr/bin/env python3
"""
Capital Preservation Test Script
=================================
Test the capital preservation system with various scenarios.

This script tests:
1. Normal operations (SAFE status)
2. Warning conditions (elevated drawdown)
3. Danger conditions (high drawdown)
4. Critical conditions (severe drawdown)
5. Ruin conditions (maximum drawdown exceeded)
6. Daily loss limits
7. Cash ratio checks
8. Market volatility checks
9. Dangerous regime detection
"""

import sys
sys.path.insert(0, '/workspace')

import pandas as pd
import logging
from risk.capital_preservation import (
    CapitalPreservationEngine,
    CapitalPreservationConfig,
    CapitalPosition,
    RiskStatus,
)
from monitoring.capital_monitor import CapitalMonitor

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def create_test_capital(
    total_capital: float = 100000,
    current_drawdown: float = 0.0,
    daily_loss: float = 0.0,
    cash_ratio: float = 0.20,
    max_position: float = 0.15,
) -> CapitalPosition:
    """Create a test capital position."""
    invested = total_capital * (1 - cash_ratio)
    cash = total_capital * cash_ratio
    
    return CapitalPosition(
        total_capital=total_capital,
        invested_capital=invested,
        cash_capital=cash,
        unrealized_pnl=0,
        realized_pnl=0,
        total_pnl=0,
        total_return=0,
        current_drawdown=current_drawdown,
        max_drawdown=current_drawdown,
        daily_loss_today=daily_loss,
    )


def create_market_data(volatility_multiplier: float = 1.0) -> pd.DataFrame:
    """Create test market data with specified volatility."""
    base_vol = 0.02
    returns = [base_vol * volatility_multiplier * (1 if i % 2 == 0 else -1) 
               for i in range(30)]
    return pd.DataFrame({'returns': returns})


def test_scenario(name: str, capital: CapitalPosition, portfolio_metrics: dict,
                  market_data: pd.DataFrame, regime: str, engine: CapitalPreservationEngine):
    """Test a specific scenario."""
    print(f"\n{'='*80}")
    print(f"SCENARIO: {name}")
    print(f"{'='*80}")
    
    action = engine.evaluate(capital, portfolio_metrics, market_data, regime)
    
    print(f"Status: {action.severity.value.upper()}")
    print(f"Multiplier: {action.multiplier:.2f}")
    print(f"Reason: {action.reason}")
    print(f"\nActions ({len(action.actions)}):")
    for a in action.actions:
        print(f"  • {a}")
    
    recommendations = engine.get_recovery_recommendations()
    if recommendations:
        print(f"\nRecommendations:")
        for r in recommendations[:3]:
            print(f"  • {r}")
    
    return action


def run_all_tests():
    """Run all capital preservation tests."""
    print("\n" + "="*80)
    print("CAPITAL PRESERVATION SYSTEM TEST")
    print("="*80)
    
    # Initialize engine
    config = CapitalPreservationConfig(
        max_drawdown_limit=0.25,
        max_daily_loss_limit=0.05,
        max_position_size=0.20,
        min_cash_ratio=0.10,
        drawdown_action_threshold=0.15,
        critical_drawdown_threshold=0.20,
        stop_trading_threshold=0.25,
    )
    engine = CapitalPreservationEngine(config)
    monitor = CapitalMonitor()
    
    portfolio_metrics_normal = {
        'max_position_size': 0.15,
        'max_correlation': 0.65,
    }
    
    market_data_normal = create_market_data(1.0)
    
    # Test 1: Normal operations
    capital_normal = create_test_capital(
        current_drawdown=0.05,
        daily_loss=0.01,
        cash_ratio=0.20,
    )
    test_scenario(
        "Normal Operations",
        capital_normal,
        portfolio_metrics_normal,
        market_data_normal,
        "NORMAL",
        engine
    )
    
    # Test 2: Warning - elevated drawdown
    capital_warning = create_test_capital(
        current_drawdown=0.12,
        daily_loss=0.02,
        cash_ratio=0.15,
    )
    test_scenario(
        "Warning - Elevated Drawdown (12%)",
        capital_warning,
        portfolio_metrics_normal,
        market_data_normal,
        "NORMAL",
        engine
    )
    
    # Test 3: Danger - action threshold exceeded
    capital_danger = create_test_capital(
        current_drawdown=0.17,
        daily_loss=0.03,
        cash_ratio=0.12,
    )
    test_scenario(
        "Danger - Action Threshold (17%)",
        capital_danger,
        portfolio_metrics_normal,
        market_data_normal,
        "NORMAL",
        engine
    )
    
    # Test 4: Critical - severe drawdown
    capital_critical = create_test_capital(
        current_drawdown=0.22,
        daily_loss=0.04,
        cash_ratio=0.08,
    )
    test_scenario(
        "Critical - Severe Drawdown (22%)",
        capital_critical,
        portfolio_metrics_normal,
        market_data_normal,
        "NORMAL",
        engine
    )
    
    # Test 5: Ruin - maximum drawdown exceeded
    capital_ruin = create_test_capital(
        current_drawdown=0.28,
        daily_loss=0.06,
        cash_ratio=0.05,
    )
    test_scenario(
        "Ruin - Maximum Drawdown Exceeded (28%)",
        capital_ruin,
        portfolio_metrics_normal,
        market_data_normal,
        "NORMAL",
        engine
    )
    
    # Test 6: Daily loss limit exceeded
    capital_daily_loss = create_test_capital(
        current_drawdown=0.10,
        daily_loss=0.06,
        cash_ratio=0.20,
    )
    test_scenario(
        "Daily Loss Limit Exceeded (6%)",
        capital_daily_loss,
        portfolio_metrics_normal,
        market_data_normal,
        "NORMAL",
        engine
    )
    
    # Test 7: Low cash ratio
    capital_low_cash = create_test_capital(
        current_drawdown=0.08,
        daily_loss=0.01,
        cash_ratio=0.03,
    )
    test_scenario(
        "Low Cash Ratio (3%)",
        capital_low_cash,
        portfolio_metrics_normal,
        market_data_normal,
        "NORMAL",
        engine
    )
    
    # Test 8: High volatility
    capital_high_vol = create_test_capital(
        current_drawdown=0.08,
        daily_loss=0.02,
        cash_ratio=0.15,
    )
    market_data_high_vol = create_market_data(2.5)
    test_scenario(
        "High Volatility (2.5x normal)",
        capital_high_vol,
        portfolio_metrics_normal,
        market_data_high_vol,
        "NORMAL",
        engine
    )
    
    # Test 9: Dangerous regime
    capital_regime = create_test_capital(
        current_drawdown=0.10,
        daily_loss=0.02,
        cash_ratio=0.15,
    )
    test_scenario(
        "Dangerous Regime (CRASH)",
        capital_regime,
        portfolio_metrics_normal,
        market_data_normal,
        "CRASH",
        engine
    )
    
    # Test 10: Multiple issues combined
    capital_combined = create_test_capital(
        current_drawdown=0.18,
        daily_loss=0.04,
        cash_ratio=0.06,
        max_position=0.35,
    )
    portfolio_metrics_bad = {
        'max_position_size': 0.35,
        'max_correlation': 0.85,
    }
    test_scenario(
        "Combined Issues (Drawdown + Low Cash + Concentration)",
        capital_combined,
        portfolio_metrics_bad,
        market_data_normal,
        "NORMAL",
        engine
    )
    
    # Generate monitor report
    print("\n" + "="*80)
    print("MONITOR REPORT")
    print("="*80)
    
    # Simulate monitoring
    for i in range(5):
        monitor.monitor(
            capital={
                'current_drawdown': 0.05 + i * 0.03,
                'daily_loss': 0.01 + i * 0.01,
                'cash_ratio': 0.20 - i * 0.03,
                'max_position_size': 0.15,
            },
            positions=[],
            market_data=market_data_normal
        )
    
    print(monitor.generate_report())
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    history = engine.get_history()
    if not history.empty:
        print(f"\nTotal evaluations: {len(history)}")
        print(f"\nStatus distribution:")
        print(history['status'].value_counts())
        
        print(f"\nMultiplier statistics:")
        print(f"  Min: {history['multiplier'].min():.2f}")
        print(f"  Max: {history['multiplier'].max():.2f}")
        print(f"  Mean: {history['multiplier'].mean():.2f}")
    
    print("\n" + "="*80)
    print("ALL TESTS COMPLETED")
    print("="*80)


if __name__ == '__main__':
    run_all_tests()
