# ML Validation Framework

## ML Philosophy

The machine learning pipeline follows **conservative, research-grade principles**:

1. **Purged Walk-Forward Validation**: Prevent look-ahead bias
2. **Causal Feature Engineering**: Only use information available at prediction time
3. **Baseline Comparison**: Must beat simple benchmarks
4. **Out-of-Sample Testing**: Never optimize on test data
5. **Model Rejection**: Clear thresholds for model acceptance

---

## Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    ML PIPELINE                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐ │
│  │   Feature    │    │    Model     │    │   Validate   │ │
│  │ Engineering  │───▶│   Training   │───▶│   OOS        │ │
│  │              │    │              │    │              │ │
│  │ - Causal     │    │ - Random     │    │ - Purged     │ │
│  │ - Lagged     │    │   Forest     │    │   CV         │ │
│  │ - Normalized │    │ - RF Regressor│   │ - Metrics    │ │
│  └──────────────┘    └──────────────┘    └──────────────┘ │
│                             │                               │
│                             ▼                               │
│                  ┌──────────────────┐                       │
│  ┌──────────────┐│  Model Registry  │┌──────────────┐      │
│  │   Baseline   │◀│                  ││   Predict    │      │
│  │   Compare    │ │ - Versioning   │ │   Inference  │      │
│  │              │ │ - Metadata     │ │              │      │
│  └──────────────┘└──────────────────┘└──────────────┘      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Components

| Component | File | Purpose |
|-----------|------|---------|
| Pipeline | `ml/pipeline.py` | Main ML workflow |
| Feature Engineering | `ml/feature_engineering.py` | Causal feature creation |
| Validation | `ml/validation.py` | Purged walk-forward CV |
| Model Registry | `ml/model_registry.py` | Version tracking |

---

## Purged Walk-Forward Validation

### Problem with Standard CV

Standard k-fold cross-validation leaks information in time-series data because:
- Future data can influence past predictions
- Autocorrelation violates i.i.d. assumption
- Look-ahead bias inflates performance

### Solution: Purged Walk-Forward

```
Training (T1) │ Purge │ Validation (V1) │ Gap │ Training (T2) │ Purge │ Validation (V2)
[────────────]│ [──]  │ [────]          │ [--]│ [────────────]│ [──]  │ [────]
              ↑       ↑                 ↑     ↑
           End T1   Start V1         End V1  Start T2
```

### Configuration

```python
from ml.validation import PurgedWalkForwardValidator

validator = PurgedWalkForwardValidator(
    n_splits=5,        # Number of folds
    test_size=0.1,     # 10% for testing
    gap=10,            # 10 periods between train/test
    purge=20,          # 20 periods removed after train
    min_train_size=100 # Minimum training samples
)
```

### Implementation

```python
# From ml/validation.py
class PurgedWalkForwardValidator:
    def __init__(self, n_splits=5, test_size=0.1, gap=10, purge=20, min_train_size=100):
        self.n_splits = n_splits
        self.test_size = test_size
        self.gap = gap
        self.purge = purge
        self.min_train_size = min_train_size
    
    def split(self, X):
        """Generate train/test indices with purging."""
        n_samples = len(X)
        test_length = int(n_samples * self.test_size)
        step = (n_samples - test_length) // self.n_splits
        
        for i in range(self.n_splits):
            test_start = i * step
            test_end = test_start + test_length
            
            # Purge period removed from training
            train_end = test_start - self.purge
            train_start = max(0, train_end - step * 2)
            
            if train_end - train_start >= self.min_train_size:
                train_idx = range(train_start, train_end)
                test_idx = range(test_start + self.gap, test_end + self.gap)
                yield train_idx, test_idx
```

---

## Feature Engineering

### Causal Features Only

**Rule**: Every feature must be computable using only information available at prediction time.

### Feature Categories

#### Technical Indicators
```python
features = {
    'rsi_14': RSI(close, 14),
    'macd': MACD(close),
    'bb_upper': BollingerBand(close, 20, 2).upper,
    'atr': AverageTrueRange(high, low, close, 14)
}
```

#### Statistical Features
```python
features = {
    'volatility_30d': rolling_std(returns, 30),
    'skewness_60d': rolling_skew(returns, 60),
    'correlation_btc': rolling_corr(asset, btc, 30)
}
```

#### Lag Features
```python
features = {
    'return_lag_1': returns.shift(1),
    'return_lag_7': returns.shift(7),
    'volume_ratio_lag_3': volume_ratio.shift(3)
}
```

#### Cross-Sectional Features
```python
features = {
    'rank_return': rank_within_universe(returns),
    'zscore_volatility': (vol - vol.mean()) / vol.std()
}
```

### Implementation

```python
# From ml/feature_engineering.py
class CausalFeatureEngineer:
    def __init__(self):
        self.feature_names = []
    
    def fit_transform(self, X):
        """Create features ensuring causality."""
        
        # Technical indicators
        X['rsi'] = self._calculate_rsi(X['close'])
        X['macd'] = self._calculate_macd(X['close'])
        
        # Volatility features
        X['volatility'] = X['returns'].rolling(30).std()
        
        # Lag features (explicitly causal)
        for lag in [1, 3, 7]:
            X[f'return_lag_{lag}'] = X['returns'].shift(lag)
        
        # Drop NaN from rolling/lag calculations
        X = X.dropna()
        
        self.feature_names = X.columns.tolist()
        return X
```

---

## Target Construction

### Return Prediction

```python
# Forward returns (must be shifted to avoid look-ahead)
def create_target(prices, horizon=5):
    """Create target: future returns over horizon."""
    
    # Shift prices forward (we predict FUTURE returns)
    future_prices = prices.shift(-horizon)
    
    # Calculate forward return
    forward_return = (future_prices - prices) / prices
    
    return forward_return.dropna()
```

### Direction Prediction

```python
def create_direction_target(prices, horizon=5):
    """Binary target: 1 if price goes up, 0 otherwise."""
    
    future_prices = prices.shift(-horizon)
    direction = (future_prices > prices).astype(int)
    
    return direction.dropna()
```

---

## Model Selection

### Default Model: Random Forest

```python
# From ml/pipeline.py
from sklearn.ensemble import RandomForestRegressor

model = RandomForestRegressor(
    n_estimators=30,
    max_depth=4,
    min_samples_leaf=5,
    random_state=42,
    n_jobs=-1
)
```

### Why Random Forest?

✅ **Pros**:
- Handles non-linear relationships
- Robust to outliers
- No feature scaling required
- Provides feature importance
- Less prone to overfitting than deep learning

❌ **Cons**:
- Can't extrapolate beyond training range
- May miss temporal patterns
- Computationally intensive for large datasets

---

## Hyperparameter Optimization

### Grid Search

```python
param_grid = {
    'n_estimators': [30, 50, 100],
    'max_depth': [3, 4, 5, 6],
    'min_samples_leaf': [3, 5, 10],
}

from sklearn.model_selection import GridSearchCV

grid_search = GridSearchCV(
    RandomForestRegressor(random_state=42),
    param_grid,
    cv=purged_validator,
    scoring='r2',
    n_jobs=-1
)
```

### Best Practices

1. **Optimize on training folds only** - Never touch test data
2. **Use conservative parameters** - Prefer simpler models
3. **Limit search space** - Prevent overfitting to validation set
4. **Document optimal params** - For reproducibility

---

## Model Registry

### Purpose

Track model versions, metadata, and performance for reproducibility.

### Implementation

```python
# From ml/model_registry.py
class ModelRegistry:
    def __init__(self, registry_path='models/registry'):
        self.registry_path = registry_path
        self.models = {}
    
    def register(self, model, metadata):
        """Register a trained model with metadata."""
        
        model_id = f"model_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        entry = {
            'model_id': model_id,
            'timestamp': datetime.now().isoformat(),
            'metrics': metadata.get('metrics', {}),
            'features': metadata.get('features', []),
            'config': metadata.get('config', {})
        }
        
        self.models[model_id] = entry
        self._save(entry)
        
        return model_id
```

---

## Baseline Comparison

### Required Baselines

Models must beat these simple benchmarks:

1. **Zero Prediction**: Always predict 0
2. **Mean Prediction**: Always predict historical mean
3. **Naive Prediction**: Predict last observed value

### Comparison Method

```python
# From ml/pipeline.py
def compare_to_baseline(self, X_test, y_test):
    """Compare ML model to simple baselines."""
    
    # ML predictions
    ml_pred = self.predict(X_test)
    ml_r2 = r2_score(y_test, ml_pred)
    
    # Mean baseline
    mean_pred = np.ones(len(y_test)) * y_test.mean()
    mean_r2 = r2_score(y_test, mean_pred)
    
    # Zero baseline
    zero_pred = np.zeros(len(y_test))
    zero_r2 = r2_score(y_test, zero_pred)
    
    # Check if ML improves
    improves = ml_r2 > mean_r2 and ml_r2 > zero_r2
    
    return {
        'ml_r2': ml_r2,
        'mean_r2': mean_r2,
        'zero_r2': zero_r2,
        'improves': improves
    }
```

### Acceptance Criteria

```python
# Model is accepted only if:
if ml_metrics['r2'] > 0.0:  # Better than zero
    if ml_metrics['r2'] > mean_baseline['r2']:  # Better than mean
        if oos_metrics['r2'] > -0.05:  # Reasonable OOS
            accept_model()
```

---

## Performance Metrics

### Regression Metrics

| Metric | Formula | Interpretation |
|--------|---------|----------------|
| R² | 1 - SS_res/SS_tot | Variance explained |
| RMSE | √MSE | Error in target units |
| MAE | Mean\|error\| | Average absolute error |
| IC | Correlation(pred, actual) | Information coefficient |

### Classification Metrics (for direction)

| Metric | Formula | Target |
|--------|---------|--------|
| Accuracy | Correct / Total | > 50% |
| Precision | TP / (TP + FP) | > 50% |
| Recall | TP / (TP + FN) | > 40% |
| AUC | Area under ROC | > 0.55 |

---

## Out-of-Sample Testing

### Requirements

```python
# Minimum OOS requirements
OOS_REQUIREMENTS = {
    'min_r2': 0.0,           # Must beat zero
    'min_ic': 0.05,          # Minimum information coefficient
    'max_drawdown': 0.20,    # Max strategy drawdown
    'min_sharpe': 0.5,       # Minimum risk-adjusted return
}
```

### Rejection Criteria

Model is **rejected** if:
- OOS R² < 0.0 (worse than predicting zero)
- OOS R² < Mean Baseline R²
- Significant degradation from in-sample to OOS
- Negative alpha after transaction costs

---

## Limitations

### Known Issues

⚠️ **Non-Stationarity**: Crypto markets change regimes frequently

⚠️ **Low Signal-to-Noise**: Financial data is inherently noisy

⚠️ **Limited History**: Crypto has short history vs traditional markets

⚠️ **Regime Dependency**: Models trained in one regime may fail in another

### Mitigation Strategies

1. **Regular Retraining**: Update models frequently
2. **Ensemble Methods**: Combine multiple models
3. **Regime Adaptation**: Adjust based on market state
4. **Conservative Sizing**: Reduce position when uncertain

---

## Usage Example

```python
from ml.pipeline import MLPipeline, MLConfig
from ml.feature_engineering import CausalFeatureEngineer

# Configure
config = MLConfig(
    model_type='random_forest',
    n_estimators=50,
    n_splits=5,
    oos_r2_threshold=0.0
)

# Initialize pipeline
pipeline = MLPipeline(config)

# Prepare data
X = feature_engineer.fit_transform(raw_data)
y = create_target(prices, horizon=5)

# Train with walk-forward validation
results = pipeline.walk_forward_validate(X, y)

# Check if model passes
avg_r2 = np.mean([r['r2'] for r in results])
if avg_r2 > config.oos_r2_threshold:
    print(f"Model accepted! Avg OOS R² = {avg_r2:.4f}")
else:
    print(f"Model rejected. Avg OOS R² = {avg_r2:.4f}")
```

---

## Version Information

- **Document Version**: 1.0
- **Last Updated**: 2024
- **Phase**: 35 (Documentation)

---

*This document reflects the actual implementation as of Phase 35.*
