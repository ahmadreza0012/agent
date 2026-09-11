#!/usr/bin/env python3
"""
Sync EC2 Database and Web API
Synchronizes the SQLite trading database (data/trading.db) with 43 closed trades and 4 open positions,
and restarts web_api.py on Port 5000.
"""

import os
import sys
import json
import sqlite3
import subprocess

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "trading.db")
SEED_PATH = os.path.join(BASE_DIR, "data", "trades_seed.json")

def sync():
    print("=========================================")
    print("🔄 همگام‌سازی پایگاه‌داده و سرور پورت ۵۰۰۰...")
    print("=========================================")

    os.makedirs(os.path.join(BASE_DIR, "data"), exist_ok=True)

    if not os.path.exists(SEED_PATH):
        print(f"❌ فایل بذر یافت نشد: {SEED_PATH}")
        return False

    with open(SEED_PATH, "r", encoding="utf-8") as f:
        seed_data = json.load(f)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS closed_trades (
            id TEXT PRIMARY KEY,
            order_id TEXT,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL,
            size REAL NOT NULL,
            leverage INTEGER DEFAULT 1,
            entry_price REAL NOT NULL,
            exit_price REAL NOT NULL,
            gross_pnl REAL NOT NULL,
            fee REAL NOT NULL,
            net_pnl REAL NOT NULL,
            roi_pct REAL NOT NULL,
            close_reason TEXT,
            opened_at TIMESTAMP NOT NULL,
            closed_at TIMESTAMP NOT NULL,
            created_at TIMESTAMP NOT NULL,
            strategy TEXT,
            features_snapshot_json TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS open_positions (
            id TEXT PRIMARY KEY,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL,
            type TEXT NOT NULL,
            size REAL NOT NULL,
            notional REAL NOT NULL,
            margin REAL NOT NULL,
            leverage INTEGER NOT NULL,
            entry_price REAL NOT NULL,
            current_price REAL NOT NULL,
            liquidation_price REAL NOT NULL,
            stop_loss REAL NOT NULL,
            take_profit REAL NOT NULL,
            unrealized_pnl REAL NOT NULL,
            roe_pct REAL NOT NULL,
            fee REAL NOT NULL,
            opened_at TIMESTAMP NOT NULL,
            last_updated TIMESTAMP NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id TEXT PRIMARY KEY,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL,
            type TEXT NOT NULL,
            size REAL NOT NULL,
            price REAL NOT NULL,
            leverage INTEGER NOT NULL,
            status TEXT NOT NULL,
            stop_loss REAL,
            take_profit REAL,
            created_at TIMESTAMP NOT NULL,
            filled_at TIMESTAMP,
            strategy TEXT
        )
    """)

    # Clear old data to prevent duplicate keys if syncing fresh
    cur.execute("DELETE FROM closed_trades")
    cur.execute("DELETE FROM open_positions")
    cur.execute("DELETE FROM orders")

    trades = seed_data.get("closed_trades", [])
    for t in trades:
        cur.execute("""
            INSERT OR REPLACE INTO closed_trades 
            (id, order_id, symbol, side, size, leverage, entry_price, exit_price, gross_pnl, fee, net_pnl, roi_pct, close_reason, opened_at, closed_at, created_at, strategy, features_snapshot_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            t.get("id"), t.get("order_id"), t.get("symbol"), t.get("side"), t.get("size"),
            t.get("leverage", 1), t.get("entry_price"), t.get("exit_price"), t.get("gross_pnl", 0),
            t.get("fee", 0), t.get("net_pnl", 0), t.get("roi_pct", 0), t.get("close_reason"),
            t.get("opened_at"), t.get("closed_at"), t.get("created_at"), t.get("strategy"),
            t.get("features_snapshot_json")
        ))

    positions = seed_data.get("open_positions", [])
    for p in positions:
        cur.execute("""
            INSERT OR REPLACE INTO open_positions
            (id, symbol, side, type, size, notional, margin, leverage, entry_price, current_price, liquidation_price, stop_loss, take_profit, unrealized_pnl, roe_pct, fee, opened_at, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            p.get("id"), p.get("symbol"), p.get("side"), p.get("type", "MARKET"), p.get("size"),
            p.get("notional", 0), p.get("margin", 0), p.get("leverage", 1), p.get("entry_price"),
            p.get("current_price"), p.get("liquidation_price", 0), p.get("stop_loss", 0),
            p.get("take_profit", 0), p.get("unrealized_pnl", 0), p.get("roe_pct", 0),
            p.get("fee", 0), p.get("opened_at"), p.get("last_updated")
        ))

    orders = seed_data.get("orders", [])
    for o in orders:
        cur.execute("""
            INSERT OR REPLACE INTO orders
            (id, symbol, side, type, size, price, leverage, status, stop_loss, take_profit, created_at, filled_at, strategy)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            o.get("id"), o.get("symbol"), o.get("side"), o.get("type", "MARKET"), o.get("size"),
            o.get("price", 0), o.get("leverage", 1), o.get("status", "FILLED"),
            o.get("stop_loss"), o.get("take_profit"), o.get("created_at"), o.get("filled_at"), o.get("strategy")
        ))

    conn.commit()
    conn.close()

    print(f"✅ تعداد {len(trades)} معامله بسته شده در پایگاه‌داده ذخیره شد.")
    print(f"✅ تعداد {len(positions)} پوزیشن باز در پایگاه‌داده ذخیره شد.")
    print(f"✅ تعداد {len(orders)} سفارش در پایگاه‌داده ذخیره شد.")

    # Restart web server
    print("🔄 در حال راه‌اندازی مجدد سرور پورت ۵۰۰۰...")
    subprocess.run(["pkill", "-f", "python.*web_api.py"], stderr=subprocess.DEVNULL)
    subprocess.run(["pkill", "-f", "node.*server.js"], stderr=subprocess.DEVNULL)
    
    launcher = os.path.join(BASE_DIR, "start_web_api.sh")
    if os.path.exists(launcher):
        subprocess.run(["bash", launcher])
    else:
        subprocess.Popen(["python3", os.path.join(BASE_DIR, "web_api.py")], env={**os.environ, "PORT": "5000"})
        print("✅ سرور پایتون اجرا شد.")

    print("=========================================")
    print("🎉 همگام‌سازی کامل شد!")
    print("👉 اکنون به آدرس http://52.23.157.88:5000 مراجعه کنید.")
    print("=========================================")
    return True

if __name__ == "__main__":
    sync()
