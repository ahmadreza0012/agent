#!/bin/bash
# Script to analyze trading logs and suggest improvements
# Usage: ./analyze_logs.sh

echo "============================================"
echo "Trading Bot Log Analyzer"
echo "============================================"
echo ""

# Check if performance_metrics.json exists
if [ -f "performance_metrics.json" ]; then
    echo "✅ Found performance_metrics.json"
    echo ""
    echo "=== Performance Summary ==="
    python3 -c "
import json
with open('performance_metrics.json', 'r') as f:
    data = json.load(f)
    
print(f\"Total Cycles: {data.get('total_cycles', 0)}\")
print(f\"Total Errors: {data.get('total_errors', 0)}\")
print(f\"Last Updated: {data.get('last_updated', 'N/A')}\")
print()

history = data.get('history', [])
if history:
    returns = [h.get('mean_monthly_return', 0) for h in history]
    drawdowns = [h.get('worst_max_drawdown', 0) for h in history]
    sharpes = [h.get('mean_sharpe', 0) for h in history]
    
    print('=== Performance Metrics ===')
    print(f'Average Monthly Return: {sum(returns)/len(returns)*100:.2f}%')
    print(f'Best Monthly Return: {max(returns)*100:.2f}%')
    print(f'Worst Monthly Return: {min(returns)*100:.2f}%')
    print()
    print(f'Average Max Drawdown: {sum(drawdowns)/len(drawdowns)*100:.2f}%')
    print(f'Worst Drawdown: {min(drawdowns)*100:.2f}%')
    print()
    print(f'Average Sharpe Ratio: {sum(sharpes)/len(sharpes):.2f}')
    print(f'Best Sharpe Ratio: {max(sharpes):.2f}')
    print()
    
    # Check if targets are being met
    target_return = 0.03
    max_dd = 0.15
    min_sharpe = 0.5
    
    profitable = sum(1 for r in returns if r >= target_return)
    safe_dd = sum(1 for d in drawdowns if abs(d) <= max_dd)
    good_sharpe = sum(1 for s in sharpes if s >= min_sharpe)
    
    print('=== Target Analysis ===')
    print(f'Cycles meeting return target (>{target_return*100}%): {profitable}/{len(returns)}')
    print(f'Cycles with safe DD (<{max_dd*100}%): {safe_dd}/{len(returns)}')
    print(f'Cycles with good Sharpe (>{min_sharpe}): {good_sharpe}/{len(returns)}')
    print()
    
    if profitable == len(returns) and safe_dd == len(returns) and good_sharpe == len(returns):
        print('✅ ALL TARGETS MET - Bot is profitable!')
    else:
        print('⚠️  Targets not consistently met - Improvements needed')
        if profitable < len(returns):
            print('   → Need to improve returns')
        if safe_dd < len(returns):
            print('   → Need to reduce drawdowns')
        if good_sharpe < len(returns):
            print('   → Need to improve risk-adjusted returns')
else:
    print('No performance history yet. Run some trading cycles first.')
"
    echo ""
    
    # Show recent errors
    echo "=== Recent Errors ==="
    python3 -c "
import json
with open('performance_metrics.json', 'r') as f:
    data = json.load(f)
    
errors = data.get('errors', [])
if errors:
    for err in errors[-5:]:  # Last 5 errors
        print(f\"[{err.get('timestamp', 'N/A')}] {err.get('error_type', 'N/A')}: {err.get('error_message', 'N/A')}\")
else:
    print('No errors recorded.')
"
    echo ""
    
    # Show recent cycles
    echo "=== Recent Trading Cycles ==="
    python3 -c "
import json
with open('performance_metrics.json', 'r') as f:
    data = json.load(f)
    
cycles = data.get('cycles', [])
if cycles:
    for cycle in cycles[-5:]:  # Last 5 cycles
        results = cycle.get('results', {})
        decision = results.get('decision', 'N/A')
        backtest = results.get('backtest_results', {})
        ret = backtest.get('mean_monthly_return', 0) * 100
        dd = backtest.get('worst_max_drawdown', 0) * 100
        sharpe = backtest.get('mean_sharpe', 0)
        print(f\"Cycle {cycle.get('cycle_number', '?')}: {decision}\")
        print(f\"  Return: {ret:.2f}%, DD: {dd:.2f}%, Sharpe: {sharpe:.2f}\")
else:
    print('No cycles recorded yet.')
"
else
    echo "❌ performance_metrics.json not found."
    echo "Run the bot first to generate trading data."
fi

echo ""
echo "============================================"
echo "To view detailed logs, check:"
echo "  - trading_log.jsonl (structured events)"
echo "  - detailed_trading.log (full log output)"
echo "============================================"
