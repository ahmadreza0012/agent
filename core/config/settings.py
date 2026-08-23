"""
Central Configuration for Crypto Portfolio Optimization System
==============================================================

This module contains all global constants and configuration parameters.
Changes here affect the entire system - use with caution.

Risk Officer Approval Required for:
- RISK_FREE_RATE changes
- Trading mode defaults
- Drawdown/Sharpe thresholds
"""

import os
from typing import Dict, Any

# =============================================================================
# RISK PARAMETERS (Risk Officer Veto Applies)
# =============================================================================

# Risk-free rate used throughout the system (backtester, optimizer, attribution)
# Rationale: Crypto markets trade 24/7; traditional RF rates (treasury) don't apply.
# Using 0.0 means Sharpe ratios reflect excess return over holding cash.
RISK_FREE_RATE = 0.0

# Default trading mode - NEVER accidentally default to 'live'
# Must be explicitly set via environment variable TRADING_MODE
DEFAULT_TRADING_MODE = 'research'

# Strict thresholds for LIVE_MODE (capital protection)
LIVE_THRESHOLDS = {
    'target_return': 0.0,        # Must be >= 0% annualized
    'max_drawdown': 0.12,        # Circuit breaker at 12% DD
    'min_sharpe': 0.0,           # Must be non-negative
    'max_position_single_asset': 0.40,  # 40% max in any single asset
    'max_gross_exposure': 1.0,   # No leverage by default
}

# Research mode thresholds (for learning/backtesting only)
RESEARCH_THRESHOLDS = {
    'target_return': -0.05,      # Allow negative for learning
    'max_drawdown': 0.25,        # Wider DD tolerance
    'min_sharpe': -1.0,          # Allow negative Sharpe in research
    'max_position_single_asset': 1.0,   # Allow concentrated positions
    'max_gross_exposure': 1.0,   # Still no leverage
}

# =============================================================================
# TRANSACTION COST ASSUMPTIONS
# =============================================================================

# Exchange fee structure (industry standard for crypto)
MAKER_FEE = 0.0004   # 0.04% - limit orders providing liquidity
TAKER_FEE = 0.0010   # 0.10% - market orders taking liquidity

# Default spread assumption (basis points)
DEFAULT_SPREAD_BPS = 10  # 0.001 = 10 bps

# Market impact model parameter (Almgren & Chriss square-root model)
MARKET_IMPACT_ALPHA = 0.01

# =============================================================================
# LIQUIDITY CONSTRAINTS
# =============================================================================

# Maximum position as % of Average Daily Volume (ADV)
MAX_POSITION_PCT_OF_ADV = 0.10  # 10% of ADV

# Maximum volume participation rate per rebalance
MAX_VOLUME_PARTICIPATION = 0.20  # 20% of daily volume

# Minimum daily volume threshold for inclusion ($USD)
MIN_LIQUIDITY_USD = 1_000_000  # $1M daily volume minimum

# Spread threshold for trading (basis points)
MAX_SPREAD_BPS = 50  # Don't trade if spread > 0.50%

# =============================================================================
# DATA QUALITY
# =============================================================================

# Minimum history required for strategy execution
MIN_HISTORY_BARS = 50  # At least 50 bars for any calculation

# Lookback period for regime detection (default ~30 days for daily data)
DEFAULT_LOOKBACK_BARS = 30

# =============================================================================
# ML / ENSEMBLE CONFIGURATION
# =============================================================================

# Walk-forward validation split
ML_TRAIN_TEST_SPLIT = 0.80  # 80% train, 20% test

# OOS Gate threshold (minimum IC correlation)
OOS_IC_THRESHOLD = 0.02  # 2% information coefficient minimum

# Ensemble weights dynamic adjustment frequency
ENSEMBLE_REBALANCE_FREQUENCY = 'daily'  # Options: 'daily', 'weekly', 'monthly'

# =============================================================================
# BACKTESTER DEFAULTS
# =============================================================================

# Initial capital for backtesting
DEFAULT_INITIAL_CAPITAL = 100_000  # $100k

# Transaction cost assumptions (flat model fallback)
DEFAULT_TRANSACTION_COST_RATE = 0.0010  # 0.10% total round-trip
DEFAULT_SLIPPAGE_RATE = 0.0005  # 0.05%

# Rebalance frequency options
REBALANCE_FREQUENCIES = ['daily', 'weekly', 'monthly']
DEFAULT_REBALANCE_FREQUENCY = 'daily'

# =============================================================================
# MONTE CARLO / ROBUSTNESS
# =============================================================================

# Default number of simulations
DEFAULT_N_SIMULATIONS = 1000

# Bootstrap block size (preserves autocorrelation)
BOOTSTRAP_BLOCK_SIZE = 20

# Ruin threshold (capital level considered "ruin")
RUIN_THRESHOLD = 0.50  # 50% loss of initial capital

# Confidence interval level for robustness reports
CONFIDENCE_LEVEL = 0.90  # 90% CI

# =============================================================================
# SCENARIO ANALYSIS STRESS FACTORS
# =============================================================================

SCENARIO_FACTORS: Dict[str, Dict[str, float]] = {
    'baseline': {
        'vol_multiplier': 1.0,
        'correlation_spike': 0.0,
        'volume_reduction': 0.0,
        'impact_multiplier': 1.0,
    },
    'high_vol': {
        'vol_multiplier': 2.0,
        'correlation_spike': 0.0,
        'volume_reduction': 0.0,
        'impact_multiplier': 1.0,
    },
    'crisis': {
        'vol_multiplier': 3.0,
        'correlation_spike': 0.5,  # Correlations go to 1 in crisis
        'volume_reduction': 0.0,
        'impact_multiplier': 1.5,
    },
    'low_liquidity': {
        'vol_multiplier': 1.0,
        'correlation_spike': 0.0,
        'volume_reduction': 0.5,  # 50% less volume
        'impact_multiplier': 2.0,
    },
    'spike_impact': {
        'vol_multiplier': 1.0,
        'correlation_spike': 0.0,
        'volume_reduction': 0.0,
        'impact_multiplier': 2.0,
    },
}

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_trading_mode() -> str:
    """
    Get current trading mode from environment or default.
    
    Returns:
        'research', 'paper', or 'live'
    """
    return os.environ.get('TRADING_MODE', DEFAULT_TRADING_MODE)


def is_live_mode() -> bool:
    """Check if system is in live trading mode."""
    return get_trading_mode() == 'live'


def is_paper_mode() -> bool:
    """Check if system is in paper trading mode."""
    return get_trading_mode() == 'paper'


def is_research_mode() -> bool:
    """Check if system is in research mode."""
    return get_trading_mode() == 'research'


def get_risk_thresholds() -> Dict[str, float]:
    """
    Get appropriate risk thresholds based on trading mode.
    
    Returns:
        Dict with threshold values
    """
    mode = get_trading_mode()
    if mode == 'live':
        return LIVE_THRESHOLDS
    elif mode == 'paper':
        # Paper uses live thresholds but without circuit breaker enforcement
        return LIVE_THRESHOLDS
    else:  # research
        return RESEARCH_THRESHOLDS


def validate_config_sanity() -> None:
    """
    Validate that configuration values are sane.
    
    Raises:
        ValueError: If any critical value is out of acceptable range
    """
    if RISK_FREE_RATE < 0:
        raise ValueError(f"RISK_FREE_RATE cannot be negative: {RISK_FREE_RATE}")
    
    if MAX_POSITION_PCT_OF_ADV <= 0 or MAX_POSITION_PCT_OF_ADV > 1:
        raise ValueError(f"MAX_POSITION_PCT_OF_ADV must be in (0, 1]: {MAX_POSITION_PCT_OF_ADV}")
    
    if MIN_LIQUIDITY_USD < 0:
        raise ValueError(f"MIN_LIQUIDITY_USD cannot be negative: {MIN_LIQUIDITY_USD}")
    
    if not 0 <= CONFIDENCE_LEVEL <= 1:
        raise ValueError(f"CONFIDENCE_LEVEL must be in [0, 1]: {CONFIDENCE_LEVEL}")
    
    # Live mode must have stricter thresholds than research
    live = LIVE_THRESHOLDS
    research = RESEARCH_THRESHOLDS
    if live['max_drawdown'] > research['max_drawdown']:
        raise ValueError(
            f"LIVE max_drawdown ({live['max_drawdown']}) must be <= "
            f"RESEARCH max_drawdown ({research['max_drawdown']})"
        )


# Run sanity check on module load
validate_config_sanity()
