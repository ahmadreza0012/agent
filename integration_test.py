"""
OFFLINE INTEGRATION TEST (not part of the delivered project)
---------------------------------------------------------------
Runs the real CryptoPortfolioSystem end-to-end, with ONLY the network-
dependent DataFetcher.fetch_all_symbols call replaced by synthetic OHLCV
data (same shape/format real Binance data would have). Everything else --
ai_sentiment, portfolio_optimizer, strategy_selector, backtester, main --
is the actual unmodified project code. This exists purely to catch wiring
bugs (like the symbol-naming mismatch found and fixed) before you run the
real thing with network access.
"""
import numpy as np
import pandas as pd
import sys

sys.path.insert(0, '/home/claude/agent_project')

from main import CryptoPortfolioSystem
import data_fetcher as data_fetcher_module


def make_synthetic_ohlcv(symbol: str, n_hours: int = 4000, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.date_range('2024-01-01', periods=n_hours, freq='h')
    rets = rng.normal(0.0001, 0.01, n_hours)
    close = 100 * np.exp(np.cumsum(rets))
    df = pd.DataFrame({
        'Open': close * (1 - 0.001), 'High': close * 1.002, 'Low': close * 0.998,
        'Close': close, 'Volume': rng.uniform(100, 1000, n_hours),
    }, index=dates)
    return df


class FakeDataFetcher(data_fetcher_module.DataFetcher):
    """Same interface as the real DataFetcher, but fetch_all_symbols returns
    synthetic data instead of calling ccxt/Binance (no network needed)."""

    def fetch_all_symbols(self, timeframe='1h', since_days=365):
        return {sym: make_synthetic_ohlcv(sym, n_hours=since_days * 24, seed=hash(sym) % 1000)
                for sym in self.symbols}


def main():
    system = CryptoPortfolioSystem(
        symbols=['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT'],
        initial_capital=100000,
    )
    # swap in the network-free fetcher, everything else is untouched
    system.data_fetcher = FakeDataFetcher(system.symbols)

    print(">>> Running full pipeline with SYNTHETIC data (integration test only)")
    print(">>> AI sentiment mode:", "MOCK" if system.sentiment_analyzer.use_mock else "REAL")

    results = system.run_full_pipeline(since_days=180, n_folds=3, use_auto_selection=True)

    from main import print_final_summary
    print_final_summary(results['evaluation'])

    # sanity checks
    wf = results['walk_forward']
    assert len(wf['folds']) > 0, "No folds ran!"
    for f in wf['folds']:
        assert len(f['strategy_log']) > 0, "No strategy selections logged!"
    print("\n>>> INTEGRATION TEST PASSED: full pipeline wiring works end-to-end.")
    print(">>> (Numbers above are from SYNTHETIC random-walk data, meaningless")
    print(">>>  for real trading -- only useful to confirm nothing crashes/misfires.)")


if __name__ == "__main__":
    main()
