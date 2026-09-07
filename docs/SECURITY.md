# Security Practices

## Security Philosophy

The Crypto Trading Agent implements **defense-in-depth** security with multiple layers of protection:

1. **Secrets Management**: API keys never in code
2. **Access Control**: Role-based permissions
3. **Network Security**: Firewall and rate limiting
4. **Data Protection**: Encryption at rest
5. **Audit Logging**: Complete activity trail

---

## API Key Management

### Storage

**NEVER** store API keys in code or version control.

```bash
# ❌ WRONG - In code
api_key = "sk_live_abc123"  # NEVER DO THIS

# ✅ CORRECT - Environment variable
import os
api_key = os.environ.get('EXCHANGE_API_KEY')
```

### .env File Security

```bash
# Add to .gitignore
echo ".env" >> .gitignore

# Set restrictive permissions
chmod 600 .env
```

### Exchange API Permissions

Configure minimal required permissions:

| Permission | Required | Reason |
|------------|----------|--------|
| Spot Trading | ✅ | Order execution |
| Read Balance | ✅ | Position tracking |
| Read Orders | ✅ | Order status |
| Withdrawals | ❌ | Never enable |
| Futures | ❌ | Unless specifically needed |

### API Key Rotation

```bash
# Schedule regular rotation (quarterly recommended)
# 1. Generate new key on exchange
# 2. Update .env
# 3. Restart application
# 4. Delete old key on exchange
# 5. Verify functionality
```

---

## Environment Variables

### Required Secrets

```bash
# Exchange credentials
EXCHANGE_API_KEY=
EXCHANGE_SECRET_KEY=

# AI service (if using)
GROQ_API_KEY=

# Database password (PostgreSQL)
TRADING_DATABASE__PASSWORD=

# API authentication
TRADING_API__API_KEY=

# Master encryption key
TRADING_MASTER_KEY=
```

### Loading Environment Variables

```python
# Using python-dotenv
from dotenv import load_dotenv
load_dotenv()  # Loads from .env file

# Access securely
import os
api_key = os.environ.get('EXCHANGE_API_KEY')
if not api_key:
    raise ValueError("EXCHANGE_API_KEY not set")
```

---

## Secret Rotation

### Automated Rotation Script

```bash
#!/bin/bash
# rotate_secrets.sh

# Generate new master key
NEW_KEY=$(openssl rand -hex 32)

# Update environment
sed -i "s/TRADING_MASTER_KEY=.*/TRADING_MASTER_KEY=$NEW_KEY/" .env

# Restart services
systemctl restart trading-agent

# Log rotation (without logging the key!)
logger "Secret rotation completed"
```

### Rotation Schedule

| Secret | Frequency | Method |
|--------|-----------|--------|
| API Keys | Quarterly | Manual |
| Database Password | Monthly | Automated |
| Master Key | Annually | Manual |
| API Tokens | Weekly | Automated |

---

## Access Control

### API Authentication

```python
# From app.py
from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import APIKeyHeader

api_key_header = APIKeyHeader(name="X-API-Key")

async def verify_api_key(api_key: str = Depends(api_key_header)):
    """Verify API key for authenticated endpoints."""
    
    expected_key = os.environ.get('TRADING_API__API_KEY')
    if not expected_key or api_key != expected_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    return api_key

@app.get("/admin")
async def admin_endpoint(key: str = Depends(verify_api_key)):
    """Protected endpoint requiring authentication."""
    return {"status": "authenticated"}
```

### Rate Limiting

```python
from slowapi import SlowAPI
from slowapi.util import get_remote_address

limiter = SlowAPI(key_func=get_remote_address)

@app.get("/status")
@limiter.limit("60/minute")
async def status(request):
    """Rate-limited endpoint."""
    return {"status": "ok"}
```

---

## Network Security

### Firewall Configuration

```bash
# Ubuntu UFW configuration
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Allow SSH (use non-standard port if possible)
sudo ufw allow 22/tcp

# Allow API port (restrict to specific IPs if possible)
sudo ufw allow from 10.0.0.0/8 to any port 8000

# Enable firewall
sudo ufw enable
```

### Security Groups (Cloud)

```yaml
# AWS Security Group example
SecurityGroup:
  GroupDescription: Trading Agent Security Group
  SecurityGroupIngress:
    - IpProtocol: tcp
      FromPort: 22
      ToPort: 22
      CidrIp: 10.0.0.0/8  # Restrict SSH
    - IpProtocol: tcp
      FromPort: 8000
      ToPort: 8000
      CidrIp: 10.0.0.0/8  # Restrict API
  SecurityGroupEgress:
    - IpProtocol: -1
      CidrIp: 0.0.0.0/0  # Allow outbound
```

---

## Data Encryption

### Encryption at Rest

```python
# Encrypt sensitive data before storage
from cryptography.fernet import Fernet

class SecretManager:
    def __init__(self, key: bytes):
        self.cipher = Fernet(key)
    
    def encrypt(self, plaintext: str) -> bytes:
        """Encrypt a secret."""
        return self.cipher.encrypt(plaintext.encode())
    
    def decrypt(self, ciphertext: bytes) -> str:
        """Decrypt a secret."""
        return self.cipher.decrypt(ciphertext).decode()
```

### Key Generation

```bash
# Generate secure random key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Store securely (e.g., AWS Secrets Manager, HashiCorp Vault)
```

---

## Audit Logging

### What to Log

✅ **DO Log**:
- API requests (endpoint, timestamp, IP)
- Authentication attempts
- Trading actions (order created, cancelled)
- Risk events (limit breach, circuit breaker)
- System events (startup, shutdown)

❌ **DON'T Log**:
- API keys or secrets
- Full request bodies with sensitive data
- Passwords or tokens

### Implementation

```python
# Structured audit logging
import logging
import json

audit_logger = logging.getLogger('audit')
audit_logger.setLevel(logging.INFO)

def log_audit_event(event_type: str, details: dict, user: str = 'system'):
    """Log an audit event."""
    
    entry = {
        'timestamp': datetime.now().isoformat(),
        'event_type': event_type,
        'user': user,
        'details': details,
    }
    
    audit_logger.info(json.dumps(entry))

# Usage
log_audit_event('ORDER_CREATED', {
    'order_id': '12345',
    'symbol': 'BTC/USDT',
    'side': 'buy',
    'amount': 0.1
})
```

---

## Security Testing

### Dependency Scanning

```bash
# Install security tools
pip install pip-audit safety bandit

# Scan dependencies
pip-audit
safety check

# Scan code for vulnerabilities
bandit -r .
```

### Regular Security Audits

```bash
#!/bin/bash
# security_audit.sh

echo "=== Dependency Check ==="
pip-audit --format=json > audit_deps.json

echo "=== Code Analysis ==="
bandit -r . --format=json > audit_code.json

echo "=== Secret Detection ==="
# Check for accidentally committed secrets
git grep -E '(api_key|secret|password)\s*=\s*["\x27][^"\x27]+["\x27]' || true

echo "=== File Permissions ==="
find . -name "*.env" -o -name "*.key" | xargs ls -la

echo "Audit complete. Review reports."
```

---

## Vulnerability Reporting

### Process

1. **Discovery**: Identify potential vulnerability
2. **Documentation**: Record details securely
3. **Assessment**: Evaluate severity and impact
4. **Remediation**: Fix vulnerability
5. **Verification**: Confirm fix is effective
6. **Disclosure**: Report to affected parties (if applicable)

### Contact

For security issues:
- Email: security@example.com (configure appropriately)
- Do NOT create public GitHub issues for security vulnerabilities

---

## Incident Response

### Preparation

```bash
# Emergency contacts
EMERGENCY_CONTACTS = {
    'security_lead': '+1-xxx-xxx-xxxx',
    'ops_lead': '+1-xxx-xxx-xxxx',
    'exchange_support': 'support@exchange.com'
}

# Kill switch access
# Ensure kill switch can be activated immediately
```

### Response Steps

1. **Contain**: Activate kill switch if needed
2. **Assess**: Determine scope of incident
3. **Mitigate**: Stop ongoing damage
4. **Recover**: Restore normal operations
5. **Review**: Post-mortem analysis
6. **Improve**: Update security measures

### Kill Switch

```python
# Immediate trading halt
from execution.kill_switch import KillSwitch

kill_switch = KillSwitch()
kill_switch.activate(reason="SECURITY_INCIDENT")

# This will:
# - Cancel all open orders
# - Prevent new orders
# - Alert administrators
# - Log the action
```

---

## Best Practices

### Do's

✅ Use environment variables for all secrets
✅ Implement least-privilege access
✅ Enable two-factor authentication on exchanges
✅ Regular security audits and updates
✅ Monitor logs for suspicious activity
✅ Keep dependencies updated
✅ Use HTTPS for all external communications
✅ Backup configurations securely

### Don'ts

❌ Hardcode API keys or secrets
❌ Commit .env files to version control
❌ Share API keys via email/chat
❌ Use same API key across environments
❌ Enable unnecessary API permissions
❌ Ignore security warnings
❌ Run as root user
❌ Expose debug endpoints in production

---

## Checklist

### Pre-Deployment Security Review

- [ ] All secrets in environment variables
- [ ] .env file in .gitignore
- [ ] API keys have minimal permissions
- [ ] Firewall configured correctly
- [ ] Rate limiting enabled
- [ ] Audit logging configured
- [ ] Dependencies scanned for vulnerabilities
- [ ] Kill switch tested
- [ ] Backup procedures verified
- [ ] Emergency contacts documented

### Ongoing Security Maintenance

- [ ] Weekly dependency updates
- [ ] Monthly security scans
- [ ] Quarterly API key rotation
- [ ] Annual security audit
- [ ] Regular backup testing
- [ ] Log review for anomalies

---

## Version Information

- **Document Version**: 1.0
- **Last Updated**: 2024
- **Phase**: 35 (Documentation)

---

*This document reflects the actual implementation as of Phase 35.*
