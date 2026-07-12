"""
Backtester

این ماژول عملکرد واقعی استراتژی را روی داده تاریخی شبیه‌سازی می‌کند و گزارش می‌دهد:
- سود/زیان کل
- تعداد معاملات
- درصد معاملات برنده
- بیشترین افت سرمایه (Max Drawdown)
"""

import pandas as pd
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_backtest(
    df: pd.DataFrame,
    initial_capital: float = 10_000_000,  # ۱۰ میلیون تومان سرمایه فرضی
    commission_pct: float = 0.0025,  # ۰.۲۵٪ کارمزد هر معامله (رایج در صرافی‌های ایرانی)
) -> dict:
    """
    شبیه‌سازی معاملات بر اساس سیگنال‌های خرید/فروش موجود در df.

    Args:
        df: DataFrame خروجی apply_moving_average_strategy (باید ستون position داشته باشد)
        initial_capital: سرمایه اولیه فرضی به تومان
        commission_pct: نرخ کارمزد هر معامله (مثلا 0.0025 یعنی 0.25%)

    Returns:
        دیکشنری شامل نتایج کامل بک‌تست
    """
    valid = df.dropna(subset=["position"]).reset_index(drop=True)
    trades = valid[valid["position"] != 0].copy()

    if len(trades) == 0:
        logger.warning("هیچ معامله‌ای برای بک‌تست وجود ندارد.")
        return {"error": "no_trades"}

    capital = initial_capital
    position_open = False
    entry_price = 0.0
    trade_log = []
    equity_curve = [initial_capital]

    for _, row in trades.iterrows():
        price = row["close"]
        action = "BUY" if row["position"] == 1 else "SELL"

        if action == "BUY" and not position_open:
            # ورود به معامله: کل سرمایه را وارد می‌کنیم (ساده‌سازی شده)
            entry_price = price * (1 + commission_pct)  # اعمال کارمزد خرید
            position_open = True

        elif action == "SELL" and position_open:
            # خروج از معامله
            exit_price = price * (1 - commission_pct)  # اعمال کارمزد فروش
            trade_return_pct = (exit_price - entry_price) / entry_price
            capital = capital * (1 + trade_return_pct)

            trade_log.append({
                "entry_price": entry_price,
                "exit_price": exit_price,
                "return_pct": trade_return_pct * 100,
                "capital_after": capital,
            })
            equity_curve.append(capital)
            position_open = False

    if len(trade_log) == 0:
        logger.warning("هیچ معامله کاملی (خرید+فروش) انجام نشد.")
        return {"error": "no_completed_trades"}

    trade_log_df = pd.DataFrame(trade_log)

    # محاسبه آمار نهایی
    total_return_pct = ((capital - initial_capital) / initial_capital) * 100
    winning_trades = (trade_log_df["return_pct"] > 0).sum()
    losing_trades = (trade_log_df["return_pct"] <= 0).sum()
    win_rate = (winning_trades / len(trade_log_df)) * 100

    # محاسبه بیشترین افت سرمایه (Max Drawdown)
    equity_series = pd.Series(equity_curve)
    running_max = equity_series.cummax()
    drawdown = (equity_series - running_max) / running_max * 100
    max_drawdown = drawdown.min()

    results = {
        "initial_capital": initial_capital,
        "final_capital": capital,
        "total_return_pct": total_return_pct,
        "num_trades": len(trade_log_df),
        "winning_trades": int(winning_trades),
        "losing_trades": int(losing_trades),
        "win_rate_pct": win_rate,
        "max_drawdown_pct": max_drawdown,
        "trade_log": trade_log_df,
    }

    return results


def print_report(results: dict) -> None:
    """چاپ گزارش خوانا از نتایج بک‌تست."""
    if "error" in results:
        print(f"خطا: {results['error']}")
        return

    print("=" * 50)
    print("گزارش بک‌تست")
    print("=" * 50)
    print(f"سرمایه اولیه:        {results['initial_capital']:,.0f} تومان")
    print(f"سرمایه نهایی:        {results['final_capital']:,.0f} تومان")
    print(f"بازده کل:            {results['total_return_pct']:+.2f}%")
    print(f"تعداد معاملات:       {results['num_trades']}")
    print(f"معاملات برنده:       {results['winning_trades']}")
    print(f"معاملات بازنده:      {results['losing_trades']}")
    print(f"درصد برد (Win Rate): {results['win_rate_pct']:.1f}%")
    print(f"بیشترین افت سرمایه:  {results['max_drawdown_pct']:.2f}%")
    print("=" * 50)


if __name__ == "__main__":
    # بارگذاری داده‌ای که با سیگنال‌ها ذخیره کرده بودیم
    df = pd.read_csv("data/btcirt_with_signals.csv", parse_dates=["timestamp"])

    # اجرای بک‌تست
    results = run_backtest(
        df,
        initial_capital=10_000_000,  # ۱۰ میلیون تومان
        commission_pct=0.0025,  # ۰.۲۵٪ کارمزد (نرخ رایج نوبیتکس)
    )

    print_report(results)

    # نمایش جزئیات هر معامله
    if "trade_log" in results:
        print("\nجزئیات معاملات:")
        print(results["trade_log"].to_string(index=False))