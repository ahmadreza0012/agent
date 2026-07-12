"""
تنظیمات پیکربندی ربات معاملاتی

این ماژول تمام پارامترهای قابل تنظیم را از متغیرهای محیطی یا مقادیر پیش‌فرض بارگذاری می‌کند.
برای امنیت، هیچ کلید API یا رمز عبوری نباید در این فایل هاردکد شود.
"""

import os
from typing import Optional, Dict, Any
from dataclasses import dataclass, field


@dataclass
class StrategyConfig:
    """پیکربندی استراتژی معاملاتی."""
    short_window: int = 9  # دوره میانگین متحرک کوتاه‌مدت
    long_window: int = 21  # دوره میانگین متحرک بلندمدت
    
    def __post_init__(self):
        if self.short_window >= self.long_window:
            raise ValueError("short_window باید کوچکتر از long_window باشد")
        if self.short_window < 2:
            raise ValueError("short_window باید حداقل 2 باشد")


@dataclass
class RiskConfig:
    """پیکربندی مدیریت ریسک."""
    max_position_size_pct: float = 1.0  # حداکثر درصد سرمایه در هر معامله (پیش‌فرض ۱۰۰٪)
    stop_loss_pct: Optional[float] = None  # درصد حد ضرر (مثلا 0.05 یعنی 5%)
    take_profit_pct: Optional[float] = None  # درصد حد سود (مثلا 0.10 یعنی 10%)
    daily_loss_limit_pct: float = 0.05  # حد ضرر روزانه (پیش‌فرض 5%)
    max_daily_trades: int = 10  # حداکثر تعداد معاملات در روز
    
    def __post_init__(self):
        if not 0 < self.max_position_size_pct <= 1.0:
            raise ValueError("max_position_size_pct باید بین 0 و 1 باشد")
        if self.stop_loss_pct is not None and self.stop_loss_pct <= 0:
            raise ValueError("stop_loss_pct باید مثبت باشد")
        if self.take_profit_pct is not None and self.take_profit_pct <= 0:
            raise ValueError("take_profit_pct باید مثبت باشد")
        if not 0 < self.daily_loss_limit_pct <= 1.0:
            raise ValueError("daily_loss_limit_pct باید بین 0 و 1 باشد")


@dataclass
class BacktestConfig:
    """پیکربندی بک‌تست."""
    initial_capital: float = 10_000_000  # سرمایه اولیه به تومان
    commission_pct: float = 0.0025  # کارمزد هر معامله (0.25%)
    slippage_pct: float = 0.001  # لغزش قیمت (0.1%)


@dataclass
class ExchangeConfig:
    """پیکربندی اتصال به صرافی."""
    # نام صرافی (برای CCXT)
    exchange_name: str = "nobitex"
    
    # جفت ارز
    symbol: str = "BTC/IRT"  # یا "BTCIRT" برای Nobitex
    
    # تایم‌فریم
    timeframe: str = "1h"
    
    # تنظیمات خاص Nobitex
    nobitex_base_url: str = "https://apiv2.nobitex.ir"
    
    # ⚠️ هشدار: هرگز API Key را در این فایل هاردکد نکنید
    # این مقادیر باید از متغیرهای محیطی خوانده شوند
    api_key: Optional[str] = field(default=None, repr=False)
    api_secret: Optional[str] = field(default=None, repr=False)
    
    def __post_init__(self):
        # برای paper trading، نیازی به API Key نیست
        pass


@dataclass
class PaperTradingConfig:
    """پیکربندی معاملات کاغذی (شبیه‌سازی شده)."""
    enabled: bool = True
    polling_interval_seconds: int = 300  # هر چند ثانیه قیمت چک شود (پیش‌فرض 5 دقیقه)
    starting_balance: float = 10_000_000  # موجودی شروع شبیه‌سازی
    log_all_decisions: bool = True  # ثبت تمام تصمیمات در لاگ


@dataclass
class LoggerConfig:
    """پیکربندی سیستم لاگ."""
    level: str = "INFO"  # DEBUG, INFO, WARNING, ERROR
    console_enabled: bool = True
    file_enabled: bool = True
    log_directory: str = "logs"
    max_file_size_mb: int = 10  # حداکثر حجم هر فایل لاگ
    backup_count: int = 5  # تعداد فایل‌های لاگ قدیمی که نگهداری می‌شوند
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


class Config:
    """
    کلاس اصلی پیکربندی که تمام تنظیمات را یکجا فراهم می‌کند.
    
    استفاده:
        config = Config.load()
        print(config.strategy.short_window)
        print(config.risk.max_position_size_pct)
    """
    
    def __init__(
        self,
        strategy: StrategyConfig,
        risk: RiskConfig,
        backtest: BacktestConfig,
        exchange: ExchangeConfig,
        paper_trading: PaperTradingConfig,
        logger: LoggerConfig,
    ):
        self.strategy = strategy
        self.risk = risk
        self.backtest = backtest
        self.exchange = exchange
        self.paper_trading = paper_trading
        self.logger = logger
    
    @classmethod
    def load(cls) -> "Config":
        """
        بارگذاری تنظیمات از متغیرهای محیطی با fallback به مقادیر پیش‌فرض.
        
        متغیرهای محیطی پشتیبانی شده:
        - STRATEGY_SHORT_WINDOW
        - STRATEGY_LONG_WINDOW
        - RISK_MAX_POSITION_SIZE_PCT
        - RISK_STOP_LOSS_PCT
        - RISK_TAKE_PROFIT_PCT
        - RISK_DAILY_LOSS_LIMIT_PCT
        - BACKTEST_INITIAL_CAPITAL
        - BACKTEST_COMMISSION_PCT
        - BACKTEST_SLIPPAGE_PCT
        - EXCHANGE_SYMBOL
        - EXCHANGE_TIMEFRAME
        - PAPER_TRADING_POLLING_INTERVAL
        - LOG_LEVEL
        """
        
        # Helper function برای خواندن ایمن از environment
        def get_env(key: str, default: Any, converter: type = None):
            value = os.environ.get(key)
            if value is None:
                return default
            if converter:
                try:
                    return converter(value)
                except (ValueError, TypeError):
                    return default
            return value
        
        # بارگذاری استراتژی
        strategy = StrategyConfig(
            short_window=get_env("STRATEGY_SHORT_WINDOW", 9, int),
            long_window=get_env("STRATEGY_LONG_WINDOW", 21, int),
        )
        
        # بارگذاری ریسک
        stop_loss_raw = get_env("RISK_STOP_LOSS_PCT", None, float)
        take_profit_raw = get_env("RISK_TAKE_PROFIT_PCT", None, float)
        
        risk = RiskConfig(
            max_position_size_pct=get_env("RISK_MAX_POSITION_SIZE_PCT", 1.0, float),
            stop_loss_pct=stop_loss_raw,
            take_profit_pct=take_profit_raw,
            daily_loss_limit_pct=get_env("RISK_DAILY_LOSS_LIMIT_PCT", 0.05, float),
            max_daily_trades=get_env("RISK_MAX_DAILY_TRADES", 10, int),
        )
        
        # بارگذاری بک‌تست
        backtest = BacktestConfig(
            initial_capital=get_env("BACKTEST_INITIAL_CAPITAL", 10_000_000, float),
            commission_pct=get_env("BACKTEST_COMMISSION_PCT", 0.0025, float),
            slippage_pct=get_env("BACKTEST_SLIPPAGE_PCT", 0.001, float),
        )
        
        # بارگذاری صرافی
        # ⚠️ توجه: API Key و Secret فقط از environment خوانده می‌شوند
        # و هرگز در این فایل ذخیره نمی‌شوند
        exchange = ExchangeConfig(
            exchange_name=get_env("EXCHANGE_NAME", "nobitex"),
            symbol=get_env("EXCHANGE_SYMBOL", "BTC/IRT"),
            timeframe=get_env("EXCHANGE_TIMEFRAME", "1h"),
            api_key=os.environ.get("EXCHANGE_API_KEY"),  # اختیاری برای paper trading
            api_secret=os.environ.get("EXCHANGE_API_SECRET"),  # اختیاری برای paper trading
        )
        
        # بارگذاری paper trading
        paper_trading = PaperTradingConfig(
            enabled=True,
            polling_interval_seconds=get_env("PAPER_TRADING_POLLING_INTERVAL", 300, int),
            starting_balance=get_env("PAPER_TRADING_STARTING_BALANCE", 10_000_000, float),
            log_all_decisions=True,
        )
        
        # بارگذاری لاگ
        logger_config = LoggerConfig(
            level=get_env("LOG_LEVEL", "INFO"),
            console_enabled=True,
            file_enabled=True,
            log_directory="logs",
            max_file_size_mb=10,
            backup_count=5,
        )
        
        return cls(
            strategy=strategy,
            risk=risk,
            backtest=backtest,
            exchange=exchange,
            paper_trading=paper_trading,
            logger=logger_config,
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """تبدیل تمام تنظیمات به دیکشنری برای نمایش یا لاگ."""
        return {
            "strategy": {
                "short_window": self.strategy.short_window,
                "long_window": self.strategy.long_window,
            },
            "risk": {
                "max_position_size_pct": self.risk.max_position_size_pct,
                "stop_loss_pct": self.risk.stop_loss_pct,
                "take_profit_pct": self.risk.take_profit_pct,
                "daily_loss_limit_pct": self.risk.daily_loss_limit_pct,
                "max_daily_trades": self.risk.max_daily_trades,
            },
            "backtest": {
                "initial_capital": self.backtest.initial_capital,
                "commission_pct": self.backtest.commission_pct,
                "slippage_pct": self.backtest.slippage_pct,
            },
            "exchange": {
                "exchange_name": self.exchange.exchange_name,
                "symbol": self.exchange.symbol,
                "timeframe": self.exchange.timeframe,
                # API keys intentionally excluded from output for security
            },
            "paper_trading": {
                "enabled": self.paper_trading.enabled,
                "polling_interval_seconds": self.paper_trading.polling_interval_seconds,
                "starting_balance": self.paper_trading.starting_balance,
            },
            "logger": {
                "level": self.logger.level,
                "log_directory": self.logger.log_directory,
            },
        }


# نمونه استفاده
if __name__ == "__main__":
    import json
    
    config = Config.load()
    print("تنظیمات فعلی:")
    print(json.dumps(config.to_dict(), indent=2, ensure_ascii=False))