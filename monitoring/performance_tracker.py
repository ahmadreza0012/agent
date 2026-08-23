"""
Phase 39: Post-Launch Monitoring & Optimization

Performance tracker for monitoring and analyzing trading system performance.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import pandas as pd
import numpy as np
import logging
import json
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class TradeRecord:
    """Record of a completed trade."""
    trade_id: str
    timestamp: datetime
    symbol: str
    side: str  # 'long' or 'short'
    size: float
    entry_price: float
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    pnl: float = 0.0
    pnl_percent: float = 0.0
    fees: float = 0.0
    slippage: float = 0.0
    strategy: str = ""
    regime: str = ""
    holding_period_hours: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'trade_id': self.trade_id,
            'timestamp': self.timestamp.isoformat(),
            'symbol': self.symbol,
            'side': self.side,
            'size': self.size,
            'entry_price': self.entry_price,
            'exit_price': self.exit_price,
            'exit_time': self.exit_time.isoformat() if self.exit_time else None,
            'pnl': self.pnl,
            'pnl_percent': self.pnl_percent,
            'fees': self.fees,
            'slippage': self.slippage,
            'strategy': self.strategy,
            'regime': self.regime,
            'holding_period_hours': self.holding_period_hours
        }


class PerformanceTracker:
    """
    Track and analyze system performance.
    
    Records trades, calculates metrics, and detects performance degradation.
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.trades: List[TradeRecord] = []
        self.daily_returns: List[float] = []
        self.weekly_returns: List[float] = []
        self.monthly_returns: List[float] = []
        self.drawdowns: List[float] = []
        self.equity_curve: List[Tuple[datetime, float]] = []
        
        # Configuration
        self.min_trades_for_analysis = self.config.get('min_trades', 30)
        self.degradation_threshold = self.config.get('degradation_threshold', 0.7)
        
        logger.info("PerformanceTracker initialized")
    
    def record_trade(self, trade_data: Dict[str, Any]):
        """Record a completed trade."""
        trade = TradeRecord(
            trade_id=trade_data.get('id', f"trade_{len(self.trades)}"),
            timestamp=datetime.fromisoformat(trade_data.get('timestamp', datetime.utcnow().isoformat())),
            symbol=trade_data.get('symbol', 'UNKNOWN'),
            side=trade_data.get('side', 'long'),
            size=trade_data.get('size', 0.0),
            entry_price=trade_data.get('entry_price', 0.0),
            exit_price=trade_data.get('exit_price'),
            exit_time=datetime.fromisoformat(trade_data['exit_time']) if trade_data.get('exit_time') else None,
            pnl=trade_data.get('pnl', 0.0),
            pnl_percent=trade_data.get('pnl_percent', 0.0),
            fees=trade_data.get('fees', 0.0),
            slippage=trade_data.get('slippage', 0.0),
            strategy=trade_data.get('strategy', ''),
            regime=trade_data.get('regime', ''),
            holding_period_hours=trade_data.get('holding_period_hours', 0.0)
        )
        
        self.trades.append(trade)
        self._update_returns(trade)
        
        logger.info(f"Recorded trade: {trade.trade_id} - PnL: {trade.pnl:.2f}")
    
    def _update_returns(self, trade: TradeRecord):
        """Update return series with new trade."""
        if trade.pnl_percent != 0:
            self.daily_returns.append(trade.pnl_percent)
            
            # Update weekly/monthly returns (simplified)
            if len(self.daily_returns) % 7 == 0:
                weekly_return = sum(self.daily_returns[-7:])
                self.weekly_returns.append(weekly_return)
            
            if len(self.daily_returns) % 30 == 0:
                monthly_return = sum(self.daily_returns[-30:])
                self.monthly_returns.append(monthly_return)
    
    def calculate_rolling_metrics(self, window_days: int = 30) -> Dict[str, float]:
        """Calculate rolling performance metrics."""
        if len(self.daily_returns) < window_days:
            returns = self.daily_returns
        else:
            returns = self.daily_returns[-window_days:]
        
        if not returns:
            return self._empty_metrics()
        
        series = pd.Series(returns)
        
        # Calculate metrics
        sharpe = self._calculate_sharpe(series)
        sortino = self._calculate_sortino(series)
        volatility = self._calculate_volatility(series)
        max_dd = self._calculate_max_drawdown(series)
        win_rate = self._calculate_win_rate(series)
        profit_factor = self._calculate_profit_factor(series)
        
        return {
            'rolling_sharpe': sharpe,
            'rolling_sortino': sortino,
            'rolling_volatility': volatility,
            'rolling_max_dd': max_dd,
            'rolling_win_rate': win_rate,
            'rolling_profit_factor': profit_factor
        }
    
    def _calculate_sharpe(self, returns: pd.Series, annualize: bool = True) -> float:
        """Calculate Sharpe ratio."""
        if returns.std() == 0 or len(returns) < 2:
            return 0.0
        
        sharpe = returns.mean() / returns.std()
        if annualize:
            sharpe *= np.sqrt(252)
        
        return round(sharpe, 4)
    
    def _calculate_sortino(self, returns: pd.Series, annualize: bool = True) -> float:
        """Calculate Sortino ratio."""
        downside = returns[returns < 0]
        if len(downside) < 2 or downside.std() == 0:
            return 0.0
        
        sortino = returns.mean() / downside.std()
        if annualize:
            sortino *= np.sqrt(252)
        
        return round(sortino, 4)
    
    def _calculate_volatility(self, returns: pd.Series, annualize: bool = True) -> float:
        """Calculate volatility."""
        vol = returns.std()
        if annualize:
            vol *= np.sqrt(252)
        
        return round(vol, 4)
    
    def _calculate_max_drawdown(self, returns: pd.Series) -> float:
        """Calculate maximum drawdown from returns."""
        cumulative = (1 + returns).cumprod()
        running_max = cumulative.cummax()
        drawdown = (cumulative - running_max) / running_max
        
        return round(abs(drawdown.min()), 4) if len(drawdown) > 0 else 0.0
    
    def _calculate_win_rate(self, returns: pd.Series) -> float:
        """Calculate win rate."""
        if len(returns) == 0:
            return 0.0
        
        wins = (returns > 0).sum()
        return round(wins / len(returns), 4)
    
    def _calculate_profit_factor(self, returns: pd.Series) -> float:
        """Calculate profit factor."""
        gross_profit = returns[returns > 0].sum()
        gross_loss = abs(returns[returns < 0].sum())
        
        if gross_loss == 0:
            return float('inf') if gross_profit > 0 else 0.0
        
        return round(gross_profit / gross_loss, 4)
    
    def _empty_metrics(self) -> Dict[str, float]:
        """Return empty metrics dict."""
        return {
            'rolling_sharpe': 0.0,
            'rolling_sortino': 0.0,
            'rolling_volatility': 0.0,
            'rolling_max_dd': 0.0,
            'rolling_win_rate': 0.0,
            'rolling_profit_factor': 0.0
        }
    
    def detect_degradation(self, lookback_days: int = 30, baseline_days: int = 90) -> Dict[str, Any]:
        """Detect if performance is degrading."""
        if len(self.daily_returns) < lookback_days:
            return {'degradation_detected': False, 'reason': 'Insufficient data'}
        
        # Get recent and baseline periods
        recent = pd.Series(self.daily_returns[-lookback_days:])
        baseline = pd.Series(self.daily_returns[-baseline_days:-lookback_days]) if len(self.daily_returns) > baseline_days else pd.Series(self.daily_returns[:-lookback_days])
        
        if len(baseline) < 10:
            return {'degradation_detected': False, 'reason': 'Insufficient baseline data'}
        
        # Compare Sharpe ratios
        recent_sharpe = self._calculate_sharpe(recent, annualize=False)
        baseline_sharpe = self._calculate_sharpe(baseline, annualize=False)
        
        degradation_detected = False
        reasons = []
        
        # Check Sharpe degradation
        if baseline_sharpe > 0 and recent_sharpe < baseline_sharpe * self.degradation_threshold:
            degradation_detected = True
            reasons.append(f"Sharpe degraded from {baseline_sharpe:.2f} to {recent_sharpe:.2f}")
        
        # Check win rate degradation
        recent_wr = self._calculate_win_rate(recent)
        baseline_wr = self._calculate_win_rate(baseline)
        if baseline_wr > 0.5 and recent_wr < baseline_wr * self.degradation_threshold:
            degradation_detected = True
            reasons.append(f"Win rate degraded from {baseline_wr:.2%} to {recent_wr:.2%}")
        
        # Check volatility increase
        recent_vol = self._calculate_volatility(recent, annualize=False)
        baseline_vol = self._calculate_volatility(baseline, annualize=False)
        if recent_vol > baseline_vol * 1.5:
            degradation_detected = True
            reasons.append(f"Volatility increased from {baseline_vol:.2%} to {recent_vol:.2%}")
        
        return {
            'degradation_detected': degradation_detected,
            'reasons': reasons,
            'recent_sharpe': recent_sharpe,
            'baseline_sharpe': baseline_sharpe,
            'recent_win_rate': recent_wr if 'recent_wr' in dir() else 0.0,
            'baseline_win_rate': baseline_wr if 'baseline_wr' in dir() else 0.0,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get comprehensive performance summary."""
        if not self.trades:
            return {'status': 'no_trades'}
        
        # Basic stats
        total_trades = len(self.trades)
        winning_trades = sum(1 for t in self.trades if t.pnl > 0)
        losing_trades = sum(1 for t in self.trades if t.pnl < 0)
        
        total_pnl = sum(t.pnl for t in self.trades)
        avg_pnl = total_pnl / total_trades if total_trades > 0 else 0.0
        
        # Calculate metrics
        returns = pd.Series([t.pnl_percent for t in self.trades if t.pnl_percent != 0])
        
        if len(returns) > 0:
            sharpe = self._calculate_sharpe(returns)
            sortino = self._calculate_sortino(returns)
            win_rate = winning_trades / total_trades
            profit_factor = self._calculate_profit_factor(returns)
            max_dd = self._calculate_max_drawdown(returns)
        else:
            sharpe = sortino = win_rate = profit_factor = max_dd = 0.0
        
        return {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'total_pnl': total_pnl,
            'avg_pnl': avg_pnl,
            'sharpe_ratio': sharpe,
            'sortino_ratio': sortino,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'max_drawdown': max_dd,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def analyze_by_strategy(self) -> Dict[str, Dict[str, Any]]:
        """Analyze performance by strategy."""
        strategies = set(t.strategy for t in self.trades if t.strategy)
        
        results = {}
        for strategy in strategies:
            strategy_trades = [t for t in self.trades if t.strategy == strategy]
            if not strategy_trades:
                continue
            
            returns = pd.Series([t.pnl_percent for t in strategy_trades if t.pnl_percent != 0])
            if len(returns) < 3:
                continue
            
            wins = sum(1 for t in strategy_trades if t.pnl > 0)
            
            results[strategy] = {
                'trade_count': len(strategy_trades),
                'total_pnl': sum(t.pnl for t in strategy_trades),
                'win_rate': wins / len(strategy_trades),
                'sharpe': self._calculate_sharpe(returns),
                'avg_pnl': sum(t.pnl for t in strategy_trades) / len(strategy_trades)
            }
        
        return results
    
    def analyze_by_regime(self) -> Dict[str, Dict[str, Any]]:
        """Analyze performance by market regime."""
        regimes = set(t.regime for t in self.trades if t.regime)
        
        results = {}
        for regime in regimes:
            regime_trades = [t for t in self.trades if t.regime == regime]
            if not regime_trades:
                continue
            
            returns = pd.Series([t.pnl_percent for t in regime_trades if t.pnl_percent != 0])
            if len(returns) < 3:
                continue
            
            wins = sum(1 for t in regime_trades if t.pnl > 0)
            
            results[regime] = {
                'trade_count': len(regime_trades),
                'total_pnl': sum(t.pnl for t in regime_trades),
                'win_rate': wins / len(regime_trades),
                'sharpe': self._calculate_sharpe(returns),
                'avg_pnl': sum(t.pnl for t in regime_trades) / len(regime_trades)
            }
        
        return results
    
    def save(self, filepath: str):
        """Save performance data to file."""
        data = {
            'trades': [t.to_dict() for t in self.trades],
            'daily_returns': self.daily_returns,
            'weekly_returns': self.weekly_returns,
            'monthly_returns': self.monthly_returns,
            'summary': self.get_performance_summary()
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        
        logger.info(f"Performance data saved to {filepath}")
    
    @classmethod
    def load(cls, filepath: str) -> 'PerformanceTracker':
        """Load performance data from file."""
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        tracker = cls()
        tracker.daily_returns = data.get('daily_returns', [])
        tracker.weekly_returns = data.get('weekly_returns', [])
        tracker.monthly_returns = data.get('monthly_returns', [])
        
        for trade_data in data.get('trades', []):
            trade = TradeRecord(
                trade_id=trade_data['trade_id'],
                timestamp=datetime.fromisoformat(trade_data['timestamp']),
                symbol=trade_data['symbol'],
                side=trade_data['side'],
                size=trade_data['size'],
                entry_price=trade_data['entry_price'],
                exit_price=trade_data.get('exit_price'),
                pnl=trade_data['pnl'],
                pnl_percent=trade_data['pnl_percent'],
                fees=trade_data.get('fees', 0.0),
                slippage=trade_data.get('slippage', 0.0),
                strategy=trade_data.get('strategy', ''),
                regime=trade_data.get('regime', ''),
                holding_period_hours=trade_data.get('holding_period_hours', 0.0)
            )
            tracker.trades.append(trade)
        
        logger.info(f"Performance data loaded from {filepath}")
        return tracker


def run_tracker(config: Optional[Dict] = None):
    """Run performance tracker demo."""
    tracker = PerformanceTracker(config)
    
    # Demo: Add some sample trades
    sample_trades = [
        {'id': 't1', 'timestamp': datetime.utcnow().isoformat(), 'symbol': 'BTC', 
         'side': 'long', 'size': 0.1, 'entry_price': 50000, 'exit_price': 51000,
         'pnl': 100, 'pnl_percent': 0.02, 'strategy': 'momentum', 'regime': 'bull'},
        {'id': 't2', 'timestamp': datetime.utcnow().isoformat(), 'symbol': 'ETH',
         'side': 'short', 'size': 1.0, 'entry_price': 3000, 'exit_price': 2900,
         'pnl': 100, 'pnl_percent': 0.033, 'strategy': 'mean_reversion', 'regime': 'bear'},
        {'id': 't3', 'timestamp': datetime.utcnow().isoformat(), 'symbol': 'BTC',
         'side': 'long', 'size': 0.1, 'entry_price': 51000, 'exit_price': 50500,
         'pnl': -50, 'pnl_percent': -0.01, 'strategy': 'momentum', 'regime': 'bull'},
    ]
    
    for trade in sample_trades:
        tracker.record_trade(trade)
    
    # Calculate metrics
    print("\n=== Performance Summary ===")
    summary = tracker.get_performance_summary()
    for key, value in summary.items():
        print(f"{key}: {value}")
    
    print("\n=== Rolling Metrics (30 days) ===")
    rolling = tracker.calculate_rolling_metrics()
    for key, value in rolling.items():
        print(f"{key}: {value}")
    
    print("\n=== Degradation Check ===")
    degradation = tracker.detect_degradation()
    for key, value in degradation.items():
        print(f"{key}: {value}")
    
    print("\n=== Strategy Analysis ===")
    strategies = tracker.analyze_by_strategy()
    for strategy, metrics in strategies.items():
        print(f"\n{strategy}:")
        for key, value in metrics.items():
            print(f"  {key}: {value}")


if __name__ == "__main__":
    run_tracker()
