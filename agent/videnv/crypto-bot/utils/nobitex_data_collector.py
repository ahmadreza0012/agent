"""
Nobitex Historical Data Collector

این اسکریپت داده تاریخی OHLC را از API رسمی نوبیتکس می‌گیرد و در CSV ذخیره می‌کند.
نیازی به API Key نیست چون این endpoint کاملا عمومی است.

مستندات رسمی: https://apidocs.nobitex.ir/
"""

import requests
import pandas as pd
import logging
import os
import time

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

BASE_URL = "https://apiv2.nobitex.ir"

# نگاشت تایم‌فریم‌های رایج به مقدار resolution نوبیتکس
# مقادیر مجاز: 1, 5, 15, 30, 60, 180, 240, 360, 720, D
RESOLUTION_MAP = {
    "1m": "1",
    "5m": "5",
    "15m": "15",
    "30m": "30",
    "1h": "60",
    "3h": "180",
    "4h": "240",
    "6h": "360",
    "12h": "720",
    "1d": "D",
}


def fetch_historical_data(
    symbol: str = "BTCIRT",
    timeframe: str = "1h",
    days: int = 30,
) -> pd.DataFrame:
    """
    دریافت داده تاریخی OHLC از نوبیتکس.

    Args:
        symbol: نماد بازار (مثلا 'BTCIRT' برای بیت‌کوین به تومان، یا 'BTCUSDT')
        timeframe: تایم‌فریم کندل، یکی از کلیدهای RESOLUTION_MAP
        days: تعداد روزهای گذشته

    Returns:
        DataFrame شامل ستون‌های timestamp, open, high, low, close, volume
    """
    if timeframe not in RESOLUTION_MAP:
        raise ValueError(
            f"تایم‌فریم نامعتبر. یکی از این‌ها را انتخاب کنید: {list(RESOLUTION_MAP.keys())}"
        )

    resolution = RESOLUTION_MAP[timeframe]

    # محاسبه بازه زمانی (یونیکس تایم‌استمپ به ثانیه)
    to_ts = int(time.time())
    from_ts = to_ts - (days * 24 * 60 * 60)

    url = f"{BASE_URL}/market/udf/history"
    params = {
        "symbol": symbol,
        "resolution": resolution,
        "from": from_ts,
        "to": to_ts,
    }

    logger.info(f"در حال دریافت داده {symbol} با تایم‌فریم {timeframe} برای {days} روز گذشته...")

    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()

        if data.get("s") != "ok":
            raise ValueError(f"پاسخ نامعتبر از نوبیتکس: {data}")

        df = pd.DataFrame({
            "timestamp": pd.to_datetime(data["t"], unit="s"),
            "open": data["o"],
            "high": data["h"],
            "low": data["l"],
            "close": data["c"],
            "volume": data["v"],
        })

        logger.info(f"دریافت داده کامل شد. تعداد ردیف‌ها: {len(df)}")
        return df

    except requests.exceptions.RequestException as e:
        logger.error(f"خطا در ارتباط با نوبیتکس: {str(e)}")
        raise
    except (KeyError, ValueError) as e:
        logger.error(f"خطا در پردازش پاسخ: {str(e)}")
        raise


def save_to_csv(df: pd.DataFrame, filename: str = "btcirt_30d.csv") -> None:
    """ذخیره DataFrame در فایل CSV داخل پوشه data/"""
    output_dir = "data"
    os.makedirs(output_dir, exist_ok=True)

    filepath = os.path.join(output_dir, filename)
    df.to_csv(filepath, index=False)
    logger.info(f"فایل ذخیره شد در: {filepath}")


if __name__ == "__main__":
    # مثال: دریافت داده ساعتی بیت‌کوین به تومان برای ۳۰ روز گذشته
    df = fetch_historical_data(
        symbol="BTCIRT",
        timeframe="1h",
        days=30,
    )

    save_to_csv(df, "btcirt_30d.csv")

    # نمایش چند ردیف اول برای بررسی سریع
    print(df.head())
    print(f"\nتعداد کل ردیف‌ها: {len(df)}")
    print(f"بازه زمانی: از {df['timestamp'].min()} تا {df['timestamp'].max()}")