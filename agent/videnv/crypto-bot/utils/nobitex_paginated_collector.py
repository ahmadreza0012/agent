"""
جمع‌آوری داده‌های تاریخی Nobitex به صورت صفحه‌بندی‌شده (Paginated)

این ماژول داده‌های OHLCV را از API عمومی Nobitex دریافت می‌کند.
از آنجا که هر درخواست حداکثر ۵۰۰ کندل برمی‌گرداند، بازه زمانی مورد نظر
به چندین قطعه (chunk) تقسیم شده و به صورت متوالی دریافت می‌شوند.

نکات کلیدی:
- بدون نیاز به API Key (اندپوینت عمومی)
- مدیریت خودکار تکرار درخواست‌ها برای بازه‌های طولانی
- حذف داده‌های تکراری در مرز قطعات
- تحمل خطا: اگر یک قطعه شکست خورد، بقیه ادامه می‌یابند
"""

import requests
import pandas as pd
import time
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

# تنظیمات لاگینگ
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# نگاشت تایم‌فریم‌ها به رزولوشن دقیقه‌ای Nobitex
TIMEFRAME_MAP = {
    '1m': '1',
    '5m': '5',
    '15m': '15',
    '30m': '30',
    '1h': '60',
    '3h': '180',
    '4h': '240',
    '6h': '360',
    '12h': '720',
    '1d': 'D',
}

def fetch_chunk(
    symbol: str,
    resolution: str,
    from_ts: int,
    to_ts: int,
    timeout: int = 15
) -> Optional[pd.DataFrame]:
    """
    دریافت یک قطعه داده از API Nobitex.

    Args:
        symbol: نماد معامله (مثلاً BTCIRT)
        resolution: رزولوشن دقیقه‌ای (مثلاً 60 برای ۱ ساعته)
        from_ts:_timestamp شروع (ثانیه یونیکس)
        to_ts: timestamp پایان (ثانیه یونیکس)
        timeout: مهلت پاسخ‌دهی به ثانیه

    Returns:
        DataFrame شامل داده‌های OHLCV یا None در صورت خطا
    """
    url = "https://apiv2.nobitex.ir/market/udf/history"
    params = {
        "symbol": symbol,
        "resolution": resolution,
        "from": from_ts,
        "to": to_ts,
    }

    try:
        logger.debug(f"درخواست به API: از {datetime.fromtimestamp(from_ts)} تا {datetime.fromtimestamp(to_ts)}")
        response = requests.get(url, params=params, timeout=timeout)
        response.raise_for_status()
        data = response.json()

        if data.get("s") == "no_data":
            logger.warning(f"داده‌ای برای این بازه یافت نشد (no_data). توقف در تاریخ {datetime.fromtimestamp(from_ts)}.")
            return None
        
        if data.get("s") != "ok":
            logger.error(f"خطای API: وضعیت '{data.get('s')}' دریافت شد.")
            return None

        # ساخت DataFrame
        df = pd.DataFrame({
            "timestamp": pd.to_datetime(data["t"], unit="s"),
            "open": data["o"],
            "high": data["h"],
            "low": data["l"],
            "close": data["c"],
            "volume": data["v"],
        })

        logger.info(f"تعداد {len(df)} کندل دریافت شد.")
        return df

    except requests.exceptions.RequestException as e:
        logger.error(f"خطای شبکه در دریافت داده: {e}")
        return None
    except Exception as e:
        logger.error(f"خطای غیرمنتظره: {e}")
        return None


def collect_historical_data(
    symbol: str = "BTCIRT",
    timeframe: str = "1h",
    days: int = 180,
    output_path: str = "data/btcirt_180d.csv",
    rate_limit_delay: float = 0.5
) -> Optional[pd.DataFrame]:
    """
    جمع‌آوری داده‌های تاریخی با تقسیم‌بندی خودکار به قطعات کوچکتر.

    Args:
        symbol: نماد معامله (پیش‌فرض: BTCIRT)
        timeframe: تایم‌فریم (مثلاً 1h, 4h, 1d)
        days: تعداد روزهای مورد نیاز برای جمع‌آوری
        output_path: مسیر فایل خروجی CSV
        rate_limit_delay: تأخیر بین درخواست‌ها برای رعایت نرخ محدودیت

    Returns:
        DataFrame نهایی ترکیب‌شده یا None در صورت شکست کامل
    """
    if timeframe not in TIMEFRAME_MAP:
        logger.error(f"تایم‌فریم '{timeframe}' معتبر نیست. مقادیر مجاز: {list(TIMEFRAME_MAP.keys())}")
        return None

    resolution = TIMEFRAME_MAP[timeframe]
    
    # محاسبه مدت زمان هر کندل به ساعت
    if resolution == "D":
        minutes_per_candle = 24 * 60
    else:
        minutes_per_candle = int(resolution)
    
    hours_per_candle = minutes_per_candle / 60
    
    # محاسبه حداکثر روزهای قابل پوشش در یک درخواست (۵۰۰ کندل)
    # کمی محافظه‌کارانه عمل می‌کنیم (۴۸۰ کندل) تا از مرز عبور نکنیم
    max_candles_per_request = 480
    days_per_chunk = (max_candles_per_request * hours_per_candle) / 24
    
    logger.info("=" * 60)
    logger.info("شروع جمع‌آوری داده‌های تاریخی Nobitex")
    logger.info(f"نماد: {symbol}")
    logger.info(f"تایم‌فریم: {timeframe} (رزولوشن: {resolution})")
    logger.info(f"بازه مورد نیاز: {days} روز")
    logger.info(f"حداکثر پوشش هر درخواست: {days_per_chunk:.1f} روز ({max_candles_per_request} کندل)")
    logger.info("=" * 60)

    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    current_from = start_date
    all_chunks: List[pd.DataFrame] = []
    chunk_count = 0
    failed_chunks = 0

    while current_from < end_date:
        # تعیین تاریخ پایان برای این قطعه
        current_to = current_from + timedelta(days=days_per_chunk)
        if current_to > end_date:
            current_to = end_date

        from_ts = int(current_from.timestamp())
        to_ts = int(current_to.timestamp())

        logger.info(f"درخواست قطعه {chunk_count + 1}: از {current_from.strftime('%Y-%m-%d %H:%M')} تا {current_to.strftime('%Y-%m-%d %H:%M')}")
        
        df_chunk = fetch_chunk(symbol, resolution, from_ts, to_ts)

        if df_chunk is not None and len(df_chunk) > 0:
            all_chunks.append(df_chunk)
            chunk_count += 1
            logger.info(f"قطعه {chunk_count} با موفقیت دریافت شد (تعداد رکورد: {len(df_chunk)})")
        elif df_chunk is None:
            # اگر no_data بود، یعنی به ابتدای تاریخ رسیده‌ایم
            logger.info("به نظر می‌رسد به ابتدای داده‌های موجود رسیده‌ایم. ادامه فرآیند متوقف شد.")
            break
        else:
            failed_chunks += 1
            logger.warning(f"دریافت قطعه ناموفق بود، اما ادامه می‌دهیم...")

        # حرکت به بازه بعدی
        current_from = current_to
        
        # رعایت نرخ محدودیت (فقط اگر قرار است درخواست بعدی بزنیم)
        if current_from < end_date:
            time.sleep(rate_limit_delay)

    if not all_chunks:
        logger.error("هیچ داده‌ای دریافت نشد. فرآیند با شکست مواجه شد.")
        return None

    logger.info("-" * 60)
    logger.info(f"تعداد قطعات دریافت‌شده: {chunk_count}")
    logger.info(f"تعداد قطعات ناموفق: {failed_chunks}")
    logger.info("در حال ترکیب و پاک‌سازی داده‌ها...")

    # ترکیب همه قطعات
    combined_df = pd.concat(all_chunks, ignore_index=True)

    # حذف داده‌های تکراری بر اساس timestamp
    initial_rows = len(combined_df)
    combined_df = combined_df.drop_duplicates(subset=["timestamp"], keep="first")
    removed_duplicates = initial_rows - len(combined_df)
    
    if removed_duplicates > 0:
        logger.info(f"تعداد {removed_duplicates} رکورد تکراری حذف شد.")

    # مرتب‌سازی بر اساس زمان
    combined_df = combined_df.sort_values(by="timestamp").reset_index(drop=True)

    # ذخیره در فایل CSV
    combined_df.to_csv(output_path, index=False)
    logger.info(f"داده‌ها در فایل '{output_path}' ذخیره شدند.")

    # چاپ خلاصه نهایی
    min_date = combined_df["timestamp"].min()
    max_date = combined_df["timestamp"].max()
    
    print("\n" + "=" * 60)
    print("خلاصه عملیات جمع‌آوری داده")
    print("=" * 60)
    print(f"تعداد کل ردیف‌های جمع‌آوری‌شده: {len(combined_df):,}")
    print(f"بازه زمانی پوشش‌داده‌شده:")
    print(f"  شروع: {min_date.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  پایان: {max_date.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"تعداد قطعات (Chunks) دریافت‌شده: {chunk_count}")
    print(f"تعداد درخواست‌های ناموفق: {failed_chunks}")
    print(f"تعداد رکوردهای تکراری حذف‌شده: {removed_duplicates}")
    print("=" * 60)

    return combined_df


if __name__ == "__main__":
    # اجرای مستقیم اسکریپت برای جمع‌آوری ۱۸۰ روز داده ۱ ساعته BTCIRT
    df = collect_historical_data(
        symbol="BTCIRT",
        timeframe="1h",
        days=180,
        output_path="data/btcirt_180d.csv"
    )
    
    if df is not None:
        print(f"\n✅ موفقیت‌آمیز! {len(df)} کندل آماده استفاده است.")
    else:
        print("\n❌ جمع‌آوری داده با شکست مواجه شد.")
