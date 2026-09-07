"""
Configuration module.

Provides centralized configuration management for the trading system.
"""

from .settings import (
    # Risk parameters
    RISK_FREE_RATE,
    DEFAULT_TRADING_MODE,
    LIVE_THRESHOLDS,
    RESEARCH_THRESHOLDS,
    # Transaction costs
    MAKER_FEE,
    TAKER_FEE,
    DEFAULT_SPREAD_BPS,
    MARKET_IMPACT_ALPHA,
    # Liquidity
    MAX_POSITION_PCT_OF_ADV,
    MAX_VOLUME_PARTICIPATION,
    MIN_LIQUIDITY_USD,
    MAX_SPREAD_BPS,
    # Data quality
    MIN_HISTORY_BARS,
    DEFAULT_LOOKBACK_BARS,
    # ML/Ensemble
    ML_TRAIN_TEST_SPLIT,
    OOS_IC_THRESHOLD,
    ENSEMBLE_REBALANCE_FREQUENCY,
    # Backtester
    DEFAULT_INITIAL_CAPITAL,
    DEFAULT_TRANSACTION_COST_RATE,
    DEFAULT_SLIPPAGE_RATE,
    REBALANCE_FREQUENCIES,
    DEFAULT_REBALANCE_FREQUENCY,
    # Monte Carlo
    DEFAULT_N_SIMULATIONS,
    BOOTSTRAP_BLOCK_SIZE,
    RUIN_THRESHOLD,
    CONFIDENCE_LEVEL,
    # Scenarios
    SCENARIO_FACTORS,
    # Helper functions
    get_trading_mode,
    is_live_mode,
    is_paper_mode,
    is_research_mode,
    get_risk_thresholds,
    validate_config_sanity,
)

__all__ = [
    # Risk parameters
    'RISK_FREE_RATE',
    'DEFAULT_TRADING_MODE',
    'LIVE_THRESHOLDS',
    'RESEARCH_THRESHOLDS',
    # Transaction costs
    'MAKER_FEE',
    'TAKER_FEE',
    'DEFAULT_SPREAD_BPS',
    'MARKET_IMPACT_ALPHA',
    # Liquidity
    'MAX_POSITION_PCT_OF_ADV',
    'MAX_VOLUME_PARTICIPATION',
    'MIN_LIQUIDITY_USD',
    'MAX_SPREAD_BPS',
    # Data quality
    'MIN_HISTORY_BARS',
    'DEFAULT_LOOKBACK_BARS',
    # ML/Ensemble
    'ML_TRAIN_TEST_SPLIT',
    'OOS_IC_THRESHOLD',
    'ENSEMBLE_REBALANCE_FREQUENCY',
    # Backtester
    'DEFAULT_INITIAL_CAPITAL',
    'DEFAULT_TRANSACTION_COST_RATE',
    'DEFAULT_SLIPPAGE_RATE',
    'REBALANCE_FREQUENCIES',
    'DEFAULT_REBALANCE_FREQUENCY',
    # Monte Carlo
    'DEFAULT_N_SIMULATIONS',
    'BOOTSTRAP_BLOCK_SIZE',
    'RUIN_THRESHOLD',
    'CONFIDENCE_LEVEL',
    # Scenarios
    'SCENARIO_FACTORS',
    # Helper functions
    'get_trading_mode',
    'is_live_mode',
    'is_paper_mode',
    'is_research_mode',
    'get_risk_thresholds',
    'validate_config_sanity',
]
