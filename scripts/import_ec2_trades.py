import json
import sqlite3
import os

user_text = """
۱۸:۴۷:۵۴	ADA/USDT	LONG	1148	$0.209	$0.35	$0.00	+$161.67	TAKE_PROFIT
۱۸:۴۴:۱۴	ADA/USDT	LONG	1151	$0.209	$0.209	$0.24	+$0.46	SCALP_TAKE_PROFIT
۱۸:۳۷:۳۰	ADA/USDT	LONG	1153	$0.208	$0.35	$0.32	+$163.30	TAKE_PROFIT
۱۷:۲۰:۴۷	ADA/USDT	LONG	1153	$0.208	$0.351	$0.32	+$164.91	TAKE_PROFIT
۱۷:۲۰:۱۲	ADA/USDT	LONG	1169	$0.205	$0.351	$0.33	+$170.58	TAKE_PROFIT
۱۶:۵۳:۲۶	ADA/USDT	LONG	1154	$0.208	$0.209	$0.24	+$0.46	SCALP_TAKE_PROFIT
۱۶:۵۲:۰۶	AVAX/USDT	LONG	31.8302	$7.54	$7.56	$0.24	+$0.52	SCALP_TAKE_PROFIT
۱۶:۵۲:۰۵	SOL/USDT	LONG	2.3678	$101.37	$101.61	$0.24	+$0.45	SCALP_TAKE_PROFIT
۱۶:۵۲:۰۵	ADA/USDT	LONG	1158	$0.207	$0.208	$0.24	+$0.69	SCALP_TAKE_PROFIT
۱۶:۵۱:۲۷	AVAX/USDT	LONG	31.8725	$7.53	$28.5	$0.57	+$667.92	TAKE_PROFIT
۱۶:۵۱:۲۷	ADA/USDT	LONG	1158	$0.207	$0.36	$0.33	+$176.73	TAKE_PROFIT
۱۶:۵۱:۲۷	SOL/USDT	LONG	2.3643	$101.52	$142.47	$0.29	+$96.65	TAKE_PROFIT
۱۶:۵۰:۴۷	AVAX/USDT	LONG	31.8725	$7.53	$28.51	$0.57	+$668.24	TAKE_PROFIT
۱۶:۵۰:۴۷	ADA/USDT	LONG	1158	$0.207	$0.36	$0.33	+$176.62	TAKE_PROFIT
۱۶:۵۰:۴۷	SOL/USDT	LONG	2.3643	$101.52	$142.51	$0.29	+$96.74	TAKE_PROFIT
۱۶:۴۴:۵۳	AVAX/USDT	LONG	31.7041	$7.57	$28.5	$0.57	+$663.12	TAKE_PROFIT
۱۶:۴۴:۵۳	SOL/USDT	LONG	2.3652	$101.48	$142.52	$0.29	+$96.90	TAKE_PROFIT
۱۶:۴۴:۵۳	ADA/USDT	LONG	1158	$0.207	$0.36	$0.33	+$176.73	TAKE_PROFIT
۱۶:۴۱:۱۵	AVAX/USDT	LONG	31.746	$7.56	$7.58	$0.24	+$0.51	SCALP_TAKE_PROFIT
۱۶:۴۰:۳۵	SOL/USDT	LONG	2.3701	$101.27	$101.47	$0.24	+$0.35	SCALP_TAKE_PROFIT
۱۶:۳۸:۳۲	LINK/USDT	SHORT	20.339	$11.8	$11.65	$0.24	+$2.93	SCALP_TAKE_PROFIT
۱۶:۳۸:۳۰	AVAX/USDT	LONG	31.679	$7.58	$28.51	$0.57	+$662.59	TAKE_PROFIT
۱۶:۳۸:۳۰	ADA/USDT	LONG	1149	$0.209	$0.36	$0.33	+$173.63	TAKE_PROFIT
۱۶:۳۸:۳۰	SOL/USDT	LONG	2.3631	$101.57	$142.5	$0.29	+$96.55	TAKE_PROFIT
۱۶:۳۰:۲۰	FLOKI/USDT	SHORT	1655172	$0	$0	$0.14	+$198.60	TAKE_PROFIT
۱۶:۳۰:۱۷	DOT/USDT	LONG	219	$1.1	$4.3	$0.59	+$700.33	TAKE_PROFIT
۱۶:۳۰:۱۷	ADA/USDT	LONG	1147	$0.209	$0.36	$0.33	+$172.64	TAKE_PROFIT
۱۶:۳۰:۱۷	AVAX/USDT	LONG	31.4961	$7.62	$28.5	$0.57	+$657.19	TAKE_PROFIT
۱۶:۲۸:۱۴	DOT/USDT	LONG	218	$1.1	$1.09	$0.24	$-2.30	STOP_LOSS
۱۶:۲۷:۴۱	DOT/USDT	LONG	217	$1.11	$1.09	$0.24	$-4.46	STOP_LOSS
۱۶:۲۱:۰۶	ADA/USDT	LONG	1149	$0.209	$0.209	$0.24	+$0.45	SCALP_TAKE_PROFIT
۱۶:۱۸:۴۳	DOT/USDT	LONG	218	$1.1	$1.11	$0.24	+$2.06	SCALP_TAKE_PROFIT
۱۶:۱۸:۴۰	DOT/USDT	LONG	216	$1.11	$1.1	$0.24	$-2.28	STOP_LOSS
۱۶:۱۸:۲۸	DOT/USDT	LONG	218	$1.1	$1.1	$0.24	$-0.12	SCALP_TAKE_PROFIT
۱۶:۱۸:۲۲	DOT/USDT	LONG	218	$1.1	$1.1	$0.24	$-0.12	SCALP_TAKE_PROFIT
۱۶:۱۸:۱۹	DOT/USDT	LONG	218	$1.1	$1.1	$0.24	$-0.12	SCALP_TAKE_PROFIT
۱۶:۱۸:۱۶	DOT/USDT	LONG	218	$1.1	$1.1	$0.24	$-0.12	SCALP_TAKE_PROFIT
۱۶:۱۸:۱۳	DOT/USDT	LONG	218	$1.1	$1.1	$0.24	$-0.12	SCALP_TAKE_PROFIT
۱۶:۱۸:۰۷	ADA/USDT	LONG	1152	$0.208	$0.209	$0.24	+$0.46	SCALP_TAKE_PROFIT
۱۶:۱۸:۰۷	SOL/USDT	LONG	2.3685	$101.34	$101.55	$0.24	+$0.38	SCALP_TAKE_PROFIT
۱۶:۱۷:۳۴	SOL/USDT	LONG	2.3746	$101.08	$101.3	$0.24	+$0.40	SCALP_TAKE_PROFIT
۱۶:۱۷:۲۸	ADA/USDT	LONG	1154	$0.208	$0.208	$0.24	+$0.46	SCALP_TAKE_PROFIT
۱۶:۰۷:۲۱	SOL/USDT	LONG	2.384	$100.68	$101.21	$0.24	+$1.14	SCALP_TAKE_PROFIT
۱۶:۰۷:۲۱	ADA/USDT	LONG	1157	$0.208	$0.208	$0.24	+$0.69	SCALP_TAKE_PROFIT
۱۶:۰۷:۲۱	AVAX/USDT	LONG	31.5375	$7.61	$7.63	$0.24	+$0.51	SCALP_TAKE_PROFIT
۱۶:۰۷:۱۲	ADA/USDT	LONG	1158	$0.207	$0.208	$0.24	+$0.46	SCALP_TAKE_PROFIT
۱۶:۰۷:۰۳	SOL/USDT	LONG	2.3916	$100.36	$100.67	$0.24	+$0.62	SCALP_TAKE_PROFIT
۱۶:۰۷:۰۳	ADA/USDT	LONG	1161	$0.207	$0.207	$0.24	+$0.58	SCALP_TAKE_PROFIT
۱۶:۰۷:۰۳	AVAX/USDT	LONG	31.8302	$7.54	$7.57	$0.24	+$0.83	SCALP_TAKE_PROFIT
۱۶:۰۶:۴۲	AVAX/USDT	LONG	31.9574	$7.51	$7.56	$0.24	+$1.48	SCALP_TAKE_PROFIT
"""

def fa_to_en(text):
    fa_digits = '۰۱۲۳۴۵۶۷۸۹'
    en_digits = '0123456789'
    for f, e in zip(fa_digits, en_digits):
        text = text.replace(f, e)
    return text

parsed_trades = []
for idx, line in enumerate(user_text.strip().split('\n')):
    parts = line.split('\t')
    if len(parts) < 9:
        continue
    time_fa, sym, side, size_str, ep_str, xp_str, fee_str, pnl_str, reason = parts[:9]
    
    time_en = fa_to_en(time_fa)
    h, m, s = [int(x) for x in time_en.split(':')]
    total_minutes = h * 60 + m - 210
    if total_minutes < 0:
        total_minutes += 1440
        date_str = '2026-09-11'
    else:
        date_str = '2026-09-12'
    
    utc_h = total_minutes // 60
    utc_m = total_minutes % 60
    iso_time = f"{date_str}T{utc_h:02d}:{utc_m:02d}:{s:02d}.{idx:03d}Z"
    
    size_val = float(fa_to_en(size_str).replace(',', ''))
    ep_val = float(fa_to_en(ep_str).replace('$', '').replace(',', ''))
    xp_val = float(fa_to_en(xp_str).replace('$', '').replace(',', ''))
    fee_val = float(fa_to_en(fee_str).replace('$', '').replace(',', ''))
    pnl_val = float(fa_to_en(pnl_str).replace('$', '').replace('+', '').replace(',', '').strip())
    
    trade_id = f"tr_ec2_{1789225000000 - idx * 1000}"
    parsed_trades.append({
        "id": trade_id,
        "order_id": trade_id,
        "symbol": sym,
        "side": side,
        "size": size_val,
        "leverage": 12,
        "entry_price": ep_val,
        "exit_price": xp_val,
        "gross_pnl": round(pnl_val + fee_val, 2),
        "fee": fee_val,
        "net_pnl": pnl_val,
        "roi_pct": round((pnl_val / max(size_val * ep_val / 12, 1)) * 100, 2),
        "close_reason": reason,
        "opened_at": iso_time,
        "closed_at": iso_time,
        "created_at": iso_time,
        "strategy": "AGENT_60_FEATURES",
        "features_snapshot_json": None
    })

print(f"Parsed {len(parsed_trades)} exact trades from EC2 user report.")

# Update trades_seed.json
seed_path = "data/trades_seed.json"
if os.path.exists(seed_path):
    with open(seed_path, "r", encoding="utf-8") as f:
        seed_data = json.load(f)
    # Put these 50 trades directly on top
    seed_data["closed_trades"] = parsed_trades
    with open(seed_path, "w", encoding="utf-8") as f:
        json.dump(seed_data, f, indent=2, ensure_ascii=False)
    print("Updated data/trades_seed.json")

# Update trading_store.json
store_path = "data/trading_store.json"
if os.path.exists(store_path):
    with open(store_path, "r", encoding="utf-8") as f:
        store_data = json.load(f)
    store_data["closed_trades"] = parsed_trades
    with open(store_path, "w", encoding="utf-8") as f:
        json.dump(store_data, f, indent=2, ensure_ascii=False)
    print("Updated data/trading_store.json")

# Update trading.db
db_path = "data/trading.db"
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("DELETE FROM closed_trades")
    insert_sql = """
    INSERT INTO closed_trades (
        id, order_id, symbol, side, size, leverage, entry_price, exit_price,
        gross_pnl, fee, net_pnl, roi_pct, close_reason, opened_at, closed_at,
        created_at, strategy, features_snapshot_json
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    for t in parsed_trades:
        cur.execute(insert_sql, (
            t["id"], t["order_id"], t["symbol"], t["side"], t["size"], t["leverage"],
            t["entry_price"], t["exit_price"], t["gross_pnl"], t["fee"], t["net_pnl"],
            t["roi_pct"], t["close_reason"], t["opened_at"], t["closed_at"],
            t["created_at"], t["strategy"], t["features_snapshot_json"]
        ))
    conn.commit()
    conn.close()
    print("Updated SQLite database data/trading.db with exact 50 trades.")
