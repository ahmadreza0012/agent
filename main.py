"""
Main Orchestrator (v3) - Crypto Portfolio Optimization System with FastAPI Server
================================================================
This version runs as a persistent web server on Railway to avoid 502 errors.
It performs trading cycles in the background while keeping the HTTP server alive.
"""

import os
import sys
import time
import logging
import threading
from datetime import datetime, timedelta
import numpy as np
from fastapi import FastAPI
import uvicorn

# Import your existing modules
from data_fetcher import DataFetcher
from ai_sentiment import AISentimentAnalyzer as AISentiment
from backtester import Backtester
from portfolio_optimizer import PortfolioOptimizer
from strategy_selector import StrategySelector

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="Crypto Portfolio System")

# Global state
system_state = {
    "status": "initializing",
    "last_cycle": None,
    "last_result": None,
    "cycles_run": 0
}

@app.get("/")
def read_root():
    return {
        "status": system_state["status"],
        "message": "Crypto Portfolio Optimization System is active",
        "cycles_run": system_state["cycles_run"],
        "last_cycle": system_state["last_cycle"]
    }

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "uptime": "running"
    }

@app.get("/stats")
def get_stats():
    return system_state

def run_trading_cycle():
    """Main trading logic loop"""
    global system_state
    
    logger.info("="*60)
    logger.info(f"Starting trading cycle #{system_state['cycles_run'] + 1}")
    logger.info("="*60)
    
    try:
        system_state["status"] = "running_cycle"
        
        # Configuration
        symbols = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT']
        initial_capital = 100000
        since_days = 365
        n_folds = 1
        
        # Initialize Components
        data_fetcher = DataFetcher(symbols=symbols)
        ai_sentiment = AISentiment()
        strategy_selector = StrategySelector(candidate_methods=['mvo', 'risk_parity'])
        backtester = Backtester(initial_capital=initial_capital)

        logger.info("STEP 1: Fetching Historical Data")
        
        df_prices = data_fetcher.fetch_all_symbols(timeframe='1d', since_days=since_days)
        if not df_prices:
            logger.error("Failed to fetch data. Sleeping for 1 hour.")
            system_state["status"] = "error_no_data"
            time.sleep(3600)
            return
        
        # Align the data
        df_prices_aligned = data_fetcher.align_data(df_prices)
        df_prices = df_prices_aligned
        
        logger.info(f"Data fetched: {df_prices.index[0]} to {df_prices.index[-1]}, {len(df_prices)} obs")

        logger.info("STEP 2: Walk-forward backtest & Optimization")

        # Calculate returns for the optimizer
        returns = data_fetcher.calculate_returns(df_prices)
        
        # Initialize optimizer with correct parameters AFTER we have data
        n_assets = len(df_prices.columns)
        optimizer = PortfolioOptimizer(n_assets=n_assets, asset_names=list(df_prices.columns))
        
        # Create strategy functions dictionary for the backtester
        from strategy_selector import compute_in_sample_scores
        
        def mvo_strategy(prices, returns):
            return optimizer.mean_variance_optimization(np.array([0.1]*n_assets), returns.cov().values)
        
        def risk_parity_strategy(prices, returns):
            return optimizer.risk_parity(returns.cov().values)
        
        strategy_fns = {
            'mvo': mvo_strategy,
            'risk_parity': risk_parity_strategy
        }

        # Run Backtest & Optimization Logic
        results = backtester.run_walk_forward(
            prices=df_prices,
            n_folds=n_folds,
            strategy_selector=strategy_selector,
            strategy_fns=strategy_fns
        )

        # Analyze Results
        if results and 'evaluation' in results:
            eval_data = results['evaluation']
            mean_return = eval_data.get('mean_monthly_return', 0)
            max_dd = eval_data.get('worst_max_drawdown', 0)
            
            logger.info("="*60)
            logger.info("FINAL ASSESSMENT")
            logger.info("="*60)
            logger.info(f"Mean monthly return: {mean_return:.2%}")
            logger.info(f"Max Drawdown: {max_dd:.2%}")

            # Decision Logic
            target_return = 0.05  # 5%
            max_allowed_dd = 0.15  # 15%

            if mean_return >= target_return and max_dd <= max_allowed_dd:
                logger.info("✅ TARGETS MET! Executing trades (Simulation Mode)...")
                system_state["status"] = "targets_met"
                system_state["last_result"] = "SUCCESS - Targets achieved"
                # TODO: Add actual execution logic here
                
                # Sleep normal cycle time
                sleep_hours = 1
            else:
                logger.warning("❌ Targets NOT met. Skipping trade execution.")
                logger.warning(f"Required: >{target_return:.0%} return, <{max_allowed_dd:.0%} DD")
                system_state["status"] = "targets_not_met"
                system_state["last_result"] = f"FAILED - Return: {mean_return:.2%}, DD: {max_dd:.2%}"
                
                # Sleep longer if targets are not met to avoid rapid retries
                sleep_hours = 4
                logger.info(f"Sleeping for {sleep_hours} hours before next check...")
            
            # Update state
            system_state["cycles_run"] += 1
            system_state["last_cycle"] = datetime.now().isoformat()
            
            logger.info(f"Cycle complete. Sleeping for {sleep_hours} hours...")
            time.sleep(sleep_hours * 3600)
        else:
            logger.error("Backtest returned no results. Sleeping for 1 hour.")
            system_state["status"] = "error_no_results"
            time.sleep(3600)

    except Exception as e:
        logger.exception(f"Error in trading cycle: {e}")
        system_state["status"] = f"error: {str(e)}"
        system_state["last_result"] = f"ERROR: {str(e)}"
        logger.info("Sleeping for 30 minutes due to error...")
        time.sleep(1800)

def background_worker():
    """Continuous loop for trading logic"""
    # Initial delay to let server start
    time.sleep(5)
    
    while True:
        run_trading_cycle()

if __name__ == "__main__":
    # Start the trading loop in a separate thread
    trader_thread = threading.Thread(target=background_worker, daemon=True)
    trader_thread.start()
    
    # Start the FastAPI server in the main thread
    port = int(os.environ.get("PORT", 8000))
    logger.info(f"Starting FastAPI server on port {port}...")
    
    # Use uvicorn to run the server
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
