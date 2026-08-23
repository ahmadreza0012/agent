"""
Performance Targets Module for Phase 32.

Realistic performance target framework for crypto trading systems.
Focuses on honest expectations, risk-adjusted targets, and market realities.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum
import pandas as pd
import numpy as np
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class TargetType(Enum):
    """Types of performance targets."""
    MINIMUM_VIABILITY = "minimum_viability"
    IMPROVEMENT = "improvement"
    EXCELLENT = "excellent"
    STRETCH = "stretch"


class MarketRegime(Enum):
    """Market regimes for target context."""
    BULL = "bull"
    BEAR = "bear"
    SIDEWAYS = "sideways"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"
    NORMAL = "normal"


@dataclass
class PerformanceTarget:
    """Definition of a performance target."""
    name: str
    target_type: TargetType
    metric: str
    value: float
    condition: str
    timeframe: str
    confidence: float
    justification: str
    risk_adjusted: bool = True
    benchmark: Optional[str] = None


@dataclass
class TargetAssessment:
    """Assessment of target achievement."""
    target: PerformanceTarget
    achieved_value: float
    percentage_achieved: float
    is_achieved: bool
    gap: float
    recommendation: str
    timestamp: str = field(default_factory=lambda: str(datetime.now()))


@dataclass
class PerformanceTargetSet:
    """Complete set of performance targets."""
    system_name: str
    version: str
    targets: List[PerformanceTarget]
    assumptions: List[str]
    risk_constraints: List[str]
    benchmark_requirements: List[str]
    created_date: str = field(default_factory=lambda: str(datetime.now()))
    review_date: Optional[str] = None


class PerformanceTargetManager:
    """
    Manage and track realistic performance targets.
    
    This class implements a comprehensive framework for defining,
    assessing, and tracking realistic performance targets for
    crypto trading systems.
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.targets: Dict[str, PerformanceTargetSet] = {}
        self.assessments: Dict[str, List[TargetAssessment]] = {}
        
    def create_target_set(self, name: str, version: str = "1.0.0") -> PerformanceTargetSet:
        """Create a new target set with realistic targets."""
        
        targets = [
            # Minimum viability targets (must achieve to consider system viable)
            PerformanceTarget(
                name="Positive Risk-Adjusted Return",
                target_type=TargetType.MINIMUM_VIABILITY,
                metric="sharpe_ratio",
                value=0.3,
                condition="all_market_conditions",
                timeframe="1_year",
                confidence=0.85,
                justification="Minimum required to justify active management",
                risk_adjusted=True,
                benchmark=None
            ),
            PerformanceTarget(
                name="Beat Buy & Hold",
                target_type=TargetType.MINIMUM_VIABILITY,
                metric="excess_return",
                value=0.05,
                condition="all_market_conditions",
                timeframe="1_year",
                confidence=0.80,
                justification="Must beat passive benchmark",
                risk_adjusted=False,
                benchmark="buy_and_hold_btc"
            ),
            PerformanceTarget(
                name="Controlled Drawdown",
                target_type=TargetType.MINIMUM_VIABILITY,
                metric="max_drawdown",
                value=0.30,
                condition="all_market_conditions",
                timeframe="1_year",
                confidence=0.90,
                justification="Risk must be manageable",
                risk_adjusted=True,
                benchmark=None
            ),
            
            # Improvement targets (good to achieve)
            PerformanceTarget(
                name="Strong Sharpe",
                target_type=TargetType.IMPROVEMENT,
                metric="sharpe_ratio",
                value=0.6,
                condition="normal_market_conditions",
                timeframe="1_year",
                confidence=0.70,
                justification="Good risk-adjusted performance",
                risk_adjusted=True,
                benchmark=None
            ),
            PerformanceTarget(
                name="Low Drawdown",
                target_type=TargetType.IMPROVEMENT,
                metric="max_drawdown",
                value=0.20,
                condition="normal_market_conditions",
                timeframe="1_year",
                confidence=0.75,
                justification="Strong risk management",
                risk_adjusted=True,
                benchmark=None
            ),
            PerformanceTarget(
                name="Positive Monthly Returns",
                target_type=TargetType.IMPROVEMENT,
                metric="win_rate",
                value=0.55,
                condition="all_market_conditions",
                timeframe="1_year",
                confidence=0.70,
                justification="Consistent performance",
                risk_adjusted=False,
                benchmark=None
            ),
            
            # Excellent targets (high achievement)
            PerformanceTarget(
                name="Excellent Sharpe",
                target_type=TargetType.EXCELLENT,
                metric="sharpe_ratio",
                value=1.0,
                condition="favorable_market_conditions",
                timeframe="1_year",
                confidence=0.50,
                justification="Top-tier risk-adjusted returns",
                risk_adjusted=True,
                benchmark=None
            ),
            PerformanceTarget(
                name="Very Low Drawdown",
                target_type=TargetType.EXCELLENT,
                metric="max_drawdown",
                value=0.15,
                condition="favorable_market_conditions",
                timeframe="1_year",
                confidence=0.55,
                justification="Exceptional risk management",
                risk_adjusted=True,
                benchmark=None
            ),
            
            # Stretch targets (aspirational)
            PerformanceTarget(
                name="Elite Sharpe",
                target_type=TargetType.STRETCH,
                metric="sharpe_ratio",
                value=1.5,
                condition="ideal_market_conditions",
                timeframe="1_year",
                confidence=0.30,
                justification="World-class performance",
                risk_adjusted=True,
                benchmark=None
            ),
        ]
        
        assumptions = [
            "Market data from major exchanges (Binance, CoinGecko)",
            "Transaction costs included: 0.10% per trade",
            "Slippage included: 0.05% per trade",
            "Risk-free rate: 0% (crypto benchmark)",
            "1-year timeframe for evaluation",
            "Minimum of 2 years out-of-sample data",
            "Daily rebalancing assumed",
            "Maximum position size: 20% of portfolio",
            "Liquidity constraints applied",
        ]
        
        risk_constraints = [
            "Maximum drawdown: 30% (hard limit)",
            "Maximum daily loss: 5%",
            "Maximum position size: 20%",
            "Maximum turnover: 200% annually",
            "Minimum liquidity: $10M daily volume",
            "Circuit breaker triggers at 15% drawdown",
        ]
        
        benchmark_requirements = [
            "Must beat Buy & Hold BTC",
            "Must beat Simple Momentum",
            "Must beat Equal Weight portfolio",
            "Must beat Risk Parity",
            "Must have positive Sharpe ratio",
            "Must have Calmar ratio > 0.5",
        ]
        
        target_set = PerformanceTargetSet(
            system_name=name,
            version=version,
            targets=targets,
            assumptions=assumptions,
            risk_constraints=risk_constraints,
            benchmark_requirements=benchmark_requirements
        )
        
        self.targets[name] = target_set
        return target_set
    
    def assess_targets(
        self,
        target_set_name: str,
        metrics: Dict[str, float],
        market_regime: Optional[MarketRegime] = None,
        period: str = "1_year"
    ) -> List[TargetAssessment]:
        """
        Assess performance against targets.
        
        Args:
            target_set_name: Name of the target set
            metrics: Dictionary of metric_name -> achieved value
            market_regime: Current market regime
            period: Evaluation period
        
        Returns:
            List of target assessments
        """
        if target_set_name not in self.targets:
            raise ValueError(f"Target set {target_set_name} not found")
        
        target_set = self.targets[target_set_name]
        assessments = []
        
        for target in target_set.targets:
            if target.metric not in metrics:
                logger.warning(f"Metric {target.metric} not provided")
                continue
            
            achieved = metrics[target.metric]
            target_value = target.value
            
            # Calculate achievement
            if target_value == 0:
                percentage = 1.0 if achieved >= 0 else 0.0
            else:
                percentage = achieved / target_value
            
            is_achieved = achieved >= target_value
            gap = achieved - target_value
            
            # Generate recommendation
            if is_achieved:
                if percentage >= 1.5:
                    recommendation = f"Exceeded {target.metric} target significantly"
                elif percentage >= 1.2:
                    recommendation = f"Exceeded {target.metric} target"
                else:
                    recommendation = f"Achieved {target.metric} target"
            else:
                if percentage < 0.5:
                    recommendation = f"Failed {target.metric} target significantly - review strategy"
                elif percentage < 0.8:
                    recommendation = f"Below {target.metric} target - consider improvements"
                else:
                    recommendation = f"Close to {target.metric} target - minor improvements needed"
            
            assessment = TargetAssessment(
                target=target,
                achieved_value=achieved,
                percentage_achieved=percentage,
                is_achieved=is_achieved,
                gap=gap,
                recommendation=recommendation
            )
            
            assessments.append(assessment)
        
        # Store assessments
        if target_set_name not in self.assessments:
            self.assessments[target_set_name] = []
        self.assessments[target_set_name].extend(assessments)
        
        return assessments
    
    def get_summary(self, target_set_name: str) -> Dict:
        """Get summary of target achievement."""
        if target_set_name not in self.assessments:
            return {'error': f'No assessments found for {target_set_name}'}
        
        assessments = self.assessments[target_set_name]
        
        by_type = {}
        total_achieved = 0
        total_targets = len(assessments)
        
        for assessment in assessments:
            target_type = assessment.target.target_type.value
            if target_type not in by_type:
                by_type[target_type] = {'total': 0, 'achieved': 0}
            by_type[target_type]['total'] += 1
            if assessment.is_achieved:
                by_type[target_type]['achieved'] += 1
                total_achieved += 1
        
        summary = {
            'target_set_name': target_set_name,
            'total_targets': total_targets,
            'total_achieved': total_achieved,
            'achievement_rate': total_achieved / total_targets if total_targets > 0 else 0,
            'by_type': by_type,
            'recommendations': [
                a.recommendation for a in assessments 
                if not a.is_achieved
            ]
        }
        
        return summary
    
    def generate_report(self, target_set_name: str) -> str:
        """Generate a text report of target achievement."""
        if target_set_name not in self.targets:
            return f"Target set {target_set_name} not found"
        
        target_set = self.targets[target_set_name]
        summary = self.get_summary(target_set_name)
        
        lines = [
            "=" * 80,
            f"PERFORMANCE TARGET REPORT: {target_set.system_name} v{target_set.version}",
            "=" * 80,
            "",
            "TARGETS BY TYPE:",
            "-" * 40,
        ]
        
        for target_type, stats in summary['by_type'].items():
            rate = stats['achieved'] / stats['total'] if stats['total'] > 0 else 0
            lines.append(f"{target_type.upper()}: {stats['achieved']}/{stats['total']} achieved ({rate:.1%})")
        
        lines.extend([
            "",
            f"OVERALL: {summary['total_achieved']}/{summary['total_targets']} achieved ({summary['achievement_rate']:.1%})",
            "",
            "DETAILED TARGET ASSESSMENT:",
            "-" * 40,
        ])
        
        for assessment in self.assessments[target_set_name]:
            status = "✅" if assessment.is_achieved else "❌"
            lines.append(
                f"{status} {assessment.target.name}: "
                f"Achieved {assessment.achieved_value:.2f} vs target {assessment.target.value:.2f} "
                f"({assessment.percentage_achieved:.1%})"
            )
        
        lines.extend([
            "",
            "RECOMMENDATIONS:",
            "-" * 40,
        ])
        
        if summary['recommendations']:
            for rec in summary['recommendations']:
                lines.append(f"• {rec}")
        else:
            lines.append("All targets achieved - excellent performance!")
        
        lines.extend([
            "",
            "ASSUMPTIONS:",
            "-" * 40,
        ])
        for assumption in target_set.assumptions:
            lines.append(f"• {assumption}")
        
        lines.extend([
            "",
            "RISK CONSTRAINTS:",
            "-" * 40,
        ])
        for constraint in target_set.risk_constraints:
            lines.append(f"• {constraint}")
        
        lines.extend([
            "",
            "=" * 80,
        ])
        
        return "\n".join(lines)
    
    def get_failed_targets(self, target_set_name: str) -> List[TargetAssessment]:
        """Get list of failed targets for detailed analysis."""
        if target_set_name not in self.assessments:
            return []
        
        return [a for a in self.assessments[target_set_name] if not a.is_achieved]
    
    def get_exceeded_targets(self, target_set_name: str) -> List[TargetAssessment]:
        """Get list of exceeded targets for recognition."""
        if target_set_name not in self.assessments:
            return []
        
        return [a for a in self.assessments[target_set_name] 
                if a.is_achieved and a.percentage_achieved >= 1.2]
