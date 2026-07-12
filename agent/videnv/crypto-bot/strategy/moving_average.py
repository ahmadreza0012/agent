"""
Moving Average Crossover Strategy

این استراتژی بر اساس تقاطع دو میانگین متحرک (کوتاه‌مدت و بلندمدت) سیگنال خرید/فروش تولید می‌کند:
- وقتی میانگین کوتاه‌مدت از میانگین بلندمدت به سمت بالا عبور کند → سیگنال خرید (Golden Cross)
- وقتی میانگین کوتاه‌مدت از میانگین بلندمدت به سمت پایین عبور کند → سیگنال فروش (Death Cross)
"""

import pandas as pd
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def apply_moving_average_strategy(
    df: pd.DataFrame,
    short_window: int = 9,
    long_window: int = 21,
) -> pd.DataFrame:
    """
    اعمال استراتژی میانگین متحرک متقاطع روی داده قیمت.

    Args:
        df: DataFrame شامل حداقل ستون 'close'
        short_window: تعداد دوره برای میانگین متحرک کوتاه‌مدت
        long_window: تعداد دوره برای میانگین متحرک بلندمدت

    Returns:
        همان DataFrame با ستون‌های اضافه‌شده: ma_short, ma_long, signal, position
    """
    if len(df) < long_window:
        raise ValueError(
            f"داده کافی نیست. حداقل {long_window} ردیف لازم است، ولی {len(df)} ردیف موجود است."
        )

    df = df.copy()

    # محاسبه میانگین‌های متحرک
    df["ma_short"] = df["close"].rolling(window=short_window).mean()
    df["ma_long"] = df["close"].rolling(window=long_window).mean()

    # سیگنال: 1 یعنی میانگین کوتاه بالای میانگین بلند است (روند صعودی)
    #          0 یعنی میانگین کوتاه پایین میانگین بلند است (روند نزولی)
    df["signal"] = 0
    df.loc[df["ma_short"] > df["ma_long"], "signal"] = 1

    # position: تغییر سیگنال نسبت به ردیف قبلی را نشان می‌دهد
    #   1  = سیگنال خرید تازه صادر شده (Golden Cross)
    #  -1  = سیگنال فروش تازه صادر شده (Death Cross)
    #   0  = بدون تغییر
    df["position"] = df["signal"].diff()

    logger.info(
        f"استراتژی اعمال شد. تعداد سیگنال خرید: {(df['position'] == 1).sum()}, "
        f"تعداد سیگنال فروش: {(df['position'] == -1).sum()}"
    )

    return df


def get_trade_signals(df: pd.DataFrame) -> pd.DataFrame:
    """
    استخراج فقط ردیف‌هایی که سیگنال معاملاتی دارند (خرید یا فروش).

    Returns:
        DataFrame شامل فقط لحظات خرید/فروش با ستون‌های timestamp, close, action
    """
    # dropna حذف می‌کند: هم ردیف اول (که diff برایش NaN است)
    # و هم ردیف‌هایی که هنوز میانگین متحرک بلندمدت محاسبه نشده (چون rolling در ابتدا NaN می‌دهد)
    valid = df.dropna(subset=["position"])
    signals = valid[valid["position"] != 0].copy()
    signals["action"] = signals["position"].map({1: "BUY", -1: "SELL"})
    return signals[["timestamp", "close", "action"]]


if __name__ == "__main__":
    # بارگذاری داده‌ای که در مرحله قبل ذخیره کردیم
    df = pd.read_csv("data/btcirt_30d.csv", parse_dates=["timestamp"])

    # اعمال استراتژی
    df = apply_moving_average_strategy(df, short_window=9, long_window=21)

    # نمایش سیگنال‌های معاملاتی
    signals = get_trade_signals(df)
    print("\nسیگنال‌های معاملاتی:")
    print(signals.to_string(index=False))

    # ذخیره نتیجه کامل (شامل میانگین‌ها و سیگنال‌ها) برای استفاده در بک‌تست
    df.to_csv("data/btcirt_with_signals.csv", index=False)
    print(f"\nفایل نتیجه با سیگنال‌ها ذخیره شد در: data/btcirt_with_signals.csv")