# Experimental Code - Not Connected to Main Pipeline

This folder contains experimental and research code that is **NOT** connected to the main trading pipeline.

## Contents

- `self_improving_agent.py` - RL-based self-improvement experiments
- `rl/` - Reinforcement learning agent prototypes
- `memory/` - Experience memory systems
- `strategies/regime_detection.py` - Old HMM-based regime detection (replaced by regime_engine.py)

## Status

**DO NOT USE IN PRODUCTION**

This code is archived for future research reference only. Any activation of these components requires:

1. Complete code audit for look-ahead bias
2. Unit tests with walk-forward purity verification
3. Out-of-sample testing on at least 2 different market regimes
4. Risk officer approval

## History

Moved to experimental in Phase 0 cleanup (2025). These components were deemed:
- Not production-ready
- Lacking proper OOS validation
- Potentially containing look-ahead bias
- Superseded by newer implementations

## Future Research Directions

If you want to reactivate any of these components:

1. Create a GitHub issue with justification
2. Assign to Senior Quant Researcher for audit
3. Implement fixes and tests
4. Run Phase 1-12 validation suite
5. Get Risk Officer sign-off

---

**Last Updated**: Phase 0 Cleanup
**Auditor**: Senior Quant Developer Team
