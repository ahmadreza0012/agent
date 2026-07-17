"""
ML Strategy Test Script - XGBoost-based Crypto Trading Strategy

This script:
1. Loads btcirt_180d.csv OHLCV data
2. Generates technical features (RSI, MACD, Bollinger Bands %b)
3. Creates target variable (1 if next hour close > current close, 0 otherwise)
4. Trains XGBoost classifier on first 70% of data (chronological split)
5. Generates predictions on last 30% (out-of-sample test)
6. Converts predictions to position signals for backtesting
7. Runs backtest and reports results

Anti-Hallucination Protocol:
- Uses REAL data from btcirt_180d.csv (NO synthetic data)
- Chronological train/test split to prevent look-ahead bias
- Reports RAW console output with actual metrics
"""

import pandas as pd
import numpy as np
from datetime import datetime
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backtest.backtester import run_backtest, print_report

# Try to import xgboost, fall back to sklearn if not available
try:
    import xgboost as xgb
    USE_XGBOOST = True
    print("Using XGBoost for ML classification")
except ImportError:
    from sklearn.ensemble import RandomForestClassifier
    USE_XGBOOST = False
    print("XGBoost not available, using RandomForest instead")

from sklearn.metrics import accuracy_score, classification_report


def calculate_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    """Calculate Relative Strength Index."""
    delta = prices.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    return rsi


def calculate_macd(prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> tuple:
    """Calculate MACD line, signal line, and histogram."""
    ema_fast = prices.ewm(span=fast, adjust=False).mean()
    ema_slow = prices.ewm(span=slow, adjust=False).mean()
    
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    
    return macd_line, signal_line, histogram


def calculate_bollinger_bands(prices: pd.Series, window: int = 20, num_std: float = 2.0) -> tuple:
    """Calculate Bollinger Bands and %b indicator."""
    sma = prices.rolling(window=window).mean()
    std = prices.rolling(window=window).std()
    
    upper_band = sma + (num_std * std)
    lower_band = sma - (num_std * std)
    
    # Bollinger Band %b: where price is relative to bands
    # %b = (close - lower_band) / (upper_band - lower_band)
    bb_percent = (prices - lower_band) / (upper_band - lower_band)
    
    # BB width (normalized)
    bb_width = (upper_band - lower_band) / sma
    
    return upper_band, lower_band, bb_percent, bb_width


def generate_features(df: pd.DataFrame) -> pd.DataFrame:
    """Generate all technical indicators as features."""
    df = df.copy()
    
    # Ensure we have a datetime index or column
    if 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # RSI
    df['rsi'] = calculate_rsi(df['close'], period=14)
    
    # MACD
    df['macd'], df['macd_signal'], df['macd_hist'] = calculate_macd(df['close'])
    
    # Bollinger Bands
    df['bb_upper'], df['bb_lower'], df['bb_percent'], df['bb_width'] = calculate_bollinger_bands(df['close'])
    
    # Additional features
    # Price momentum (rate of change)
    df['momentum'] = df['close'].pct_change(periods=10)
    
    # Volume change
    df['volume_change'] = df['volume'].pct_change()
    
    # High-Low range normalized
    df['hl_range'] = (df['high'] - df['low']) / df['close']
    
    # Close position within day's range
    df['close_position'] = (df['close'] - df['low']) / (df['high'] - df['low'])
    
    return df


def create_target(df: pd.DataFrame) -> pd.DataFrame:
    """Create target variable: 1 if next hour's close > current close, 0 otherwise."""
    df = df.copy()
    df['target'] = (df['close'].shift(-1) > df['close']).astype(int)
    return df


def convert_predictions_to_signals(predictions: pd.Series, probability_threshold: float = 0.55) -> pd.Series:
    """
    Convert ML predictions to trading signals.
    
    The backtester expects:
    - position = 1: Buy/Enter long position
    - position = -1: Sell/Close long position
    - position = 0: Hold/No action
    
    We use prediction probability to determine confidence:
    - If P(up) > threshold: Enter long (position = 1)
    - If P(up) < (1 - threshold): Exit/Short (position = -1)
    - Otherwise: Hold (position = 0)
    """
    signals = pd.Series(index=predictions.index, dtype=int)
    signals[:] = 0  # Default to hold
    
    # Get probabilities if available (for XGBoost)
    if hasattr(predictions, 'values'):
        probs = predictions.values if predictions.dtype == float else predictions
    else:
        probs = predictions
    
    # For binary predictions without probabilities, use simple logic
    if predictions.dtype == int or predictions.dtype == bool:
        # Simple: predict up = buy, predict down = sell previous position
        signals = predictions.replace({0: -1, 1: 1})
    else:
        # Use probability thresholds
        for idx in predictions.index:
            prob = predictions.loc[idx]
            if prob >= probability_threshold:
                signals.loc[idx] = 1  # Buy signal
            elif prob <= (1 - probability_threshold):
                signals.loc[idx] = -1  # Sell signal
            else:
                signals.loc[idx] = 0  # Hold
    
    return signals


def main():
    print("=" * 70)
    print("ML STRATEGY BACKTEST - XGBoost Crypto Trading")
    print("=" * 70)
    print(f"Timestamp: {datetime.now().isoformat()}")
    print()
    
    # Load data
    data_path = os.path.join(os.path.dirname(__file__), 'data', 'btcirt_180d.csv')
    print(f"Loading data from: {data_path}")
    
    if not os.path.exists(data_path):
        print(f"ERROR: Data file not found at {data_path}")
        sys.exit(1)
    
    df = pd.read_csv(data_path, parse_dates=['timestamp'])
    print(f"Loaded {len(df)} rows of OHLCV data")
    print(f"Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
    print()
    
    # Generate features
    print("Generating technical features...")
    df = generate_features(df)
    df = create_target(df)
    
    # Drop rows with NaN values (from rolling calculations)
    df_clean = df.dropna().reset_index(drop=True)
    print(f"After feature generation: {len(df_clean)} rows (removed {len(df) - len(df_clean)} NaN rows)")
    print()
    
    # Define feature columns
    feature_cols = [
        'rsi', 'macd', 'macd_signal', 'macd_hist',
        'bb_percent', 'bb_width',
        'momentum', 'volume_change', 'hl_range', 'close_position'
    ]
    
    # Verify all features exist
    missing_features = [col for col in feature_cols if col not in df_clean.columns]
    if missing_features:
        print(f"ERROR: Missing features: {missing_features}")
        sys.exit(1)
    
    # Chronological train/test split (70/30)
    split_idx = int(len(df_clean) * 0.70)
    
    train_df = df_clean.iloc[:split_idx].copy()
    test_df = df_clean.iloc[split_idx:].copy()
    
    print(f"Chronological split:")
    print(f"  Training set: {len(train_df)} rows ({train_df['timestamp'].min()} to {train_df['timestamp'].max()})")
    print(f"  Test set:     {len(test_df)} rows ({test_df['timestamp'].min()} to {test_df['timestamp'].max()})")
    print()
    
    # Prepare training data
    X_train = train_df[feature_cols].values
    y_train = train_df['target'].values
    
    X_test = test_df[feature_cols].values
    y_test = test_df['target'].values
    
    print(f"Target distribution in training set: {np.bincount(y_train.astype(int))}")
    print(f"Target distribution in test set: {np.bincount(y_test.astype(int))}")
    print()
    
    # Train model
    print("Training ML model...")
    if USE_XGBOOST:
        model = xgb.XGBClassifier(
            n_estimators=100,
            max_depth=4,
            learning_rate=0.1,
            objective='binary:logistic',
            eval_metric='logloss',
            random_state=42,
            use_label_encoder=False
        )
        
        # Print XGBoost version
        print(f"XGBoost version: {xgb.__version__}")
        
        model.fit(
            X_train, y_train,
            eval_set=[(X_test, y_test)],
            verbose=True
        )
        
        # Get probability predictions
        y_pred_proba = model.predict_proba(X_test)[:, 1]
        y_pred = model.predict(X_test)
        
    else:
        model = RandomForestClassifier(
            n_estimators=100,
            max_depth=4,
            random_state=42
        )
        model.fit(X_train, y_train)
        y_pred_proba = model.predict_proba(X_test)[:, 1]
        y_pred = model.predict(X_test)
    
    print()
    
    # Calculate accuracy on test set
    accuracy = accuracy_score(y_test, y_pred)
    print("-" * 50)
    print("ML MODEL OUT-OF-SAMPLE PERFORMANCE (Test Set)")
    print("-" * 50)
    print(f"Accuracy: {accuracy:.4f} ({accuracy*100:.2f}%)")
    print()
    print("Classification Report:")
    print(classification_report(y_test, y_pred, target_names=['Down', 'Up']))
    print()
    
    # Feature importance (if available)
    if hasattr(model, 'feature_importances_'):
        print("Feature Importance:")
        for feat, imp in sorted(zip(feature_cols, model.feature_importances_), key=lambda x: -x[1]):
            print(f"  {feat}: {imp:.4f}")
        print()
    
    # Convert predictions to trading signals
    # Use probability threshold for more selective trading
    probability_threshold = 0.55
    test_signals = convert_predictions_to_signals(pd.Series(y_pred_proba, index=test_df.index), probability_threshold)
    
    # Count signal distribution
    signal_counts = test_signals.value_counts()
    print(f"Signal distribution in test set (threshold={probability_threshold}):")
    for sig in [-1, 0, 1]:
        count = signal_counts.get(sig, 0)
        pct = count / len(test_signals) * 100
        label = {1: "Buy", -1: "Sell", 0: "Hold"}.get(sig, "Unknown")
        print(f"  {label} ({sig}): {count} ({pct:.1f}%)")
    print()
    
    # Create backtest dataframe with signals
    # We need to align signals with the original test_df structure
    backtest_df = test_df.copy()
    backtest_df['position'] = test_signals
    
    # Run backtest
    print("=" * 70)
    print("RUNNING BACKTEST ON ML PREDICTIONS")
    print("=" * 70)
    print()
    
    results = run_backtest(
        backtest_df,
        initial_capital=10_000_000,
        commission_pct=0.0025,  # 0.25% per trade
        slippage_pct=0.001,     # 0.1% slippage
        position_size_pct=1.0,  # Full position
    )
    
    print()
    print_report(results)
    
    # Final summary
    print()
    print("=" * 70)
    print("FINAL SUMMARY - 5% DAILY PROFIT ANALYSIS")
    print("=" * 70)
    
    if 'error' not in results:
        total_return = results['total_return_pct']
        num_trades = results['num_trades']
        win_rate = results['win_rate_pct']
        max_dd = results['max_drawdown_pct']
        
        # Calculate test period duration
        test_days = (test_df['timestamp'].max() - test_df['timestamp'].min()).days
        
        # Daily return calculation
        if test_days > 0:
            daily_return = ((1 + total_return/100) ** (1/test_days) - 1) * 100
        else:
            daily_return = total_return
        
        print(f"Test period: {test_days} days")
        print(f"Total return: {total_return:+.2f}%")
        print(f"Dailyized return: {daily_return:+.4f}%")
        print(f"Number of trades: {num_trades}")
        print(f"Win rate: {win_rate:.1f}%")
        print(f"Max drawdown: {max_dd:.2f}%")
        print()
        
        # Reality check on 5% daily profit goal
        print("-" * 70)
        print("MATHEMATICAL REALITY CHECK: 5% DAILY PROFIT GOAL")
        print("-" * 70)
        
        if daily_return >= 5.0:
            print(f"RESULT: 5% daily profit ACHIEVED ({daily_return:.4f}% daily)")
            print("WARNING: This is statistically improbable in real markets.")
            print("Possible causes: look-ahead bias, overfitting, or data issues.")
            print("Such returns are NOT sustainable in live trading.")
        else:
            print(f"RESULT: 5% daily profit NOT ACHIEVED")
            print(f"Achieved: {daily_return:.4f}% daily (target was 5%)")
            print()
            print("Mathematical Reality:")
            print("- 5% daily profit compounds to ~7,000,000% annually")
            print("- This is mathematically impossible to sustain")
            print("- Market efficiency and transaction costs prevent such returns")
            print("- Even the best quant funds achieve 10-30% ANNUALLY, not daily")
            print()
            print(f"The ML model achieved {total_return:.2f}% over {test_days} days,")
            print(f"which equals {daily_return:.4f}% daily or {(1+daily_return/100)**252-1:.2f}% annualized.")
            print()
            print("CONCLUSION: 5% daily profit is mathematically impossible/unsustainable.")
            print("The ML model provides realistic but modest returns, as expected.")
    else:
        print(f"Backtest failed with error: {results.get('error', 'Unknown')}")
    
    print("=" * 70)
    
    return results


if __name__ == "__main__":
    main()
