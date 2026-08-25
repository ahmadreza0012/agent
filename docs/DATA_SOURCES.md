# Data Sources

## Overview

The system acquires market data from multiple sources with built-in redundancy and validation.

---

## Supported Data Providers

### Primary Provider: CoinGecko

**Purpose**: Historical and real-time price data for cryptocurrencies.

**Configuration**:
```bash
DATA_PROVIDER="coingecko"
```

**Features**:
- Free API tier available
- Wide cryptocurrency coverage
- Historical data access
- Rate limiting enforced

**Limitations**:
- Rate limits: 10-50 calls/minute (free tier)
- Some delays in real-time data
- Limited intraday granularity

### Exchange Data: ccxt

**Purpose**: Direct exchange data for supported platforms.

**Supported Exchanges**:
- Binance (primary)
- Coinbase
- Kraken
- Other ccxt-supported exchanges

**Configuration**:
```bash
TRADING_EXCHANGE__NAME=binance
TRADING_EXCHANGE__SANDBOX=true  # Use testnet
```

### Sentiment Data: Groq AI

**Purpose**: AI-powered sentiment analysis from news and social media.

**Configuration**:
```bash
GROQ_API_KEY=your_key_here
```

---

## Supported Timeframes

| Timeframe | Code | Use Case |
|-----------|------|----------|
| 1 minute | `1m` | High-frequency trading |
| 5 minutes | `5m` | Intraday strategies |
| 15 minutes | `15m` | Short-term trading |
| 1 hour | `1h` | Medium-term strategies |
| 4 hours | `4h` | **Default** - Balance of signal/noise |
| Daily | `1d` | Long-term strategies |
| Weekly | `1w` | Strategic allocation |

---

## Data Quality Validation

### Automated Checks

```python
def validate_data(df):
    """Validate OHLCV data quality."""
    
    checks = {
        'no_missing_timestamps': df.index.is_unique,
        'positive_prices': (df['open'] > 0).all() and (df['close'] > 0).all(),
        'high_low_valid': (df['high'] >= df['low']).all(),
        'volume_non_negative': (df['volume'] >= 0).all(),
        'no_gaps': _check_continuity(df.index),
    }
    
    return all(checks.values()), checks
```

### Validation Rules

| Check | Description | Action on Failure |
|-------|-------------|-------------------|
| Missing timestamps | Gaps in time series | Interpolate or reject |
| Negative prices | Invalid price data | Reject data point |
| High < Low | Impossible OHLC | Reject data point |
| Volume < 0 | Invalid volume | Set to 0 or reject |
| Extreme outliers | Price > 3σ from mean | Flag for review |

---

## Data Caching

### Configuration

```bash
DATA_CACHE_ENABLED=true
DATA_CACHE_DIR=.cache/data
CACHE_TTL_HOURS=24
```

### Cache Structure

```
.cache/
├── data/
│   ├── coingecko/
│   │   ├── BTC_USDT_4h.parquet
│   │   └── ETH_USDT_4h.parquet
│   └── binance/
│       └── ...
└── metadata/
    └── cache_manifest.json
```

### Cache Invalidation

Cache is invalidated when:
- TTL expires (default 24 hours)
- Manual cache clear requested
- Data validation fails
- New data available with newer timestamp

---

## Symbol Normalization

### Format Standardization

The system normalizes symbols across different providers:

| Provider | Format | Normalized |
|----------|--------|------------|
| CoinGecko | `bitcoin/usdt` | `BTC/USDT` |
| Binance | `BTCUSDT` | `BTC/USDT` |
| ccxt | `BTC/USDT` | `BTC/USDT` |

### Implementation

```python
def normalize_symbol(symbol: str, provider: str) -> str:
    """Normalize symbol to standard format."""
    
    if provider == 'binance':
        # BTCUSDT → BTC/USDT
        symbol = re.sub(r'(USD|USDT|BTC|ETH)', r'/\1', symbol).strip('/')
    elif provider == 'coingecko':
        # bitcoin/usdt → BTC/USDT
        symbol = symbol.upper().replace('BITCOIN', 'BTC').replace('ETHEREUM', 'ETH')
    
    return symbol
```

---

## Volume Handling

### Volume Validation

```python
def validate_volume(volume_data, min_liquidity_usd=1_000_000):
    """Check if asset meets minimum liquidity requirements."""
    
    avg_daily_volume = volume_data.mean() * price_data.mean()
    
    if avg_daily_volume < min_liquidity_usd:
        logger.warning(f"Liquidity below threshold: ${avg_daily_volume:,.0f}")
        return False
    
    return True
```

### ADV Calculation

```python
def calculate_adv(prices, volumes, window=30):
    """Calculate Average Daily Volume in USD."""
    
    dollar_volume = prices * volumes
    adv = dollar_volume.rolling(window).mean()
    
    return adv
```

---

## Data Fallbacks

### Fallback Chain

```
Primary (CoinGecko) → Secondary (Exchange API) → Cache → Error
```

### Implementation

```python
def fetch_with_fallback(symbol, timeframe):
    """Fetch data with automatic fallback."""
    
    # Try primary source
    try:
        data = fetch_from_coingecko(symbol, timeframe)
        if validate_data(data):
            return data
    except Exception as e:
        logger.warning(f"Primary source failed: {e}")
    
    # Try secondary source
    try:
        data = fetch_from_exchange(symbol, timeframe)
        if validate_data(data):
            return data
    except Exception as e:
        logger.warning(f"Secondary source failed: {e}")
    
    # Try cache
    cached = get_from_cache(symbol, timeframe)
    if cached and not is_cache_stale(cached):
        logger.info("Using cached data")
        return cached
    
    raise DataError("All sources failed")
```

---

## Rate Limiting

### Rate Limit Configuration

```python
RATE_LIMITS = {
    'coingecko': {
        'calls_per_minute': 30,
        'calls_per_day': 10000,
    },
    'binance': {
        'weight_per_minute': 1200,
    }
}
```

### Rate Limit Handler

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=60)
)
def fetch_with_rate_limit(symbol):
    """Fetch data respecting rate limits."""
    
    if rate_limiter.is_rate_limited():
        sleep_time = rate_limiter.get_wait_time()
        logger.info(f"Rate limited, waiting {sleep_time}s")
        time.sleep(sleep_time)
    
    return api_call(symbol)
```

---

## Data Storage

### SQLite (Development)

```bash
TRADING_DATABASE__TYPE=sqlite
TRADING_DATABASE__PATH=data/trading.db
```

**Schema**:
```sql
CREATE TABLE price_data (
    symbol TEXT NOT NULL,
    timestamp DATETIME NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume REAL,
    PRIMARY KEY (symbol, timestamp)
);
```

### PostgreSQL (Production)

```bash
TRADING_DATABASE__TYPE=postgresql
TRADING_DATABASE__HOST=localhost
TRADING_DATABASE__PORT=5432
TRADING_DATABASE__DATABASE=trading
TRADING_DATABASE__USER=trading
TRADING_DATABASE__PASSWORD=secret
```

**Advantages**:
- Better concurrency
- Larger capacity
- Advanced indexing
- Replication support

---

## Custom Data Sources

### Adding a New Provider

```python
class CustomDataProvider:
    def __init__(self, config):
        self.config = config
    
    def fetch(self, symbol, timeframe, start, end):
        """Fetch data from custom source."""
        # Implement data fetching logic
        pass
    
    def validate(self, df):
        """Validate data quality."""
        # Implement validation logic
        pass
```

### Registration

```python
# In config.py
DATA_PROVIDERS = {
    'coingecko': CoinGeckoProvider,
    'binance': BinanceProvider,
    'custom': CustomDataProvider,  # Add your own
}
```

---

## Troubleshooting

### Missing Data Points

**Symptoms**: Gaps in time series.

**Causes**:
- Exchange downtime
- API rate limiting
- Network issues

**Resolution**:
```bash
# Clear cache and refetch
rm -rf .cache/data/*
python scripts/fetch_data.py --symbols BTC/USDT --days 30
```

### Data Validation Failures

**Symptoms**: Repeated validation errors.

**Diagnosis**:
```python
from data_fetcher import DataFetcher

fetcher = DataFetcher()
df = fetcher.fetch('BTC/USDT', '4h')
valid, checks = fetcher.validate(df)
print(f"Failed checks: {[k for k, v in checks.items() if not v]}")
```

### Rate Limit Errors

**Symptoms**: HTTP 429 errors.

**Resolution**:
1. Increase cache TTL
2. Reduce fetch frequency
3. Upgrade API tier
4. Implement request queuing

---

## Best Practices

1. **Always validate data** before use
2. **Use caching** to reduce API calls
3. **Implement fallbacks** for reliability
4. **Monitor data quality** continuously
5. **Respect rate limits** to avoid bans
6. **Store raw data** for reproducibility
7. **Document data sources** and limitations

---

## Version Information

- **Document Version**: 1.0
- **Last Updated**: 2024
- **Phase**: 35 (Documentation)

---

*This document reflects the actual implementation as of Phase 35.*
