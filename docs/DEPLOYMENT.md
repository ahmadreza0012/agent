# Deployment Guide

## System Requirements

### Minimum Requirements

| Component | Requirement |
|-----------|-------------|
| CPU | 2 cores |
| RAM | 4 GB |
| Storage | 10 GB SSD |
| Network | Stable internet connection |

### Recommended Requirements

| Component | Requirement |
|-----------|-------------|
| CPU | 4+ cores |
| RAM | 8+ GB |
| Storage | 50 GB SSD |
| Network | Low-latency connection |

---

## Environment Setup

### Python Version

```bash
# Check Python version
python --version  # Must be 3.10+

# Install if needed
# Ubuntu/Debian
sudo apt-get install python3.10 python3.10-venv

# macOS
brew install python@3.10
```

### Dependencies

```bash
# Clone repository
git clone https://github.com/ahmadreza0012/agent
cd agent

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
```

---

## Configuration

### Environment Variables

```bash
# Copy example configuration
cp .env.example .env

# Edit with your settings
nano .env
```

### Required Settings

```bash
# Trading mode
TRADING_MODE=paper  # Start with paper trading

# Exchange credentials (for shadow/live modes)
TRADING_EXCHANGE__NAME=binance
TRADING_EXCHANGE__SANDBOX=true
TRADING_EXCHANGE__API_KEY=your_api_key
TRADING_EXCHANGE__API_SECRET=your_secret

# Database
TRADING_DATABASE__TYPE=sqlite
TRADING_DATABASE__PATH=data/trading.db

# API settings
TRADING_API__HOST=0.0.0.0
TRADING_API__PORT=8000
```

### Optional Settings

```bash
# Logging
TRADING_LOG_LEVEL=INFO

# Safety limits
TRADING_LIMITS__MAX_DAILY_LOSS=0.05
TRADING_LIMITS__MAX_TOTAL_DRAWDOWN=0.15

# ML settings
TRADING_ML__ENABLED=true
TRADING_ML__RETRAIN_INTERVAL_HOURS=24
```

---

## Docker Deployment

### Dockerfile

```dockerfile
FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create data directory
RUN mkdir -p data logs models

# Expose API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/status || exit 1

# Run application
CMD ["python", "main.py", "--mode", "paper"]
```

### Docker Compose

```yaml
version: '3.8'

services:
  trading-agent:
    build: .
    container_name: crypto-trading-agent
    restart: unless-stopped
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
      - ./models:/app/models
    env_file:
      - .env
    environment:
      - TRADING_ENV=production
    
  postgres:
    image: postgres:15-alpine
    container_name: trading-db
    restart: unless-stopped
    volumes:
      - postgres_data:/var/lib/postgresql/data
    environment:
      - POSTGRES_DB=trading
      - POSTGRES_USER=trading
      - POSTGRES_PASSWORD=${DB_PASSWORD:-secure_password}
    ports:
      - "5432:5432"

volumes:
  postgres_data:
```

### Running with Docker

```bash
# Build image
docker-compose build

# Start services
docker-compose up -d

# View logs
docker-compose logs -f trading-agent

# Stop services
docker-compose down
```

---

## Cloud Deployment

### Railway

1. **Connect Repository**
   ```bash
   # Push to GitHub
   git push origin main
   ```

2. **Configure Railway**
   - Connect GitHub repository
   - Set environment variables
   - Deploy

3. **Railway Configuration**
   ```json
   {
     "$schema": "https://railway.app/railway.schema.json",
     "build": {
       "builder": "DOCKERFILE"
     },
     "deploy": {
       "startCommand": "python main.py --mode paper",
       "restartPolicyType": "ON_FAILURE",
       "restartPolicyMaxRetries": 10
     }
   }
   ```

### AWS

#### EC2 Deployment

```bash
# Launch EC2 instance
# - AMI: Ubuntu 22.04
# - Type: t3.medium
# - Storage: 50 GB

# SSH into instance
ssh -i key.pem ubuntu@<instance-ip>

# Install dependencies
sudo apt update
sudo apt install -y python3.10 python3-pip git

# Clone repository
git clone <repository-url>
cd agent

# Setup and run
./setup.sh
python main.py --mode live
```

#### ECS Deployment

```yaml
# task-definition.json
{
  "family": "trading-agent",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "1024",
  "memory": "2048",
  "containerDefinitions": [
    {
      "name": "trading-agent",
      "image": "<ecr-repo>/trading-agent:latest",
      "portMappings": [{"containerPort": 8000}],
      "environment": [
        {"name": "TRADING_MODE", "value": "live"}
      ],
      "secrets": [
        {"name": "EXCHANGE_API_KEY", "valueFrom": "arn:aws:secretsmanager:..."}
      ]
    }
  ]
}
```

---

## Database Setup

### SQLite (Development)

```bash
# Already configured by default
TRADING_DATABASE__TYPE=sqlite
TRADING_DATABASE__PATH=data/trading.db

# Initialize database
python scripts/init_db.py
```

### PostgreSQL (Production)

```bash
# Install PostgreSQL
sudo apt install postgresql postgresql-contrib

# Create database and user
sudo -u postgres psql
CREATE DATABASE trading;
CREATE USER trading WITH PASSWORD 'secure_password';
GRANT ALL PRIVILEGES ON DATABASE trading TO trading;
\q

# Update configuration
TRADING_DATABASE__TYPE=postgresql
TRADING_DATABASE__HOST=localhost
TRADING_DATABASE__PORT=5432
TRADING_DATABASE__DATABASE=trading
TRADING_DATABASE__USER=trading
TRADING_DATABASE__PASSWORD=secure_password
```

---

## Monitoring Setup

### Health Checks

```python
# API health endpoint
GET /status

# Response
{
  "status": "healthy",
  "mode": "paper",
  "last_cycle": "2024-01-15T10:30:00Z",
  "cycles_run": 1542
}
```

### Metrics Endpoint

```python
# Metrics endpoint
GET /metrics

# Response includes:
# - Portfolio value
# - P&L
# - Position sizes
# - Risk metrics
```

### Log Aggregation

```bash
# Configure log rotation
sudo nano /etc/logrotate.d/trading-agent

# Content
/var/log/trading-agent/*.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    create 0640 ubuntu ubuntu
}
```

---

## Maintenance Procedures

### Daily Checks

```bash
# 1. Check system status
curl http://localhost:8000/status

# 2. Review logs for errors
grep ERROR logs/*.log | tail -20

# 3. Verify positions
curl http://localhost:8000/positions

# 4. Check database size
du -sh data/
```

### Weekly Maintenance

```bash
# 1. Clear old cache
find .cache -type f -mtime +7 -delete

# 2. Rotate logs
logrotate -f /etc/logrotate.d/trading-agent

# 3. Backup database
cp data/trading.db data/trading.db.backup.$(date +%Y%m%d)

# 4. Update dependencies
pip list --outdated
```

### Monthly Tasks

```bash
# 1. Full system backup
tar -czf backup_$(date +%Y%m).tar.gz data/ models/

# 2. Performance review
python scripts/performance_report.py --month $(date +%m)

# 3. Security audit
pip-audit
safety check
```

---

## Troubleshooting

### Application Won't Start

```bash
# Check Python version
python --version  # Must be 3.10+

# Check dependencies
pip install -r requirements.txt

# Check environment
cat .env | grep -v "^#" | grep -v "="  # Find empty values

# Check logs
tail -100 logs/*.log
```

### Database Errors

```bash
# SQLite: Check file permissions
ls -la data/trading.db
chmod 644 data/trading.db

# PostgreSQL: Check connection
psql -h localhost -U trading -d trading

# Reinitialize if needed
rm data/trading.db
python scripts/init_db.py
```

### API Not Responding

```bash
# Check if process is running
ps aux | grep python

# Check port binding
netstat -tlnp | grep 8000

# Restart application
pkill -f "python main.py"
python main.py --mode paper &
```

### High Memory Usage

```bash
# Monitor memory
watch -n 1 'ps aux | grep python | awk "{print $2, $4}"'

# Reduce data history
# In config, reduce lookback periods

# Clear cache
rm -rf .cache/*
```

---

## Performance Tuning

### Database Optimization

```sql
-- Add indexes for common queries
CREATE INDEX IF NOT EXISTS idx_price_symbol_time 
ON price_data(symbol, timestamp);

CREATE INDEX IF NOT EXISTS idx_orders_status 
ON orders(status);

-- Vacuum database regularly
VACUUM;
ANALYZE;
```

### Application Tuning

```python
# In config.py
# Adjust these based on your hardware

# Reduce ML frequency
ML_RETRAIN_INTERVAL_HOURS = 24  # Once per day

# Limit data history
MAX_HISTORY_DAYS = 365  # Keep 1 year

# Batch operations
BATCH_SIZE = 100  # Process in batches
```

### Network Optimization

```bash
# Use persistent connections
# Already implemented via requests.Session

# Enable TCP keepalive
# Handled by ccxt library

# Reduce API calls through caching
DATA_CACHE_ENABLED=true
CACHE_TTL_HOURS=24
```

---

## Disaster Recovery

### Backup Strategy

```bash
#!/bin/bash
# backup.sh

BACKUP_DIR="/backups/trading/$(date +%Y%m%d)"
mkdir -p $BACKUP_DIR

# Backup database
cp data/trading.db $BACKUP_DIR/

# Backup models
cp -r models/ $BACKUP_DIR/

# Backup configuration
cp .env $BACKUP_DIR/

# Backup to remote location
rsync -av $BACKUP_DIR user@backup-server:/backups/

# Keep only last 30 days
find /backups/trading -type d -mtime +30 -delete
```

### Recovery Procedure

```bash
# 1. Stop application
pkill -f "python main.py"

# 2. Restore from backup
cp /backups/trading/20240115/trading.db data/
cp -r /backups/trading/20240115/models/ ./

# 3. Verify integrity
python scripts/verify_backup.py

# 4. Restart application
python main.py --mode paper &
```

---

## Version Information

- **Document Version**: 1.0
- **Last Updated**: 2024
- **Phase**: 35 (Documentation)

---

*This document reflects the actual implementation as of Phase 35.*
