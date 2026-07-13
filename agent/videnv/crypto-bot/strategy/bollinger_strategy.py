"""
Bollinger Bands Mean-Reversion Strategy

این استراتژی بر پایه بازگشت به میانگین (Mean Reversion) است، نه تعقیب روند:
- وقتی قیمت از زیر باند پایین به بالای آن برگردد → سیگنال خرید (فرض: قیمت بیش‌ازحد افت کرده و برمی‌گردد)
- وقتی قیمت از بالای باند بالا به زیر آن برگردد → سیگنال فروش (فرض: قیمت بیش‌ازحد رشد کرده و اصلاح می‌شود)
"""

import pandas as pd
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def apply_bollinger_strategy(df: pd.DataFrame, window: int = 20, num_std: float = 2.0) -> pd.DataFrame:
    """
    اعمال استراتژی بولینگر باند (بازگشت به میانگین).

    Args:
        df: DataFrame شامل ستون 'close'
        window: تعداد دوره برای محاسبه میانگین متحرک و انحراف معیار
        num_std: تعداد انحراف معیار برای فاصله باندها از میانگین

    Returns:
        DataFrame با ستون‌های اضافه‌شده: middle_band, upper_band, lower_band, position
    """
    # جلوگیری از تغییر DataFrame ورودی (باگی که چند بار در این پروژه رخ داد)
    df = df.copy()

    if len(df) < window:
        raise ValueError(f"داده‌ها برای محاسبه پنجره {window} کافی نیستند.")

    # محاسبه باند میانی (میانگین متحرک ساده) و انحراف معیار متحرک
    df["middle_band"] = df["close"].rolling(window=window).mean()
    rolling_std = df["close"].rolling(window=window).std()

    df["upper_band"] = df["middle_band"] + (num_std * rolling_std)
    df["lower_band"] = df["middle_band"] - (num_std * rolling_std)

    df["position"] = 0

    # سیگنال خرید: دیروز زیر باند پایین بود، امروز بالای آن است (بازگشت از اشباع فروش)
    buy_condition = (df["close"].shift(1) < df["lower_band"].shift(1)) & (df["close"] >= df["lower_band"])
    df.loc[buy_condition, "position"] = 1

    # سیگنال فروش: دیروز بالای باند بالا بود، امروز زیر آن است (بازگشت از اشباع خرید)
    sell_condition = (df["close"].shift(1) > df["upper_band"].shift(1)) & (df["close"] <= df["upper_band"])
    df.loc[sell_condition, "position"] = -1

    buy_count = (df["position"] == 1).sum()
    sell_count = (df["position"] == -1).sum()

    logger.info(f"استراتژی بولینگر اعمال شد. پنجره: {window}, انحراف معیار: {num_std}")
    logger.info(f"تعداد سیگنال خرید: {buy_count}, تعداد سیگنال فروش: {sell_count}")

    return df