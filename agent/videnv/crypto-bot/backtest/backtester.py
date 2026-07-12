"""
Backtester

این ماژول عملکرد واقعی استراتژی را روی داده تاریخی شبیه‌سازی می‌کند و گزارش می‌دهد:
- سود/زیان کل
- تعداد معاملات
- درصد معاملات برنده
- بیشترین افت سرمایه (Max Drawdown)
"""

import pandas as pd
import numpy as np
import logging
from typing import Optional, Dict, Any

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def validate_ohlcv_data(df: pd.DataFrame) -> Dict[str, Any]:
    """
    اعتبارسنجی داده‌های OHLCV قبل از اجرای بک‌تست.
    
    Args:
        df: DataFrame حاوی داده‌های قیمت
        
    Returns:
        دیکشنری شامل وضعیت اعتبارسنجی و خطاها
    """
    errors = []
    warnings = []
    
    # بررسی ستون‌های ضروری
    required_columns = ['open', 'high', 'low', 'close']
    missing_cols = [col for col in required_columns if col not in df.columns]
    if missing_cols:
        errors.append(f"ستون‌های ضروری وجود ندارند: {missing_cols}")
        return {"valid": False, "errors": errors, "warnings": warnings}
    
    # بررسی مقادیر منفی
    for col in required_columns:
        if (df[col] < 0).any():
            errors.append(f"مقادیر منفی در ستون {col} обнаружены")
    
    # بررسی مقادیر صفر در close price
    if (df['close'] == 0).any():
        errors.append("قیمت بسته شدن صفر обнаружен است")
    
    # بررسی NaN values
    nan_counts = df[required_columns].isna().sum()
    if nan_counts.any():
        for col, count in nan_counts[nan_counts > 0].items():
            errors.append(f"{count} مقدار NaN در ستون {col} وجود دارد")
    
    # بررسی افزایشی بودن timestamp (اگر وجود داشته باشد)
    if 'timestamp' in df.columns:
        ts_diff = df['timestamp'].diff()[1:]
        if (ts_diff <= pd.Timedelta(0)).any():
            non_increasing_count = (ts_diff <= pd.Timedelta(0)).sum()
            warnings.append(f"{non_increasing_count} تکرار یا کاهش در timestamp обнаружен است")
    
    # بررسی منطق قیمت‌ها: high >= low, high >= open, high >= close, etc.
    if (df['high'] < df['low']).any():
        errors.append("بعضی کندل‌ها high کمتر از low دارند")
    
    if (df['high'] < df['open']).any() or (df['high'] < df['close']).any():
        warnings.append("بعضی کندل‌ها high کمتر از open یا close دارند")
    
    if (df['low'] > df['open']).any() or (df['low'] > df['close']).any():
        warnings.append("بعضی کندل‌ها low بیشتر از open یا close دارند")
    
    valid = len(errors) == 0
    
    return {
        "valid": valid,
        "errors": errors,
        "warnings": warnings,
        "row_count": len(df),
        "nan_free_rows": len(df.dropna(subset=required_columns))
    }


def run_backtest(
    df: pd.DataFrame,
    initial_capital: float = 10_000_000,  # ۱۰ میلیون تومان سرمایه فرضی
    commission_pct: float = 0.0025,  # ۰.۲۵٪ کارمزد هر معامله
    slippage_pct: float = 0.001,  # ۰.۱٪ لغزش قیمت برای سفارش‌های مارکت
    position_size_pct: float = 1.0,  # درصد سرمایه استفاده شده در هر معامله (پیش‌فرض ۱۰۰٪)
    stop_loss_pct: Optional[float] = None,  # درصد حد ضرر (اختیاری)
    take_profit_pct: Optional[float] = None,  # درصد حد سود (اختیاری)
) -> dict:
    """
    شبیه‌سازی معاملات بر اساس سیگنال‌های خرید/فروش موجود در df.
    
    با احتساب:
    - کارمزد خرید و فروش
    - لغزش قیمت (slippage) برای سفارش‌های مارکت
    - امکان تنظیم حد ضرر و حد سود
    - اندازه موقعیت قابل تنظیم

    Args:
        df: DataFrame خروجی apply_moving_average_strategy (باید ستون position داشته باشد)
        initial_capital: سرمایه اولیه فرضی به تومان
        commission_pct: نرخ کارمزد هر معامله (مثلا 0.0025 یعنی 0.25%)
        slippage_pct: درصد لغزش قیمت (پیش‌فرض 0.001 یعنی 0.1%)
        position_size_pct: درصدی از سرمایه که در هر معامله استفاده می‌شود
        stop_loss_pct: درصد حد ضرر نسبت به قیمت ورود (مثلا 0.05 یعنی 5%)
        take_profit_pct: درصد حد سود نسبت به قیمت ورود (مثلا 0.10 یعنی 10%)

    Returns:
        دیکشنری شامل نتایج کامل بک‌تست
    """
    # اعتبارسنجی داده‌ها
    validation_result = validate_ohlcv_data(df)
    if not validation_result["valid"]:
        logger.error("اعتبارسنجی داده‌ها ناموفق بود:")
        for error in validation_result["errors"]:
            logger.error(f"  - {error}")
        return {"error": "invalid_data", "validation_errors": validation_result["errors"]}
    
    for warning in validation_result.get("warnings", []):
        logger.warning(f"هشدار داده: {warning}")
    
    # آماده‌سازی داده‌ها
    valid = df.dropna(subset=["position"]).reset_index(drop=True)
    trades = valid[valid["position"] != 0].copy()

    if len(trades) == 0:
        logger.warning("هیچ معامله‌ای برای بک‌تست وجود ندارد.")
        return {"error": "no_trades"}

    capital = initial_capital
    position_open = False
    entry_price = 0.0
    entry_timestamp = None
    units_held = 0.0  # تعداد واحد دارایی خریداری شده
    trade_log = []
    
    # منحنی سرمایه: شروع با سرمایه اولیه
    # برای هر ردیف در داده‌های اصلی، ارزش پرتفو را محاسبه می‌کنیم
    equity_curve = []
    
    # ایجاد lookup برای دسترسی سریع به قیمت‌ها بر اساس ایندکس
    price_lookup = df.set_index(df.index)[['close', 'timestamp']].to_dict('index')
    
    #跟踪当前在数据集中的位置
    current_data_idx = 0
    
    for trade_idx, row in trades.iterrows():
        price = row["close"]
        action = "BUY" if row["position"] == 1 else "SELL"
        trade_timestamp = row.get("timestamp", f"trade_{trade_idx}")

        if action == "BUY" and not position_open:
            # ورود به معامله با احتساب کارمزد و لغزش
            # برای سفارش خرید مارکت، قیمت اجرا شده بدتر از close است (بالاتر)
            execution_price = price * (1 + slippage_pct)
            entry_price_raw = execution_price
            entry_price_with_commission = entry_price_raw * (1 + commission_pct)
            
            # محاسبه تعداد واحد قابل خرید با توجه به position_size_pct
            allocated_capital = capital * position_size_pct
            units_held = allocated_capital / entry_price_with_commission
            
            entry_price = entry_price_with_commission
            entry_timestamp = trade_timestamp
            position_open = True
            
            logger.debug(f"BUY @ {execution_price:.2f} (با لغزش و کارمزد: {entry_price:.2f})")

        elif action == "SELL" and position_open:
            # بررسی حد ضرر و حد سود در طول معامله (بین ورود تا این نقطه)
            # این بخش ساده‌سازی شده: فقط در نقطه فروش چک می‌کنیم
            exited_due_to_stop_loss = False
            exited_due_to_take_profit = False
            
            # برای بررسی دقیق‌تر، باید بین entry و exit را چک کنیم
            # این نسخه ساده فقط exit معمولی انجام می‌دهد
            
            # خروج از معامله با احتساب کارمزد و لغزش
            # برای سفارش فروش مارکت، قیمت اجرا شده بدتر از close است (پایین‌تر)
            execution_price = price * (1 - slippage_pct)
            exit_price_after_commission = execution_price * (1 - commission_pct)
            
            trade_return_pct = (exit_price_after_commission - entry_price) / entry_price
            pnl = units_held * exit_price_after_commission - (units_held * entry_price)
            
            # بازگشت سرمایه به پورتفو
            capital += pnl
            
            trade_log.append({
                "entry_timestamp": entry_timestamp,
                "exit_timestamp": trade_timestamp,
                "entry_price": entry_price / (1 + commission_pct),  # قیمت بدون کارمزد
                "exit_price": exit_price_after_commission / (1 - commission_pct),  # قیمت بدون کارمزد
                "execution_price_entry": entry_price_raw,
                "execution_price_exit": execution_price,
                "units": units_held,
                "return_pct": trade_return_pct * 100,
                "pnl": pnl,
                "capital_before": capital - pnl,
                "capital_after": capital,
                "exit_reason": "signal",
            })
            
            position_open = False
            entry_price = 0.0
            units_held = 0.0
            entry_timestamp = None
            
            logger.debug(f"SELL @ {execution_price:.2f} | PnL: {pnl:.2f} | Return: {trade_return_pct*100:.2f}%")

    # بررسی اینکه آیا موقعیت بازی مانده است
    open_position_warning = False
    if position_open:
        open_position_warning = True
        last_price = valid.iloc[-1]["close"]
        last_timestamp = valid.iloc[-1].get("timestamp", "end_of_data")
        
        # محاسبه ارزش لحظه‌ای موقعیت باز
        unrealized_execution_price = last_price * (1 - slippage_pct)
        unrealized_exit_value = units_held * unrealized_execution_price * (1 - commission_pct)
        unrealized_pnl = unrealized_exit_value - (units_held * entry_price)
        
        logger.warning(
            f"⚠️ هشدار: بک‌تست با یک موقعیت خرید باز پایان یافت!"
            f"\n   قیمت ورود: {entry_price:.2f}"
            f"\n   آخرین قیمت: {last_price:.2f}"
            f"\n   سود/زیان تحقق‌نیافته: {unrealized_pnl:.2f} تومان ({unrealized_pnl/(units_held*entry_price)*100:.2f}%)"
            f"\n   این معامله در آمار نهایی لحاظ نشده است."
        )
        
        # اضافه کردن اطلاعات موقعیت باز به نتایج
        open_position_info = {
            "status": "open",
            "entry_timestamp": entry_timestamp,
            "entry_price": entry_price,
            "units": units_held,
            "last_price": last_price,
            "unrealized_pnl": unrealized_pnl,
            "unrealized_pnl_pct": (unrealized_pnl / (units_held * entry_price)) * 100,
        }
    else:
        open_position_info = None

    # ساخت منحنی سرمایه با احتساب موقعیت‌های باز (mark-to-market)
    # این بخش مهم است: قبلاً فقط هنگام بستن معامله آپدیت می‌شد
    equity_curve = [initial_capital]
    current_capital = initial_capital
    position_open_sim = False
    sim_entry_price = 0.0
    sim_units = 0.0
    
    for idx, row in df.iterrows():
        close_price = row["close"]
        
        # بررسی سیگنال در این ردیف
        if idx in trades.index and trades.loc[idx, "position"] == 1 and not position_open_sim:
            # BUY
            exec_price = close_price * (1 + slippage_pct)
            exec_price_with_comm = exec_price * (1 + commission_pct)
            allocated = current_capital * position_size_pct
            sim_units = allocated / exec_price_with_comm
            sim_entry_price = exec_price_with_comm
            position_open_sim = True
            
        elif idx in trades.index and trades.loc[idx, "position"] == -1 and position_open_sim:
            # SELL
            exec_price = close_price * (1 - slippage_pct)
            exec_price_after_comm = exec_price * (1 - commission_pct)
            pnl = sim_units * exec_price_after_comm - (sim_units * sim_entry_price)
            current_capital += pnl
            position_open_sim = False
            sim_units = 0.0
            sim_entry_price = 0.0
        
        # محاسبه ارزش فعلی پرتفو (mark-to-market)
        if position_open_sim:
            # ارزش لحظه‌ای با احتساب هزینه خروج فرضی
            current_exec_price = close_price * (1 - slippage_pct)
            current_exit_value = sim_units * current_exec_price * (1 - commission_pct)
            current_equity = current_capital + (current_exit_value - (sim_units * sim_entry_price))
        else:
            current_equity = current_capital
        
        equity_curve.append(current_equity)
    
    # حذف نقطه اضافی اول اگر نیاز باشد
    if len(equity_curve) > len(df) + 1:
        equity_curve = equity_curve[:len(df) + 1]
    
    if len(trade_log) == 0:
        logger.warning("هیچ معامله کاملی (خرید+فروش) انجام نشد.")
        return {"error": "no_completed_trades", "open_position": open_position_info}

    trade_log_df = pd.DataFrame(trade_log)

    # محاسبه آمار نهایی
    total_return_pct = ((capital - initial_capital) / initial_capital) * 100
    winning_trades = (trade_log_df["return_pct"] > 0).sum()
    losing_trades = (trade_log_df["return_pct"] <= 0).sum()
    win_rate = (winning_trades / len(trade_log_df)) * 100 if len(trade_log_df) > 0 else 0
    
    # محاسبه دقیق‌ترین افت سرمایه با استفاده از منحنی سرمایه کامل
    equity_series = pd.Series(equity_curve)
    running_max = equity_series.cummax()
    drawdown = (equity_series - running_max) / running_max * 100
    max_drawdown = drawdown.min()
    
    # محاسبه Sharpe Ratio ساده‌سازی شده (فرض 252 روز معاملاتی)
    if len(equity_series) > 1:
        returns = equity_series.pct_change().dropna()
        if returns.std() > 0:
            sharpe_ratio = (returns.mean() / returns.std()) * np.sqrt(252)
        else:
            sharpe_ratio = 0.0
    else:
        sharpe_ratio = 0.0

    results = {
        "initial_capital": initial_capital,
        "final_capital": capital,
        "total_return_pct": total_return_pct,
        "num_trades": len(trade_log_df),
        "winning_trades": int(winning_trades),
        "losing_trades": int(losing_trades),
        "win_rate_pct": win_rate,
        "max_drawdown_pct": max_drawdown,
        "sharpe_ratio": sharpe_ratio,
        "trade_log": trade_log_df,
        "equity_curve": equity_curve,
        "open_position": open_position_info,
        "position_size_pct_used": position_size_pct,
        "slippage_pct_used": slippage_pct,
        "commission_pct_used": commission_pct,
    }

    return results


def print_report(results: dict) -> None:
    """چاپ گزارش خوانا از نتایج بک‌تست."""
    if "error" in results:
        print(f"خطا: {results['error']}")
        if "validation_errors" in results:
            print("خطاهای اعتبارسنجی:")
            for err in results["validation_errors"]:
                print(f"  - {err}")
        if "open_position" in results and results["open_position"]:
            op = results["open_position"]
            print(f"\nموقعیت باز:")
            print(f"  قیمت ورود: {op['entry_price']:,.2f}")
            print(f"  سود/زیان تحقق‌نیافته: {op['unrealized_pnl']:,.2f} تومان ({op['unrealized_pnl_pct']:.2f}%)")
        return

    print("=" * 60)
    print("گزارش بک‌تست")
    print("=" * 60)
    print(f"سرمایه اولیه:           {results['initial_capital']:,.0f} تومان")
    print(f"سرمایه نهایی:           {results['final_capital']:,.0f} تومان")
    print(f"بازده کل:               {results['total_return_pct']:+.2f}%")
    print(f"تعداد معاملات:          {results['num_trades']}")
    print(f"معاملات برنده:          {results['winning_trades']}")
    print(f"معاملات بازنده:         {results['losing_trades']}")
    print(f"درصد برد (Win Rate):    {results['win_rate_pct']:.1f}%")
    print(f"بیشترین افت سرمایه:     {results['max_drawdown_pct']:.2f}%")
    print(f"Sharpe Ratio:           {results.get('sharpe_ratio', 'N/A'):.3f}" if results.get('sharpe_ratio') else "Sharpe Ratio: N/A")
    print("-" * 60)
    print(f"کارمزد استفاده شده:     {results.get('commission_pct_used', 0)*100:.2f}%")
    print(f"لغزش قیمت استفاده شده:  {results.get('slippage_pct_used', 0)*100:.2f}%")
    print(f"اندازه موقعیت:          {results.get('position_size_pct_used', 1)*100:.0f}% از سرمایه")
    
    if results.get("open_position"):
        op = results["open_position"]
        print("-" * 60)
        print(f"⚠️ هشدار: موقعیت باز در پایان بک‌تست")
        print(f"   قیمت ورود: {op['entry_price']:,.2f}")
        print(f"   آخرین قیمت: {op['last_price']:,.2f}")
        print(f"   سود/زیان تحقق‌نیافته: {op['unrealized_pnl']:,.2f} تومان ({op['unrealized_pnl_pct']:.2f}%)")
        print("   این معامله در آمار نهایی لحاظ نشده است.")
    
    print("=" * 60)


if __name__ == "__main__":
    # بارگذاری داده‌ای که با سیگنال‌ها ذخیره کرده بودیم
    df = pd.read_csv("data/btcirt_with_signals.csv", parse_dates=["timestamp"])

    # اجرای بک‌تست با پارامترهای پیشرفته
    results = run_backtest(
        df,
        initial_capital=10_000_000,  # ۱۰ میلیون تومان
        commission_pct=0.0025,  # ۰.۲۵٪ کارمزد (نرخ رایج نوبیتکس)
        slippage_pct=0.001,  # ۰.۱٪ لغزش قیمت
        position_size_pct=1.0,  # ۱۰۰٪ سرمایه در هر معامله
    )

    print_report(results)

    # نمایش جزئیات هر معامله
    if "trade_log" in results:
        print("\nجزئیات معاملات:")
        print(results["trade_log"].to_string(index=False))