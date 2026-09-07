"""
Performance Optimization Documentation.

This document describes the performance optimization framework and guidelines
for the trading system.
"""

# PHASE 29: PERFORMANCE OPTIMIZATION

## Overview

Phase 29 implements a comprehensive performance optimization framework for the 
trading system. The focus is on **profiling first, optimizing second**, and 
**never sacrificing correctness for speed**.

## Key Components

### 1. Performance Profiler (`utils/profiler.py`)

The profiler provides tools for measuring execution time:

```python
from utils.profiler import profiler, PerformanceProfiler, Timer, benchmark

# Enable profiling
profiler.enabled = True

# Profile a function with decorator
@profiler.profile("expensive_function")
def my_function():
    pass

# Profile a code block
with profiler.measure("data_processing"):
    process_data()

# Generate report
print(profiler.report())
profiler.save_report('performance_report.txt')

# Quick timing
with Timer("operation_name"):
    do_something()

# Benchmark multiple iterations
stats = benchmark(my_function, arg1, arg2, iterations=20)
```

**Features:**
- Function-level profiling with decorators
- Context manager for code blocks
- Statistical analysis (min, max, avg, total)
- cProfile integration for detailed analysis
- Thread-safe operation
- Report generation and export

### 2. Smart Cache (`utils/cache.py`)

Intelligent caching to avoid redundant computations:

```python
from utils.cache import cache, SmartCache

# Use as decorator
@cache.cached(ttl_hours=6)
def expensive_calculation(data, params):
    pass

# Manual operations
key = cache.key("function_name", arg1, arg2)
cached = cache.get(key)
if cached is None:
    result = compute()
    cache.set(key, result)

# Cache statistics
stats = cache.stats()
```

**Features:**
- File-based persistence for large objects
- In-memory LRU cache for frequently accessed items
- TTL (time-to-live) based expiration
- Automatic cache cleanup
- Thread-safe operation

### 3. Benchmark Framework (`tests/benchmark.py`)

Compare different implementations:

```python
from tests.benchmark import Benchmark, compare_implementations

# Run benchmarks
benchmark = Benchmark(iterations=20)
benchmark.run("Old Implementation", old_func, data)
benchmark.run("New Implementation", new_func, data)

# Generate report
print(benchmark.report())
benchmark.save_report('results.csv')

# Compare two implementations
comparison = compare_implementations(
    "Old", old_func,
    "New", new_func,
    data, iterations=20
)
print(f"Speedup: {comparison['speedup']:.2f}x")
```

### 4. Cached Data Provider (`data/providers/cached.py`)

Avoid redundant data downloads:

```python
from data.providers.cached import CachedDataProvider
from data.providers.historical import HistoricalDataProvider

# Wrap base provider with caching
base = HistoricalDataProvider()
cached = CachedDataProvider(base, cache_dir='data/cache')

# Fetch data (uses cache if available)
data = cached.fetch_ohlcv('BTC/USDT', '1h', since_days=30)

# Check cache stats
stats = cached.get_cache_stats()
```

### 5. Profiling Script (`scripts/profile_system.py`)

Run the full system profile:

```bash
python scripts/profile_system.py
```

This generates a comprehensive performance report showing:
- Data operation timings
- Covariance calculation performance
- Portfolio optimization timings
- Caching effectiveness
- Full pipeline breakdown

## Performance Targets

| Component | Target |
|-----------|--------|
| Data loading (per symbol/day) | < 100ms |
| Regime detection | < 50ms |
| Strategy calculation (per symbol) | < 10ms |
| Ensemble selection | < 20ms |
| Portfolio optimization | < 50ms |
| Risk evaluation | < 20ms |
| Total decision loop | < 250ms |

## Optimization Guidelines

### When to Optimize

✅ Function called 1000+ times per day
✅ Data processing taking > 1 second
✅ Backtesting taking > 10 seconds per year
✅ API response time > 200ms
✅ Memory usage > 1GB
✅ Inference taking > 100ms per prediction

### When NOT to Optimize

❌ Function called less than 10 times per day
❌ Code that is rarely used
❌ Code that is already fast enough
❌ Code that is changing frequently
❌ Code that is difficult to test
❌ Code that sacrifices clarity

### Rules

⚠️ **NEVER:** Optimize at the expense of correctness
⚠️ **NEVER:** Optimize before profiling
⚠️ **NEVER:** Change mathematical behavior
⚠️ **NEVER:** Remove safety checks
⚠️ **NEVER:** Optimize without tests

✅ **ALWAYS:** Profile first
✅ **ALWAYS:** Measure improvement
✅ **ALWAYS:** Maintain tests
✅ **ALWAYS:** Document changes
✅ **ALWAYS:** Keep code readable

## Common Optimizations

### 1. Pandas Operations

```python
# BEFORE - Slow
df['return'] = df['close'].pct_change()
for col in df.columns:
    df[f'{col}_lag1'] = df[col].shift(1)

# AFTER - Vectorized
df['return'] = df['close'].pct_change()
lag_cols = ['close', 'volume', 'high', 'low']
for col in lag_cols:
    df[f'{col}_lag1'] = df[col].shift(1)
```

### 2. Data Types

```python
# Use efficient data types
df['price'] = df['price'].astype('float32')  # Instead of float64
df['volume'] = df['volume'].astype('int32')
```

### 3. Covariance Calculation

```python
from sklearn.covariance import LedoitWolf

# Use shrinkage estimator for better stability
lw = LedoitWolf()
cov = lw.fit(returns).covariance_
```

### 4. Caching Expensive Operations

```python
@cache.cached(ttl_hours=24)
def calculate_covariance_matrix(returns_data):
    # Expensive computation
    return cov_matrix
```

## Usage Examples

### Example 1: Profile a Function

```python
from utils.profiler import profiler

profiler.enabled = True

@profiler.profile("my_strategy")
def run_strategy(data):
    # Strategy logic
    pass

run_strategy(data)
print(profiler.report())
```

### Example 2: Benchmark Two Implementations

```python
from tests.benchmark import Benchmark

benchmark = Benchmark(iterations=20)

# Test old implementation
benchmark.run("Covariance - Standard", np.cov, returns)

# Test optimized implementation  
benchmark.run("Covariance - Shrinkage", fast_cov, returns)

# Show comparison
print(benchmark.report())
print(benchmark.summary())
```

### Example 3: Add Caching

```python
from utils.cache import cache

@cache.cached(ttl_hours=6)
def fetch_and_process_data(symbol, start, end):
    # Expensive data fetching and processing
    return processed_data

# First call computes and caches
data = fetch_and_process_data('BTC/USDT', '2023-01-01', '2024-01-01')

# Second call uses cache
data = fetch_and_process_data('BTC/USDT', '2023-01-01', '2024-01-01')
```

## Files Created/Modified

| File | Purpose |
|------|---------|
| `utils/profiler.py` | Performance profiling framework |
| `utils/cache.py` | Smart caching system |
| `tests/benchmark.py` | Benchmarking framework |
| `scripts/profile_system.py` | System profiling script |
| `data/providers/cached.py` | Enhanced cached data provider |

## Verification

Run the profiling script to verify everything works:

```bash
python scripts/profile_system.py
```

Expected output:
- All components profile successfully
- Performance report generated
- No errors or warnings

Run existing tests to ensure no regressions:

```bash
python -m unittest tests.performance.test_pandas_operations -v
```

## Next Steps

After profiling, identify bottlenecks and apply targeted optimizations:

1. **Profile** - Run `scripts/profile_system.py`
2. **Identify** - Find slowest functions in the report
3. **Optimize** - Apply appropriate optimization techniques
4. **Measure** - Verify improvement with benchmarks
5. **Test** - Ensure all tests still pass
6. **Document** - Update this documentation

## References

- Python cProfile: https://docs.python.org/3/library/profile.html
- Pandas Performance Tips: https://pandas.pydata.org/docs/user_guide/enhancingperf.html
- NumPy Optimization: https://numpy.org/doc/stable/reference/routines.math.html
