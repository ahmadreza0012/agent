"""
Advanced AI Test - Multi-Exchange, Sentiment-Aware ML Trading Strategy
=======================================================================
This script implements:
1. Data loading from Nobitex (BTC/IRT) and Binance (BTC/USDT)
2. Cross-exchange feature engineering
3. Mock sentiment generation (proxy for historical news)
4. XGBoost classifier training
5. Backtest evaluation using existing backtester

GOAL: Achieve 20% monthly profit (mathematically challenging with 0.35% round-trip costs)
"""

import pandas as pd
import numpy as np
import requests
import logging
import sys
from datetime import datetime, timedelta
from typing import Tuple, Optional

# Import backtester
sys.path.insert(0, '.')
from backtest.backtester import run_backtest, print_report

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def fetch_binance_data(symbol: str = 'BTCUSDT', interval: str = '1h', 
                       start_date: str = '2025-07-01', end_date: str = '2026-07-17') -> pd.DataFrame:
    """
    Fetch historical BTC/USDT data from Binance public API in chunks.
    
    Binance API returns max 1000 candles per request, so we fetch in chunks.
    
    Args:
        symbol: Trading pair symbol
        interval: Candlestick interval (1h, 4h, 1d, etc.)
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
    
    Returns:
        DataFrame with columns: timestamp, open, high, low, close, volume
    """
    logger.info(f"Fetching Binance data for {symbol} from {start_date} to {end_date}")
    
    base_url = "https://api.binance.com/api/v3/klines"
    
    # Parse dates
    start_dt = datetime.strptime(start_date, '%Y-%m-%d')
    end_dt = datetime.strptime(end_date, '%Y-%m-%d')
    
    all_candles = []
    current_start = start_dt
    
    while current_start < end_dt:
        # Convert to milliseconds timestamp
        start_ts = int(current_start.timestamp() * 1000)
        
        params = {
            'symbol': symbol,
            'interval': interval,
            'startTime': start_ts,
            'limit': 1000
        }
        
        try:
            response = requests.get(base_url, params=params, timeout=30)
            response.raise_for_status()
            
            candles = response.json()
            
            if not candles:
                logger.warning("No more data returned from Binance API")
                break
            
            all_candles.extend(candles)
            
            # Update start time for next chunk (last candle timestamp + 1 hour)
            last_candle_time = candles[-1][0]
            current_start = datetime.fromtimestamp(last_candle_time / 1000) + timedelta(hours=1)
            
            logger.info(f"Fetched {len(candles)} candles. Current progress: {current_start.date()}")
            
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {e}")
            break
    
    if not all_candles:
        logger.error("Failed to fetch any data from Binance")
        return pd.DataFrame()
    
    # Parse candles into DataFrame
    # Binance format: [open_time, open, high, low, close, volume, close_time, ...]
    df = pd.DataFrame(all_candles, columns=[
        'open_time', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_asset_volume', 'number_of_trades',
        'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
    ])
    
    # Convert timestamp to datetime
    df['timestamp'] = pd.to_datetime(df['open_time'], unit='ms')
    
    # Convert numeric columns
    numeric_cols = ['open', 'high', 'low', 'close', 'volume']
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    
    # Select and rename columns
    df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']].copy()
    
    # Filter by date range
    df = df[(df['timestamp'] >= start_dt) & (df['timestamp'] <= end_dt)]
    
    logger.info(f"Total Binance candles fetched: {len(df)}")
    logger.info(f"Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
    
    return df


def load_nobitex_data(filepath: str) -> pd.DataFrame:
    """Load Nobitex BTC/IRT data from CSV."""
    logger.info(f"Loading Nobitex data from {filepath}")
    
    df = pd.read_csv(filepath, parse_dates=['timestamp'])
    
    logger.info(f"Loaded {len(df)} rows. Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
    
    return df


def align_dataframes(nobitex_df: pd.DataFrame, binance_df: pd.DataFrame) -> pd.DataFrame:
    """
    Align Nobitex and Binance data by timestamp.
    
    Since both are hourly data, we merge on rounded timestamps.
    Forward-fill Binance data to match Nobitex timestamps.
    """
    logger.info("Aligning Nobitex and Binance data by timestamp...")
    
    # Ensure timestamps are datetime
    nobitex_df = nobitex_df.copy()
    binance_df = binance_df.copy()
    
    nobitex_df['timestamp'] = pd.to_datetime(nobitex_df['timestamp'])
    binance_df['timestamp'] = pd.to_datetime(binance_df['timestamp'])
    
    # Round timestamps to nearest hour for alignment
    nobitex_df['timestamp_aligned'] = nobitex_df['timestamp'].dt.floor('H')
    binance_df['timestamp_aligned'] = binance_df['timestamp'].dt.floor('H')
    
    # Merge on aligned timestamp
    merged = nobitex_df.merge(
        binance_df[['timestamp_aligned', 'open', 'high', 'low', 'close', 'volume']],
        on='timestamp_aligned',
        how='left',
        suffixes=('_irt', '_usdt')
    )
    
    # Forward fill missing Binance data
    usdt_cols = ['open_usdt', 'high_usdt', 'low_usdt', 'close_usdt', 'volume_usdt']
    merged[usdt_cols] = merged[usdt_cols].ffill()
    
    # Drop NaN rows (beginning where no Binance data exists)
    merged = merged.dropna(subset=['close_usdt']).reset_index(drop=True)
    
    logger.info(f"Aligned data has {len(merged)} rows")
    
    return merged


def compute_technical_features(df: pd.DataFrame, suffix: str = '') -> pd.DataFrame:
    """
    Compute technical indicators for a price series.
    
    Features:
    - RSI (14-period)
    - MACD (12, 26, 9)
    - Bollinger Bands (20, 2)
    - Volatility (rolling std)
    - Momentum (rate of change)
    - Moving averages (SMA 20, SMA 50)
    
    Args:
        df: DataFrame with OHLCV data
        suffix: Column suffix ('_irt' or '_usdt')
    """
    df = df.copy()
    
    close_col = f'close{suffix}' if suffix else 'close'
    high_col = f'high{suffix}' if suffix else 'high'
    low_col = f'low{suffix}' if suffix else 'low'
    open_col = f'open{suffix}' if suffix else 'open'
    
    prices = df[close_col].values
    
    # RSI (14-period)
    delta = np.diff(prices, prepend=prices[0])
    gain = np.where(delta > 0, delta, 0)
    loss = np.where(delta < 0, -delta, 0)
    
    avg_gain = pd.Series(gain).rolling(window=14).mean().values
    avg_loss = pd.Series(loss).rolling(window=14).mean().values
    
    rs = np.divide(avg_gain, avg_loss, out=np.zeros_like(avg_gain), where=avg_loss != 0)
    rsi = 100 - (100 / (1 + rs))
    df[f'rsi{suffix}'] = rsi
    
    # MACD (12, 26, 9)
    ema12 = pd.Series(prices).ewm(span=12, adjust=False).mean().values
    ema26 = pd.Series(prices).ewm(span=26, adjust=False).mean().values
    macd_line = ema12 - ema26
    signal_line = pd.Series(macd_line).ewm(span=9, adjust=False).mean().values
    macd_hist = macd_line - signal_line
    
    df[f'macd{suffix}'] = macd_line
    df[f'macd_signal{suffix}'] = signal_line
    df[f'macd_hist{suffix}'] = macd_hist
    
    # Bollinger Bands (20, 2)
    sma20 = pd.Series(prices).rolling(window=20).mean().values
    std20 = pd.Series(prices).rolling(window=20).std().values
    bb_upper = sma20 + 2 * std20
    bb_lower = sma20 - 2 * std20
    bb_width = (bb_upper - bb_lower) / sma20
    
    df[f'sma20{suffix}'] = sma20
    df[f'bb_width{suffix}'] = bb_width
    df[f'bb_position{suffix}'] = (prices - bb_lower) / (bb_upper - bb_lower)
    
    # Volatility (rolling std of returns)
    returns = np.diff(prices, prepend=prices[0]) / prices
    volatility = pd.Series(returns).rolling(window=20).std().values
    df[f'volatility{suffix}'] = volatility
    
    # Momentum (rate of change over 10 periods)
    momentum_10 = np.zeros_like(prices)
    for i in range(10, len(prices)):
        momentum_10[i] = (prices[i] - prices[i-10]) / prices[i-10]
    df[f'momentum{suffix}'] = momentum_10
    
    # SMA 50
    sma50 = pd.Series(prices).rolling(window=50).mean().values
    df[f'sma50{suffix}'] = sma50
    
    # Price relative to moving averages
    df[f'price_sma20_ratio{suffix}'] = prices / sma20
    df[f'price_sma50_ratio{suffix}'] = prices / sma50
    
    return df


def generate_cross_exchange_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Generate cross-exchange features that may act as leading indicators.
    
    Features:
    - Binance volatility领先 indicator
    - Binance momentum领先 indicator  
    - Price spread between exchanges
    - Volume ratio
    """
    df = df.copy()
    
    # Binance volatility (may lead Nobitex due to higher liquidity)
    df['binance_vol_leading'] = df['volatility_usdt'].shift(1)
    
    # Binance momentum领先
    df['binance_mom_leading'] = df['momentum_usdt'].shift(1)
    
    # Binance RSI领先
    df['binance_rsi_leading'] = df['rsi_usdt'].shift(1)
    
    # Price spread (Nobitex vs Binance, normalized)
    # This captures arbitrage opportunities and local demand
    df['price_spread'] = (df['close_irt'] - df['close_usdt'] * df['close_irt'].iloc[0] / df['close_usdt'].iloc[0]) / df['close_irt']
    
    # Volume ratio (relative trading activity)
    vol_irt_norm = df['volume_irt'] / df['volume_irt'].rolling(20).mean()
    vol_usdt_norm = df['volume_usdt'] / df['volume_usdt'].rolling(20).mean()
    df['volume_ratio'] = vol_irt_norm / vol_usdt_norm
    
    # Lagged Binance features (multiple lags for potential leading signals)
    for lag in [1, 2, 3]:
        df[f'binance_close_lag{lag}'] = df['close_usdt'].shift(lag)
        df[f'binance_return_lag{lag}'] = df['momentum_usdt'].shift(lag)
    
    return df


def generate_mock_sentiment(df: pd.DataFrame) -> pd.DataFrame:
    """
    Generate synthetic sentiment time series.
    
    MOCK IMPLEMENTATION: Since free APIs don't provide historical news archives,
    we generate sentiment based on price volatility and returns as a proxy.
    
    This is clearly marked as mock data for backtesting purposes only.
    """
    logger.info("=" * 60)
    logger.info("GENERATING MOCK SENTIMENT DATA")
    logger.info("NOTE: This is synthetic data based on price volatility.")
    logger.info("Real historical news requires paid API access (e.g., RavenPack, NewsAPI).")
    logger.info("=" * 60)
    
    df = df.copy()
    
    prices = df['close_irt'].values
    n = len(prices)
    
    # Calculate returns
    returns = np.diff(prices, prepend=prices[0]) / prices
    
    # Rolling statistics
    window = 20
    sentiment = np.zeros(n)
    
    for i in range(n):
        start_idx = max(0, i - window)
        window_returns = returns[start_idx:i+1]
        
        if len(window_returns) > 1:
            vol = np.std(window_returns)
            mean_ret = np.mean(window_returns)
            
            # Base sentiment from return direction
            base = np.tanh(mean_ret * 100)
            
            # Volatility amplifies sentiment (fear/greed)
            vol_factor = min(vol * 50, 0.5)
            
            if mean_ret > 0:
                sentiment[i] = base + vol_factor
            else:
                sentiment[i] = base - vol_factor
            
            sentiment[i] = np.clip(sentiment[i], -1, 1)
        else:
            sentiment[i] = 0.0
    
    df['sentiment'] = sentiment
    
    # Add lagged sentiment (news effect persists)
    df['sentiment_lag1'] = df['sentiment'].shift(1)
    df['sentiment_lag2'] = df['sentiment'].shift(2)
    
    # Sentiment change (momentum of sentiment)
    df['sentiment_change'] = df['sentiment'].diff()
    
    logger.info(f"Generated sentiment series. Range: [{sentiment.min():.3f}, {sentiment.max():.3f}]")
    
    return df


def prepare_features_and_target(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
    """
    Prepare feature matrix and target variable for ML training.
    
    Target: Next period direction (1 if price goes up, 0 if down)
    """
    df = df.copy()
    
    # Target: 1 if next close > current close, else 0
    df['target'] = (df['close_irt'].shift(-1) > df['close_irt']).astype(int)
    
    # Define feature columns
    feature_cols = [
        # Nobitex technical features
        'rsi_irt', 'macd_irt', 'macd_signal_irt', 'macd_hist_irt',
        'volatility_irt', 'momentum_irt', 'bb_width_irt', 'bb_position_irt',
        'price_sma20_ratio_irt', 'price_sma50_ratio_irt',
        
        # Binance technical features (cross-exchange)
        'rsi_usdt', 'macd_usdt', 'volatility_usdt', 'momentum_usdt',
        
        # Cross-exchange leading indicators
        'binance_vol_leading', 'binance_mom_leading', 'binance_rsi_leading',
        'price_spread', 'volume_ratio',
        'binance_return_lag1', 'binance_return_lag2', 'binance_return_lag3',
        
        # Sentiment features (mock)
        'sentiment', 'sentiment_lag1', 'sentiment_lag2', 'sentiment_change',
    ]
    
    # Drop rows with NaN values
    df_clean = df.dropna(subset=feature_cols + ['target']).reset_index(drop=True)
    
    X = df_clean[feature_cols]
    y = df_clean['target']
    
    logger.info(f"Feature matrix shape: {X.shape}")
    logger.info(f"Target distribution: {y.value_counts().to_dict()}")
    
    return df_clean, X, y


def train_xgboost(X_train: pd.DataFrame, y_train: pd.Series, 
                  X_test: pd.DataFrame, y_test: pd.Series) -> tuple:
    """
    Train XGBoost classifier and evaluate on test set.
    """
    try:
        import xgboost as xgb
    except ImportError:
        logger.error("xgboost not installed. Installing...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "xgboost"])
        import xgboost as xgb
    
    logger.info("Training XGBoost classifier...")
    
    # Create DMatrix for XGBoost
    dtrain = xgb.DMatrix(X_train, label=y_train)
    dtest = xgb.DMatrix(X_test, label=y_test)
    
    # Model parameters
    params = {
        'objective': 'binary:logistic',
        'eval_metric': 'logloss',
        'max_depth': 6,
        'learning_rate': 0.1,
        'n_estimators': 100,
        'subsample': 0.8,
        'colsample_bytree': 0.8,
        'seed': 42,
    }
    
    # Train model
    model = xgb.train(
        params,
        dtrain,
        num_boost_round=100,
        evals=[(dtrain, 'train'), (dtest, 'eval')],
        verbose_eval=10
    )
    
    # Predictions
    y_pred_proba = model.predict(dtest)
    y_pred = (y_pred_proba >= 0.5).astype(int)
    
    # Accuracy
    accuracy = (y_pred == y_test).mean()
    
    logger.info(f"\n{'='*60}")
    logger.info("XGBoost Training Complete")
    logger.info(f"Test Set Accuracy: {accuracy:.4f} ({accuracy*100:.2f}%)")
    logger.info(f"{'='*60}")
    
    return model, y_pred_proba, y_pred, accuracy


def convert_predictions_to_positions(y_pred_proba: np.ndarray, threshold: float = 0.55) -> np.ndarray:
    """
    Convert probability predictions to position signals.
    
    Position mapping for long-only strategy with explicit exit signals:
    - prob >= threshold → Long (1) - enter/hold position
    - prob < threshold → Exit (-1) - close position
    
    This creates alternating signals that trigger entries and exits.
    """
    positions = np.zeros(len(y_pred_proba))
    
    # Generate initial binary signal
    binary_signal = (y_pred_proba >= threshold).astype(int)
    
    # Convert to position changes: detect transitions
    # When signal goes from 0->1, emit 1 (buy)
    # When signal goes from 1->0, emit -1 (sell)
    for i in range(1, len(binary_signal)):
        if binary_signal[i] == 1 and binary_signal[i-1] == 0:
            positions[i] = 1  # Buy signal
        elif binary_signal[i] == 0 and binary_signal[i-1] == 1:
            positions[i] = -1  # Sell signal
        else:
            positions[i] = 0  # Hold
    
    logger.info(f"Position distribution (threshold={threshold}):")
    logger.info(f"  Buy (1): {(positions == 1).sum()}")
    logger.info(f"  Sell (-1): {(positions == -1).sum()}")
    logger.info(f"  Hold (0): {(positions == 0).sum()}")
    
    return positions


def run_ml_backtest(test_df: pd.DataFrame, positions: np.ndarray) -> dict:
    """
    Run backtest on test set using generated positions.
    """
    # Create a copy with positions
    backtest_df = test_df.copy().reset_index(drop=True)
    backtest_df['position'] = positions
    
    # Ensure we have required OHLCV columns with correct names
    backtest_df = backtest_df.rename(columns={
        'open_irt': 'open',
        'high_irt': 'high', 
        'low_irt': 'low',
        'close_irt': 'close',
        'volume_irt': 'volume'
    })
    
    logger.info("\n" + "=" * 60)
    logger.info("Running Backtest on Test Set")
    logger.info("=" * 60)
    
    # Run backtest with 0.25% commission + 0.1% slippage (as specified)
    results = run_backtest(
        backtest_df,
        initial_capital=10_000_000,  # 10M Tomans
        commission_pct=0.0025,  # 0.25%
        slippage_pct=0.001,     # 0.1%
        position_size_pct=1.0,
    )
    
    return results


def main():
    """Main execution pipeline."""
    print("=" * 70)
    print("ADVANCED AI TRADING TEST - Multi-Exchange, Sentiment-Aware")
    print("=" * 70)
    
    # Step 1: Load Nobitex data
    print("\n[Step 1] Loading Nobitex BTC/IRT data...")
    nobitex_df = load_nobitex_data('data/btcirt_1year.csv')
    
    # Step 2: Fetch Binance data
    print("\n[Step 2] Fetching Binance BTC/USDT data from API...")
    # Determine date range from Nobitex data
    start_date = nobitex_df['timestamp'].min().strftime('%Y-%m-%d')
    end_date = nobitex_df['timestamp'].max().strftime('%Y-%m-%d')
    
    binance_df = fetch_binance_data(
        symbol='BTCUSDT',
        interval='1h',
        start_date=start_date,
        end_date=end_date
    )
    
    if binance_df.empty:
        logger.error("Failed to fetch Binance data. Exiting.")
        return
    
    # Step 3: Align dataframes
    print("\n[Step 3] Aligning Nobitex and Binance data...")
    merged_df = align_dataframes(nobitex_df, binance_df)
    
    # Step 4: Compute technical features
    print("\n[Step 4] Computing technical features for both exchanges...")
    merged_df = compute_technical_features(merged_df, suffix='_irt')
    merged_df = compute_technical_features(merged_df, suffix='_usdt')
    
    # Step 5: Generate cross-exchange features
    print("\n[Step 5] Generating cross-exchange features...")
    merged_df = generate_cross_exchange_features(merged_df)
    
    # Step 6: Generate mock sentiment
    print("\n[Step 6] Generating mock sentiment series...")
    merged_df = generate_mock_sentiment(merged_df)
    
    # Step 7: Prepare features and target
    print("\n[Step 7] Preparing features and target variable...")
    df_clean, X, y = prepare_features_and_target(merged_df)
    
    # Step 8: Chronological train/test split (70/30)
    print("\n[Step 8] Splitting data chronologically (70% train, 30% test)...")
    split_idx = int(len(df_clean) * 0.7)
    
    train_df = df_clean.iloc[:split_idx].reset_index(drop=True)
    test_df = df_clean.iloc[split_idx:].reset_index(drop=True)
    
    X_train = X.iloc[:split_idx]
    y_train = y.iloc[:split_idx]
    X_test = X.iloc[split_idx:]
    y_test = y.iloc[split_idx:]
    
    logger.info(f"Train set: {len(train_df)} samples ({train_df['timestamp'].min()} to {train_df['timestamp'].max()})")
    logger.info(f"Test set: {len(test_df)} samples ({test_df['timestamp'].min()} to {test_df['timestamp'].max()})")
    
    # Step 9: Train XGBoost
    print("\n[Step 9] Training XGBoost classifier...")
    model, y_pred_proba, y_pred, ml_accuracy = train_xgboost(
        X_train, y_train, X_test, y_test
    )
    
    # Step 10: Convert predictions to positions (threshold=0.55)
    print("\n[Step 10] Converting predictions to position signals (threshold=0.55)...")
    positions = convert_predictions_to_positions(y_pred_proba, threshold=0.55)
    
    # Step 11: Run backtest
    print("\n[Step 11] Running backtest on test set...")
    results = run_ml_backtest(test_df, positions)
    
    # Print results
    print("\n" + "=" * 70)
    print("FINAL RESULTS")
    print("=" * 70)
    
    print(f"\nML Model Performance:")
    print(f"  Test Set Accuracy: {ml_accuracy:.4f} ({ml_accuracy*100:.2f}%)")
    
    if 'error' not in results:
        print(f"\nBacktest Metrics:")
        print_report(results)
        
        # Extract key metrics
        total_return = results.get('total_return_pct', 0)
        num_trades = results.get('num_trades', 0)
        win_rate = results.get('win_rate_pct', 0)
        max_drawdown = results.get('max_drawdown_pct', 0)
        
        print("\n" + "=" * 70)
        print("SUMMARY METRICS")
        print("=" * 70)
        print(f"  ML Accuracy:      {ml_accuracy*100:.2f}%")
        print(f"  Num Trades:       {num_trades}")
        print(f"  Total Return:     {total_return:+.2f}%")
        print(f"  Win Rate:         {win_rate:.1f}%")
        print(f"  Max Drawdown:     {max_drawdown:.2f}%")
        
        # Calculate monthly return estimate
        test_period_days = (test_df['timestamp'].max() - test_df['timestamp'].min()).days
        if test_period_days > 0:
            monthly_return = ((1 + total_return/100) ** (30/test_period_days) - 1) * 100
            print(f"  Est. Monthly Ret: {monthly_return:+.2f}%")
            
            print("\n" + "=" * 70)
            print("20% MONTHLY PROFIT MANDATE ASSESSMENT")
            print("=" * 70)
            
            if monthly_return >= 20:
                print(f"✓ ACHIEVED: {monthly_return:.2f}% monthly return exceeds 20% target")
            else:
                print(f"✗ NOT ACHIEVED: {monthly_return:.2f}% monthly return is below 20% target")
                print(f"\nMATHEMATICAL REALITY:")
                print(f"  With 0.35% round-trip transaction costs (0.25% commission + 0.1% slippage),")
                print(f"  each trade needs >0.35% price movement just to break even.")
                print(f"  ML accuracy of {ml_accuracy*100:.2f}% with win rate of {win_rate:.1f}%")
                print(f"  produces {total_return:.2f}% total return over {test_period_days} days.")
                print(f"  Sustaining 20% monthly ({(1.2**12-1)*100:.0f}% annually) is mathematically unsustainable")
                print(f"  for most market conditions without excessive risk or leverage.")
    else:
        print(f"\nBacktest Error: {results.get('error')}")
    
    print("\n" + "=" * 70)
    print("END OF ADVANCED AI TEST")
    print("=" * 70)


if __name__ == "__main__":
    main()
