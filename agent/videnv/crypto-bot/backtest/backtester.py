"""
Backtester (نسخه بازنویسی‌شده - یک‌پارچه)

این ماژول عملکرد واقعی استراتژی را روی داده تاریخی شبیه‌سازی می‌کند.

نکته مهم درباره زمان‌بندی اجرا (جلوگیری از Look-Ahead Bias):
- سیگنال بر اساس close کندل N تولید می‌شود
- اجرای معامله با قیمت open کندل N+1 انجام می‌شود (چون در واقعیت
  نمی‌توانید در لحظه تولید سیگنال، در قیمت close همان کندل معامله کنید)

این نسخه عمداً از یک حلقه واحد استفاده می‌کند (نه دو حلقه موازی برای
trade_log و equity_curve) تا ریسک ناهم‌ترازی و واگرایی بین دو محاسبه
از بین برود.
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
    """اعتبارسنجی داده‌های OHLCV قبل از اجرای بک‌تست."""
    errors = []
    warnings = []

    required_columns = ['open', 'high', 'low', 'close']
    missing_cols = [col for col in required_columns if col not in df.columns]
    if missing_cols:
        errors.append(f"ستون‌های ضروری وجود ندارند: {missing_cols}")
        return {"valid": False, "errors": errors, "warnings": warnings}

    for col in required_columns:
        if (df[col] < 0).any():
            errors.append(f"مقادیر منفی در ستون {col} یافت شد")

    if (df['close'] == 0).any():
        errors.append("قیمت بسته شدن صفر یافت شد")

    nan_counts = df[required_columns].isna().sum()
    if nan_counts.any():
        for col, count in nan_counts[nan_counts > 0].items():
            errors.append(f"{count} مقدار NaN در ستون {col} وجود دارد")

    if 'timestamp' in df.columns:
        ts_diff = df['timestamp'].diff()[1:]
        if (ts_diff <= pd.Timedelta(0)).any():
            non_increasing_count = (ts_diff <= pd.Timedelta(0)).sum()
            warnings.append(f"{non_increasing_count} تکرار یا کاهش در timestamp یافت شد")

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
        "nan_free_rows": len(df.dropna(subset=required_columns)),
    }


def run_backtest(
    df: pd.DataFrame,
    initial_capital: float = 10_000_000,
    commission_pct: float = 0.0025,
    slippage_pct: float = 0.001,
    position_size_pct: float = 1.0,
    stop_loss_pct: Optional[float] = None,
    take_profit_pct: Optional[float] = None,
) -> dict:
    """
    شبیه‌سازی معاملات با یک حلقه واحد روی تمام ردیف‌های داده.

    منطق زمان‌بندی:
    - در ردیف idx، ابتدا چک می‌کنیم آیا سیگنالی در ردیف قبلی (idx-1)
      صادر شده بود؛ اگر بله، با قیمت open همین ردیف (idx) اجرا می‌شود.
    - سپس ارزش لحظه‌ای پرتفو (mark-to-market) با قیمت close همین ردیف
      محاسبه و در equity_curve ثبت می‌شود.

    این ترتیب تضمین می‌کند که هیچ معامله‌ای با اطلاعات از آینده انجام نشود.
    
    پارامترهای اختیاری:
    - stop_loss_pct: درصد حد ضرر نسبت به قیمت ورود (مثلاً 0.05 = 5%). 
      اگر None باشد، غیرفعال است.
    - take_profit_pct: درصد حد سود نسبت به قیمت ورود (مثلاً 0.10 = 10%).
      اگر None باشد، غیرفعال است.
      
    بررسی حد ضرر/حد سود درون‌کندلی:
    برای هر کندلی که موقعیت باز وجود دارد، قبل از پردازش سیگنال جدید:
    1. اگر low کندل به سطح stop_loss رسیده باشد، خروج در max(open, stop_loss_level)
       با دلیل "stop_loss"
    2. اگر high کندل به سطح take_profit رسیده باشد، خروج در min(open, take_profit_level)
       با دلیل "take_profit"
    3. اگر هیچ‌کدام فعال نشد، ادامه با منطق مبتنی بر سیگنال (اجرای سیگنال
       کندل قبل در open این کندل)
    """
    validation_result = validate_ohlcv_data(df)
    if not validation_result["valid"]:
        logger.error("اعتبارسنجی داده‌ها ناموفق بود:")
        for error in validation_result["errors"]:
            logger.error(f"  - {error}")
        return {"error": "invalid_data", "validation_errors": validation_result["errors"]}

    for warning in validation_result.get("warnings", []):
        logger.warning(f"هشدار داده: {warning}")

    # ایندکس را کاملاً یکدست (0..n-1) می‌کنیم تا هیچ‌جا ناهم‌ترازی ایندکس رخ ندهد
    df = df.reset_index(drop=True)
    n = len(df)

    if "position" not in df.columns:
        return {"error": "missing_position_column"}

    capital = initial_capital
    position_open = False
    entry_price = 0.0
    entry_timestamp = None
    units_held = 0.0
    trade_log = []
    equity_curve = []
    equity_timestamps = []

    for idx in range(n):
        row = df.loc[idx]

        # ---- بررسی حد ضرر/حد سود درون‌کندلی (قبل از پردازش سیگنال جدید) ----
        # این بررسی فقط زمانی انجام می‌شود که یک موقعیت باز وجود داشته باشد
        if position_open and (stop_loss_pct is not None or take_profit_pct is not None):
            this_open = row["open"]
            this_high = row["high"]
            this_low = row["low"]
            this_timestamp = row.get("timestamp", idx)
            
            # محاسبه سطوح حد ضرر و حد سود بر اساس entry_price
            stop_loss_level = entry_price * (1 - stop_loss_pct) if stop_loss_pct is not None else None
            take_profit_level = entry_price * (1 + take_profit_pct) if take_profit_pct is not None else None
            
            exited = False
            exit_reason = None
            exit_price = None
            
            # اولویت 1: بررسی حد ضرر - اگر low کندل به stop_loss_level رسیده باشد
            if stop_loss_level is not None and this_low <= stop_loss_level:
                # خروج در max(open, stop_loss_level) - بدترین حالت برای خریدار
                # اگر open پایین‌تر از stop_loss باشد، یعنی gap down داشته و در stop_loss پر شده
                # اگر open بالاتر باشد، در open خارج می‌شویم (چون قیمت از open شروع به کاهش کرده)
                exit_price = max(this_open, stop_loss_level)
                # اعمال لغزش و کارمزد برای خروج
                exit_price = exit_price * (1 - slippage_pct) * (1 - commission_pct)
                exit_reason = "stop_loss"
                exited = True
            
            # اولویت 2: بررسی حد سود - اگر high کندل به take_profit_level رسیده باشد
            elif take_profit_level is not None and this_high >= take_profit_level:
                # خروج در min(open, take_profit_level) - بهترین قیمت قابل دسترس
                # اگر open بالاتر از take_profit باشد، یعنی gap up داشته و در take_profit پر شده
                # اگر open پایین‌تر باشد، در open خارج می‌شویم
                exit_price = min(this_open, take_profit_level)
                # اعمال لغزش و کارمزد برای خروج
                exit_price = exit_price * (1 - slippage_pct) * (1 - commission_pct)
                exit_reason = "take_profit"
                exited = True
            
            # اگر حد ضرر یا حد سود فعال شد، موقعیت را ببند
            if exited:
                pnl = units_held * exit_price - units_held * entry_price
                capital += pnl
                
                trade_log.append({
                    "entry_timestamp": entry_timestamp,
                    "exit_timestamp": this_timestamp,
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "units": units_held,
                    "pnl": pnl,
                    "return_pct": (exit_price - entry_price) / entry_price * 100,
                    "capital_after": capital,
                    "exit_reason": exit_reason,
                })
                
                position_open = False
                units_held = 0.0
                entry_price = 0.0
                entry_timestamp = None

        # ---- اجرای سیگنالی که در ردیف قبلی (idx-1) تولید شده بود ----
        if idx > 0:
            prev_signal = df.loc[idx - 1, "position"]

            if pd.notna(prev_signal) and prev_signal != 0:
                this_open = row["open"]
                this_timestamp = row.get("timestamp", idx)

                if prev_signal == 1 and not position_open:
                    # ورود: قیمت اجرا بدتر از open است (لغزش خرید به سمت بالا)
                    execution_price = this_open * (1 + slippage_pct)
                    entry_price = execution_price * (1 + commission_pct)
                    allocated_capital = capital * position_size_pct
                    units_held = allocated_capital / entry_price
                    entry_timestamp = this_timestamp
                    position_open = True

                elif prev_signal == -1 and position_open:
                    # خروج: قیمت اجرا بدتر از open است (لغزش فروش به سمت پایین)
                    execution_price = this_open * (1 - slippage_pct)
                    exit_price = execution_price * (1 - commission_pct)
                    pnl = units_held * exit_price - units_held * entry_price
                    capital += pnl

                    trade_log.append({
                        "entry_timestamp": entry_timestamp,
                        "exit_timestamp": this_timestamp,
                        "entry_price": entry_price,
                        "exit_price": exit_price,
                        "units": units_held,
                        "pnl": pnl,
                        "return_pct": (exit_price - entry_price) / entry_price * 100,
                        "capital_after": capital,
                        "exit_reason": "signal",
                    })

                    position_open = False
                    units_held = 0.0
                    entry_price = 0.0
                    entry_timestamp = None

        # ---- محاسبه ارزش لحظه‌ای پرتفو (mark-to-market) با close همین ردیف ----
        close_price = row["close"]
        current_equity = units_held * close_price if position_open else capital

        equity_curve.append(current_equity)
        equity_timestamps.append(row.get("timestamp", idx))

    # ---- بررسی موقعیت باز در پایان داده ----
    open_position_info = None
    if position_open:
        last_price = df.loc[n - 1, "close"]
        unrealized_value = units_held * last_price
        unrealized_pnl = unrealized_value - (units_held * entry_price)

        logger.warning(
            f"⚠️ هشدار: بک‌تست با یک موقعیت خرید باز پایان یافت!"
            f"\n   قیمت ورود: {entry_price:.2f}"
            f"\n   آخرین قیمت: {last_price:.2f}"
            f"\n   سود/زیان تحقق‌نیافته: {unrealized_pnl:.2f} تومان "
            f"({(unrealized_pnl/(units_held*entry_price))*100:.2f}%)"
            f"\n   این معامله در آمار «تعداد معاملات» لحاظ نشده، ولی در equity_curve نهایی لحاظ شده است."
        )

        open_position_info = {
            "status": "open",
            "entry_timestamp": entry_timestamp,
            "entry_price": entry_price,
            "units": units_held,
            "last_price": last_price,
            "unrealized_pnl": unrealized_pnl,
            "unrealized_pnl_pct": (unrealized_pnl / (units_held * entry_price)) * 100,
        }

    if len(trade_log) == 0:
        logger.warning("هیچ معامله کاملی (خرید+فروش) انجام نشد.")
        return {
            "error": "no_completed_trades",
            "open_position": open_position_info,
            "equity_curve": equity_curve,
        }

    trade_log_df = pd.DataFrame(trade_log)

    # سرمایه نهایی: از آخرین مقدار equity_curve می‌گیریم تا موقعیت باز هم لحاظ شود
    final_capital = equity_curve[-1]
    total_return_pct = ((final_capital - initial_capital) / initial_capital) * 100
    winning_trades = (trade_log_df["return_pct"] > 0).sum()
    losing_trades = (trade_log_df["return_pct"] <= 0).sum()
    win_rate = (winning_trades / len(trade_log_df)) * 100

    equity_series = pd.Series(equity_curve)
    running_max = equity_series.cummax()
    drawdown = (equity_series - running_max) / running_max * 100
    max_drawdown = drawdown.min()

    if len(equity_series) > 1:
        returns = equity_series.pct_change().dropna()
        sharpe_ratio = (returns.mean() / returns.std()) * np.sqrt(252) if returns.std() > 0 else 0.0
    else:
        sharpe_ratio = 0.0

    results = {
        "initial_capital": initial_capital,
        "final_capital": final_capital,
        "position_still_open": position_open,
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
        if results.get("open_position"):
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
    print(f"Sharpe Ratio:           {results['sharpe_ratio']:.3f}")
    print("-" * 60)
    print(f"کارمزد استفاده شده:     {results['commission_pct_used']*100:.2f}%")
    print(f"لغزش قیمت استفاده شده:  {results['slippage_pct_used']*100:.2f}%")
    print(f"اندازه موقعیت:          {results['position_size_pct_used']*100:.0f}% از سرمایه")

    if results.get("open_position"):
        op = results["open_position"]
        print("-" * 60)
        print(f"⚠️ هشدار: موقعیت باز در پایان بک‌تست")
        print(f"   قیمت ورود: {op['entry_price']:,.2f}")
        print(f"   آخرین قیمت: {op['last_price']:,.2f}")
        print(f"   سود/زیان تحقق‌نیافته: {op['unrealized_pnl']:,.2f} تومان ({op['unrealized_pnl_pct']:.2f}%)")
        print("   این مبلغ در سرمایه نهایی لحاظ شده، ولی به‌عنوان یک معامله بسته‌شده شمرده نشده.")

    print("=" * 60)


if __name__ == "__main__":
    df = pd.read_csv("data/btcirt_with_signals.csv", parse_dates=["timestamp"])

    results = run_backtest(
        df,
        initial_capital=10_000_000,
        commission_pct=0.0025,
        slippage_pct=0.001,
        position_size_pct=1.0,
    )

    print_report(results)

    if "trade_log" in results:
        print("\nجزئیات معاملات:")
        print(results["trade_log"].to_string(index=False))
