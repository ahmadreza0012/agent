"""
ML Module for Cryptocurrency Algorithmic Trading
Implements predictive models with RSI, MACD, and volatility features.
Automatically disables ML if OOS R² is negative.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from sklearn.linear_model import Ridge, Lasso
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import r2_score, mean_squared_error
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CryptoMLPredictor:
    """
    Machine Learning predictor for cryptocurrency returns.
    Uses quantitative features (RSI, MACD, Volatility) and validates OOS performance.
    """
    
    def __init__(
        self,
        model_type: str = 'ridge',
        lookback_period: int = 14,
        prediction_horizon: int = 5,
        min_oos_r2: float = 0.0  # Minimum acceptable OOS R²
    ):
        """
        Initialize the ML predictor.
        
        Args:
            model_type: Model type ('ridge', 'lasso', 'rf', 'gb')
            lookback_period: Lookback for feature calculation
            prediction_horizon: Days ahead to predict
            min_oos_r2: Minimum acceptable OOS R² (below this, ML is disabled)
        """
        self.model_type = model_type
        self.lookback_period = lookback_period
        self.prediction_horizon = prediction_horizon
        self.min_oos_r2 = min_oos_r2
        
        self.model = self._initialize_model()
        self.scaler = StandardScaler()
        self.feature_columns = []
        self.is_disabled = False
        self.last_oos_r2 = None
        
    def _initialize_model(self):
        """Initialize the ML model based on type."""
        if self.model_type == 'ridge':
            return Ridge(alpha=1.0)
        elif self.model_type == 'lasso':
            return Lasso(alpha=0.1, max_iter=10000)
        elif self.model_type == 'rf':
            return RandomForestRegressor(n_estimators=100, max_depth=5, random_state=42)
        elif self.model_type == 'gb':
            return GradientBoostingRegressor(n_estimators=100, max_depth=3, random_state=42)
        else:
            logger.warning(f"Unknown model type '{self.model_type}', using Ridge")
            return Ridge(alpha=1.0)
    
    def generate_features(self, prices: pd.DataFrame) -> pd.DataFrame:
        """
        Generate quantitative features for ML model.
        Includes RSI, MACD, rolling volatility, and momentum.
        
        Args:
            prices: DataFrame of asset prices
            
        Returns:
            DataFrame with feature columns
        """
        features = pd.DataFrame(index=prices.index)
        
        for col in prices.columns:
            prefix = col.replace('/', '_').replace(' ', '_')
            price_series = prices[col]
            
            # === Returns ===
            features[f'{prefix}_ret_1d'] = price_series.pct_change(1)
            features[f'{prefix}_ret_{self.lookback_period}d'] = price_series.pct_change(self.lookback_period)
            
            # === RSI (Relative Strength Index) ===
            delta = price_series.diff()
            gain = delta.where(delta > 0, 0).rolling(window=self.lookback_period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=self.lookback_period).mean()
            rs = gain / (loss + 1e-10)
            features[f'{prefix}_rsi'] = 100 - (100 / (1 + rs))
            
            # === MACD ===
            exp12 = price_series.ewm(span=12, adjust=False).mean()
            exp26 = price_series.ewm(span=26, adjust=False).mean()
            macd_line = exp12 - exp26
            signal_line = macd_line.ewm(span=9, adjust=False).mean()
            features[f'{prefix}_macd_hist'] = macd_line - signal_line  # Histogram
            features[f'{prefix}_macd_line'] = macd_line
            features[f'{prefix}_macd_signal'] = signal_line
            features[f'{prefix}_macd_cross'] = (macd_line > signal_line).astype(int)
            
            # === Rolling Volatility ===
            features[f'{prefix}_vol_{self.lookback_period}d'] = price_series.pct_change().rolling(self.lookback_period).std()
            features[f'{prefix}_vol_21d'] = price_series.pct_change().rolling(21).std()
            
            # === ATR (Average True Range) ===
            high = price_series
            low = price_series
            close = price_series
            
            tr1 = high - low
            tr2 = abs(high - close.shift(1))
            tr3 = abs(low - close.shift(1))
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            features[f'{prefix}_atr'] = tr.rolling(self.lookback_period).mean()
            features[f'{prefix}_atr_norm'] = features[f'{prefix}_atr'] / close
            
            # === Moving Averages ===
            features[f'{prefix}_ma_7'] = price_series.rolling(7).mean()
            features[f'{prefix}_ma_21'] = price_series.rolling(21).mean()
            features[f'{prefix}_ma_ratio'] = features[f'{prefix}_ma_7'] / features[f'{prefix}_ma_21']
            features[f'{prefix}_ma_distance'] = (price_series - features[f'{prefix}_ma_21']) / features[f'{prefix}_ma_21']
            
            # === Momentum ===
            features[f'{prefix}_mom_7d'] = price_series / price_series.shift(7) - 1
            features[f'{prefix}_mom_14d'] = price_series / price_series.shift(14) - 1
            features[f'{prefix}_mom_21d'] = price_series / price_series.shift(21) - 1
            
            # === Bollinger Bands ===
            ma20 = price_series.rolling(20).mean()
            std20 = price_series.rolling(20).std()
            features[f'{prefix}_bb_upper'] = ma20 + 2 * std20
            features[f'{prefix}_bb_lower'] = ma20 - 2 * std20
            features[f'{prefix}_bb_position'] = (price_series - features[f'{prefix}_bb_lower']) / (features[f'{prefix}_bb_upper'] - features[f'{prefix}_bb_lower'] + 1e-10)
            
            # === Volume-based features (if available) ===
            if 'volume' in prices.columns:
                vol_col = f"{col}_volume" if f"{col}_volume" in prices.columns else None
                if vol_col:
                    features[f'{prefix}_vol_ma_ratio'] = prices[vol_col] / prices[vol_col].rolling(self.lookback_period).mean()
        
        # Drop NaN rows
        features = features.dropna()
        
        self.feature_columns = list(features.columns)
        logger.info(f"Generated {len(self.feature_columns)} features")
        
        return features
    
    def prepare_target(self, prices: pd.DataFrame, horizon: Optional[int] = None) -> pd.Series:
        """
        Prepare target variable (future returns).
        
        Args:
            prices: DataFrame of asset prices
            horizon: Prediction horizon in days
            
        Returns:
            Series of target returns
        """
        if horizon is None:
            horizon = self.prediction_horizon
        
        # Forward returns as target
        target = prices.pct_change(horizon).shift(-horizon)
        target = target.dropna()
        
        return target
    
    def fit(
        self,
        prices: pd.DataFrame,
        validation_split: float = 0.2,
        n_splits: int = 5
    ) -> Dict:
        """
        Fit the ML model with time-series cross-validation.
        
        Args:
            prices: Price DataFrame
            validation_split: Fraction for validation
            n_splits: Number of CV splits
            
        Returns:
            Dictionary with fit results including OOS R²
        """
        # Generate features
        features = self.generate_features(prices)
        target = self.prepare_target(prices)
        
        # Align features and target
        common_index = features.index.intersection(target.index)
        X = features.loc[common_index]
        y = target.loc[common_index]
        
        if len(X) < 50:
            logger.warning("Insufficient data for ML training")
            self.is_disabled = True
            return {'oos_r2': -1.0, 'disabled': True}
        
        # Scale features
        X_scaled = pd.DataFrame(
            self.scaler.fit_transform(X),
            columns=X.columns,
            index=X.index
        )
        
        # Time series cross-validation
        tscv = TimeSeriesSplit(n_splits=n_splits)
        oos_scores = []
        
        for train_idx, test_idx in tscv.split(X_scaled):
            X_train, X_test = X_scaled.iloc[train_idx], X_scaled.iloc[test_idx]
            y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]
            
            try:
                self.model.fit(X_train, y_train)
                y_pred = self.model.predict(X_test)
                r2 = r2_score(y_test, y_pred)
                oos_scores.append(r2)
            except Exception as e:
                logger.warning(f"CV fold failed: {e}")
                oos_scores.append(-1.0)
        
        # Average OOS R²
        avg_oos_r2 = np.mean(oos_scores)
        self.last_oos_r2 = avg_oos_r2
        
        logger.info(f"OOS R² scores: {oos_scores}")
        logger.info(f"Average OOS R²: {avg_oos_r2:.4f}")
        
        # Check if ML should be disabled
        if avg_oos_r2 < self.min_oos_r2:
            logger.warning(f"ML has no OOS predictive power (R²={avg_oos_r2:.4f}). Disabling ML strategy.")
            self.is_disabled = True
        else:
            # Fit final model on all data
            self.model.fit(X_scaled, y)
            self.is_disabled = False
        
        return {
            'oos_r2': avg_oos_r2,
            'cv_scores': oos_scores,
            'disabled': self.is_disabled,
            'feature_importance': self._get_feature_importance()
        }
    
    def _get_feature_importance(self) -> Dict[str, float]:
        """Get feature importance from the model."""
        if hasattr(self.model, 'coef_'):
            coef = self.model.coef_
            # Handle multi-output case
            if len(coef.shape) > 1:
                coef = np.mean(coef, axis=0)
            importance = dict(zip(self.feature_columns, np.abs(coef)))
        elif hasattr(self.model, 'feature_importances_'):
            importance = dict(zip(self.feature_columns, self.model.feature_importances_))
        else:
            importance = {}
        
        # Sort by importance - handle numpy array values
        try:
            sorted_items = sorted(importance.items(), key=lambda x: float(x[1]), reverse=True)
            importance = dict(sorted_items[:10])
        except (TypeError, ValueError):
            pass
        
        return importance
    
    def predict(self, prices: pd.DataFrame) -> pd.DataFrame:
        """
        Generate predictions for current prices.
        
        Args:
            prices: Current price DataFrame
            
        Returns:
            DataFrame of predicted returns
        """
        if self.is_disabled:
            logger.info("ML is disabled, returning zero predictions")
            return pd.DataFrame(0.0, columns=prices.columns, index=prices.index[-1:])
        
        features = self.generate_features(prices)
        
        # Get last row
        X_last = features.iloc[-1:].copy()
        
        # Scale
        X_scaled = pd.DataFrame(
            self.scaler.transform(X_last),
            columns=X_last.columns,
            index=X_last.index
        )
        
        # Predict
        predictions = self.model.predict(X_scaled)
        
        result = pd.DataFrame(
            [predictions],
            columns=prices.columns,
            index=[prices.index[-1]]
        )
        
        logger.info(f"ML predictions: {result.to_dict('records')[0]}")
        return result
    
    def get_weights(
        self,
        prices: pd.DataFrame,
        risk_parity_weights: Optional[np.ndarray] = None
    ) -> np.ndarray:
        """
        Get ML-based portfolio weights.
        If ML is disabled, returns risk parity weights or equal weights.
        
        Args:
            prices: Price DataFrame
            risk_parity_weights: Fallback weights if ML is disabled
            
        Returns:
            Array of portfolio weights
        """
        n_assets = len(prices.columns)
        
        if self.is_disabled:
            logger.info("ML disabled, distributing allocation to Risk Parity")
            if risk_parity_weights is not None:
                return risk_parity_weights
            else:
                return np.ones(n_assets) / n_assets
        
        # Get predictions
        predictions = self.predict(prices)
        pred_array = predictions.values[0]
        
        # Convert predictions to weights (softmax-like)
        # Higher expected return -> higher weight
        exp_predictions = np.exp(pred_array * 10)  # Scale for sensitivity
        weights = exp_predictions / np.sum(exp_predictions)
        
        # Ensure minimum weight for diversification
        min_weight = 0.05
        weights = np.maximum(weights, min_weight)
        weights = weights / np.sum(weights)
        
        logger.info(f"ML weights: {weights}")
        return weights


def evaluate_ml_strategy(
    prices: pd.DataFrame,
    model_type: str = 'ridge',
    min_r2_threshold: float = 0.0
) -> Dict:
    """
    Evaluate ML strategy and return weights allocation decision.
    
    Args:
        prices: Price DataFrame
        model_type: ML model type
        min_r2_threshold: Minimum R² to enable ML
        
    Returns:
        Dictionary with evaluation results and recommended weights
    """
    predictor = CryptoMLPredictor(
        model_type=model_type,
        min_oos_r2=min_r2_threshold
    )
    
    fit_results = predictor.fit(prices)
    
    return {
        'oos_r2': fit_results['oos_r2'],
        'is_disabled': fit_results['disabled'],
        'feature_importance': fit_results.get('feature_importance', {}),
        'predictor': predictor
    }


if __name__ == "__main__":
    # Example usage
    np.random.seed(42)
    
    # Create sample price data
    dates = pd.date_range('2023-01-01', periods=300, freq='D')
    n_assets = 5
    assets = [f'Asset_{i}' for i in range(n_assets)]
    
    # Simulate prices with some autocorrelation for ML to potentially capture
    returns = np.random.randn(300, n_assets) * 0.02
    # Add slight autocorrelation
    for i in range(1, 300):
        returns[i] += 0.1 * returns[i-1]
    
    prices = pd.DataFrame(
        100 * np.cumprod(1 + returns),
        index=dates,
        columns=assets
    )
    
    print("\n=== Testing ML Predictor ===")
    
    predictor = CryptoMLPredictor(
        model_type='ridge',
        lookback_period=14,
        prediction_horizon=5,
        min_oos_r2=-0.1  # Allow slightly negative R²
    )
    
    # Generate features
    features = predictor.generate_features(prices)
    print(f"\nFeatures shape: {features.shape}")
    print(f"Feature columns: {list(features.columns)[:10]}...")
    
    # Fit model
    fit_results = predictor.fit(prices)
    print(f"\nOOS R²: {fit_results['oos_r2']:.4f}")
    print(f"ML Disabled: {fit_results['disabled']}")
    print(f"Top Features: {fit_results.get('feature_importance', {})}")
    
    # Get predictions
    if not fit_results['disabled']:
        predictions = predictor.predict(prices)
        print(f"\nLatest predictions: {predictions.to_dict('records')[0]}")
        
        # Get weights
        weights = predictor.get_weights(prices)
        print(f"ML weights: {weights}")
    
    # Test with stricter threshold (will likely disable ML)
    print("\n=== Testing with Stricter R² Threshold ===")
    predictor_strict = CryptoMLPredictor(
        model_type='ridge',
        min_oos_r2=0.0  # Require non-negative R²
    )
    
    fit_strict = predictor_strict.fit(prices)
    print(f"OOS R²: {fit_strict['oos_r2']:.4f}")
    print(f"ML Disabled: {fit_strict['disabled']}")
    
    # Get fallback weights
    rp_weights = np.ones(n_assets) / n_assets
    final_weights = predictor_strict.get_weights(prices, risk_parity_weights=rp_weights)
    print(f"Final weights (fallback to RP): {final_weights}")
