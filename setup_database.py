#!/usr/bin/env python3
"""
Single-file Database Setup & Server Refresh
Directly initializes data/trading.db with the full 43 trade records and starts web_api.py on Port 5000.
"""

import os
import sys
import json
import sqlite3
import subprocess

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "trading.db")

def main():
    print("🚀 در حال بارگذاری ۴۳ معامله در دیتابیس محلی سرور...")
    os.makedirs(os.path.join(BASE_DIR, "data"), exist_ok=True)
    
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

    seed_file = os.path.join(BASE_DIR, "data", "trades_seed.json")
    if os.path.exists(seed_file):
        with open(seed_file, "r", encoding="utf-8") as f:
            seed_data = json.load(f)
        
        for t in seed_data.get("closed_trades", []):
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

        for p in seed_data.get("open_positions", []):
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

        conn.commit()
    conn.close()

    print("✅ پایگاه‌داده با موفقیت پر شد.")
    subprocess.run(["pkill", "-f", "python.*web_api.py"], stderr=subprocess.DEVNULL)
    subprocess.run(["pkill", "-f", "node.*server.js"], stderr=subprocess.DEVNULL)
    
    print("🚀 در حال راه‌اندازی سرور پورت 5000...")
    subprocess.run(["bash", os.path.join(BASE_DIR, "start_web_api.sh")])

if __name__ == "__main__":
    main()
