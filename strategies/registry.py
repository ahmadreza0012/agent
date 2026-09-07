"""
Strategy Registry for Phase 30: Strategy Robustness

This module provides a centralized registry for tracking all trading strategies,
their validation status, and metadata. Only strategies that pass validation
should be marked as ACTIVE for production use.
"""

from typing import Dict, List, Optional, Type, Any
from enum import Enum
from dataclasses import dataclass
import pandas as pd
from datetime import datetime
import logging
import json

from .validation import ValidationResult, ValidationStatus, StrategyHypothesis

logger = logging.getLogger(__name__)


class StrategyStatus(Enum):
    """Status of a strategy in the registry."""
    ACTIVE = "active"           # Passed validation, approved for production
    INACTIVE = "inactive"       # Temporarily disabled
    DEPRECATED = "deprecated"   # Being phased out
    EXPERIMENTAL = "experimental"  # Under testing, not for production
    REJECTED = "rejected"       # Failed validation, do not use
    PENDING_REVIEW = "pending_review"  # Awaiting validation


@dataclass
class StrategyMetadata:
    """Metadata for a registered strategy."""
    name: str
    class_name: str
    description: str
    status: StrategyStatus
    tags: List[str]
    version: str
    author: str
    registered_at: datetime
    last_validated: Optional[datetime]
    validation_score: Optional[float]
    hypothesis: Optional[StrategyHypothesis]
    parameters: Dict[str, Any]
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            'name': self.name,
            'class_name': self.class_name,
            'description': self.description,
            'status': self.status.value,
            'tags': self.tags,
            'version': self.version,
            'author': self.author,
            'registered_at': self.registered_at.isoformat() if self.registered_at else None,
            'last_validated': self.last_validated.isoformat() if self.last_validated else None,
            'validation_score': self.validation_score,
            'hypothesis': self.hypothesis.__dict__ if self.hypothesis else None,
            'parameters': self.parameters,
        }


class StrategyRegistry:
    """
    Centralized registry for all trading strategies.
    
    Features:
    - Track strategy metadata and status
    - Store validation results
    - Filter by status, tags, or performance
    - Generate reports on strategy inventory
    
    Usage:
        registry = StrategyRegistry()
        
        # Register a strategy
        registry.register(
            MomentumStrategy,
            name="momentum",
            description="Momentum-based strategy",
            status=StrategyStatus.EXPERIMENTAL,
            tags=["trend", "momentum"],
            hypothesis=my_hypothesis
        )
        
        # Update status after validation
        registry.set_validation_result("momentum", validation_result)
        
        # Get active strategies
        active = registry.get_active_strategies()
    """
    
    def __init__(self):
        """Initialize the strategy registry."""
        self._strategies: Dict[str, Type] = {}
        self._metadata: Dict[str, StrategyMetadata] = {}
        self._validation_results: Dict[str, ValidationResult] = {}
        
        logger.info("StrategyRegistry initialized")
    
    def register(
        self,
        strategy_class: Type,
        name: Optional[str] = None,
        description: str = "",
        status: StrategyStatus = StrategyStatus.EXPERIMENTAL,
        tags: Optional[List[str]] = None,
        version: str = "1.0.0",
        author: str = "Unknown",
        hypothesis: Optional[StrategyHypothesis] = None,
        **kwargs
    ):
        """
        Register a strategy in the registry.
        
        Args:
            strategy_class: The strategy class to register
            name: Strategy name (defaults to class name)
            description: Strategy description
            status: Initial status (default: EXPERIMENTAL)
            tags: Tags for categorization
            version: Strategy version
            author: Strategy author
            hypothesis: Economic hypothesis for the strategy
            **kwargs: Additional metadata
        """
        if not name:
            name = strategy_class.__name__
        
        # Get default parameters if available
        parameters = {}
        if hasattr(strategy_class, 'get_default_params'):
            parameters = strategy_class.get_default_params()
        elif hasattr(strategy_class, 'get_params'):
            try:
                # Try to get params from a default instance
                instance = strategy_class.__new__(strategy_class)
                if hasattr(instance, 'get_params'):
                    parameters = instance.get_params()
            except:
                pass
        
        # Create metadata
        metadata = StrategyMetadata(
            name=name,
            class_name=strategy_class.__name__,
            description=description,
            status=status,
            tags=tags or [],
            version=version,
            author=author,
            registered_at=datetime.now(),
            last_validated=None,
            validation_score=None,
            hypothesis=hypothesis,
            parameters=parameters,
        )
        
        # Store in registry
        self._strategies[name] = strategy_class
        self._metadata[name] = metadata
        
        logger.info(f"Strategy registered: {name} ({status.value})")
        
        return name
    
    def update_status(self, name: str, status: StrategyStatus):
        """
        Update the status of a strategy.
        
        Args:
            name: Strategy name
            status: New status
        """
        if name not in self._metadata:
            raise ValueError(f"Strategy '{name}' not found in registry")
        
        old_status = self._metadata[name].status
        self._metadata[name].status = status
        
        logger.info(f"Strategy '{name}' status updated: {old_status.value} -> {status.value}")
    
    def set_validation_result(self, name: str, result: ValidationResult):
        """
        Store validation result for a strategy and update status accordingly.
        
        Args:
            name: Strategy name
            result: ValidationResult from validator
        """
        if name not in self._metadata:
            raise ValueError(f"Strategy '{name}' not found in registry")
        
        # Store validation result
        self._validation_results[name] = result
        
        # Update metadata
        self._metadata[name].last_validated = datetime.now()
        self._metadata[name].validation_score = result.score
        
        # Update status based on validation result
        if result.status == ValidationStatus.PASS:
            self.update_status(name, StrategyStatus.ACTIVE)
        elif result.status == ValidationStatus.REJECTED:
            self.update_status(name, StrategyStatus.REJECTED)
        elif result.status == ValidationStatus.FAIL:
            self.update_status(name, StrategyStatus.INACTIVE)
        elif result.status == ValidationStatus.INCONCLUSIVE:
            self.update_status(name, StrategyStatus.PENDING_REVIEW)
        
        logger.info(f"Validation result stored for '{name}': {result.status.value} (score: {result.score:.2f})")
    
    def get_strategy(self, name: str) -> Type:
        """
        Get a strategy class by name.
        
        Args:
            name: Strategy name
            
        Returns:
            Strategy class
        """
        if name not in self._strategies:
            raise ValueError(f"Strategy '{name}' not found in registry")
        return self._strategies[name]
    
    def get_metadata(self, name: str) -> StrategyMetadata:
        """
        Get metadata for a strategy.
        
        Args:
            name: Strategy name
            
        Returns:
            StrategyMetadata
        """
        if name not in self._metadata:
            raise ValueError(f"Strategy '{name}' not found in registry")
        return self._metadata[name]
    
    def get_validation_result(self, name: str) -> Optional[ValidationResult]:
        """
        Get validation result for a strategy.
        
        Args:
            name: Strategy name
            
        Returns:
            ValidationResult or None if not validated
        """
        return self._validation_results.get(name)
    
    def get_active_strategies(self) -> List[str]:
        """
        Get all active strategies (approved for production).
        
        Returns:
            List of strategy names
        """
        return [
            name for name, meta in self._metadata.items()
            if meta.status == StrategyStatus.ACTIVE
        ]
    
    def get_strategies_by_status(self, status: StrategyStatus) -> List[str]:
        """
        Get strategies with a specific status.
        
        Args:
            status: Status to filter by
            
        Returns:
            List of strategy names
        """
        return [
            name for name, meta in self._metadata.items()
            if meta.status == status
        ]
    
    def get_strategies_by_tag(self, tag: str) -> List[str]:
        """
        Get strategies with a specific tag.
        
        Args:
            tag: Tag to filter by
            
        Returns:
            List of strategy names
        """
        return [
            name for name, meta in self._metadata.items()
            if tag in meta.tags
        ]
    
    def get_strategies_by_min_score(self, min_score: float) -> List[str]:
        """
        Get strategies with validation score above threshold.
        
        Args:
            min_score: Minimum validation score
            
        Returns:
            List of strategy names
        """
        return [
            name for name, meta in self._metadata.items()
            if meta.validation_score is not None and meta.validation_score >= min_score
        ]
    
    def list_strategies(self) -> Dict[str, Dict]:
        """
        List all registered strategies with their metadata.
        
        Returns:
            Dictionary of strategy info
        """
        return {
            name: {
                'name': name,
                'class_name': meta.class_name,
                'status': meta.status.value,
                'tags': meta.tags,
                'version': meta.version,
                'author': meta.author,
                'validation_score': meta.validation_score,
                'last_validated': meta.last_validated.isoformat() if meta.last_validated else None,
                'has_hypothesis': meta.hypothesis is not None,
            }
            for name, meta in self._metadata.items()
        }
    
    def generate_inventory_report(self) -> pd.DataFrame:
        """
        Generate a comprehensive inventory report of all strategies.
        
        Returns:
            DataFrame with strategy information
        """
        rows = []
        
        for name, meta in self._metadata.items():
            validation = self._validation_results.get(name)
            
            row = {
                'name': name,
                'class': meta.class_name,
                'status': meta.status.value,
                'version': meta.version,
                'author': meta.author,
                'tags': ', '.join(meta.tags),
                'has_hypothesis': meta.hypothesis is not None,
                'validation_score': meta.validation_score,
                'oos_sharpe': validation.metrics.get('oos_sharpe') if validation else None,
                'cost_adjusted_sharpe': validation.metrics.get('cost_adjusted_sharpe') if validation else None,
                'regime_consistency': validation.metrics.get('regime_consistency') if validation else None,
                'param_robustness': validation.metrics.get('param_robustness') if validation else None,
                'last_validated': meta.last_validated,
            }
            rows.append(row)
        
        df = pd.DataFrame(rows)
        if len(df) > 0:
            df = df.sort_values(['status', 'validation_score'], ascending=[True, False])
        
        return df
    
    def remove_strategy(self, name: str):
        """
        Remove a strategy from the registry.
        
        Args:
            name: Strategy name to remove
        """
        if name not in self._metadata:
            raise ValueError(f"Strategy '{name}' not found in registry")
        
        del self._strategies[name]
        del self._metadata[name]
        if name in self._validation_results:
            del self._validation_results[name]
        
        logger.info(f"Strategy removed from registry: {name}")
    
    def count_by_status(self) -> Dict[str, int]:
        """
        Count strategies by status.
        
        Returns:
            Dictionary with status counts
        """
        counts = {status.value: 0 for status in StrategyStatus}
        for meta in self._metadata.values():
            counts[meta.status.value] += 1
        return counts
    
    def save_to_file(self, filepath: str):
        """
        Save registry state to a JSON file.
        
        Args:
            filepath: Path to save file
        """
        data = {
            'strategies': {
                name: meta.to_dict()
                for name, meta in self._metadata.items()
            },
            'validation_results': {
                name: result.to_dict()
                for name, result in self._validation_results.items()
            }
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        
        logger.info(f"Registry saved to {filepath}")
    
    def load_from_file(self, filepath: str):
        """
        Load registry state from a JSON file.
        
        Note: This only loads metadata, not the actual strategy classes.
        Strategy classes must be registered separately.
        
        Args:
            filepath: Path to load file
        """
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        # Load metadata
        for name, meta_dict in data.get('strategies', {}).items():
            # Convert status from string to enum
            meta_dict['status'] = StrategyStatus(meta_dict['status'])
            # Convert dates from string to datetime
            if meta_dict.get('registered_at'):
                meta_dict['registered_at'] = datetime.fromisoformat(meta_dict['registered_at'])
            if meta_dict.get('last_validated'):
                meta_dict['last_validated'] = datetime.fromisoformat(meta_dict['last_validated'])
            
            # Reconstruct hypothesis if present
            if meta_dict.get('hypothesis'):
                meta_dict['hypothesis'] = StrategyHypothesis(**meta_dict['hypothesis'])
            
            self._metadata[name] = StrategyMetadata(**meta_dict)
        
        # Load validation results
        for name, result_dict in data.get('validation_results', {}).items():
            result_dict['status'] = ValidationStatus(result_dict['status'])
            self._validation_results[name] = ValidationResult(**result_dict)
        
        logger.info(f"Registry loaded from {filepath}")


# Global registry instance
registry = StrategyRegistry()


def get_registry() -> StrategyRegistry:
    """Get the global registry instance."""
    return registry
