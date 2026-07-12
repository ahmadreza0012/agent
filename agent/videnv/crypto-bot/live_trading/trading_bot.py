"""
Paper Trading Bot - ربات معاملات کاغذی

این ماژول یک شبیه‌ساز معاملات است که:
- قیمت‌های لحظه‌ای را از API عمومی نوبیتکس دریافت می‌کند
- سیگنال‌های استراتژی را محاسبه می‌کند
- تصمیمات خرید/فروش را به صورت شبیه‌سازی شده اجرا می‌کند
- هیچ پول واقعی درگیر نیست و هیچ سفارشی به صرافی ارسال نمی‌شود

ویژگی‌ها:
- پیگیری موجودی و موقعیت‌ها
- حد ضرر روزانه (daily loss limit)
- ثبت تمام تصمیمات با جزئیات
- گزارش‌گیری کامل
"""

import time
from datetime import datetime, date
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field
import logging

from utils.nobitex_data_collector import fetch_historical_data
from strategy.moving_average import apply_moving_average_strategy


@dataclass
class Trade:
    """نمایش یک معامله انجام شده."""
    timestamp: datetime
    action: str  # "BUY" یا "SELL"
    price: float
    units: float
    total_value: float
    commission: float
    slippage: float
    reason: str  # چرا این معامله انجام شد؟
    pnl: float = 0.0  # فقط برای معاملات فروش


@dataclass
class DailyStats:
    """آمار روزانه برای بررسی حد ضرر روزانه."""
    date: date
    trades_count: int = 0
    daily_pnl: float = 0.0
    max_loss_reached: bool = False


class PaperTradingBot:
    """
    ربات معاملات کاغذی که استراتژی را روی داده زنده شبیه‌سازی می‌کند.
    
    ⚠️ توجه: این ربات هیچ سفارش واقعی ارسال نمی‌کند!
    """
    
    def __init__(
        self,
        starting_balance: float = 10_000_000,
        polling_interval_seconds: int = 300,
        short_window: int = 9,
        long_window: int = 21,
        max_position_size_pct: float = 1.0,
        stop_loss_pct: Optional[float] = None,
        take_profit_pct: Optional[float] = None,
        daily_loss_limit_pct: float = 0.05,
        commission_pct: float = 0.0025,
        slippage_pct: float = 0.001,
        logger: Optional[logging.Logger] = None,
    ):
        """
        مقداردهی اولیه ربات معاملات کاغذی.
        
        Args:
            starting_balance: موجودی اولیه به تومان
            polling_interval_seconds: فاصله زمانی بین هر بار چک کردن قیمت
            short_window: دوره میانگین متحرک کوتاه‌مدت
            long_window: دوره میانگین متحرک بلندمدت
            max_position_size_pct: حداکثر درصد سرمایه در هر معامله
            stop_loss_pct: درصد حد ضرر
            take_profit_pct: درصد حد سود
            daily_loss_limit_pct: حد ضرر روزانه
            commission_pct: کارمزد هر معامله
            slippage_pct: لغزش قیمت
            logger: لاگر برای ثبت رویدادها
        """
        self.starting_balance = starting_balance
        self.balance = starting_balance
        self.polling_interval = polling_interval_seconds
        
        # پارامترهای استراتژی
        self.short_window = short_window
        self.long_window = long_window
        
        # پارامترهای ریسک
        self.max_position_size_pct = max_position_size_pct
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.daily_loss_limit_pct = daily_loss_limit_pct
        
        # پارامترهای هزینه
        self.commission_pct = commission_pct
        self.slippage_pct = slippage_pct
        
        # وضعیت فعلی
        self.position_open = False
        self.entry_price = 0.0
        self.units_held = 0.0
        self.entry_timestamp = None
        
        # تاریخچه معاملات
        self.trades: List[Trade] = []
        
        # آمار روزانه
        self.current_date = None
        self.daily_stats: Dict[date, DailyStats] = {}
        
        # داده‌های تاریخی برای محاسبه میانگین
        self.price_history: List[Dict[str, Any]] = []
        self.min_history_length = long_window + 5  # حداقل داده برای محاسبه سیگنال
        
        # لاگر
        self.logger = logger or logging.getLogger(__name__)
        
        self.logger.info(
            f"ربات معاملات کاغذی راه‌اندازی شد:\n"
            f"  موجودی اولیه: {starting_balance:,.0f} تومان\n"
            f"  فاصله polling: {polling_interval_seconds} ثانیه\n"
            f"  استراتژی: MA({short_window}/{long_window})\n"
            f"  حد ضرر روزانه: {daily_loss_limit_pct*100:.1f}%"
        )
    
    def _fetch_current_price(self) -> Optional[float]:
        """
        دریافت آخرین قیمت از نوبیتکس.
        
        Returns:
            قیمت فعلی یا None در صورت خطا
        """
        try:
            # دریافت ۱ کندل آخر (آخرین قیمت)
            df = fetch_historical_data(
                symbol="BTCIRT",
                timeframe="1h",
                days=1,  # فقط داده امروز
            )
            
            if len(df) == 0:
                self.logger.warning("داده‌ای از نوبیتکس دریافت نشد")
                return None
            
            last_row = df.iloc[-1]
            price = last_row["close"]
            
            # ذخیره در تاریخچه
            self.price_history.append({
                "timestamp": last_row["timestamp"],
                "close": price,
                "high": last_row["high"],
                "low": last_row["low"],
                "open": last_row["open"],
                "volume": last_row["volume"],
            })
            
            # محدود کردن اندازه تاریخچه
            if len(self.price_history) > self.long_window * 2:
                self.price_history = self.price_history[-self.long_window * 2:]
            
            return price
            
        except Exception as e:
            self.logger.error(f"خطا در دریافت قیمت: {str(e)}")
            return None
    
    def _calculate_signal(self) -> Optional[int]:
        """
        محاسبه سیگنال بر اساس استراتژی میانگین متحرک.
        
        Returns:
            1 برای خرید، -1 برای فروش، 0 برای بدون تغییر، None برای داده ناکافی
        """
        if len(self.price_history) < self.min_history_length:
            return None
        
        # تبدیل به DataFrame برای محاسبه استراتژی
        import pandas as pd
        df = pd.DataFrame(self.price_history)
        
        try:
            df = apply_moving_average_strategy(
                df,
                short_window=self.short_window,
                long_window=self.long_window,
            )
            
            # گرفتن آخرین سیگنال
            last_position = df.iloc[-1]["position"]
            
            if pd.isna(last_position):
                return 0
            
            return int(last_position)
            
        except Exception as e:
            self.logger.error(f"خطا در محاسبه سیگنال: {str(e)}")
            return None
    
    def _check_daily_loss_limit(self) -> bool:
        """
        بررسی اینکه آیا حد ضرر روزانه رسیده است.
        
        Returns:
            True اگر حد ضرر رسیده باشد، False otherwise
        """
        today = date.today()
        
        if self.current_date != today:
            # شروع روز جدید
            self.current_date = today
            if today not in self.daily_stats:
                self.daily_stats[today] = DailyStats(date=today)
        
        stats = self.daily_stats[today]
        
        # محاسبه ضرر روزانه
        daily_loss_pct = abs(stats.daily_pnl) / self.starting_balance if stats.daily_pnl < 0 else 0
        
        if daily_loss_pct >= self.daily_loss_limit_pct:
            if not stats.max_loss_reached:
                self.logger.warning(
                    f"⚠️ حد ضرر روزانه رسید! "
                    f"ضرر امروز: {stats.daily_pnl:,.0f} تومان ({daily_loss_pct*100:.2f}%)"
                )
                stats.max_loss_reached = True
            return True
        
        return False
    
    def _execute_buy(self, price: float, reason: str) -> None:
        """اجرای شبیه‌سازی شده خرید."""
        # محاسبه قیمت اجرا با احتساب لغزش
        execution_price = price * (1 + self.slippage_pct)
        
        # محاسبه کارمزد
        allocated_capital = self.balance * self.max_position_size_pct
        commission = allocated_capital * self.commission_pct
        
        # محاسبه تعداد واحد قابل خرید
        total_cost = allocated_capital + commission
        self.units_held = allocated_capital / execution_price
        
        # کسر از موجودی
        self.balance -= commission
        
        # ثبت معامله
        trade = Trade(
            timestamp=datetime.now(),
            action="BUY",
            price=execution_price,
            units=self.units_held,
            total_value=total_cost,
            commission=commission,
            slippage=allocated_capital * self.slippage_pct,
            reason=reason,
        )
        self.trades.append(trade)
        
        # بروزرسانی وضعیت
        self.position_open = True
        self.entry_price = execution_price
        self.entry_timestamp = datetime.now()
        
        self.logger.info(
            f"🟢 BUY شبیه‌سازی شد @ {execution_price:,.0f} تومان | "
            f"واحد: {self.units_held:.6f} | کارمزد: {commission:,.0f}"
        )
    
    def _execute_sell(self, price: float, reason: str) -> None:
        """اجرای شبیه‌سازی شده فروش."""
        if not self.position_open:
            return
        
        # محاسبه قیمت اجرا با احتساب لغزش
        execution_price = price * (1 - self.slippage_pct)
        
        # محاسبه ارزش فروش
        gross_value = self.units_held * execution_price
        commission = gross_value * self.commission_pct
        net_value = gross_value - commission
        
        # محاسبه سود/زیان
        cost_basis = self.units_held * self.entry_price
        pnl = net_value - cost_basis
        
        # اضافه کردن به موجودی
        self.balance += net_value
        
        # ثبت معامله
        trade = Trade(
            timestamp=datetime.now(),
            action="SELL",
            price=execution_price,
            units=self.units_held,
            total_value=net_value,
            commission=commission,
            slippage=self.units_held * execution_price * self.slippage_pct,
            reason=reason,
            pnl=pnl,
        )
        self.trades.append(trade)
        
        # بروزرسانی آمار روزانه
        today = date.today()
        if today not in self.daily_stats:
            self.daily_stats[today] = DailyStats(date=today)
        self.daily_stats[today].trades_count += 1
        self.daily_stats[today].daily_pnl += pnl
        
        # بروزرسانی وضعیت
        pnl_pct = (pnl / cost_basis) * 100 if cost_basis > 0 else 0
        self.logger.info(
            f"🔴 SELL شبیه‌سازی شد @ {execution_price:,.0f} تومان | "
            f"PnL: {pnl:,.0f} تومان ({pnl_pct:+.2f}%) | کارمزد: {commission:,.0f}"
        )
        
        self.position_open = False
        self.entry_price = 0.0
        self.units_held = 0.0
        self.entry_timestamp = None
    
    def _check_stop_loss_take_profit(self, current_price: float) -> Optional[str]:
        """
        بررسی شرایط حد ضرر و حد سود.
        
        Returns:
            دلیل خروج اگر شرایط برقرار باشد، None otherwise
        """
        if not self.position_open:
            return None
        
        pnl_pct = (current_price - self.entry_price) / self.entry_price
        
        # بررسی حد ضرر
        if self.stop_loss_pct and pnl_pct <= -self.stop_loss_pct:
            return f"Stop Loss ({pnl_pct*100:.2f}%)"
        
        # بررسی حد سود
        if self.take_profit_pct and pnl_pct >= self.take_profit_pct:
            return f"Take Profit ({pnl_pct*100:.2f}%)"
        
        return None
    
    def run(self) -> None:
        """
        حلقه اصلی ربات معاملات کاغذی.
        
        این تابع تا زمانی که کاربر Ctrl+C نزند ادامه می‌یابد.
        """
        self.logger.info("شروع حلقه معاملات...")
        
        while True:
            try:
                # دریافت قیمت فعلی
                current_price = self._fetch_current_price()
                
                if current_price is None:
                    self.logger.warning("قیمت دریافت نشد، منتظر دور بعدی...")
                    time.sleep(self.polling_interval)
                    continue
                
                self.logger.debug(f"قیمت فعلی: {current_price:,.0f} تومان")
                
                # بررسی حد ضرر/سود برای موقعیت باز
                if self.position_open:
                    exit_reason = self._check_stop_loss_take_profit(current_price)
                    if exit_reason:
                        self._execute_sell(current_price, exit_reason)
                        time.sleep(self.polling_interval)
                        continue
                
                # بررسی حد ضرر روزانه
                if self._check_daily_loss_limit():
                    self.logger.info("معامله جدید به دلیل رسیدن به حد ضرر روزانه مسدود شد")
                    time.sleep(self.polling_interval)
                    continue
                
                # محاسبه سیگنال
                signal = self._calculate_signal()
                
                if signal is None:
                    self.logger.debug("داده کافی برای محاسبه سیگنال نیست")
                elif signal == 1 and not self.position_open:
                    # سیگنال خرید
                    self._execute_buy(current_price, "MA Crossover (Golden Cross)")
                elif signal == -1 and self.position_open:
                    # سیگنال فروش
                    self._execute_sell(current_price, "MA Crossover (Death Cross)")
                else:
                    self.logger.debug("بدون سیگنال جدید")
                
                # انتظار برای دور بعدی
                time.sleep(self.polling_interval)
                
            except KeyboardInterrupt:
                raise
            except Exception as e:
                self.logger.error(f"خطا در حلقه اصلی: {str(e)}", exc_info=True)
                time.sleep(self.polling_interval)
    
    def print_final_report(self) -> None:
        """چاپ گزارش نهایی معاملات."""
        print("\n" + "=" * 70)
        print("گزارش نهایی معاملات کاغذی")
        print("=" * 70)
        
        if len(self.trades) == 0:
            print("هیچ معامله‌ای انجام نشد.")
            return
        
        # محاسبه آمار
        total_trades = len(self.trades)
        buy_trades = [t for t in self.trades if t.action == "BUY"]
        sell_trades = [t for t in self.trades if t.action == "SELL"]
        
        completed_trades = len(sell_trades)
        winning_trades = sum(1 for t in sell_trades if t.pnl > 0)
        losing_trades = sum(1 for t in sell_trades if t.pnl <= 0)
        
        total_pnl = sum(t.pnl for t in sell_trades)
        total_commission = sum(t.commission for t in self.trades)
        total_slippage = sum(t.slippage for t in self.trades)
        
        win_rate = (winning_trades / completed_trades * 100) if completed_trades > 0 else 0
        
        # محاسبه سرمایه نهایی
        final_balance = self.balance
        if self.position_open:
            # اضافه کردن ارزش موقعیت باز (فرضی)
            unrealized_value = self.units_held * self.price_history[-1]["close"] if self.price_history else 0
            final_balance += unrealized_value
        
        total_return_pct = ((final_balance - self.starting_balance) / self.starting_balance) * 100
        
        print(f"موجودی اولیه:          {self.starting_balance:,.0f} تومان")
        print(f"موجودی نهایی:           {final_balance:,.0f} تومان")
        print(f"بازده کل:               {total_return_pct:+.2f}%")
        print("-" * 70)
        print(f"تعداد کل معاملات:       {total_trades}")
        print(f"معاملات خرید:           {len(buy_trades)}")
        print(f"معاملات فروش:           {len(sell_trades)}")
        print(f"معاملات کامل:           {completed_trades}")
        print(f"معاملات برنده:          {winning_trades}")
        print(f"معاملات بازنده:         {losing_trades}")
        print(f"درصد برد:               {win_rate:.1f}%")
        print("-" * 70)
        print(f"سود/زیان خالص:          {total_pnl:,.0f} تومان")
        print(f"مجموع کارمزدها:         {total_commission:,.0f} تومان")
        print(f"مجموع لغزش قیمت:       {total_slippage:,.0f} تومان")
        
        if self.position_open:
            print("-" * 70)
            print(f"⚠️ موقعیت باز:")
            print(f"   قیمت ورود: {self.entry_price:,.0f}")
            print(f"   واحد: {self.units_held:.6f}")
            current_val = self.units_held * (self.price_history[-1]["close"] if self.price_history else 0)
            print(f"   ارزش فعلی: ~{current_val:,.0f} تومان")
        
        print("=" * 70)
        
        # نمایش جزئیات معاملات
        if self.trades:
            print("\nجزئیات معاملات:")
            print("-" * 70)
            for i, trade in enumerate(self.trades[-10:], 1):  # آخرین ۱۰ معامله
                pnl_str = f"PnL: {trade.pnl:,.0f}" if trade.action == "SELL" else ""
                print(f"{i}. {trade.timestamp.strftime('%Y-%m-%d %H:%M')} | {trade.action} @ {trade.price:,.0f} | {pnl_str} | {trade.reason}")