"""
Fetch 1-year BTCIRT data from Nobitex API and run XGBoost ML backtest.
Data is fetched in 30-day chunks to avoid API limitations.
"""

import requests
import pandas as pd
import numpy as np
import time
import os
from datetime import datetime, timedelta
import logging
import sys

# Add project root to path
sys.path.insert(0, '/workspace/agent/videnv/crypto-bot')

from backtest.backtester import run_backtest, print_report

try:
    import xgboost as xgb
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import accuracy_score
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Please install: pip install xgboost scikit-learn")
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Using apiv2.nobitex.ir which is accessible
BASE_URL = "https://apiv2.nobitex.ir/market/udf/history"


def fetch_30day_chunk(symbol: str, from_ts: int, to_ts: int) -> pd.DataFrame:
    """Fetch data for a single 30-day chunk from Nobitex API."""
    params = {
        "symbol": symbol,
        "resolution": "60",  # hourly
        "from": from_ts,
        "to": to_ts,
    }
    
    try:
        response = requests.get(BASE_URL, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        if data.get("s") != "ok":
            logger.warning(f"API returned status: {data.get('s')}")
            return pd.DataFrame()
        
        df = pd.DataFrame({
            "timestamp": pd.to_datetime(data["t"], unit="s"),
            "open": data["o"],
            "high": data["h"],
            "low": data["l"],
            "close": data["c"],
            "volume": data["v"],
        })
        
        return df
    except Exception as e:
        logger.error(f"Error fetching chunk {from_ts} to {to_ts}: {e}")
        return pd.DataFrame()


def fetch_1year_data(symbol: str = "BTCIRT") -> pd.DataFrame:
    """
    Fetch 1 year of data in 30-day chunks, looping backwards from now.
    Concatenates all chunks and returns cleaned DataFrame.
    """
    now_ts = int(time.time())
    day_seconds = 24 * 60 * 60
    chunk_days = 30
    total_days = 365
    
    all_chunks = []
    
    logger.info(f"Fetching {total_days} days of {symbol} data in {chunk_days}-day chunks...")
    
    # Loop backwards from now
    current_end = now_ts
    chunk_num = 0
    
    while current_end > (now_ts - total_days * day_seconds):
        current_start = current_end - (chunk_days * day_seconds)
        
        logger.info(f"Fetching chunk {chunk_num + 1}: {datetime.fromtimestamp(current_start)} to {datetime.fromtimestamp(current_end)}")
        
        chunk_df = fetch_30day_chunk(symbol, current_start, current_end)
        
        if len(chunk_df) > 0:
            all_chunks.append(chunk_df)
            logger.info(f"  Retrieved {len(chunk_df)} rows")
        else:
            logger.warning(f"  No data returned for this chunk")
        
        current_end = current_start
        chunk_num += 1
        time.sleep(0.5)  # Rate limiting
    
    if not all_chunks:
        raise ValueError("No data retrieved from API")
    
    # Concatenate all chunks
    df = pd.concat(all_chunks, ignore_index=True)
    
    # Clean data: drop duplicates, sort by timestamp
    logger.info(f"Total rows before dedup: {len(df)}")
    df = df.drop_duplicates(subset=["timestamp"])
    df = df.sort_values("timestamp").reset_index(drop=True)
    
    logger.info(f"Total rows after dedup: {len(df)}")
    
    # Handle NaNs
    df = df.dropna(subset=["open", "high", "low", "close", "volume"])
    
    return df


def add_technical_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add RSI, MACD, Bollinger %b, momentum, volatility features."""
    df = df.copy()
    
    # RSI (14-period)
    delta = df["close"].diff()
    gain = delta.where(delta > 0, 0).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df["rsi"] = 100 - (100 / (1 + rs))
    
    # MACD (12, 26, 9)
    ema12 = df["close"].ewm(span=12, adjust=False).mean()
    ema26 = df["close"].ewm(span=26, adjust=False).mean()
    df["macd"] = ema12 - ema26
    df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
    df["macd_hist"] = df["macd"] - df["macd_signal"]
    
    # Bollinger Bands (20, 2)
    sma20 = df["close"].rolling(window=20).mean()
    std20 = df["close"].rolling(window=20).std()
    bb_upper = sma20 + 2 * std20
    bb_lower = sma20 - 2 * std20
    df["bb_pct"] = (df["close"] - bb_lower) / (bb_upper - bb_lower)
    
    # Momentum (10-period)
    df["momentum"] = df["close"].diff(10)
    
    # Volatility (10-period rolling std of returns)
    df["returns"] = df["close"].pct_change()
    df["volatility"] = df["returns"].rolling(window=10).std()
    
    # Drop intermediate columns
    df = df.drop(columns=["returns"], errors="ignore")
    
    return df


def create_target(df: pd.DataFrame) -> pd.DataFrame:
    """Create target: 1 if next hour's close > current close, else 0."""
    df = df.copy()
    df["target"] = (df["close"].shift(-1) > df["close"]).astype(int)
    return df


def main():
    print("=" * 60)
    print("XGBoost ML Backtest with 1-Year Nobitex Data")
    print("=" * 60)
    
    # Step 1: Fetch data
    print("\n[Step 1] Fetching 1-year data from Nobitex API...")
    df = fetch_1year_data("BTCIRT")
    
    # Step 2: Save to CSV
    print("\n[Step 2] Saving data to data/btcirt_1year.csv...")
    os.makedirs("data", exist_ok=True)
    output_path = "data/btcirt_1year.csv"
    df.to_csv(output_path, index=False)
    print(f"Saved {len(df)} rows to {output_path}")
    
    # Step 3: Data validation
    print("\n[Step 3] Data Validation:")
    print("-" * 40)
    print("df.head():")
    print(df.head())
    print("\ndf.tail():")
    print(df.tail())
    print(f"\nlen(df) = {len(df)}")
    print(f"df['timestamp'].min() = {df['timestamp'].min()}")
    print(f"df['timestamp'].max() = {df['timestamp'].max()}")
    
    # Step 4: Add features and target
    print("\n[Step 4] Adding technical features...")
    df = add_technical_features(df)
    df = create_target(df)
    
    # Drop rows with NaN from feature calculation
    df = df.dropna().reset_index(drop=True)
    print(f"Rows after feature calculation and dropping NaN: {len(df)}")
    
    # Define features
    feature_cols = ["rsi", "macd", "macd_signal", "macd_hist", "bb_pct", "momentum", "volatility"]
    
    # Check for any remaining NaN or inf in features
    for col in feature_cols:
        if df[col].isna().any() or np.isinf(df[col]).any():
            logger.warning(f"Column {col} has NaN or inf values")
    
    df = df.replace([np.inf, -np.inf], np.nan).dropna()
    print(f"Rows after removing inf/nan: {len(df)}")
    
    X = df[feature_cols]
    y = df["target"]
    
    # Step 5: Chronological 70/30 split
    print("\n[Step 5] Chronological Train/Test Split (70/30)...")
    split_idx = int(len(df) * 0.7)
    
    X_train = X.iloc[:split_idx]
    X_test = X.iloc[split_idx:]
    y_train = y.iloc[:split_idx]
    y_test = y.iloc[split_idx:]
    
    print(f"Train size: {len(X_train)}, Test size: {len(X_test)}")
    
    # Get test data with original indices for backtesting
    test_df = df.iloc[split_idx:].copy().reset_index(drop=True)
    
    # Step 6: Train XGBoost
    print("\n[Step 6] Training XGBoost Classifier...")
    model = xgb.XGBClassifier(
        n_estimators=100,
        max_depth=6,
        learning_rate=0.1,
        objective="binary:logistic",
        eval_metric="logloss",
        random_state=42,
        use_label_encoder=False
    )
    
    model.fit(X_train, y_train)
    print("Training complete.")
    
    # Step 7: Generate predictions on Test set
    print("\n[Step 7] Generating predictions on Test set...")
    y_pred_proba = model.predict_proba(X_test)[:, 1]
    y_pred = model.predict(X_test)
    
    # Accuracy
    accuracy = accuracy_score(y_test, y_pred)
    print(f"\nML Accuracy on Test Set: {accuracy:.4f} ({accuracy*100:.2f}%)")
    
    # Step 8: Convert predictions to position column (threshold 0.55)
    print("\n[Step 8] Converting predictions to positions (threshold=0.55)...")
    threshold = 0.55
    positions = np.where(y_pred_proba >= threshold, 1, np.where(y_pred_proba <= (1 - threshold), -1, 0))
    test_df["position"] = positions
    
    print(f"Position distribution:")
    print(f"  Long (1):  {(positions == 1).sum()}")
    print(f"  Short (-1): {(positions == -1).sum()}")
    print(f"  Hold (0):   {(positions == 0).sum()}")
    
    # Step 9: Run backtest
    print("\n[Step 9] Running backtest with 0.25% commission + 0.1% slippage...")
    print("-" * 40)
    
    results = run_backtest(
        test_df,
        initial_capital=10_000_000,
        commission_pct=0.0025,
        slippage_pct=0.001,
        position_size_pct=1.0
    )
    
    print("\n" + "=" * 60)
    print("BACKTEST RESULTS")
    print("=" * 60)
    print_report(results)
    
    # Summary comparison
    print("\n" + "=" * 60)
    print("SUMMARY COMPARISON")
    print("=" * 60)
    print("180-day ML performance: 54% accuracy, -75% return (due to costs)")
    print(f"1-year ML performance:  {accuracy*100:.2f}% accuracy, {results.get('total_return_pct', 'N/A'):.2f}% return")
    
    if results.get("total_return_pct", 0) > 0:
        print("\nThe larger 1-year dataset IMPROVED the edge - strategy is now profitable!")
    else:
        print("\nThe larger 1-year dataset did NOT improve the edge - still unprofitable due to costs.")


if __name__ == "__main__":
    main()
