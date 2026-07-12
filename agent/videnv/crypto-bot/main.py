"""
ورودی اصلی ربات معاملاتی

این اسکریپت نقطه شروع برنامه است و حالت‌های مختلف اجرا را مدیریت می‌کند:
- backtest: اجرای بک‌تست روی داده تاریخی
- paper: اجرای معاملات کاغذی (شبیه‌سازی شده بدون پول واقعی)

⚠️ توجه: حالت live_trading با پول واقعی عمداً پیاده‌سازی نشده است.
"""

import argparse
import sys
import time
from datetime import datetime

from config.settings import Config
from utils.logger import get_logger
from backtest.backtester import run_backtest, print_report
from strategy.moving_average import apply_moving_average_strategy
from utils.nobitex_data_collector import fetch_historical_data


def run_backtest_mode(config: Config, logger) -> None:
    """اجرای حالت بک‌تست."""
    logger.info("شروع حالت بک‌تست...")
    
    # دریافت داده تاریخی
    logger.info(f"در حال دریافت داده {config.exchange.symbol} برای بک‌تست...")
    df = fetch_historical_data(
        symbol=config.exchange.symbol.replace("/", ""),
        timeframe=config.exchange.timeframe,
        days=90,  # ۹۰ روز داده برای بک‌تست
    )
    
    if len(df) == 0:
        logger.error("داده‌ای دریافت نشد.")
        return
    
    logger.info(f"{len(df)} کندل دریافت شد.")
    
    # اعمال استراتژی
    logger.info("اعمال استراتژی میانگین متحرک...")
    df = apply_moving_average_strategy(
        df,
        short_window=config.strategy.short_window,
        long_window=config.strategy.long_window,
    )
    
    # اجرای بک‌تست
    logger.info("اجرای بک‌تست...")
    results = run_backtest(
        df,
        initial_capital=config.backtest.initial_capital,
        commission_pct=config.backtest.commission_pct,
        slippage_pct=config.backtest.slippage_pct,
        position_size_pct=config.risk.max_position_size_pct,
    )
    
    # نمایش گزارش
    print_report(results)
    
    logger.info("بک‌تست کامل شد.")


def run_paper_trading_mode(config: Config, logger) -> None:
    """اجرای حالت معاملات کاغذی (Paper Trading)."""
    logger.info("شروع حالت معاملات کاغذی...")
    
    from live_trading.trading_bot import PaperTradingBot
    
    # ایجاد بات معاملات کاغذی
    bot = PaperTradingBot(
        starting_balance=config.paper_trading.starting_balance,
        polling_interval_seconds=config.paper_trading.polling_interval_seconds,
        short_window=config.strategy.short_window,
        long_window=config.strategy.long_window,
        max_position_size_pct=config.risk.max_position_size_pct,
        stop_loss_pct=config.risk.stop_loss_pct,
        take_profit_pct=config.risk.take_profit_pct,
        daily_loss_limit_pct=config.risk.daily_loss_limit_pct,
        commission_pct=config.backtest.commission_pct,
        slippage_pct=config.backtest.slippage_pct,
        logger=logger,
    )
    
    logger.info(f"معاملات کاغذی شروع شد. موجودی اولیه: {config.paper_trading.starting_balance:,.0f} تومان")
    logger.info(f"هر {config.paper_trading.polling_interval_seconds} ثانیه قیمت چک می‌شود.")
    logger.info("برای توقف، کلید Ctrl+C را فشار دهید.")
    
    try:
        bot.run()
    except KeyboardInterrupt:
        logger.info("توسط کاربر متوقف شد.")
        
        # نمایش گزارش نهایی
        print("\n" + "=" * 60)
        print("گزارش نهایی معاملات کاغذی")
        print("=" * 60)
        bot.print_final_report()


def main():
    """تابع اصلی ورودی برنامه."""
    parser = argparse.ArgumentParser(
        description="ربات معاملاتی مبتنی بر میانگین متحرک",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
مثال‌ها:
  python main.py --mode=backtest
  python main.py --mode=paper
  python main.py --mode=paper --log-level=DEBUG
        """,
    )
    
    parser.add_argument(
        "--mode",
        type=str,
        choices=["backtest", "paper"],
        default="backtest",
        help="حالت اجرا: backtest یا paper (پیش‌فرض: backtest)"
    )
    
    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="سطح لاگ (پیش‌فرض: INFO)"
    )
    
    parser.add_argument(
        "--config-file",
        type=str,
        default=None,
        help="مسیر فایل تنظیمات اضافی (اختیاری)"
    )
    
    args = parser.parse_args()
    
    # بارگذاری تنظیمات
    config = Config.load()
    
    # تنظیم سطح لاگ از خط فرمان
    config.logger.level = args.log_level
    
    # ایجاد logger
    logger = get_logger("main")
    logger.info(f"ربات معاملاتی شروع شد - حالت: {args.mode}")
    logger.info(f"تنظیمات بارگذاری شد: short_window={config.strategy.short_window}, long_window={config.strategy.long_window}")
    
    # انتخاب حالت اجرا
    if args.mode == "backtest":
        run_backtest_mode(config, logger)
    elif args.mode == "paper":
        run_paper_trading_mode(config, logger)
    else:
        logger.error(f"حالت نامعتبر: {args.mode}")
        sys.exit(1)
    
    logger.info("پایان اجرا.")


if __name__ == "__main__":
    main()