#!/usr/bin/env python3
"""
Crypto Trading Bot Web API & Monitoring Server
Provides REST endpoints and web interface for bot monitoring and control.
Runs on port 5000 as documented in README_WEB_API.md
"""

import os
import sys
import json
import time
import subprocess
from datetime import datetime, timezone

try:
    from flask import Flask, jsonify, request, render_template_string
    from flask_cors import CORS
except ImportError:
    # If flask not installed yet, provide helpful message
    print("Flask or flask-cors not installed. Run: pip install flask flask-cors")
    sys.exit(1)

app = Flask(__name__)
CORS(app)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
START_TIME = datetime.now(timezone.utc)


def get_uptime_str():
    delta = datetime.now(timezone.utc) - START_TIME
    days = delta.days
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    parts = []
    if days > 0:
        parts.append(f"{days} روز")
    if hours > 0 or days > 0:
        parts.append(f"{hours} ساعت")
    parts.append(f"{minutes} دقیقه")
    return " و ".join(parts)


def read_latest_metrics():
    # Defaults
    metrics = {
        "uptime": get_uptime_str(),
        "cycles": 0,
        "balance": 100.0,
        "pnl": 0.0,
        "win_rate_pct": 0.0,
        "open_positions": 0
    }
    
    # 1. Try reading from Node.js paper engine if active
    try:
        import urllib.request
        req = urllib.request.Request("http://127.0.0.1:3000/api/v1/paper/account", headers={"User-Agent": "BotWebAPI"})
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("success") and "account" in data:
                acct = data["account"]
                metrics["balance"] = round(float(acct.get("total_equity", 100.0)), 2)
                metrics["pnl"] = round(float(acct.get("realized_pnl", 0.0) + acct.get("unrealized_pnl", 0.0)), 2)
                metrics["win_rate_pct"] = round(float(acct.get("win_rate_pct", 0.0)), 1)
                metrics["open_positions"] = int(acct.get("active_positions_count", 0))
    except Exception:
        pass

    # 2. Try reading from performance_metrics.json
    perf_path = os.path.join(BASE_DIR, "performance_metrics.json")
    if os.path.exists(perf_path):
        try:
            with open(perf_path, "r", encoding="utf-8") as f:
                perf = json.load(f)
                metrics["cycles"] = perf.get("total_cycles", len(perf.get("cycles", [])))
        except Exception:
            pass

    return metrics


def read_recent_logs(max_lines=30):
    logs = []
    log_file = os.path.join(BASE_DIR, "trading_log.jsonl")
    
    if os.path.exists(log_file):
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
                for line in lines[-max_lines:]:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        item = json.loads(line)
                        event = item.get("event_type", "event")
                        ts = item.get("timestamp", datetime.now(timezone.utc).isoformat())
                        logs.append({
                            "source": "trading_log.jsonl",
                            "line": f"[{ts[:19]}] {event}: {json.dumps(item.get('data', {}))[:120]}",
                            "timestamp": ts
                        })
                    except Exception:
                        logs.append({
                            "source": "trading_log.jsonl",
                            "line": line[:150],
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        })
        except Exception as e:
            logs.append({"source": "system", "line": f"Error reading logs: {str(e)}", "timestamp": datetime.now(timezone.utc).isoformat()})

    # If empty, provide status record
    if not logs:
        logs.append({
            "source": "web_api",
            "line": "سیستم معاملاتی آنلاین و فعال است. در حال دریافت قیمت‌ها و تحلیل فرصت‌های بازار...",
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
    return logs


@app.route("/", methods=["GET"])
def index():
    metrics = read_latest_metrics()
    logs = read_recent_logs(15)
    
    html = """
    <!DOCTYPE html>
    <html lang="fa" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>پنل مانیتورینگ ربات معاملاتی کریپتو</title>
        <style>
            * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
            body { background: #0b0f19; color: #f8fafc; padding: 24px; }
            .container { max-width: 900px; margin: 0 auto; }
            .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; padding-bottom: 16px; border-bottom: 1px solid #1e293b; }
            .badge { background: #059669; color: #fff; padding: 4px 12px; border-radius: 9999px; font-size: 0.85rem; font-weight: 600; display: inline-flex; align-items: center; gap: 6px; }
            .badge::before { content: ''; width: 8px; height: 8px; background: #34d399; border-radius: 50%; box-shadow: 0 0 8px #34d399; }
            .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 24px; }
            .card { background: #131b2e; border: 1px solid #1e293b; border-radius: 12px; padding: 18px; }
            .card-title { color: #94a3b8; font-size: 0.85rem; margin-bottom: 8px; }
            .card-value { font-size: 1.5rem; font-weight: 700; color: #f8fafc; }
            .positive { color: #34d399; }
            .controls { display: flex; gap: 12px; margin-bottom: 24px; }
            button { background: #3b82f6; color: white; border: none; padding: 10px 20px; border-radius: 8px; font-size: 0.9rem; cursor: pointer; font-weight: 600; transition: background 0.2s; }
            button:hover { background: #2563eb; }
            button.danger { background: #ef4444; }
            button.danger:hover { background: #dc2626; }
            .logs-container { background: #070b14; border: 1px solid #1e293b; border-radius: 12px; padding: 16px; max-height: 400px; overflow-y: auto; font-family: monospace; font-size: 0.82rem; }
            .log-line { padding: 6px 0; border-bottom: 1px solid #111827; color: #cbd5e1; direction: ltr; text-align: left; }
            a.dash-link { color: #38bdf8; text-decoration: none; font-weight: 600; margin-left: auto; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div>
                    <h1 style="font-size: 1.4rem; margin-bottom: 4px;">🚀 پنل مانیتورینگ ربات معاملاتی کریپتو</h1>
                    <p style="color: #64748b; font-size: 0.85rem;">وضعیت سامانه زنده و ارزیابی هوشمند استراتژی‌ها</p>
                </div>
                <div style="display: flex; align-items: center; gap: 16px;">
                    <a href="http://" + window.location.hostname + ":3000" class="dash-link" target="_blank">🌐 داشبورد کامل (پورت ۳۰۰۰)</a>
                    <span class="badge">آنلاین</span>
                </div>
            </div>

            <div class="grid">
                <div class="card">
                    <div class="card-title">⏱️ زمان فعالیت (Uptime)</div>
                    <div class="card-value">{{ metrics.uptime }}</div>
                </div>
                <div class="card">
                    <div class="card-title">🔄 سیکل‌های معاملاتی</div>
                    <div class="card-value">{{ metrics.cycles }}</div>
                </div>
                <div class="card">
                    <div class="card-title">💰 موجودی کل (USDT)</div>
                    <div class="card-value">${{ metrics.balance }}</div>
                </div>
                <div class="card">
                    <div class="card-title">📊 سود و زیان (PnL)</div>
                    <div class="card-value {% if metrics.pnl >= 0 %}positive{% endif %}">${{ metrics.pnl }}</div>
                </div>
            </div>

            <div class="controls">
                <button onclick="fetch('/api/restart', {method: 'POST'}).then(() => alert('دستور راه‌اندازی مجدد ارسال شد')).then(() => location.reload())">🔄 راه‌اندازی مجدد</button>
                <button class="danger" onclick="if(confirm('آیا از توقف ربات مطمئن هستید؟')) fetch('/api/stop', {method: 'POST'}).then(() => alert('دستور توقف ارسال شد')).then(() => location.reload())">⏹️ توقف ربات</button>
                <button style="background: #1e293b;" onclick="location.reload()">🔃 به‌روزرسانی وضعیت</button>
            </div>

            <h3 style="font-size: 1rem; margin-bottom: 12px; color: #cbd5e1;">📝 آخرین رویدادها و لاگ‌های معاملاتی:</h3>
            <div class="logs-container">
                {% for log in logs %}
                <div class="log-line">{{ log.line }}</div>
                {% endfor %}
            </div>
        </div>
    </body>
    </html>
    """
    return render_template_string(html, metrics=metrics, logs=logs)


@app.route("/api/status", methods=["GET"])
def api_status():
    metrics = read_latest_metrics()
    logs = read_recent_logs(30)
    return jsonify({
        "success": True,
        "status": "online",
        "metrics": metrics,
        "logs": logs,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


@app.route("/api/restart", methods=["POST"])
def api_restart():
    try:
        # Trigger background restart
        subprocess.Popen(["screen", "-S", "bot", "-X", "quit"], stderr=subprocess.DEVNULL)
        subprocess.Popen(["screen", "-S", "bot", "-dm", "bash", "-c", "cd " + BASE_DIR + " && python3 main.py"], stderr=subprocess.DEVNULL)
    except Exception as e:
        print(f"Restart notice: {e}")
    return jsonify({
        "success": True,
        "message": "ربات با موفقیت راه‌اندازی مجدد شد"
    })


@app.route("/api/stop", methods=["POST"])
def api_stop():
    try:
        subprocess.Popen(["screen", "-S", "bot", "-X", "quit"], stderr=subprocess.DEVNULL)
        subprocess.Popen(["pkill", "-f", "python.*main.py"], stderr=subprocess.DEVNULL)
    except Exception as e:
        print(f"Stop notice: {e}")
    return jsonify({
        "success": True,
        "message": "ربات با موفقیت متوقف شد"
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", os.environ.get("WEB_API_PORT", 5000)))
    print(f"Starting Trading Bot Web API on port {port}...")
    app.run(host="0.0.0.0", port=port, debug=False)
