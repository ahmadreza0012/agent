# Configuration & Secrets Management - Phase 26

## Overview

This module provides secure configuration and secrets management for the trading system, ensuring:
- **Environment-based configuration** (dev/test/paper/shadow/production)
- **Secret encryption at rest** using Fernet symmetric encryption
- **Pydantic-based validation** with type safety
- **Graceful degradation** with safe defaults
- **No hard-coded secrets** anywhere in the codebase

## Critical Rules

1. **Never hard-code API keys, secrets, or passwords**
2. **All sensitive data must come from environment variables or secure vault**
3. **Production credentials must NEVER be used in tests**
4. **Configuration must be validated on startup**
5. **Secrets must never appear in logs**
6. **Different environments require separate configs**
7. **All config changes must be audited**
8. **Default values must be safe (disable features, not enable)**
9. **Configuration files must not contain secrets**
10. **All secrets must be encrypted at rest**

## Directory Structure

```
config/
├── __init__.py           # Package exports
├── settings.py           # Pydantic settings models
├── secrets.py            # Secret encryption/decryption
├── validator.py          # Configuration validation
├── loader.py             # Config loading and merging
└── environments/
    ├── __init__.py
    ├── development.py    # Development environment
    ├── testing.py        # Testing environment
    ├── paper.py          # Paper trading environment
    ├── shadow.py         # Shadow trading environment
    └── production.py     # Production environment
```

## Usage

### Basic Usage

```python
from config import get_settings

settings = get_settings()
print(settings.environment)
print(settings.trading_mode)
print(settings.exchange.name)
```

### Loading Specific Environment

```python
from config.loader import ConfigLoader

loader = ConfigLoader('production')
settings = loader.load()
```

### Accessing Secrets

```python
from config import get_secret_manager

manager = get_secret_manager()

# Get secret from environment variable
api_key = manager.get_secret('exchange__api_key')

# Store encrypted secret
manager.store_encrypted('my_secret', 'secret_value')

# Load encrypted secret
value = manager.load_encrypted('my_secret')
```

## Settings Models

### Environment Enum

```python
class Environment(str, Enum):
    DEVELOPMENT = "development"
    TESTING = "testing"
    PAPER = "paper"
    SHADOW = "shadow"
    PRODUCTION = "production"
```

### ExchangeConfig

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| name | str | "binance" | Exchange name |
| api_key | SecretStr | None | API key (encrypted) |
| api_secret | SecretStr | None | API secret (encrypted) |
| api_passphrase | SecretStr | None | API passphrase (encrypted) |
| sandbox | bool | True | Use sandbox/testnet |
| timeout_seconds | int | 30 | Request timeout |
| retry_attempts | int | 3 | Retry count |
| retry_backoff | float | 1.0 | Backoff multiplier |

### DatabaseConfig

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| type | str | "sqlite" | sqlite or postgresql |
| path | str | "data/trading.db" | SQLite file path |
| host | Optional[str] | None | PostgreSQL host |
| port | Optional[int] | None | PostgreSQL port |
| database | Optional[str] | None | Database name |
| user | Optional[str] | None | Database user |
| password | SecretStr | None | Database password |
| max_connections | int | 10 | Connection pool size |

### TradingLimitsConfig

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| max_daily_loss | float | 0.05 | 5% daily loss limit |
| max_total_drawdown | float | 0.15 | 15% total drawdown |
| max_position_size | float | 0.20 | 20% max position |
| max_exposure | float | 0.60 | 60% max exposure |
| max_leverage | float | 1.0 | No leverage by default |

### SafetyConfig

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| kill_switch_enabled | bool | True | Kill switch active |
| auto_derisk | bool | True | Auto reduce risk |
| halt_on_discrepancy | bool | True | Stop on mismatch |
| max_api_failures | int | 3 | Max failures before halt |

## Environment Configurations

### Development

- Mode: paper
- Debug: true
- Log Level: DEBUG
- Sandbox: true
- Alerts: disabled
- Database: SQLite (data/trading_dev.db)

### Testing

- Mode: paper
- Debug: true
- Log Level: DEBUG
- Sandbox: true
- Alerts: disabled
- Safety: relaxed for testing
- Database: SQLite (data/trading_test.db)

### Paper

- Mode: paper
- Debug: false
- Log Level: INFO
- Sandbox: true
- Alerts: enabled
- Safety: full protection
- Database: SQLite (data/trading_paper.db)

### Shadow

- Mode: shadow
- Debug: false
- Log Level: INFO
- Sandbox: false (real market data)
- Alerts: enabled
- Safety: full protection
- Database: SQLite (data/trading_shadow.db)

### Production

- Mode: live (required)
- Debug: false
- Log Level: WARNING
- Sandbox: false
- Alerts: enabled
- Safety: strictest limits
- Database: PostgreSQL

## Environment Variables

All settings can be configured via environment variables using the `TRADING_` prefix:

```bash
# Environment
TRADING_ENV=development
TRADING_DEBUG=true
TRADING_LOG_LEVEL=INFO

# Trading Mode
TRADING_MODE=paper

# Exchange
TRADING_EXCHANGE__NAME=binance
TRADING_EXCHANGE__SANDBOX=true
TRADING_EXCHANGE__API_KEY=your_api_key
TRADING_EXCHANGE__API_SECRET=your_api_secret

# Database
TRADING_DATABASE__TYPE=sqlite
TRADING_DATABASE__PATH=data/trading.db

# API
TRADING_API__HOST=0.0.0.0
TRADING_API__PORT=8000
TRADING_API__RATE_LIMIT=60

# Alerts
TRADING_ALERTS__ENABLED=true
TRADING_ALERTS__MIN_SEVERITY=warning
TRADING_ALERTS__SLACK_WEBHOOK_URL=https://hooks.slack.com/...

# Master Key (for secret encryption)
TRADING_MASTER_KEY=your_secure_master_key
TRADING_SALT=trading_system_salt
```

See `.env.example` for a complete list of available variables.

## Secret Encryption

The `SecretManager` class provides encryption for sensitive data:

```python
from config.secrets import SecretManager

# Initialize with custom key path
manager = SecretManager(key_path="data/secret.key")

# Encrypt a secret
encrypted = manager.encrypt("my_secret_value")

# Decrypt a secret
decrypted = manager.decrypt(encrypted)

# Store encrypted secret in JSON file
manager.store_encrypted("api_key", "key_123", "data/secrets.json")

# Load encrypted secret
value = manager.load_encrypted("api_key", "data/secrets.json")
```

### Key Derivation

If `TRADING_MASTER_KEY` is set, the encryption key is derived using PBKDF2:
- Algorithm: SHA256
- Iterations: 100,000
- Salt: `TRADING_SALT` environment variable (default: "trading_system_salt")

## Configuration Validation

On startup, all configuration is validated:

```python
from config.settings import Settings
from config.validator import ConfigValidator

settings = Settings()
validator = ConfigValidator(settings)
is_valid, errors, warnings = validator.validate_all()

if not is_valid:
    for error in errors:
        print(f"❌ {error}")
    raise ValueError("Configuration validation failed")

for warning in warnings:
    print(f"⚠ {warning}")
```

### Validations Performed

1. **Paths**: Required directories exist or can be created
2. **Exchange**: API credentials present for live mode
3. **Database**: Required fields for PostgreSQL
4. **API**: Port availability, API key for production
5. **Alerts**: At least one channel if enabled
6. **Mode/Environment**: Compatibility checks (production requires live mode)

## Security Best Practices

### DO ✅

- Use environment variables for secrets
- Encrypt secrets at rest
- Use different configs per environment
- Validate configuration on startup
- Keep `.env` files out of version control
- Use safe defaults (features disabled)

### DON'T ❌

- Hard-code API keys or passwords
- Commit `.env` files to git
- Use production credentials in tests
- Log sensitive information
- Share encryption keys
- Disable safety features in production

## Testing

Run the configuration tests:

```bash
python -m unittest tests.test_phase26_config -v
```

Tests cover:
- Settings validation and loading
- Secret encryption/decryption
- Configuration validation
- Environment-specific configurations

## Migration from Old Config

The old `config.py` file uses global constants. To migrate:

1. Replace direct imports with settings access:
   ```python
   # Old
   from config import RISK_FREE_RATE
   
   # New
   from config import get_settings
   settings = get_settings()
   rate = settings.limits.max_leverage  # or similar
   ```

2. Move secrets to environment variables:
   ```bash
   export TRADING_EXCHANGE__API_KEY=your_key
   ```

3. Use environment-specific configs instead of manual overrides

## Troubleshooting

### "Configuration validation failed"

Check the error messages for specific issues:
- Missing API keys for live mode
- Invalid database configuration
- Port conflicts

### "Secret not found"

Ensure the environment variable is set:
```bash
export TRADING_EXCHANGE__API_KEY=your_key
```

Or store encrypted:
```python
manager.store_encrypted('exchange__api_key', 'your_key')
```

### Encryption key lost

If you lose the encryption key and don't have `TRADING_MASTER_KEY`:
1. Delete `data/secret.key`
2. Re-store all encrypted secrets
3. Or set `TRADING_MASTER_KEY` to recover

## Next Steps

After Phase 26, continue with:
- **Phase 27:** Testing enhancements
- **Phase 28:** Static quality checks
- **Phase 29:** Performance optimization
