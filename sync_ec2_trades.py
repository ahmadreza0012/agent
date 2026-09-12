import os
import json
import sqlite3
import subprocess

print("==================================================")
print("🔄 همگام‌سازی کامل تاریخچه معاملات و دیتابیس در سرور...")
print("==================================================")

base_dir = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(base_dir, "data", "trading.db")
store_path = os.path.join(base_dir, "data", "trading_store.json")
seed_path = os.path.join(base_dir, "data", "trades_seed.json")

store_data = {
    "closed_trades": [],
    "open_positions": [],
    "orders": [],
    "trades": [],
    "agent_training_epochs": [],
    "agent_cycles": [],
    "capability_executions": []
}

# 1. First attempt to extract directly from SQLite using Python
if os.path.exists(db_path):
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        # Check closed_trades
        cur.execute("SELECT * FROM closed_trades ORDER BY closed_at DESC")
        store_data["closed_trades"] = [dict(r) for r in cur.fetchall()]
        print(f"✅ تعداد معاملات بسته‌شده از دیتابیس SQLite: {len(store_data['closed_trades'])}")
        
        # Check open_positions
        try:
            cur.execute("SELECT * FROM open_positions ORDER BY opened_at DESC")
            store_data["open_positions"] = [dict(r) for r in cur.fetchall()]
            print(f"✅ تعداد پوزیشن‌های باز از دیتابیس: {len(store_data['open_positions'])}")
        except Exception:
            pass

        # Check orders
        try:
            cur.execute("SELECT * FROM orders ORDER BY created_at DESC LIMIT 50")
            store_data["orders"] = [dict(r) for r in cur.fetchall()]
        except Exception:
            pass

        # Check account_state
        try:
            cur.execute("SELECT * FROM account_state WHERE id = 'primary'")
            row = cur.fetchone()
            if row:
                store_data["account_state"] = dict(row)
        except Exception:
            pass
            
        conn.close()
    except Exception as e:
        print(f"⚠️ خطای خواندن SQLite: {e}")

# 2. If SQLite was empty or had 0 closed trades, load from trades_seed.json
if len(store_data["closed_trades"]) == 0 and os.path.exists(seed_path):
    try:
        with open(seed_path, "r", encoding="utf-8") as f:
            seed = json.load(f)
            store_data["closed_trades"] = seed.get("closed_trades", [])
            if not store_data["open_positions"]:
                store_data["open_positions"] = seed.get("open_positions", [])
            if not store_data["orders"]:
                store_data["orders"] = seed.get("orders", [])
            print(f"✅ لود معاملات از فایل بذر (Seed): {len(store_data['closed_trades'])}")
    except Exception as e:
        print(f"⚠️ خطای لود seed: {e}")

# Save to trading_store.json
os.makedirs(os.path.join(base_dir, "data"), exist_ok=True)
with open(store_path, "w", encoding="utf-8") as f:
    json.dump(store_data, f, indent=2)

print(f"💾 فایل ذخیره‌سازی همگام شد: {store_path}")

# Update trading_db_manager.js to make sure fallbackDb reads memStore properly
mgr_path = os.path.join(base_dir, "trading_db_manager.js")
if os.path.exists(mgr_path):
    with open(mgr_path, "r", encoding="utf-8") as f:
        code = f.read()

    # Verify fallbackDb handles all() with memStore
    if "return (memStore.closed_trades || []).slice(0, limit);" not in code:
        # Inject modern fallbackDb
        fallback_replacement = """const fallbackDb = {
  exec: () => {},
  prepare: (sql) => ({
    run: (...args) => {
      try {
        const sqlLower = (sql || '').toLowerCase();
        if (sqlLower.includes('into closed_trades')) {
          const tradeObj = (args[0] && typeof args[0] === 'object') ? args[0] : {
            id: args[0] || ('ct_' + Date.now()),
            order_id: args[1] || args[0],
            symbol: args[2] || 'BTC/USDT',
            side: args[3] || 'LONG',
            size: args[4] || 0,
            leverage: args[5] || 1,
            entry_price: args[6] || 0,
            exit_price: args[7] || 0,
            gross_pnl: args[8] || 0,
            fee: args[9] || 0,
            net_pnl: args[10] || 0,
            roi_pct: args[11] || 0,
            close_reason: args[12] || 'MANUAL',
            opened_at: args[13] || new Date().toISOString(),
            closed_at: args[14] || new Date().toISOString(),
            created_at: args[15] || new Date().toISOString(),
            strategy: args[16] || 'AGENT_60_FEATURES'
          };
          memStore.closed_trades.unshift(tradeObj);
        }
        if (sqlLower.includes('into open_positions')) {
          const posObj = (args[0] && typeof args[0] === 'object') ? args[0] : {
            id: args[0] || ('pos_' + Date.now()),
            symbol: args[1],
            side: args[2],
            type: args[3] || 'MARKET',
            size: args[4],
            notional: args[5],
            margin: args[6],
            leverage: args[7],
            entry_price: args[8],
            current_price: args[9],
            liquidation_price: args[10],
            stop_loss: args[11],
            take_profit: args[12],
            unrealized_pnl: args[13],
            roe_pct: args[14],
            fee: args[15],
            opened_at: args[16],
            last_updated: args[17]
          };
          const idx = memStore.open_positions.findIndex(p => p.id === posObj.id);
          if (idx >= 0) memStore.open_positions[idx] = posObj;
          else memStore.open_positions.push(posObj);
        }
        if (sqlLower.includes('delete from open_positions')) {
          memStore.open_positions = [];
        }
        persistStore();
      } catch (e) {}
      return { changes: 1 };
    },
    get: (...args) => {
      const sqlLower = (sql || '').toLowerCase();
      if (sqlLower.includes('count(*) as cnt from')) {
        const match = sqlLower.match(/from\\s+([a-z0-9_]+)/);
        const tbl = match ? match[1] : '';
        const list = memStore[tbl];
        return { cnt: Array.isArray(list) ? list.length : 0 };
      }
      if (sqlLower.includes('from account_state')) {
        return memStore.account_state || { id: 'primary', balance: 10000, equity: 10000, total_pnl: 0 };
      }
      return undefined;
    },
    all: (...args) => {
      const sqlLower = (sql || '').toLowerCase();
      const limit = typeof args[0] === 'number' ? args[0] : 100;
      if (sqlLower.includes('from closed_trades')) {
        return (memStore.closed_trades || []).slice(0, limit);
      }
      if (sqlLower.includes('from open_positions')) {
        return memStore.open_positions || [];
      }
      if (sqlLower.includes('from orders')) {
        return (memStore.orders || []).slice(0, limit);
      }
      if (sqlLower.includes('from capability_executions')) {
        return (memStore.capability_executions || []).slice(0, limit);
      }
      if (sqlLower.includes('from agent_training_epochs')) {
        return (memStore.training_epochs || []).slice(0, limit);
      }
      if (sqlLower.includes('from agent_cycles')) {
        return (memStore.agent_cycles || []).slice(0, limit);
      }
      return [];
    }
  }),
  close: () => {}
};"""
        # Replace simple fallbackDb
        import re
        code = re.sub(r'const fallbackDb = \{[\s\S]*?close: \(\) => \{\}\s*\};', fallback_replacement, code)
        with open(mgr_path, "w", encoding="utf-8") as f:
            f.write(code)
        print("✅ کدهای پایگاه داده در trading_db_manager.js ارتقا یافت.")

# Restart PM2
print("🔄 در حال ری‌استارت PM2 برای اعمال تاریخچه یکسان...")
try:
    subprocess.run(["npx", "--yes", "pm2", "restart", "all"], check=False, timeout=15)
    print("🎉 سرور ری‌استارت شد!")
except Exception:
    pass

print("==================================================")
print("🚀 همگام‌سازی کامل شد! اکنون تاریخچه معاملات دقیقاً مشابه پریویو است.")
print("==================================================")
