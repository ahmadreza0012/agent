import sys; sys.path.insert(0, '/workspace')
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

def test_validation():
    from ml.validation import PurgedWalkForwardValidator
    n = 500; data = pd.DataFrame({'x': np.random.randn(n), 'y': np.random.randn(n)})
    v = PurgedWalkForwardValidator(n_splits=3, test_size=0.1, gap=5, purge=10)
    folds = list(v.split(data))
    assert len(folds) >= 2
    for train, test in folds:
        assert len(set(train) & set(test)) == 0
    print("✅ Validation PASSED")

def test_features():
    from ml.feature_engineering import CausalFeatureEngineer
    dates = pd.date_range('2023-01-01', periods=100, freq='D')
    data = pd.DataFrame({'close': 100 + np.cumsum(np.random.randn(100)*0.5), 'volume': np.random.randint(100,1000,100)}, index=dates)
    eng = CausalFeatureEngineer(); features = eng.calculate_features(data, timestamp=dates[50])
    assert all(np.isfinite(v) for v in features.values())
    print("✅ Features PASSED")

def test_registry():
    from ml.model_registry import ModelRegistry
    r = ModelRegistry()
    vid = r.register_model(None, {'training_start': datetime.now(), 'training_end': datetime.now(), 'hyperparameters': {'n': 30}, 'training_metrics': {'r2': 0.5}, 'validation_metrics': {'r2': 0.3}})
    assert vid.startswith('v'); assert r.get_model(vid) is not None
    print("✅ Registry PASSED")

def test_ensemble():
    from ensemble import StrategyScorer
    s = StrategyScorer()
    score = s.calculate_score('test', [0.01,0.02,-0.01], 0.8, 0.6, -0.05, 'bull_trend', {'bull_trend': 0.05}, turnover=0.1)
    assert 0 <= score.final_score <= 1
    print("✅ Ensemble PASSED")

def test_robustness():
    from backtesting.robustness import RobustnessAnalyzer
    a = RobustnessAnalyzer(n_simulations=100)
    returns = np.random.randn(252) * 0.001
    results = a.simulate(returns, lambda x: x)
    assert len(results['total_return']) == 100
    print("✅ Robustness PASSED")

if __name__ == "__main__":
    print("="*60); print("🧪 PHASES 6-12 TESTS"); print("="*60)
    for test in [test_validation, test_features, test_registry, test_ensemble, test_robustness]:
        try: test()
        except Exception as e: print(f"❌ {test.__name__}: {e}")
    print("="*60); print("✅ All tests complete"); print("="*60)
