#!/bin/bash

# Real Environment Testing Script
# Tests the crypto trading agent against live Binance data

echo "╔════════════════════════════════════════════════════════════════════╗"
echo "║         REAL ENVIRONMENT TESTING - BINANCE LIVE DATA              ║"
echo "╚════════════════════════════════════════════════════════════════════╝"
echo ""
echo "Start Time: $(date '+%Y-%m-%d %H:%M:%S')"
echo "Testing System Against Live Market Data..."
echo ""

# Run the test
python test_live_environment.py

echo ""
echo "╔════════════════════════════════════════════════════════════════════╗"
echo "║                    TEST COMPLETED                                  ║"
echo "╚════════════════════════════════════════════════════════════════════╝"
echo ""
echo "End Time: $(date '+%Y-%m-%d %H:%M:%S')"
echo "Results saved to: test_live_environment.log"
