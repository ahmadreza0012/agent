import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error
from sklearn.preprocessing import StandardScaler
import logging
from .validation import PurgedWalkForwardValidator
from .feature_engineering import CausalFeatureEngineer
from .model_registry import ModelRegistry
logger = logging.getLogger(__name__)

@dataclass
class MLConfig:
    model_type: str = 'random_forest'; n_estimators: int = 30; max_depth: int = 4
    min_samples_leaf: int = 5; n_splits: int = 5; test_size: float = 0.1
    gap: int = 10; purge: int = 20; min_train_size: int = 100
    oos_r2_threshold: float = 0.0; random_state: int = 42

class MLPipeline:
    def __init__(self, config: Optional[MLConfig] = None):
        self.config = config or MLConfig()
        self.feature_engineer = CausalFeatureEngineer()
        self.validator = PurgedWalkForwardValidator(n_splits=self.config.n_splits, test_size=self.config.test_size, gap=self.config.gap, purge=self.config.purge, min_train_size=self.config.min_train_size)
        self.model_registry = ModelRegistry()
        self.model = None; self.scaler = StandardScaler(); self.feature_names = []; self.is_fitted = False
        self._oos_metrics = None; self._baseline_metrics = None
    
    def train(self, X_train: pd.DataFrame, y_train: pd.Series, validate: bool = True) -> Dict[str, float]:
        self.feature_names = X_train.columns.tolist()
        X_scaled = self.scaler.fit_transform(X_train)
        X_scaled = pd.DataFrame(X_scaled, index=X_train.index, columns=X_train.columns)
        self.model = RandomForestRegressor(n_estimators=self.config.n_estimators, max_depth=self.config.max_depth, min_samples_leaf=self.config.min_samples_leaf, random_state=self.config.random_state, n_jobs=-1)
        self.model.fit(X_scaled, y_train); self.is_fitted = True
        pred = self.model.predict(X_scaled)
        metrics = {'rmse': np.sqrt(mean_squared_error(y_train, pred)), 'mae': mean_absolute_error(y_train, pred), 'r2': r2_score(y_train, pred)}
        logger.info(f"Training: RMSE={metrics['rmse']:.4f}, R²={metrics['r2']:.4f}")
        return metrics
    
    def predict(self, X_test: pd.DataFrame) -> np.ndarray:
        if not self.is_fitted: raise ValueError("Model not fitted")
        missing = set(self.feature_names) - set(X_test.columns)
        if missing: raise ValueError(f"Missing features: {missing}")
        X_scaled = self.scaler.transform(X_test[self.feature_names])
        return self.model.predict(X_scaled)
    
    def validate(self, X_test: pd.DataFrame, y_test: pd.Series) -> Dict[str, float]:
        if not self.is_fitted: raise ValueError("Model not fitted")
        y_pred = self.predict(X_test)
        metrics = {'rmse': np.sqrt(mean_squared_error(y_test, y_pred)), 'mae': mean_absolute_error(y_test, y_pred), 'r2': r2_score(y_test, y_pred)}
        self._oos_metrics = metrics
        if metrics['r2'] < self.config.oos_r2_threshold:
            logger.warning(f"OOS R²={metrics['r2']:.4f} below threshold - model rejected")
        return metrics
    
    def walk_forward_validate(self, X: pd.DataFrame, y: pd.Series) -> List[Dict[str, float]]:
        results = []
        for fold_idx, (train_idx, test_idx) in enumerate(self.validator.split(X)):
            X_train, y_train = X.iloc[train_idx], y.iloc[train_idx]
            X_test, y_test = X.iloc[test_idx], y.iloc[test_idx]
            self.train(X_train, y_train, validate=False)
            metrics = self.validate(X_test, y_test)
            metrics['fold_idx'] = fold_idx; metrics['train_size'] = len(train_idx); metrics['test_size'] = len(test_idx)
            results.append(metrics)
        avg = {'avg_rmse': np.mean([r['rmse'] for r in results]), 'avg_r2': np.mean([r['r2'] for r in results]), 'std_r2': np.std([r['r2'] for r in results]), 'n_folds': len(results)}
        self._oos_metrics = avg
        if avg['avg_r2'] < self.config.oos_r2_threshold:
            logger.warning(f"Avg OOS R²={avg['avg_r2']:.4f} below threshold - ML rejected")
        return results
    
    def compare_to_baseline(self, X_test: pd.DataFrame, y_test: pd.Series) -> Dict[str, Any]:
        if not self.is_fitted: raise ValueError("Model not fitted")
        ml_pred = self.predict(X_test)
        ml = {'rmse': np.sqrt(mean_squared_error(y_test, ml_pred)), 'r2': r2_score(y_test, ml_pred)}
        mean_pred = np.ones(len(y_test)) * y_test.mean()
        mean = {'rmse': np.sqrt(mean_squared_error(y_test, mean_pred)), 'r2': r2_score(y_test, mean_pred)}
        zero = {'rmse': np.sqrt(mean_squared_error(y_test, np.zeros(len(y_test)))), 'r2': r2_score(y_test, np.zeros(len(y_test)))}
        self._baseline_metrics = {'ml': ml, 'mean': mean, 'zero': zero}
        improves = ml['r2'] > mean['r2'] and ml['r2'] > zero['r2']
        return {'metrics': self._baseline_metrics, 'ml_improves': improves}
    
    def get_oos_metrics(self) -> Optional[Dict[str, float]]: return self._oos_metrics
    def save_model(self, path: str) -> None:
        import joblib; joblib.dump({'model': self.model, 'scaler': self.scaler, 'feature_names': self.feature_names}, path)
    def load_model(self, path: str) -> None:
        import joblib; data = joblib.load(path); self.model = data['model']; self.scaler = data['scaler']; self.feature_names = data['feature_names']; self.is_fitted = True
