# 🤖 Self-Improving Trading Bot - Automatic Log Analysis System

## Overview
This system automatically records all trading events, errors, and performance metrics to enable **automatic analysis and improvement** without manual log submission.

## How It Works

### 1. Automatic Logging (`auto_logger.py`)
Every trading cycle is automatically logged with:
- ✅ Cycle start/end timestamps
- ✅ Performance metrics (returns, drawdown, Sharpe ratio)
- ✅ Trading decisions and reasoning
- ✅ Errors and exceptions
- ✅ Strategy performance data

### 2. Data Files Generated
After each run on Railway, these files are created/updated:

| File | Description |
|------|-------------|
| `performance_metrics.json` | Aggregated performance data and statistics |
| `trading_log.jsonl` | Structured event log (JSON Lines format) |
| `detailed_trading.log` | Full detailed log with timestamps |

### 3. How to Request Analysis

**You don't need to send logs manually!** Just tell me:

> "بررسی کن" or "Check the logs" or "Analyze performance"

I will automatically:
1. Read `performance_metrics.json` to see historical performance
2. Analyze `trading_log.jsonl` for recent events
3. Check `detailed_trading.log` for errors
4. Identify patterns causing losses or suboptimal performance
5. Suggest and implement code improvements
6. Update optimization parameters

### 4. Analysis Script
Run locally to quickly check performance:
```bash
./analyze_logs.sh
```

Or after deploying to Railway, just ask me to analyze the logs.

## Performance Targets

The bot aims to achieve:
- **Monthly Return**: ≥ 3%
- **Max Drawdown**: ≤ 15%
- **Sharpe Ratio**: ≥ 0.5
- **Positive Months**: ≥ 50%

## Continuous Improvement Loop

```
┌─────────────────┐
│  Run on Railway │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Auto-Log Events │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ You Ask to      │
│ Analyze         │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ I Analyze Logs  │
│ & Find Issues   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Apply Code      │
│ Improvements    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Deploy Updated  │
│ Version         │
└─────────────────┘
```

## Next Steps

1. **Deploy** the updated code to Railway (it includes auto-logging)
2. **Wait** for at least one trading cycle to complete
3. **Ask me**: "لاگ‌ها را بررسی کن" (Check the logs)
4. **I'll analyze** and suggest improvements automatically
5. **Repeat** until targets are consistently met

## Files Modified

- ✅ `auto_logger.py` - New automatic logging module
- ✅ `main.py` - Integrated auto-logger into trading cycle
- ✅ `analyze_logs.sh` - Local analysis script
- ✅ `SELF_IMPROVING_AGENT_README.md` - This documentation

## Example Commands

After running on Railway:
- "لاگ‌ها را بررسی کن" - Analyze trading logs
- "عملکرد ربات چطور است؟" - How is the bot performing?
- "چرا به سوددهی نرسیدیم؟" - Why haven't we reached profitability?
- "چه تغییراتی نیاز است؟" - What changes are needed?

The system will automatically have all the data needed to answer these questions!
