# Testing Documentation - Phase 27

## Overview

This document describes the comprehensive testing strategy for the trading system. All tests follow best practices for unit, integration, security, time-series, fault, and performance testing.

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

## Running Tests

### Run All Tests
```bash
cd /workspace
python -m pytest tests/ -v
```

### Run Specific Test Category
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
