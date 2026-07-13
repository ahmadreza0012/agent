"""
RSI (Relative Strength Index) Strategy

این ماژول سیگنال‌های خرید و فروش بر اساس اندیکاتور RSI تولید می‌کند.
منطق:
- خرید (1): وقتی RSI از پایین به بالا خط اشباع فروش (Oversold) را قطع می‌کند.
- فروش (-1): وقتی RSI از بالا به پایین خط اشباع خرید (Overbought) را قطع می‌کند.
"""

import pandas as pd
import numpy as np
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def apply_rsi_strategy(df: pd.DataFrame, rsi_period: int = 14, 
                       oversold: int = 30, overbought: int = 70) -> pd.DataFrame:
    """
    اعمال استراتژی RSI.

    نکات ایمنی:
    - این تابع با `df = df.copy()` شروع می‌شود تا از تغییر داده‌های ورودی جلوگیری کند.
      (جلوگیری از باگ Mutation که قبلاً در پروژه رخ داد)
    """
    # ✅ CRITICAL FIX: Create a copy to prevent mutating the input DataFrame
    df = df.copy()

    if len(df) < rsi_period + 5:
        raise ValueError(f"داده‌ها برای محاسبه RSI با دوره {rsi_period} کافی نیستند.")

    # محاسبه تغییرات قیمت
    delta = df['close'].diff()

    # جدا کردن سودها و زیان‌ها
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)

    # محاسبه میانگین متحرک نمایی (Wilder's Smoothing)
    # فرمول Wilder: alpha = 1 / period
    alpha = 1.0 / rsi_period
    
    # محاسبه سری زمانی میانگین سود و زیان با روش نمایی
    avg_gain = gain.ewm(alpha=alpha, adjust=False).mean()
    avg_loss = loss.ewm(alpha=alpha, adjust=False).mean()

    # محاسبه RS و RSI
    # رفع باگ منطقی: وقتی avg_loss صفر است (روند صعودی خالص)، RSI باید 100 باشد، نه 0
    df['rsi'] = 50.0  # مقدار پیش‌فرض برای حالت‌های خاص
    
    # شرط 1: زیان صفر و سود مثبت -> RSI = 100
    mask_uptrend = (avg_loss == 0) & (avg_gain > 0)
    df.loc[mask_uptrend, 'rsi'] = 100.0
    
    # شرط 2: سود و زیان هر دو صفر -> RSI = 50 (بدون حرکت)
    mask_flat = (avg_loss == 0) & (avg_gain == 0)
    df.loc[mask_flat, 'rsi'] = 50.0
    
    # شرط 3: حالت عادی -> محاسبه استاندارد
    mask_normal = (avg_loss > 0)
    rs_normal = avg_gain[mask_normal] / avg_loss[mask_normal]
    df.loc[mask_normal, 'rsi'] = 100 - (100 / (1 + rs_normal))

    # تولید سیگنال‌ها
    df['position'] = 0

    # شرط خرید: RSI از زیرِ Oversold می‌آید و بالای آن می‌رود
    # دیروز <= oversold AND امروز > oversold
    buy_condition = (df['rsi'].shift(1) <= oversold) & (df['rsi'] > oversold)
    df.loc[buy_condition, 'position'] = 1

    # شرط فروش: RSI از بالایِ Overbought می‌آید و زیر آن می‌رود
    # دیروز >= overbought AND امروز < overbought
    sell_condition = (df['rsi'].shift(1) >= overbought) & (df['rsi'] < overbought)
    df.loc[sell_condition, 'position'] = -1

    buy_count = (df['position'] == 1).sum()
    sell_count = (df['position'] == -1).sum()

    logger.info(f"استراتژی RSI اعمال شد. دوره: {rsi_period}, آستانه‌ها: {oversold}/{overbought}")
    logger.info(f"تعداد سیگنال خرید: {buy_count}, تعداد سیگنال فروش: {sell_count}")

    return df
