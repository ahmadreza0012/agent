"""
Historical Data Collector for Cryptocurrency Exchanges

این اسکریپت داده تاریخی قیمت (OHLCV) را از صرافی می‌گیرد و در یک فایل CSV ذخیره می‌کند.
نیازی به API Key نیست چون داده تاریخی عمومی است.
"""

import ccxt
import pandas as pd
import logging
import os

# تنظیم لاگ برای دیدن پیشرفت کار
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def fetch_historical_data(
    exchange_name: str = "binance",
    symbol: str = "BTC/USDT",
    timeframe: str = "1h",
    days: int = 30,
) -> pd.DataFrame:
    """
    دریافت داده تاریخی OHLCV از صرافی.

    Args:
        exchange_name: نام صرافی (مثلا 'binance')
        symbol: جفت‌ارز (مثلا 'BTC/USDT')
        timeframe: تایم‌فریم هر کندل (مثلا '1h', '1d')
        days: تعداد روزهای گذشته که می‌خواهیم داده بگیریم

    Returns:
        DataFrame شامل ستون‌های timestamp, open, high, low, close, volume
    """
    try:
        # ساخت اتصال به صرافی (بدون نیاز به API Key برای داده عمومی)
        exchange = getattr(ccxt, exchange_name)()

        # محاسبه زمان شروع (میلی‌ثانیه)
        since = exchange.milliseconds() - days * 24 * 60 * 60 * 1000

        all_ohlcv = []
        limit = 1000  # حداکثر تعداد کندل در هر درخواست

        logger.info(f"شروع دریافت داده {symbol} از {exchange_name}...")

        while True:
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since, limit)
            if not ohlcv:
                break

            all_ohlcv.extend(ohlcv)
            since = ohlcv[-1][0] + 1  # برای درخواست بعدی، از آخرین زمان به بعد

            # اگر داده کمتر از limit برگشت، یعنی به آخر رسیدیم
            if len(ohlcv) < limit:
                break

        # تبدیل به DataFrame
        df = pd.DataFrame(
            all_ohlcv,
            columns=["timestamp", "open", "high", "low", "close", "volume"]
        )

        # تبدیل timestamp میلی‌ثانیه به تاریخ خوانا
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")

        logger.info(f"دریافت داده کامل شد. تعداد ردیف‌ها: {len(df)}")
        return df

    except Exception as e:
        logger.error(f"خطا در دریافت داده: {str(e)}")
        raise


def save_to_csv(df: pd.DataFrame, filename: str = "btcusdt_30d.csv") -> None:
    """ذخیره DataFrame در فایل CSV داخل پوشه data/"""
    output_dir = "data"
    os.makedirs(output_dir, exist_ok=True)

    filepath = os.path.join(output_dir, filename)
    df.to_csv(filepath, index=False)
    logger.info(f"فایل ذخیره شد در: {filepath}")


if __name__ == "__main__":
    # تنظیمات پیش‌فرض
    df = fetch_historical_data(
        exchange_name="binance",
        symbol="BTC/USDT",
        timeframe="1h",
        days=30,
    )

    save_to_csv(df, "btcusdt_30d.csv")

    # نمایش چند ردیف اول برای بررسی سریع
    print(df.head())
    print(f"\nتعداد کل ردیف‌ها: {len(df)}")