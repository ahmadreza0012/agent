# Testing Guide

## Testing Philosophy

The Crypto Trading Agent testing strategy follows these principles:

1. **Comprehensive Coverage**: Test all critical paths
2. **Isolation**: Unit tests don't depend on external services
3. **Reproducibility**: Tests produce consistent results
4. **Realistic Scenarios**: Integration tests mirror production
5. **Security First**: Dedicated security test suite
6. **Time-Series Aware**: Special handling for temporal data

---

## Test Structure

```
tests/
├── unit/                    # Unit tests for individual components
│   ├── test_indicators.py   # Technical indicator tests
│   ├── test_returns.py      # Return calculation tests
│   ├── test_portfolio_math.py # Portfolio optimization tests
│   ├── test_risk_engine.py  # Risk engine tests
│   └── test_circuit_breaker.py # Circuit breaker tests
├── integration/             # Integration tests
│   ├── test_data_provider.py # Data provider integration
│   └── test_backtester.py   # Backtester integration
├── security/                # Security tests
│   └── test_secret_leakage.py # Secret leakage detection
├── time_series/             # Time-series specific tests
│   └── test_look_ahead_bias.py # Look-ahead bias detection
├── fault/                   # Fault tolerance tests
│   └── test_exchange_failure.py # Exchange failure handling
└── performance/             # Performance benchmarks
    └── test_pandas_operations.py # Pandas performance tests
```

---

## Running Tests

### Run All Tests

```bash
cd /workspace
python -m pytest tests/ -v
```

### Run Specific Categories

```bash
# Unit tests only
python -m pytest tests/unit/ -v

# Integration tests only
python -m pytest tests/integration/ -v

# Security tests only
python -m pytest tests/security/ -v

# Time-series tests only
python -m pytest tests/time_series/ -v

# Fault tests only
python -m pytest tests/fault/ -v
```

### Run with Coverage

```bash
# Generate coverage report
python -m pytest --cov=. tests/ --cov-report=html

# View coverage summary
python -m pytest --cov=. tests/ --cov-report=term-summary

# Fail if coverage below threshold
python -m pytest --cov=. tests/ --cov-fail-under=80
```

### Run Specific Test

```bash
# Run single test file
python -m pytest tests/unit/test_risk_engine.py -v

# Run single test function
python -m pytest tests/unit/test_risk_engine.py::test_drawdown_calculation -v

# Run tests matching pattern
python -m pytest -k "circuit" -v
```

---

## Writing Tests

### Unit Test Template

```python
import pytest
from risk.circuit_breaker import CircuitBreaker, BreakerState

class TestCircuitBreaker:
    """Test circuit breaker state machine."""
    
    def setup_method(self):
        """Setup before each test."""
        self.breaker = CircuitBreaker()
    
    def test_initial_state_is_normal(self):
        """Verify initial state is NORMAL."""
        assert self.breaker.state == BreakerState.NORMAL
    
    def test_warning_triggered_at_5pct_drawdown(self):
        """Verify WARNING state at 5% drawdown."""
        self.breaker.update(drawdown=0.05, daily_pnl=-0.015)
        assert self.breaker.state == BreakerState.WARNING
    
    def test_halt_triggered_at_12pct_drawdown(self):
        """Verify HALT state at 12% drawdown."""
        self.breaker.update(drawdown=0.12)
        assert self.breaker.state == BreakerState.HALT
        assert not self.breaker.can_trade()
```

### Integration Test Template

```python
import pytest
from backtester import Backtester
from data_fetcher import DataFetcher

class TestBacktesterIntegration:
    """Test backtester with real data."""
    
    @pytest.fixture
    def sample_data(self):
        """Load sample historical data."""
        fetcher = DataFetcher()
        return fetcher.fetch('BTC/USDT', '4h', days=365)
    
    def test_walk_forward_validation(self, sample_data):
        """Test walk-forward validation produces results."""
        backtester = Backtester(initial_capital=100000)
        results = backtester.walk_forward_test(sample_data)
        
        assert len(results['folds']) > 0
        assert 'sharpe' in results['metrics']
```

### Security Test Template

```python
import pytest
import os

class TestSecretLeakage:
    """Test for secret exposure."""
    
    def test_no_secrets_in_logs(self, caplog):
        """Verify secrets are not logged."""
        from execution.exchange_adapter import ExchangeAdapter
        
        with caplog.at_level('INFO'):
            adapter = ExchangeAdapter()
            # Trigger some operations
            adapter.fetch_balance()
        
        # Check logs don't contain API key
        assert 'EXCHANGE_API_KEY' not in caplog.text
        for record in caplog.records:
            assert len(record.getMessage()) < 200  # No large blobs
    
    def test_env_file_not_committed(self):
        """Verify .env is in .gitignore."""
        with open('.gitignore', 'r') as f:
            gitignore = f.read()
        
        assert '.env' in gitignore
```

### Time-Series Test Template

```python
import pytest
import pandas as pd
import numpy as np

class TestLookAheadBias:
    """Test for look-ahead bias in features."""
    
    def test_features_are_causal(self):
        """Verify features only use past data."""
        from ml.feature_engineering import CausalFeatureEngineer
        
        # Create sample data
        dates = pd.date_range('2024-01-01', periods=100, freq='D')
        prices = pd.Series(np.random.randn(100).cumsum() + 100, index=dates)
        
        engineer = CausalFeatureEngineer()
        features = engineer.fit_transform(pd.DataFrame({'close': prices}))
        
        # Verify no future data leakage
        # (features at time t should not depend on prices at t+1 or later)
        for col in features.columns:
            correlation_with_future = features[col].corr(prices.shift(-1))
            assert abs(correlation_with_future) < 0.1  # Should be near zero
```

### Fault Test Template

```python
import pytest
from unittest.mock import Mock, patch
import ccxt

class TestExchangeFailure:
    """Test exchange failure handling."""
    
    def test_retry_on_network_error(self):
        """Verify retry logic on network errors."""
        from execution.exchange_adapter import ExchangeAdapter
        
        adapter = ExchangeAdapter()
        
        # Mock exchange to fail twice, then succeed
        mock_exchange = Mock()
        mock_exchange.fetch_balance.side_effect = [
            ccxt.NetworkError(),
            ccxt.NetworkError(),
            {'total': 1000}
        ]
        adapter.exchange = mock_exchange
        
        # Should succeed after retries
        balance = adapter.fetch_balance()
        assert balance['total'] == 1000
        assert mock_exchange.fetch_balance.call_count == 3
    
    def test_halt_on_auth_error(self):
        """Verify system halts on authentication error."""
        from execution.kill_switch import KillSwitch
        
        kill_switch = KillSwitch()
        
        # Simulate auth error
        try:
            raise ccxt.AuthenticationError("Invalid API key")
        except ccxt.AuthenticationError:
            kill_switch.activate(reason="AUTH_ERROR")
        
        assert kill_switch.is_active()
```

---

## Test Coverage Requirements

### Minimum Coverage

| Component | Minimum Coverage |
|-----------|-----------------|
| Risk Engine | 90% |
| Circuit Breaker | 95% |
| Order Manager | 85% |
| Portfolio Optimizer | 80% |
| ML Pipeline | 75% |
| Data Fetcher | 70% |

### Critical Paths

These paths MUST be tested:
- Circuit breaker state transitions
- Risk limit enforcement
- Order creation and submission
- Position reconciliation
- Kill switch activation
- Drawdown calculations

---

## CI/CD Integration

### GitHub Actions Example

```yaml
# .github/workflows/tests.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11"]
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install -r requirements-dev.txt
    
    - name: Run tests
      run: |
        pytest tests/ -v --cov=. --cov-report=xml
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
```

---

## Troubleshooting

### Test Fails Intermittently

**Cause**: Race condition or external dependency.

**Solution**:
```python
# Use mocks for external dependencies
@pytest.fixture
def mock_exchange():
    with patch('ccxt.binance') as mock:
        yield mock

# Add retry decorator for flaky tests
from flaky import flaky

@flaky(max_runs=3, min_passes=1)
def test_sometimes_flaky():
    ...
```

### Test Too Slow

**Cause**: Expensive operations or large datasets.

**Solution**:
```python
# Mark slow tests
@pytest.mark.slow
def test_large_dataset():
    ...

# Run slow tests separately
pytest -m "not slow"  # Fast tests only
pytest -m slow        # Slow tests only
```

### Fixtures Not Working

**Cause**: Scope or naming issues.

**Solution**:
```python
# Ensure correct scope
@pytest.fixture(scope='module')  # Once per module
@pytest.fixture(scope='function')  # Once per test (default)

# Use correct naming
@pytest.fixture
def my_fixture():  # Must match parameter name
    return value

def test_something(my_fixture):  # Parameter name matches fixture
    ...
```

---

## Best Practices

1. **Name tests descriptively** - `test_circuit_breaker_halts_at_12pct_drawdown`
2. **Use fixtures for setup** - Don't repeat setup code
3. **Test behavior, not implementation** - Focus on what, not how
4. **Keep tests independent** - No test should depend on another
5. **Mock external services** - Don't call real APIs in unit tests
6. **Use parametrization** - Test multiple inputs efficiently
7. **Assert specific conditions** - Not just `assert result`
8. **Clean up after tests** - Use teardown or context managers

---

## Version Information

- **Document Version**: 1.0
- **Last Updated**: 2024
- **Phase**: 35 (Documentation)

---

*This document reflects the actual implementation as of Phase 35.*

# Fault tests only
python -m pytest tests/fault/ -v

# Performance tests only
python -m pytest tests/performance/ -v
```

### Run with Coverage
```bash
python -m pytest tests/ --cov=. --cov-report=html --cov-fail-under=80
```

### Run Single Test File
```bash
python -m pytest tests/unit/test_indicators.py -v
```

## Test Categories

### 1. Unit Tests

Test individual components in isolation with mocked dependencies.

**Coverage Requirements:**
- All public functions must have tests
- Edge cases must be tested
- Invalid inputs must be tested
- Expected outputs must be verified

**Example:**
```python
def test_ema_causal(self):
    """Test EMA uses only past data."""
    ema = EMA(self.prices, period=20)
    for i in range(20, len(self.prices)):
        truncated = self.prices.iloc[:i+1]
        ema_truncated = EMA(truncated, period=20)
        self.assertEqual(ema.iloc[i], ema_truncated.iloc[-1])
```

### 2. Integration Tests

Test component interactions with mocked external services.

**Requirements:**
- No live API calls
- Mock all external dependencies
- Test data flow between components
- Verify end-to-end functionality

### 3. Security Tests

Test for vulnerabilities and secret leakage.

**Tests Include:**
- No hard-coded secrets in code
- No secrets in config files
- No secrets in logs
- Input validation

### 4. Time-Series Tests

Critical tests to ensure no look-ahead bias or data leakage.

**Key Principles:**
- All features must be causal (use only past data)
- Scalers must not use future statistics
- Rolling windows must not be centered
- Imputation must not use future values

### 5. Fault Tests

Test system behavior under failure conditions.

**Scenarios Tested:**
- Exchange API timeouts
- Connection failures
- Partial fills
- Duplicate orders
- Stale data
- Database restarts

**Requirements:**
- Graceful degradation
- Proper error handling
- Retry logic with backoff
- State preservation

### 6. Performance Tests

Establish performance baselines for critical operations.

**Benchmarks:**
- Rolling mean: < 1s for 10k rows
- EWM: < 1s for 10k rows
- Covariance matrix: < 0.5s for 5 assets
- DataFrame merge: < 0.5s for 5k rows

## Test Best Practices

### Deterministic Tests
All tests must be deterministic and repeatable:
```python
np.random.seed(42)  # Set seed for reproducibility
```

### No Live Dependencies
Never use live data or real credentials:
```python
@patch('data.providers.exchange.BinanceProvider')
def test_something(self, mock_exchange):
    mock_exchange.get_ohlcv.return_value = mock_data
```

### Proper Assertions
Use specific assertions:
```python
self.assertEqual(len(result), expected_length)
self.assertIsInstance(value, float)
self.assertGreater(sharpe, -10)
```

### Skip Unavailable Tests
Gracefully skip tests for unimplemented features:
```python
try:
    from module import Feature
except ImportError:
    self.skipTest("Feature not implemented yet")
```

## Continuous Integration

Tests are configured to run automatically on:
- Every commit
- Pull requests
- Before deployments

### CI Configuration
```yaml
test:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v2
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: 3.9
    - name: Install dependencies
      run: pip install -r requirements.txt
    - name: Run tests
      run: pytest tests/ --cov=. --cov-fail-under=80
```

## Coverage Requirements

| Component | Minimum Coverage |
|-----------|-----------------|
| Core algorithms | 90% |
| Risk management | 95% |
| Execution engine | 90% |
| Data processing | 85% |
| Utilities | 80% |

## Known Limitations

1. Some tests may skip if optional dependencies are not installed
2. Performance tests may vary based on hardware
3. Integration tests require mock setup

## Future Improvements

1. Add mutation testing
2. Increase coverage to 95%+
3. Add property-based testing with Hypothesis
4. Add chaos engineering tests
5. Add load testing for API endpoints

## References

- [Python Testing Best Practices](https://docs.python.org/3/library/unittest.html)
- [pytest Documentation](https://docs.pytest.org/)
- [Testing Python Applications](https://testdriven.io/courses/test-driven-development-with-pytest/)
