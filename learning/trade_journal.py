"""
Phase 39: Post-Launch Monitoring & Optimization

Trade journal for detailed trade analysis and learning.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import pandas as pd
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class TradeEntry:
    """Detailed trade record for journal."""
    trade_id: str
    timestamp: datetime
    symbol: str
    side: str
    size: float
    entry_price: float
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    pnl: float = 0.0
    pnl_percent: float = 0.0
    fees: float = 0.0
    slippage: float = 0.0
    strategy: str = ""
    signal_strength: float = 0.0
    regime: str = ""
    market_conditions: Dict[str, Any] = field(default_factory=dict)
    holding_period_hours: float = 0.0
    notes: str = ""
    
    # Analysis fields
    outcome: str = ""  # 'win', 'loss', 'breakeven'
    effectiveness_score: float = 0.0
    lessons_learned: str = ""
    
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
            'signal_strength': self.signal_strength,
            'regime': self.regime,
            'market_conditions': self.market_conditions,
            'holding_period_hours': self.holding_period_hours,
            'notes': self.notes,
            'outcome': self.outcome,
            'effectiveness_score': self.effectiveness_score,
            'lessons_learned': self.lessons_learned
        }


class TradeJournal:
    """
    Maintain detailed trade journal for learning and analysis.
    
    Records trades with full context and analyzes patterns.
    """
    
    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = storage_path or 'results/trade_journal.json'
        self.trades: List[TradeEntry] = []
        self.analyses: List[Dict] = []
        
        # Load existing trades if available
        self._load_trades()
        
        logger.info(f"TradeJournal initialized - {len(self.trades)} trades loaded")
    
    def _load_trades(self):
        """Load trades from storage."""
        path = Path(self.storage_path)
        if path.exists():
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                    self.trades = [
                        TradeEntry(
                            trade_id=t['trade_id'],
                            timestamp=datetime.fromisoformat(t['timestamp']),
                            symbol=t['symbol'],
                            side=t['side'],
                            size=t['size'],
                            entry_price=t['entry_price'],
                            exit_price=t.get('exit_price'),
                            exit_time=datetime.fromisoformat(t['exit_time']) if t.get('exit_time') else None,
                            pnl=t.get('pnl', 0.0),
                            pnl_percent=t.get('pnl_percent', 0.0),
                            fees=t.get('fees', 0.0),
                            slippage=t.get('slippage', 0.0),
                            strategy=t.get('strategy', ''),
                            signal_strength=t.get('signal_strength', 0.0),
                            regime=t.get('regime', ''),
                            market_conditions=t.get('market_conditions', {}),
                            holding_period_hours=t.get('holding_period_hours', 0.0),
                            notes=t.get('notes', ''),
                            outcome=t.get('outcome', ''),
                            effectiveness_score=t.get('effectiveness_score', 0.0),
                            lessons_learned=t.get('lessons_learned', '')
                        )
                        for t in data.get('trades', [])
                    ]
                    self.analyses = data.get('analyses', [])
                logger.info(f"Loaded {len(self.trades)} trades from {self.storage_path}")
            except Exception as e:
                logger.error(f"Failed to load journal: {e}")
    
    def _save_trades(self):
        """Save trades to storage."""
        data = {
            'trades': [t.to_dict() for t in self.trades],
            'analyses': self.analyses,
            'last_updated': datetime.utcnow().isoformat()
        }
        
        Path(self.storage_path).parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.storage_path, 'w') as f:
            json.dump(data, f, indent=2, default=str)
    
    def record_trade(self, trade_data: Dict[str, Any]) -> str:
        """Record a new trade."""
        trade = TradeEntry(
            trade_id=trade_data.get('id', f"trade_{len(self.trades)}"),
            timestamp=datetime.fromisoformat(trade_data.get('timestamp', datetime.utcnow().isoformat())),
            symbol=trade_data.get('symbol', 'UNKNOWN'),
            side=trade_data.get('side', 'long'),
            size=trade_data.get('size', 0.0),
            entry_price=trade_data.get('entry_price', 0.0),
            signal_strength=trade_data.get('signal_strength', 0.0),
            regime=trade_data.get('regime', ''),
            market_conditions=trade_data.get('market_conditions', {}),
            strategy=trade_data.get('strategy', ''),
            notes=trade_data.get('notes', '')
        )
        
        self.trades.append(trade)
        self._save_trades()
        
        logger.info(f"Recorded trade: {trade.trade_id} - {trade.side} {trade.size} {trade.symbol}")
        return trade.trade_id
    
    def record_exit(self, trade_id: str, exit_price: float, 
                   exit_time: Optional[datetime] = None,
                   fees: float = 0.0, slippage: float = 0.0):
        """Record trade exit and analyze."""
        for trade in self.trades:
            if trade.trade_id == trade_id:
                trade.exit_price = exit_price
                trade.exit_time = exit_time or datetime.utcnow()
                trade.fees = fees
                trade.slippage = slippage
                
                # Calculate PnL
                if trade.side == 'long':
                    trade.pnl = (exit_price - trade.entry_price) * trade.size - fees
                else:
                    trade.pnl = (trade.entry_price - exit_price) * trade.size - fees
                
                trade.pnl_percent = trade.pnl / (trade.entry_price * trade.size) if trade.entry_price > 0 else 0
                
                # Calculate holding period
                trade.holding_period_hours = (trade.exit_time - trade.timestamp).total_seconds() / 3600
                
                # Determine outcome
                if trade.pnl > 0:
                    trade.outcome = 'win'
                elif trade.pnl < 0:
                    trade.outcome = 'loss'
                else:
                    trade.outcome = 'breakeven'
                
                # Analyze trade
                self.analyze_trade(trade)
                
                self._save_trades()
                logger.info(f"Recorded exit for {trade_id}: PnL={trade.pnl:.2f}")
                return
        
        logger.warning(f"Trade {trade_id} not found")
    
    def analyze_trade(self, trade: TradeEntry):
        """Analyze a completed trade."""
        analysis = {
            'trade_id': trade.trade_id,
            'timestamp': datetime.utcnow().isoformat(),
            'profit_percentage': trade.pnl_percent,
            'holding_period_hours': trade.holding_period_hours,
            'strategy': trade.strategy,
            'regime': trade.regime,
            'outcome': trade.outcome,
            'signal_strength': trade.signal_strength,
            'fees_paid': trade.fees,
            'slippage_paid': trade.slippage
        }
        
        # Add effectiveness analysis
        analysis['effectiveness'] = self._evaluate_effectiveness(trade)
        
        # Add pattern analysis
        analysis['patterns'] = self._identify_patterns(trade)
        
        self.analyses.append(analysis)
        
        # Update trade with lessons
        trade.effectiveness_score = analysis['effectiveness']['score']
        trade.lessons_learned = self._generate_lessons(trade, analysis)
    
    def _evaluate_effectiveness(self, trade: TradeEntry) -> Dict[str, Any]:
        """Evaluate trade effectiveness."""
        score = 0.0
        factors = []
        
        # PnL contribution
        if trade.pnl_percent > 0.02:
            score += 0.3
            factors.append('strong_profit')
        elif trade.pnl_percent > 0:
            score += 0.15
            factors.append('profit')
        
        # Signal strength alignment
        if trade.signal_strength > 0.7 and trade.pnl > 0:
            score += 0.2
            factors.append('strong_signal_validated')
        
        # Holding period efficiency
        if 1 <= trade.holding_period_hours <= 48:
            score += 0.2
            factors.append('optimal_holding_period')
        elif trade.holding_period_hours < 1:
            score += 0.1
            factors.append('short_term')
        
        # Cost efficiency
        cost_ratio = (trade.fees + trade.slippage) / abs(trade.pnl) if trade.pnl != 0 else 1
        if cost_ratio < 0.1:
            score += 0.3
            factors.append('low_costs')
        elif cost_ratio < 0.2:
            score += 0.15
            factors.append('reasonable_costs')
        
        return {
            'score': min(score, 1.0),
            'factors': factors,
            'cost_ratio': cost_ratio
        }
    
    def _identify_patterns(self, trade: TradeEntry) -> Dict[str, Any]:
        """Identify patterns in the trade."""
        patterns = {}
        
        # Check if this matches historical patterns
        similar_trades = [
            t for t in self.trades[:-1]  # Exclude current trade
            if t.strategy == trade.strategy and t.regime == trade.regime
        ]
        
        if similar_trades:
            avg_pnl = sum(t.pnl_percent for t in similar_trades) / len(similar_trades)
            win_rate = sum(1 for t in similar_trades if t.pnl > 0) / len(similar_trades)
            
            patterns['historical_performance'] = {
                'avg_pnl': avg_pnl,
                'win_rate': win_rate,
                'sample_size': len(similar_trades)
            }
        
        return patterns
    
    def _generate_lessons(self, trade: TradeEntry, analysis: Dict) -> str:
        """Generate lessons learned from trade."""
        lessons = []
        
        if trade.outcome == 'win':
            if trade.pnl_percent > 0.05:
                lessons.append("Strong profit - strategy working well in this regime")
            if trade.holding_period_hours < 4:
                lessons.append("Quick profit taking was effective")
        else:
            if trade.pnl_percent < -0.05:
                lessons.append("Large loss - review stop loss strategy")
            if trade.holding_period_hours > 168:  # 1 week
                lessons.append("Very long holding period - consider time-based exits")
        
        if analysis['effectiveness']['cost_ratio'] > 0.2:
            lessons.append("High transaction costs - review execution strategy")
        
        return "; ".join(lessons) if lessons else "No specific lessons identified"
    
    def get_summary_statistics(self) -> Dict[str, Any]:
        """Get summary statistics from journal."""
        if not self.trades:
            return {'status': 'no_trades'}
        
        closed_trades = [t for t in self.trades if t.exit_price is not None]
        
        if not closed_trades:
            return {'status': 'no_closed_trades'}
        
        total_pnl = sum(t.pnl for t in closed_trades)
        wins = [t for t in closed_trades if t.pnl > 0]
        losses = [t for t in closed_trades if t.pnl < 0]
        
        return {
            'total_trades': len(closed_trades),
            'wins': len(wins),
            'losses': len(losses),
            'win_rate': len(wins) / len(closed_trades),
            'total_pnl': total_pnl,
            'avg_pnl': total_pnl / len(closed_trades),
            'avg_win': sum(t.pnl for t in wins) / len(wins) if wins else 0,
            'avg_loss': sum(t.pnl for t in losses) / len(losses) if losses else 0,
            'profit_factor': abs(sum(t.pnl for t in wins) / sum(t.pnl for t in losses)) if losses and sum(t.pnl for t in losses) != 0 else float('inf'),
            'avg_holding_period_hours': sum(t.holding_period_hours for t in closed_trades) / len(closed_trades),
            'avg_effectiveness_score': sum(t.effectiveness_score for t in closed_trades) / len(closed_trades)
        }
    
    def analyze_by_strategy(self) -> Dict[str, Dict[str, Any]]:
        """Analyze performance by strategy."""
        strategies = set(t.strategy for t in self.trades if t.strategy and t.exit_price)
        
        results = {}
        for strategy in strategies:
            strat_trades = [t for t in self.trades if t.strategy == strategy and t.exit_price]
            if not strat_trades:
                continue
            
            wins = [t for t in strat_trades if t.pnl > 0]
            total_pnl = sum(t.pnl for t in strat_trades)
            
            results[strategy] = {
                'trade_count': len(strat_trades),
                'wins': len(wins),
                'losses': len(strat_trades) - len(wins),
                'win_rate': len(wins) / len(strat_trades),
                'total_pnl': total_pnl,
                'avg_pnl': total_pnl / len(strat_trades),
                'avg_effectiveness': sum(t.effectiveness_score for t in strat_trades) / len(strat_trades)
            }
        
        return results
    
    def analyze_by_regime(self) -> Dict[str, Dict[str, Any]]:
        """Analyze performance by market regime."""
        regimes = set(t.regime for t in self.trades if t.regime and t.exit_price)
        
        results = {}
        for regime in regimes:
            regime_trades = [t for t in self.trades if t.regime == regime and t.exit_price]
            if not regime_trades:
                continue
            
            wins = [t for t in regime_trades if t.pnl > 0]
            total_pnl = sum(t.pnl for t in regime_trades)
            
            results[regime] = {
                'trade_count': len(regime_trades),
                'wins': len(wins),
                'win_rate': len(wins) / len(regime_trades),
                'total_pnl': total_pnl,
                'avg_pnl': total_pnl / len(regime_trades)
            }
        
        return results
    
    def export_report(self, filepath: str):
        """Export journal report to file."""
        report = {
            'generated_at': datetime.utcnow().isoformat(),
            'summary': self.get_summary_statistics(),
            'by_strategy': self.analyze_by_strategy(),
            'by_regime': self.analyze_by_regime(),
            'recent_trades': [t.to_dict() for t in self.trades[-20:]],
            'analyses': self.analyses[-50:]
        }
        
        with open(filepath, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        logger.info(f"Report exported to {filepath}")


def init_journal(storage_path: Optional[str] = None) -> TradeJournal:
    """Initialize trade journal."""
    return TradeJournal(storage_path)


if __name__ == "__main__":
    # Demo usage
    journal = TradeJournal('results/demo_trade_journal.json')
    
    # Record sample trades
    trade1_id = journal.record_trade({
        'id': 'demo_1',
        'symbol': 'BTC',
        'side': 'long',
        'size': 0.1,
        'entry_price': 50000,
        'strategy': 'momentum',
        'regime': 'bull',
        'signal_strength': 0.8,
        'market_conditions': {'volatility': 0.02, 'volume': 'high'}
    })
    
    # Record exit
    journal.record_exit(
        trade1_id,
        exit_price=51500,
        fees=5,
        slippage=2
    )
    
    # Print summary
    print("\n=== Trade Journal Summary ===")
    summary = journal.get_summary_statistics()
    for key, value in summary.items():
        print(f"{key}: {value}")
    
    print("\n=== By Strategy ===")
    strategies = journal.analyze_by_strategy()
    print(json.dumps(strategies, indent=2))
