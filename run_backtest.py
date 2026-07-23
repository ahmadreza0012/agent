"""
Quick Backtest Runner - Test the Self-Improving Agent
Run this to see actual performance with real Binance data
"""
import numpy as np
import pandas as pd
from datetime import datetime

# Import components
from data.enhanced_data_fetcher import MultiExchangeDataFetcher
from portfolio_optimizer import PortfolioOptimizer
from backtester import Backtester
from strategies.regime_detection import MarketRegimeDetector, RegimeAdaptiveStrategy

def run_production_backtest():
    """Run a production-quality backtest with 1 year of data"""
    
    print("=" * 70)
    print("SELF-IMPROVING CRYPTO TRADING AGENT - BACKTEST")
    print(f"Time: {datetime.now().isoformat()}")
    print("=" * 70)
    
    # Configuration
    SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT']
    INITIAL_CAPITAL = 100000
    TIMEFRAME = '1h'
    SINCE_DAYS = 365  # 1 year
    
    # Fetch data
    print("\n📊 Fetching historical data from Binance...")
    fetcher = MultiExchangeDataFetcher(symbols=SYMBOLS, exchange='binance')
    data = fetcher.fetch_all_symbols(timeframe=TIMEFRAME, since_days=SINCE_DAYS, use_cache=True)
    prices = fetcher.align_data(data)
    returns = fetcher.calculate_returns(prices)
    
    print(f"   Data range: {prices.index.min()} to {prices.index.max()}")
    print(f"   Observations: {len(prices)}")
    print(f"   Assets: {list(prices.columns)}")
    
    # Detect regimes
    print("\n🔍 Detecting market regimes...")
    regime_detector = MarketRegimeDetector(n_regimes=4)
    regime_features = regime_detector.extract_features(prices, returns)
    regime_detector.fit(regime_features)
    regimes = regime_detector.predict(regime_features)
    
    regime_counts = regimes.value_counts()
    print(f"   Regime distribution:")
    for regime_id, count in regime_counts.items():
        regime_name = regime_detector.regime_names.get(regime_id, 'Unknown')
        print(f"      - {regime_name}: {count} periods ({count/len(regimes)*100:.1f}%)")
    
    # Initialize optimizer and backtester
    optimizer = PortfolioOptimizer(
        n_assets=len(SYMBOLS),
        asset_names=[s.replace('/USDT', '') for s in SYMBOLS]
    )
    backtester = Backtester(
        initial_capital=INITIAL_CAPITAL,
        transaction_cost=0.001,
        slippage=0.0005
    )
    
    # Define adaptive strategy
    regime_strategy = RegimeAdaptiveStrategy()
    
    def adaptive_weights(prices_df, returns_df):
        """Get weights based on current regime"""
        # Get recent regime (simplified - use last known regime)
        if len(regimes) > 0:
            current_regime = regimes.iloc[-1] if hasattr(regimes, 'iloc') else 2
        else:
            current_regime = 2
        
        # Select strategy based on regime
        strategy = regime_strategy.get_optimal_strategy(current_regime)
        
        n_assets = len(prices_df.columns)
        cov_matrix = returns_df.cov().values * 24 * 365
        
        if strategy == 'momentum':
            exp_ret = returns_df.mean().values * 24 * 365
            momentum = prices_df.pct_change(168).iloc[-1].values
            exp_ret *= (1 + momentum)
            weights = optimizer.mean_variance_optimization(exp_ret, cov_matrix, method='max_sharpe')
        elif strategy == 'mean_reversion':
            momentum = prices_df.pct_change(168).iloc[-1].values
            exp_ret = -momentum * 0.1
            weights = optimizer.mean_variance_optimization(exp_ret, cov_matrix, method='min_volatility')
        elif strategy == 'risk_parity':
            weights = optimizer.risk_parity(cov_matrix)
        elif strategy == 'cvar':
            weights = optimizer.cvar_optimization(returns_df.values, cvar_limit=0.05)
        else:
            weights = np.ones(n_assets) / n_assets
        
        return weights
    
    # Run backtest
    print("\n🚀 Running walk-forward backtest...")
    result = backtester.run(
        prices=prices,
        weights_strategy=adaptive_weights,
        rebalance_freq='W',
        lookback_hours=168,
        train_split=0.75
    )
    
    # Print results
    metrics = result['metrics']
    
    print("\n" + "=" * 70)
    print("BACKTEST RESULTS")
    print("=" * 70)
    
    print(f"\n💰 PERFORMANCE METRICS:")
    print(f"   Initial Capital:     ${INITIAL_CAPITAL:,.2f}")
    print(f"   Final Value:         ${metrics['final_value']:,.2f}")
    print(f"   Total Return:        {metrics['total_return']:.2%}")
    print(f"   Monthly Return:      {metrics['monthly_return']:.2%}")
    print(f"   Annualized Return:   {metrics['annualized_return']:.2%}")
    
    print(f"\n📈 RISK METRICS:")
    print(f"   Max Drawdown:        {metrics['max_drawdown']:.2%}")
    print(f"   Volatility:          {metrics['volatility']:.2%}")
    print(f"   Sharpe Ratio:        {metrics['sharpe_ratio']:.2f}")
    print(f"   VaR (95%):           {metrics['var_95']:.2%}")
    print(f"   CVaR (95%):          {metrics['cvar_95']:.2%}")
    
    print(f"\n💸 TRANSACTION COSTS:")
    print(f"   Total Costs:         ${metrics['total_transaction_costs']:,.2f}")
    print(f"   Number of Rebalances: {metrics['n_rebalances']}")
    print(f"   Average Turnover:    {metrics['avg_turnover']:.2%}")
    
    # Target assessment
    print("\n" + "=" * 70)
    print("TARGET ASSESSMENT")
    print("=" * 70)
    
    target_return = 0.05  # 5% monthly
    max_dd_limit = 0.15   # 15% max drawdown
    
    return_ok = metrics['monthly_return'] >= target_return
    dd_ok = abs(metrics['max_drawdown']) <= max_dd_limit
    
    print(f"\n🎯 Monthly Return Target ({target_return:.0%}):")
    print(f"   Required:  {target_return:.2%}")
    print(f"   Achieved:  {metrics['monthly_return']:.2%}")
    print(f"   Status:    {'✅ ACHIEVED' if return_ok else '❌ NOT ACHIEVED'}")
    
    print(f"\n🛡️  Max Drawdown Limit ({max_dd_limit:.0%}):")
    print(f"   Limit:     {max_dd_limit:.2%}")
    print(f"   Actual:    {abs(metrics['max_drawdown']):.2%}")
    print(f"   Status:    {'✅ ACHIEVED' if dd_ok else '❌ NOT ACHIEVED'}")
    
    # Verdict
    print("\n" + "=" * 70)
    if return_ok and dd_ok:
        print("🏆 VERDICT: SUCCESS - Both targets achieved!")
    elif return_ok:
        print("⚠️  VERDICT: PARTIAL - Return target met, but drawdown exceeded")
    elif dd_ok:
        print("⚠️  VERDICT: PARTIAL - Drawdown controlled, but return target not met")
    else:
        print("❌ VERDICT: FAILED - Neither target achieved")
    
    print("=" * 70)
    
    # Reality check note
    print("\n📝 IMPORTANT NOTES:")
    print("   - Past performance does not guarantee future results")
    print("   - Backtests assume perfect execution (no slippage beyond estimate)")
    print("   - Real trading involves additional risks (exchange risk, liquidity)")
    print("   - Always start with paper trading before live deployment")
    print("   - This is NOT financial advice")
    
    return result


if __name__ == "__main__":
    results = run_production_backtest()
