#!/usr/bin/env python3
"""
Strategy Pruning Script for Phase 30: Strategy Robustness

This script identifies and prunes weak strategies from the registry based on
validation results. It helps maintain a high-quality set of strategies that
meet robustness criteria.

Usage:
    python scripts/prune_strategies.py [--dry-run] [--output report.csv]
"""

import sys
import os
import argparse
import pandas as pd
import logging
from datetime import datetime

# Add workspace to path
sys.path.insert(0, '/workspace')

from strategies.registry import StrategyRegistry, StrategyStatus, get_registry
from strategies.validation import StrategyRobustnessValidator, ValidationStatus

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def prune_weak_strategies(
    registry: StrategyRegistry,
    validator: StrategyRobustnessValidator = None,
    dry_run: bool = False,
    min_score: float = 0.4,
) -> dict:
    """
    Identify and prune weak strategies from the registry.
    
    Args:
        registry: StrategyRegistry instance
        validator: Optional validator for re-validation
        dry_run: If True, only report what would be pruned
        min_score: Minimum validation score to keep strategy
        
    Returns:
        Dictionary with pruning results
    """
    results = {
        'kept': [],
        'removed': [],
        'inconclusive': [],
        'needs_review': [],
        'already_rejected': [],
    }
    
    # Get all strategies
    all_strategies = registry.list_strategies()
    
    logger.info(f"Analyzing {len(all_strategies)} strategies...")
    
    for name, info in all_strategies.items():
        status = info['status']
        
        # Skip already rejected strategies
        if status == StrategyStatus.REJECTED.value:
            results['already_rejected'].append(name)
            continue
        
        # Get validation result if available
        validation = registry.get_validation_result(name)
        
        if not validation:
            # No validation data - needs review
            logger.info(f"  {name}: No validation data - needs review")
            results['needs_review'].append(name)
            continue
        
        # Check validation status
        if validation.status == ValidationStatus.PASS:
            if validation.score >= min_score:
                logger.info(f"  {name}: PASS (score: {validation.score:.2f}) - KEEP")
                results['kept'].append({
                    'name': name,
                    'score': validation.score,
                    'oos_sharpe': validation.metrics.get('oos_sharpe'),
                    'cost_adjusted_sharpe': validation.metrics.get('cost_adjusted_sharpe'),
                })
            else:
                logger.info(f"  {name}: PASS but low score ({validation.score:.2f}) - REVIEW")
                results['needs_review'].append(name)
                
        elif validation.status == ValidationStatus.REJECTED:
            logger.info(f"  {name}: REJECTED (score: {validation.score:.2f}) - REMOVE")
            if not dry_run:
                registry.update_status(name, StrategyStatus.REJECTED)
            results['removed'].append({
                'name': name,
                'score': validation.score,
                'reason': validation.reasons[0] if validation.reasons else 'Unknown',
            })
            
        elif validation.status == ValidationStatus.FAIL:
            logger.info(f"  {name}: FAIL (score: {validation.score:.2f}) - REMOVE")
            if not dry_run:
                registry.update_status(name, StrategyStatus.INACTIVE)
            results['removed'].append({
                'name': name,
                'score': validation.score,
                'reason': validation.reasons[0] if validation.reasons else 'Failed validation',
            })
            
        elif validation.status == ValidationStatus.INCONCLUSIVE:
            logger.info(f"  {name}: INCONCLUSIVE (score: {validation.score:.2f}) - NEEDS MORE DATA")
            results['inconclusive'].append({
                'name': name,
                'score': validation.score,
            })
    
    # Log summary
    logger.info("\n" + "="*60)
    logger.info("PRUNING SUMMARY")
    logger.info("="*60)
    logger.info(f"  Kept:              {len(results['kept'])}")
    logger.info(f"  Removed:           {len(results['removed'])}")
    logger.info(f"  Inconclusive:      {len(results['inconclusive'])}")
    logger.info(f"  Needs review:      {len(results['needs_review'])}")
    logger.info(f"  Already rejected:  {len(results['already_rejected'])}")
    logger.info("="*60)
    
    if dry_run:
        logger.info("\nDRY RUN - No changes made")
    
    return results


def generate_pruning_report(results: dict, output_file: str = None) -> pd.DataFrame:
    """
    Generate a detailed pruning report.
    
    Args:
        results: Results dictionary from prune_weak_strategies
        output_file: Optional file path to save CSV report
        
    Returns:
        DataFrame with report data
    """
    rows = []
    
    # Kept strategies
    for item in results.get('kept', []):
        rows.append({
            'category': 'KEPT',
            'name': item['name'],
            'score': item.get('score', 0),
            'oos_sharpe': item.get('oos_sharpe'),
            'cost_adjusted_sharpe': item.get('cost_adjusted_sharpe'),
            'reason': 'Passed validation with acceptable score',
        })
    
    # Removed strategies
    for item in results.get('removed', []):
        rows.append({
            'category': 'REMOVED',
            'name': item['name'],
            'score': item.get('score', 0),
            'oos_sharpe': None,
            'cost_adjusted_sharpe': None,
            'reason': item.get('reason', 'Failed validation'),
        })
    
    # Inconclusive
    for item in results.get('inconclusive', []):
        rows.append({
            'category': 'INCONCLUSIVE',
            'name': item['name'],
            'score': item.get('score', 0),
            'oos_sharpe': None,
            'cost_adjusted_sharpe': None,
            'reason': 'Needs more data or testing',
        })
    
    # Needs review
    for name in results.get('needs_review', []):
        rows.append({
            'category': 'NEEDS_REVIEW',
            'name': name,
            'score': None,
            'oos_sharpe': None,
            'cost_adjusted_sharpe': None,
            'reason': 'No validation data available',
        })
    
    df = pd.DataFrame(rows)
    
    if output_file:
        df.to_csv(output_file, index=False)
        logger.info(f"Report saved to {output_file}")
    
    return df


def main():
    parser = argparse.ArgumentParser(description='Prune weak strategies from registry')
    parser.add_argument('--dry-run', action='store_true', help='Do not make changes, just report')
    parser.add_argument('--output', type=str, default='strategy_pruning_report.csv',
                       help='Output file for report')
    parser.add_argument('--min-score', type=float, default=0.4,
                       help='Minimum validation score to keep strategy')
    parser.add_argument('--registry-file', type=str, default=None,
                       help='Load registry from file (optional)')
    
    args = parser.parse_args()
    
    # Initialize registry
    registry = get_registry()
    
    # Load from file if specified
    if args.registry_file and os.path.exists(args.registry_file):
        registry.load_from_file(args.registry_file)
    
    # Create validator
    validator = StrategyRobustnessValidator()
    
    # Run pruning
    logger.info(f"Starting strategy pruning (dry_run={args.dry_run})...")
    results = prune_weak_strategies(
        registry=registry,
        validator=validator,
        dry_run=args.dry_run,
        min_score=args.min_score,
    )
    
    # Generate report
    df = generate_pruning_report(results, args.output)
    
    # Print summary
    print("\n" + "="*60)
    print("STRATEGY PRUNING REPORT")
    print("="*60)
    print(f"\nTotal strategies analyzed: {len(df)}")
    
    if len(df) > 0:
        print(f"\nBy category:")
        print(df.groupby('category').size().to_string())
    else:
        print("\nNo strategies found in registry.")
        print("Register strategies first using registry.register()")
    
    if len(results['kept']) > 0:
        print(f"\nKept strategies ({len(results['kept'])}):")
        for item in results['kept']:
            print(f"  - {item['name']} (score: {item['score']:.2f})")
    
    if len(results['removed']) > 0:
        print(f"\nRemoved strategies ({len(results['removed'])}):")
        for item in results['removed']:
            print(f"  - {item['name']}: {item['reason']}")
    
    print(f"\nFull report saved to: {args.output}")
    
    if args.dry_run:
        print("\nNOTE: This was a dry run. Use --dry-run=false to apply changes.")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
