"""
Data Quality Validator

Validates OHLCV data for common issues:
- Missing timestamps / gaps
- Duplicate timestamps
- Out-of-order index
- Non-positive prices
- NaNs in OHLCV
- Zero-volume ratio
- Abnormal jumps (z-score spikes)

Returns structured quality report.
"""

from typing import Dict, List, Optional, Any
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)


class DataQualityValidator:
    """
    Validates market data quality and returns structured reports.
    
    Critical issues cause validation failure (valid=False).
    Warnings are logged but don't necessarily fail validation.
    """
    
    def __init__(self, 
                 max_gap_ratio: float = 0.05,
                 max_nan_ratio: float = 0.01,
                 zero_volume_threshold: float = 0.1,
                 jump_zscore_threshold: float = 5.0):
        """
        Initialize validator with configurable thresholds.
        
        Args:
            max_gap_ratio: Maximum allowed ratio of missing candles
            max_nan_ratio: Maximum allowed ratio of NaN values
            zero_volume_threshold: Ratio of zero-volume bars that triggers warning
            jump_zscore_threshold: Z-score threshold for abnormal price jumps
        """
        self.max_gap_ratio = max_gap_ratio
        self.max_nan_ratio = max_nan_ratio
        self.zero_volume_threshold = zero_volume_threshold
        self.jump_zscore_threshold = jump_zscore_threshold
    
    def validate(self, df: pd.DataFrame, symbol: str = 'UNKNOWN',
                 timeframe: str = 'UNKNOWN') -> Dict[str, Any]:
        """
        Validate OHLCV DataFrame.
        
        Args:
            df: DataFrame with columns [Open, High, Low, Close, Volume]
                and DatetimeIndex
            symbol: Symbol name for reporting
            timeframe: Timeframe for gap detection
            
        Returns:
            Quality report dictionary:
            {
                'valid': bool,
                'missing_candles_est': int,
                'duplicate_candles': int,
                'out_of_order': bool,
                'zero_volume_ratio': float,
                'nan_ratio': float,
                'abnormal_jumps': int,
                'warnings': list,
                'errors': list
            }
        """
        report = {
            'valid': True,
            'symbol': symbol,
            'timeframe': timeframe,
            'row_count': len(df),
            'missing_candles_est': 0,
            'duplicate_candles': 0,
            'out_of_order': False,
            'zero_volume_ratio': 0.0,
            'nan_ratio': 0.0,
            'abnormal_jumps': 0,
            'warnings': [],
            'errors': []
        }
        
        if df.empty:
            report['valid'] = False
            report['errors'].append("Empty DataFrame")
            return report
        
        # Check index type
        if not isinstance(df.index, pd.DatetimeIndex):
            report['valid'] = False
            report['errors'].append("Index is not DatetimeIndex")
            return report
        
        # 1. Check for duplicates
        duplicates = df.index.duplicated().sum()
        report['duplicate_candles'] = duplicates
        if duplicates > 0:
            report['errors'].append(f"Found {duplicates} duplicate timestamps")
            report['valid'] = False
        
        # 2. Check for out-of-order index
        if not df.index.is_monotonic_increasing:
            report['out_of_order'] = True
            report['errors'].append("Index is not monotonically increasing")
            report['valid'] = False
        
        # 3. Check for missing timestamps / gaps
        expected_freq = self._infer_expected_frequency(df, timeframe)
        if expected_freq is not None:
            missing_count = self._count_missing_timestamps(df, expected_freq)
            report['missing_candles_est'] = missing_count
            total_expected = len(pd.date_range(df.index.min(), df.index.max(), freq=expected_freq))
            if total_expected > 0:
                gap_ratio = missing_count / total_expected
                if gap_ratio > self.max_gap_ratio:
                    report['errors'].append(
                        f"Gap ratio {gap_ratio:.2%} exceeds threshold {self.max_gap_ratio:.2%}"
                    )
                    report['valid'] = False
                elif gap_ratio > 0:
                    report['warnings'].append(f"Missing {missing_count} candles ({gap_ratio:.2%})")
        
        # 4. Check for NaNs in critical columns
        required_cols = ['Open', 'High', 'Low', 'Close']
        nan_count = 0
        total_values = 0
        
        for col in required_cols:
            if col in df.columns:
                col_nans = df[col].isna().sum()
                nan_count += col_nans
                total_values += len(df)
            else:
                report['errors'].append(f"Missing required column: {col}")
                report['valid'] = False
        
        if 'Volume' in df.columns:
            vol_nans = df['Volume'].isna().sum()
            if vol_nans == len(df):
                report['warnings'].append("Volume column is entirely NaN (unavailable)")
            elif vol_nans > 0:
                report['warnings'].append(f"Volume has {vol_nans} NaN values")
        
        if total_values > 0:
            nan_ratio = nan_count / total_values
            report['nan_ratio'] = round(nan_ratio, 4)
            if nan_ratio > self.max_nan_ratio:
                report['errors'].append(
                    f"NaN ratio {nan_ratio:.2%} exceeds threshold {self.max_nan_ratio:.2%}"
                )
                report['valid'] = False
        
        # 5. Check for non-positive prices
        for col in ['Open', 'High', 'Low', 'Close']:
            if col in df.columns:
                non_positive = (df[col] <= 0).sum()
                if non_positive > 0:
                    report['warnings'].append(f"{col} has {non_positive} non-positive values")
        
        # 6. Check volume quality
        if 'Volume' in df.columns:
            # Count zero volume (but not NaN - NaN means unavailable)
            valid_volume = df['Volume'].dropna()
            if len(valid_volume) > 0:
                zero_vol_count = (valid_volume == 0).sum()
                zero_vol_ratio = zero_vol_count / len(valid_volume)
                report['zero_volume_ratio'] = round(zero_vol_ratio, 4)
                
                if zero_vol_ratio > self.zero_volume_threshold:
                    report['warnings'].append(
                        f"Zero volume ratio {zero_vol_ratio:.2%} exceeds threshold"
                    )
        
        # 7. Check for abnormal jumps (z-score spikes in returns)
        if 'Close' in df.columns and len(df) > 10:
            returns = df['Close'].pct_change().dropna()
            if len(returns) > 0 and returns.std() > 0:
                z_scores = np.abs((returns - returns.mean()) / returns.std())
                abnormal_jumps = (z_scores > self.jump_zscore_threshold).sum()
                report['abnormal_jumps'] = int(abnormal_jumps)
                if abnormal_jumps > 0:
                    report['warnings'].append(
                        f"Found {abnormal_jumps} abnormal price jumps (z>{self.jump_zscore_threshold})"
                    )
        
        # Log results
        if report['valid']:
            logger.info(f"✅ Validation PASSED for {symbol} {timeframe}: "
                       f"{report['row_count']} rows, {len(report['warnings'])} warnings")
        else:
            logger.error(f"❌ Validation FAILED for {symbol} {timeframe}: "
                        f"{report['errors']}")
        
        for warning in report['warnings']:
            logger.warning(f"⚠️ {symbol} {timeframe}: {warning}")
        
        return report
    
    def _infer_expected_frequency(self, df: pd.DataFrame, 
                                   timeframe: str) -> Optional[pd.Timedelta]:
        """Infer expected bar frequency from timeframe string."""
        try:
            if timeframe == '1h':
                return pd.Timedelta(hours=1)
            elif timeframe == '4h':
                return pd.Timedelta(hours=4)
            elif timeframe == '1d':
                return pd.Timedelta(days=1)
            else:
                # Try to infer from median delta
                deltas = df.index.to_series().diff().dropna()
                if len(deltas) > 0:
                    median_delta = deltas.median()
                    return pd.Timedelta(median_delta)
        except Exception:
            pass
        return None
    
    def _count_missing_timestamps(self, df: pd.DataFrame,
                                   expected_freq: pd.Timedelta) -> int:
        """Count missing timestamps based on expected frequency."""
        if len(df) < 2:
            return 0
        
        full_range = pd.date_range(
            start=df.index.min(),
            end=df.index.max(),
            freq=expected_freq
        )
        
        missing = full_range.difference(df.index)
        return len(missing)


def validate_multiple(data: Dict[str, pd.DataFrame], 
                      validator: DataQualityValidator,
                      timeframe: str = '1h') -> Dict[str, Dict]:
    """
    Validate multiple symbols and return aggregated report.
    
    Args:
        data: Dictionary mapping symbol to DataFrame
        validator: DataQualityValidator instance
        timeframe: Timeframe for all symbols
        
    Returns:
        Dictionary with per-symbol reports and overall summary
    """
    reports = {}
    all_valid = True
    total_warnings = 0
    total_errors = 0
    
    for symbol, df in data.items():
        report = validator.validate(df, symbol=symbol, timeframe=timeframe)
        reports[symbol] = report
        
        if not report['valid']:
            all_valid = False
        total_warnings += len(report['warnings'])
        total_errors += len(report['errors'])
    
    summary = {
        'all_valid': all_valid,
        'symbols_checked': len(reports),
        'symbols_passed': sum(1 for r in reports.values() if r['valid']),
        'symbols_failed': sum(1 for r in reports.values() if not r['valid']),
        'total_warnings': total_warnings,
        'total_errors': total_errors
    }
    
    return {
        'summary': summary,
        'reports': reports
    }
