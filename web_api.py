#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Web API برای نمایش وضعیت ربات معاملاتی کریپتو با تمام قابلیت‌ها
Crypto Trading Bot Web API with Full Capabilities Monitoring

این فایل یک رابط وب زیبا و فارسی برای مانیتورینگ تمام ۶۰ قابلیت ربات معاملاتی فراهم می‌کند.
هر قابلیت دارای لاگ اختصاصی است و لاگ‌ها به صورت خودکار توسط LLM تحلیل می‌شوند.
"""

import os
import sys
import json
import glob
import subprocess
import requests
from datetime import datetime, timedelta
from flask import Flask, jsonify, render_template_string, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# مسیر پروژه
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILES = [
    os.path.join(PROJECT_DIR, 'detailed_trading.log'),
    os.path.join(PROJECT_DIR, 'logs', 'trading.log'),
    os.path.join(PROJECT_DIR, '.screenlog.0'),
    os.path.join(PROJECT_DIR, 'server.log'),
]

# فایل ذخیره وضعیت ربات
BOT_STATE_FILE = os.path.join(PROJECT_DIR, '.bot_state')
CAPABILITIES_LOG_DIR = os.path.join(PROJECT_DIR, 'capabilities_logs')
LLM_ANALYSIS_DIR = os.path.join(PROJECT_DIR, 'llm_analysis')

# ایجاد پوشه‌ها اگر وجود ندارند
os.makedirs(CAPABILITIES_LOG_DIR, exist_ok=True)
os.makedirs(LLM_ANALYSIS_DIR, exist_ok=True)

# لیست کامل ۶۰ قابلیت در ۷ دسته
ALL_CAPABILITIES = {
    "core_trading": {
        "name": "ترید الگوریتمی",
        "capabilities": [
            {"id": "crypto_algo_trading", "name": "ترید الگوریتمی کریپتو", "icon": "🤖"},
            {"id": "multi_exchange", "name": "پشتیبانی چند صرافی (Binance, Bybit, KuCoin)", "icon": "🏢"},
            {"id": "market_data", "name": "دریافت داده بازار (OHLCV, قیمت, حجم)", "icon": "📊"},
            {"id": "multi_timeframe", "name": "تحلیل چند تایم‌فریمی", "icon": "⏱️"},
            {"id": "technical_strategies", "name": "استراتژی‌های تکنیکال متعدد", "icon": "📈"},
            {"id": "market_regime", "name": "تشخیص Market Regime", "icon": "🔍"},
            {"id": "ensemble_strategies", "name": "ترکیب چند استراتژی (Ensemble)", "icon": "🎯"},
            {"id": "portfolio_optimization", "name": "Portfolio Optimization", "icon": "⚖️"},
        ]
    },
    "risk_management": {
        "name": "مدیریت ریسک",
        "capabilities": [
            {"id": "risk_management", "name": "Risk Management (Exposure, Drawdown, Volatility)", "icon": "🛡️"},
            {"id": "position_sizing", "name": "Position Sizing", "icon": "📏"},
            {"id": "stop_loss_take_profit", "name": "Stop Loss / Take Profit", "icon": "🛑"},
            {"id": "trailing_stop", "name": "Trailing Stop", "icon": "📉"},
            {"id": "breakeven", "name": "Breakeven Stop", "icon": "⚖️"},
            {"id": "partial_take_profit", "name": "Partial Take Profit", "icon": "💰"},
            {"id": "max_positions", "name": "حداکثر تعداد پوزیشن و Exposure", "icon": "🔢"},
            {"id": "circuit_breaker", "name": "Circuit Breaker", "icon": "⚡"},
            {"id": "kill_switch", "name": "Kill Switch", "icon": "🔴"},
            {"id": "live_safety_engine", "name": "Live Safety Engine", "icon": "🔐"},
        ]
    },
    "order_execution": {
        "name": "اجرای سفارشات",
        "capabilities": [
            {"id": "order_manager", "name": "Order Manager", "icon": "📝"},
            {"id": "idempotency", "name": "Idempotency (جلوگیری از سفارش تکراری)", "icon": "✅"},
            {"id": "fill_manager", "name": "Fill Manager (Partial/Full Fills)", "icon": "🧩"},
            {"id": "position_manager", "name": "Position Manager", "icon": "📦"},
            {"id": "exchange_reconciliation", "name": "Exchange Reconciliation", "icon": "🔄"},
            {"id": "crash_recovery", "name": "Crash Recovery", "icon": "♻️"},
        ]
    },
    "backtesting_quant": {
        "name": "بک‌تست و کوانت",
        "capabilities": [
            {"id": "walk_forward_backtest", "name": "Walk-Forward Backtesting", "icon": "🔙"},
            {"id": "out_of_sample", "name": "Out-of-Sample Testing", "icon": "🧪"},
            {"id": "transaction_cost", "name": "Transaction Cost Modeling", "icon": "💸"},
            {"id": "slippage_modeling", "name": "Slippage Modeling", "icon": "📊"},
            {"id": "no_trade_zone", "name": "No-Trade Zone", "icon": "🚫"},
            {"id": "benchmarking", "name": "Benchmarking", "icon": "📈"},
            {"id": "ensemble_backtest", "name": "Ensemble Backtesting", "icon": "🎭"},
            {"id": "performance_metrics", "name": "Performance Metrics", "icon": "📉"},
            {"id": "regime_analysis", "name": "Regime-based Analysis", "icon": "🔬"},
            {"id": "monte_carlo", "name": "Monte Carlo / Robustness Analysis", "icon": "🎲"},
        ]
    },
    "ai_ml": {
        "name": "هوش مصنوعی و یادگیری ماشین",
        "capabilities": [
            {"id": "ml_pipeline", "name": "ML Pipeline", "icon": "🔧"},
            {"id": "feature_engineering", "name": "Feature Engineering", "icon": "🔨"},
            {"id": "causal_features", "name": "Causal Feature Engineering", "icon": "🔗"},
            {"id": "purged_walkforward", "name": "Purged Walk-Forward Validation", "icon": "🚿"},
            {"id": "ml_prediction", "name": "ML Prediction", "icon": "🔮"},
            {"id": "model_registry", "name": "Model Registry & Versioning", "icon": "📚"},
            {"id": "model_drift", "name": "Model Drift Monitoring", "icon": "📡"},
            {"id": "ml_strategy_integration", "name": "ترکیب ML با استراتژی‌های معاملاتی", "icon": "🔀"},
        ]
    },
    "ai_sentiment": {
        "name": "تحلیل احساسات و اخبار",
        "capabilities": [
            {"id": "sentiment_analysis", "name": "Sentiment Analysis", "icon": "😊"},
            {"id": "news_context", "name": "News/Context Analysis", "icon": "📰"},
            {"id": "llm_integration", "name": "LLM Integration", "icon": "🧠"},
            {"id": "sentiment_signal", "name": "استفاده از Sentiment به‌عنوان سیگنال", "icon": "📶"},
        ]
    },
    "infrastructure": {
        "name": "زیرساخت و مانیتورینگ",
        "capabilities": [
            {"id": "fastapi", "name": "FastAPI Backend", "icon": "⚡"},
            {"id": "trading_api", "name": "Trading API", "icon": "🌐"},
            {"id": "health_monitoring", "name": "Health / Status Monitoring", "icon": "❤️"},
            {"id": "logging", "name": "Logging System", "icon": "📝"},
            {"id": "observability", "name": "Observability", "icon": "👁️"},
            {"id": "config_management", "name": "Configuration Management", "icon": "⚙️"},
            {"id": "database", "name": "SQLite/PostgreSQL Database", "icon": "🗄️"},
            {"id": "docker_deployment", "name": "Docker/Deployment Support", "icon": "🐳"},
            {"id": "ci_cd", "name": "CI/CD Support", "icon": "🔄"},
            {"id": "paper_trading", "name": "Paper Trading", "icon": "📄"},
            {"id": "shadow_trading", "name": "Shadow Trading", "icon": "👤"},
            {"id": "live_trading", "name": "Live Trading Architecture", "icon": "🔴"},
        ]
    }
}

# آدرس API برای تحلیل LLM (Groq API)
GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')
LLM_API_URL = 'https://api.groq.com/openai/v1/chat/completions'
LLM_MODEL = 'llama-3.1-70b-versatile'


def get_bot_state():
    """دریافت وضعیت ربات از فایل یا بررسی فرآیند در حال اجرا"""
    try:
        if os.path.exists(BOT_STATE_FILE):
            with open(BOT_STATE_FILE, 'r', encoding='utf-8') as f:
                state = f.read().strip()
                return state if state in ['online', 'offline'] else 'unknown'
        
        result = subprocess.run(
            ['pgrep', '-f', 'python.*main.py'],
            capture_output=True,
            text=True
        )
        if result.returncode == 0 and result.stdout.strip():
            return 'online'
        
        result = subprocess.run(
            ['screen', '-ls'],
            capture_output=True,
            text=True
        )
        if 'bot' in result.stdout and ('Attached' in result.stdout or len(result.stdout.split('\n')) > 2):
            return 'online'
            
        return 'offline'
    except Exception as e:
        app.logger.error(f"Error getting bot state: {e}")
        return 'unknown'


def set_bot_state(state):
    """ذخیره وضعیت ربات"""
    try:
        with open(BOT_STATE_FILE, 'w', encoding='utf-8') as f:
            f.write(state)
    except Exception as e:
        app.logger.error(f"Error setting bot state: {e}")


def log_capability_event(capability_id, event_type, message, details=None):
    """ثبت رویداد برای یک قابلیت"""
    try:
        log_file = os.path.join(CAPABILITIES_LOG_DIR, f"{capability_id}.jsonl")
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "message": message,
            "details": details or {}
        }
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
        return True
    except Exception as e:
        app.logger.error(f"Error logging capability event: {e}")
        return False


def analyze_with_llm(capability_id, log_entries):
    """ارسال لاگ‌ها به LLM برای تحلیل"""
    try:
        # ساخت پرامپت برای تحلیل
        logs_text = "\n".join([f"- {entry['timestamp']}: {entry['message']}" for entry in log_entries[-10:]])
        
        prompt = f"""
تحلیل وضعیت قابلیت: {capability_id}

لاگ‌های اخیر:
{logs_text}

لطفاً وضعیت این قابلیت را تحلیل کن و موارد زیر را مشخص کن:
1. وضعیت فعلی (سالم/هشدار/خطا)
2. مشکلات احتمالی
3. پیشنهادات بهبود

پاسخ را به صورت JSON بده با فیلدهای: status, issues, recommendations
"""
        
        payload = {
            "model": LLM_MODEL,
            "prompt": prompt,
            "stream": False,
            "max_tokens": 500
        }
        
        response = requests.post(LLM_API_URL, json=payload, timeout=30)
        if response.status_code == 200:
            result = response.json()
            analysis = {
                "timestamp": datetime.now().isoformat(),
                "capability_id": capability_id,
                "analysis": result.get('response', ''),
                "raw_response": result
            }
            
            # ذخیره تحلیل
            analysis_file = os.path.join(LLM_ANALYSIS_DIR, f"{capability_id}_analysis.json")
            with open(analysis_file, 'w', encoding='utf-8') as f:
                json.dump(analysis, f, ensure_ascii=False, indent=2)
            
            return analysis
        else:
            app.logger.warning(f"LLM API returned status {response.status_code}")
            return None
            
    except requests.exceptions.RequestException as e:
        app.logger.warning(f"LLM API request failed: {e}")
        return None
    except Exception as e:
        app.logger.error(f"Error analyzing with LLM: {e}")
        return None


def get_capability_logs(capability_id, limit=10):
    """دریافت لاگ‌های یک قابلیت"""
    try:
        log_file = os.path.join(CAPABILITIES_LOG_DIR, f"{capability_id}.jsonl")
        if not os.path.exists(log_file):
            return []
        
        logs = []
        with open(log_file, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    logs.append(json.loads(line.strip()))
                except:
                    continue
        
        return logs[-limit:]
    except Exception as e:
        app.logger.error(f"Error getting capability logs: {e}")
        return []


def get_llm_analysis(capability_id):
    """دریافت تحلیل LLM برای یک قابلیت"""
    try:
        analysis_file = os.path.join(LLM_ANALYSIS_DIR, f"{capability_id}_analysis.json")
        if os.path.exists(analysis_file):
            with open(analysis_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None
    except Exception as e:
        app.logger.error(f"Error getting LLM analysis: {e}")
        return None


def get_category_evaluation(category_key):
    """دریافت ارزیابی LLM برای یک دسته‌بندی"""
    try:
        eval_file = os.path.join(LLM_ANALYSIS_DIR, f"{category_key}_category_eval.json")
        if os.path.exists(eval_file):
            with open(eval_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None
    except Exception as e:
        app.logger.error(f"Error getting category evaluation: {e}")
        return None


def get_all_category_evaluations():
    """دریافت تمام ارزیابی‌های دسته‌بندی"""
    evaluations = {}
    for category_key in ALL_CAPABILITIES.keys():
        evaluations[category_key] = get_category_evaluation(category_key)
    return evaluations


def read_last_lines(filepath, num_lines=30):
    """خواندن آخرین خطوط یک فایل لاگ"""
    try:
        if not os.path.exists(filepath):
            return []
        
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
            return lines[-num_lines:] if len(lines) > num_lines else lines
    except Exception as e:
        app.logger.error(f"Error reading log file {filepath}: {e}")
        return []


def get_all_logs():
    """دریافت لاگ‌ها از تمام منابع"""
    all_logs = []
    
    for log_file in LOG_FILES:
        logs = read_last_lines(log_file)
        for line in logs:
            all_logs.append({
                'source': os.path.basename(log_file),
                'line': line.strip(),
                'timestamp': datetime.now().isoformat()
            })
    
    all_logs.reverse()
    return all_logs[:30]


def get_metrics():
    """دریافت متریک‌های ربات"""
    metrics = {
        'uptime': 'نامشخص',
        'cycles': 0,
        'balance': 0.0,
        'pnl': 0.0,
        'last_trade': None,
        'active_strategies': 0,
        'total_capabilities': 60,
        'active_logs': 0
    }
    
    try:
        result = subprocess.run(
            ['pgrep', '-f', 'python.*main.py'],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            pids = result.stdout.strip().split('\n')
            if pids:
                pid = pids[0]
                stat_file = f'/proc/{pid}/stat'
                if os.path.exists(stat_file):
                    with open(stat_file, 'r') as f:
                        stat = f.read().split()
                        if len(stat) > 21:
                            starttime = int(stat[21])
                            clk_tck = os.sysconf(os.sysconf_names['SC_CLK_TCK'])
                            uptime_seconds = (datetime.now().timestamp() - (starttime / clk_tck))
                            days = int(uptime_seconds // 86400)
                            hours = int((uptime_seconds % 86400) // 3600)
                            minutes = int((uptime_seconds % 3600) // 60)
                            metrics['uptime'] = f"{days}روز و {hours}ساعت و {minutes}دقیقه"
    except Exception as e:
        app.logger.error(f"Error getting uptime: {e}")
    
    try:
        all_logs = ''.join([log['line'] for log in get_all_logs()])
        cycle_count = all_logs.count('cycle') + all_logs.count('Cycle') + all_logs.count('سیکل')
        metrics['cycles'] = max(cycle_count, 0)
    except Exception as e:
        app.logger.error(f"Error getting cycles: {e}")
    
    # شمارش لاگ‌های فعال قابلیت‌ها
    try:
        if os.path.exists(CAPABILITIES_LOG_DIR):
            log_files = [f for f in os.listdir(CAPABILITIES_LOG_DIR) if f.endswith('.jsonl')]
            metrics['active_logs'] = len(log_files)
    except Exception as e:
        app.logger.error(f"Error counting active logs: {e}")
    
    return metrics


def simulate_capability_activity():
    """شبیه‌سازی فعالیت قابلیت‌ها برای نمایش لاگ"""
    import random
    
    for category_key, category_data in ALL_CAPABILITIES.items():
        for cap in category_data['capabilities']:
            cap_id = cap['id']
            
            # احتمال تولید لاگ جدید
            if random.random() < 0.3:  # 30% chance
                event_types = ['info', 'success', 'warning', 'error']
                weights = [0.6, 0.25, 0.1, 0.05]
                event_type = random.choices(event_types, weights=weights)[0]
                
                messages = {
                    'info': f'عملیات عادی در حال اجرا - {cap["name"]}',
                    'success': f'عملیات با موفقیت انجام شد - {cap["name"]}',
                    'warning': f'هشدار: عملکرد زیر بهینه - {cap["name"]}',
                    'error': f'خطا در پردازش - {cap["name"]}'
                }
                
                log_capability_event(
                    cap_id,
                    event_type,
                    messages[event_type],
                    {'random_value': random.randint(1, 100)}
                )


# قالب HTML
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ربات معاملاتی کریپتو | Crypto Trading Bot Dashboard</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Tahoma', 'Segoe UI', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
            color: #fff;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        
        header {
            text-align: center;
            margin-bottom: 30px;
            padding: 20px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 15px;
            backdrop-filter: blur(10px);
        }
        
        h1 {
            font-size: 2em;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        
        .status-indicator {
            display: inline-block;
            width: 20px;
            height: 20px;
            border-radius: 50%;
            margin-left: 10px;
            animation: pulse 2s infinite;
        }
        
        .status-online {
            background-color: #4ade80;
            box-shadow: 0 0 10px #4ade80;
        }
        
        .status-offline {
            background-color: #f87171;
            box-shadow: 0 0 10px #f87171;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .metric-card {
            background: rgba(255, 255, 255, 0.15);
            padding: 20px;
            border-radius: 10px;
            text-align: center;
            backdrop-filter: blur(5px);
        }
        
        .metric-value {
            font-size: 2em;
            font-weight: bold;
            margin-bottom: 5px;
        }
        
        .metric-label {
            font-size: 0.9em;
            opacity: 0.9;
        }
        
        .category-section {
            background: rgba(255, 255, 255, 0.1);
            border-radius: 15px;
            padding: 20px;
            margin-bottom: 25px;
            backdrop-filter: blur(10px);
        }
        
        .category-header {
            font-size: 1.5em;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid rgba(255, 255, 255, 0.2);
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .capabilities-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 15px;
        }
        
        .capability-card {
            background: rgba(255, 255, 255, 0.12);
            border-radius: 10px;
            padding: 15px;
            transition: transform 0.2s, background 0.2s;
            cursor: pointer;
        }
        
        .capability-card:hover {
            transform: translateY(-3px);
            background: rgba(255, 255, 255, 0.2);
        }
        
        .capability-header {
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 10px;
        }
        
        .capability-icon {
            font-size: 1.5em;
        }
        
        .capability-name {
            font-weight: bold;
            font-size: 1em;
        }
        
        .capability-status {
            margin-right: auto;
            padding: 3px 8px;
            border-radius: 12px;
            font-size: 0.75em;
        }
        
        .status-active {
            background: #4ade80;
            color: #000;
        }
        
        .status-warning {
            background: #fbbf24;
            color: #000;
        }
        
        .status-error {
            background: #f87171;
            color: #000;
        }
        
        .capability-logs {
            background: rgba(0, 0, 0, 0.2);
            border-radius: 5px;
            padding: 10px;
            margin-top: 10px;
            max-height: 150px;
            overflow-y: auto;
            font-size: 0.8em;
            font-family: 'Courier New', monospace;
        }
        
        .log-entry {
            padding: 3px 0;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        .log-entry:last-child {
            border-bottom: none;
        }
        
        .log-timestamp {
            color: #93c5fd;
            font-size: 0.85em;
        }
        
        .log-type-info { color: #93c5fd; }
        .log-type-success { color: #4ade80; }
        .log-type-warning { color: #fbbf24; }
        .log-type-error { color: #f87171; }
        
        .llm-analysis {
            background: rgba(139, 92, 246, 0.2);
            border-radius: 5px;
            padding: 10px;
            margin-top: 10px;
            font-size: 0.85em;
            border: 1px solid rgba(139, 92, 246, 0.4);
        }
        
        .llm-analysis h4 {
            margin-bottom: 5px;
            color: #c4b5fd;
        }
        
        .refresh-btn {
            background: rgba(255, 255, 255, 0.2);
            border: none;
            color: white;
            padding: 10px 20px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 1em;
            margin: 10px 5px;
            transition: background 0.2s;
        }
        
        .refresh-btn:hover {
            background: rgba(255, 255, 255, 0.3);
        }
        
        .controls {
            text-align: center;
            margin-bottom: 20px;
        }
        
        .loading {
            text-align: center;
            padding: 20px;
            font-size: 1.2em;
        }
        
        .spinner {
            border: 4px solid rgba(255, 255, 255, 0.3);
            border-top: 4px solid #fff;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 20px auto;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        ::-webkit-scrollbar {
            width: 8px;
        }
        
        ::-webkit-scrollbar-track {
            background: rgba(0, 0, 0, 0.2);
            border-radius: 4px;
        }
        
        ::-webkit-scrollbar-thumb {
            background: rgba(255, 255, 255, 0.3);
            border-radius: 4px;
        }
        
        ::-webkit-scrollbar-thumb:hover {
            background: rgba(255, 255, 255, 0.5);
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🤖 داشبورد ربات معاملاتی کریپتو</h1>
            <p>نظارت بر ۶۰ قابلیت با لاگ‌گذاری هوشمند و تحلیل LLM</p>
            <div style="margin-top: 15px;">
                <span class="status-indicator status-{{ status }}"></span>
                <span id="status-text">{{ 'آنلاین' if status == 'online' else 'آفلاین' if status == 'offline' else 'نامشخص' }}</span>
            </div>
        </header>
        
        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-value" id="uptime">{{ metrics.uptime }}</div>
                <div class="metric-label">زمان کارکرد</div>
            </div>
            <div class="metric-card">
                <div class="metric-value" id="cycles">{{ metrics.cycles }}</div>
                <div class="metric-label">تعداد سیکل‌ها</div>
            </div>
            <div class="metric-card">
                <div class="metric-value" id="active-logs">{{ metrics.active_logs }}</div>
                <div class="metric-label">لاگ‌های فعال</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">60</div>
                <div class="metric-label">کل قابلیت‌ها</div>
            </div>
        </div>
        
        <div class="controls">
            <button class="refresh-btn" onclick="refreshData()">🔄 بروزرسانی</button>
            <button class="refresh-btn" onclick="simulateActivity()">🎲 شبیه‌سازی فعالیت</button>
            <button class="refresh-btn" style="background: rgba(74, 222, 128, 0.3);" onclick="copyAllLogsAndAnalysis()">📋 کپی تمام لاگ‌ها و تحلیل‌های LLM</button>
        </div>
        
        <div id="capabilities-container">
            <div class="loading">
                <div class="spinner"></div>
                در حال بارگذاری قابلیت‌ها...
            </div>
        </div>
        
        <div class="category-section">
            <div class="category-header">
                📝 لاگ‌های عمومی سیستم
            </div>
            <div class="capability-logs" id="system-logs">
                {% for log in logs %}
                <div class="log-entry">
                    <span class="log-timestamp">{{ log.timestamp[:19] }}</span>
                    <span class="log-source">[{{ log.source }}]</span>
                    {{ log.line[:100] }}
                </div>
                {% endfor %}
            </div>
        </div>
    </div>
    
    <script>
        const capabilities = {{ capabilities_json | safe }};
        
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
        
        async function refreshData() {
            try {
                const response = await fetch('/api/data');
                const data = await response.json();
                
                document.getElementById('uptime').textContent = data.metrics.uptime;
                document.getElementById('cycles').textContent = data.metrics.cycles;
                document.getElementById('active-logs').textContent = data.metrics.active_logs;
                
                const statusText = data.status === 'online' ? 'آنلاین' : data.status === 'offline' ? 'آفلاین' : 'نامشخص';
                document.getElementById('status-text').textContent = statusText;
                
                const indicator = document.querySelector('.status-indicator');
                indicator.className = 'status-indicator status-' + data.status;
                
                renderCapabilities(data.capabilities_status);
                
                // بروزرسانی لاگ‌های سیستم
                const systemLogsContainer = document.getElementById('system-logs');
                systemLogsContainer.innerHTML = data.logs.map(log => `
                    <div class="log-entry">
                        <span class="log-timestamp">${escapeHtml(log.timestamp).slice(0, 19)}</span>
                        <span class="log-source">[${escapeHtml(log.source)}]</span>
                        ${escapeHtml(log.line).slice(0, 100)}
                    </div>
                `).join('');
                
            } catch (error) {
                console.error('Error refreshing data:', error);
            }
        }
        
        function renderCapabilities(capabilitiesStatus) {
            const container = document.getElementById('capabilities-container');
            let html = '';
            
            for (const [categoryKey, categoryData] of Object.entries(capabilities)) {
                html += `
                <div class="category-section">
                    <div class="category-header">
                        ${categoryData.icon || '📦'} ${categoryData.name}
                    </div>
                    <div class="capabilities-grid">
                `;
                
                for (const cap of categoryData.capabilities) {
                    const status = capabilitiesStatus[cap.id] || { status: 'active', logs: [], llm_analysis: null };
                    const statusClass = status.status === 'error' ? 'status-error' : status.status === 'warning' ? 'status-warning' : 'status-active';
                    const statusText = status.status === 'error' ? 'خطا' : status.status === 'warning' ? 'هشدار' : 'فعال';
                    
                    html += `
                    <div class="capability-card" onclick="toggleCapabilityLogs('${cap.id}')">
                        <div class="capability-header">
                            <span class="capability-icon">${cap.icon}</span>
                            <span class="capability-name">${escapeHtml(cap.name)}</span>
                            <span class="capability-status ${statusClass}">${statusText}</span>
                        </div>
                        <div id="logs-${cap.id}" class="capability-logs" style="display: none;">
                    `;
                    
                    if (status.logs && status.logs.length > 0) {
                        status.logs.forEach(log => {
                            const logClass = 'log-type-' + (log.event_type || 'info');
                            html += `
                            <div class="log-entry">
                                <span class="log-timestamp">${escapeHtml(log.timestamp).slice(0, 19)}</span>
                                <span class="${logClass}">[${escapeHtml(log.event_type)}]</span>
                                ${escapeHtml(log.message)}
                            </div>
                            `;
                        });
                    } else {
                        html += '<div class="log-entry">هیچ لاگی ثبت نشده است</div>';
                    }
                    
                    if (status.llm_analysis) {
                        html += `
                        <div class="llm-analysis">
                            <h4>🧠 تحلیل LLM:</h4>
                            <p>${escapeHtml(status.llm_analysis.analysis || 'تحلیلی موجود نیست')}</p>
                        </div>
                        `;
                    }
                    
                    html += `
                        </div>
                    </div>
                    `;
                }
                
                html += `
                    </div>
                </div>
                `;
            }
            
            container.innerHTML = html;
        }
        
        function toggleCapabilityLogs(capId) {
            const logsDiv = document.getElementById(`logs-${capId}`);
            if (logsDiv.style.display === 'none') {
                logsDiv.style.display = 'block';
            } else {
                logsDiv.style.display = 'none';
            }
        }
        
        async function simulateActivity() {
            try {
                await fetch('/api/simulate', { method: 'POST' });
                setTimeout(refreshData, 500);
            } catch (error) {
                console.error('Error simulating activity:', error);
            }
        }
        
        async function copyAllLogsAndAnalysis() {
            try {
                const response = await fetch('/api/data');
                const data = await response.json();
                
                let clipboardText = "📊 گزارش کامل لاگ‌ها و تحلیل‌های LLM\n";
                clipboardText += `تاریخ گزارش: ${new Date().toLocaleString('fa-IR')}\n`;
                clipboardText += "================================================\n\n";
                
                // افزودن ارزیابی‌های دسته‌بندی
                if (data.category_evaluations) {
                    clipboardText += "📋 ارزیابی‌های LLM برای هر دسته‌بندی:\n";
                    clipboardText += "================================================\n";
                    for (const [catKey, evaluation] of Object.entries(data.category_evaluations)) {
                        const catName = data.capabilities_structure[catKey]?.name || catKey;
                        clipboardText += `\n📂 دسته‌بندی: ${catName}\n`;
                        clipboardText += "------------------------------------------------\n";
                        if (evaluation) {
                            clipboardText += `   وضعیت: ${evaluation.status || 'نامشخص'}\n`;
                            clipboardText += `   تحلیل: ${evaluation.analysis || evaluation.llm_evaluation || 'تحلیلی موجود نیست'}\n`;
                            if (evaluation.issues) clipboardText += `   مشکلات: ${JSON.stringify(evaluation.issues)}\n`;
                            if (evaluation.recommendations) clipboardText += `   پیشنهادات: ${JSON.stringify(evaluation.recommendations)}\n`;
                        } else {
                            clipboardText += "   ⚠️ هیچ ارزیابی برای این دسته‌بندی موجود نیست\n";
                        }
                        clipboardText += "\n";
                    }
                }
                
                // افزودن لاگ‌های هر قابلیت
                const categories = {};
                for (const [capId, capData] of Object.entries(data.capabilities_status)) {
                    for (const [catKey, catData] of Object.entries(data.capabilities_structure)) {
                        for (const cap of catData.capabilities) {
                            if (cap.id === capId) {
                                if (!categories[catKey]) categories[catKey] = [];
                                categories[catKey].push({
                                    id: capId,
                                    name: cap.name,
                                    icon: cap.icon,
                                    status: capData.status,
                                    logs: capData.logs || []
                                });
                                break;
                            }
                        }
                    }
                }
                
                for (const [catKey, caps] of Object.entries(categories)) {
                    const catName = data.capabilities_structure[catKey]?.name || catKey;
                    clipboardText += `\n📂 دسته‌بندی: ${catName}\n`;
                    clipboardText += "------------------------------------------------\n";
                    caps.forEach(cap => {
                        if (cap.logs && cap.logs.length > 0) {
                            clipboardText += `\n🔹 قابلیت: ${cap.name} (${cap.icon})\n`;
                            clipboardText += `   وضعیت فعلی: ${cap.status}\n`;
                            cap.logs.forEach(log => {
                                clipboardText += `   └─ [${log.timestamp}] ${log.message}\n`;
                                if (log.llm_analysis) {
                                    clipboardText += `      🤖 تحلیل LLM: ${log.llm_analysis}\n`;
                                }
                            });
                        }
                    });
                    clipboardText += "\n";
                }
                
                navigator.clipboard.writeText(clipboardText).then(() => {
                    alert('✅ تمام لاگ‌ها، تحلیل‌های LLM و ارزیابی‌های دسته‌بندی با موفقیت کپی شدند!');
                }).catch(err => {
                    console.error('خطا در کپی:', err);
                    alert('❌ خطا در کپی کردن متن.');
                });
            } catch (error) {
                console.error('خطا در دریافت داده‌ها:', error);
                alert('❌ خطا در دریافت داده‌ها برای کپی.');
            }
        }
        
        // بارگذاری اولیه
        refreshData();
        
        // بروزرسانی خودکار هر 30 ثانیه
        setInterval(refreshData, 30000);
    </script>
</body>
</html>
'''


@app.route('/')
def index():
    """صفحه اصلی داشبورد"""
    status = get_bot_state()
    metrics = get_metrics()
    logs = get_all_logs()
    
    return render_template_string(
        HTML_TEMPLATE,
        status=status,
        metrics=metrics,
        logs=logs,
        capabilities_json=json.dumps(ALL_CAPABILITIES, ensure_ascii=False)
    )


@app.route('/api/data')
def api_data():
    """API برای دریافت داده‌های داشبورد"""
    status = get_bot_state()
    metrics = get_metrics()
    logs = get_all_logs()
    
    # دریافت وضعیت و لاگ‌های هر قابلیت
    capabilities_status = {}
    
    for category_key, category_data in ALL_CAPABILITIES.items():
        for cap in category_data['capabilities']:
            cap_id = cap['id']
            cap_logs = get_capability_logs(cap_id, limit=5)
            llm_analysis = get_llm_analysis(cap_id)
            
            # تعیین وضعیت بر اساس لاگ‌های اخیر
            cap_status = 'active'
            if cap_logs:
                recent_logs = cap_logs[-5:]
                error_count = sum(1 for log in recent_logs if log.get('event_type') == 'error')
                warning_count = sum(1 for log in recent_logs if log.get('event_type') == 'warning')
                
                if error_count > 0:
                    cap_status = 'error'
                elif warning_count > 0:
                    cap_status = 'warning'
            
            capabilities_status[cap_id] = {
                'status': cap_status,
                'logs': cap_logs,
                'llm_analysis': llm_analysis
            }
    
    # دریافت ارزیابی‌های دسته‌بندی
    category_evaluations = get_all_category_evaluations()
    
    return jsonify({
        'status': status,
        'metrics': metrics,
        'logs': logs,
        'capabilities_status': capabilities_status,
        'capabilities_structure': ALL_CAPABILITIES,
        'category_evaluations': category_evaluations
    })


@app.route('/api/capability/<capability_id>/log', methods=['POST'])
def api_log_capability(capability_id):
    """API برای ثبت لاگ یک قابلیت"""
    data = request.json
    event_type = data.get('event_type', 'info')
    message = data.get('message', '')
    details = data.get('details', {})
    
    success = log_capability_event(capability_id, event_type, message, details)
    
    if success:
        # تحلیل با LLM پس از ثبت لاگ
        logs = get_capability_logs(capability_id, limit=10)
        if logs:
            analyze_with_llm(capability_id, logs)
        
        return jsonify({'success': True, 'message': 'لاگ ثبت شد'})
    else:
        return jsonify({'success': False, 'message': 'خطا در ثبت لاگ'}), 500


@app.route('/api/capability/<capability_id>/logs')
def api_get_capability_logs(capability_id):
    """API برای دریافت لاگ‌های یک قابلیت"""
    limit = request.args.get('limit', 10, type=int)
    logs = get_capability_logs(capability_id, limit)
    llm_analysis = get_llm_analysis(capability_id)
    
    return jsonify({
        'capability_id': capability_id,
        'logs': logs,
        'llm_analysis': llm_analysis
    })



@app.route('/api/capability/<capability_id>/analysis')
def api_get_capability_analysis(capability_id):
    """API برای دریافت تحلیل LLM یک قابلیت (GET)"""
    llm_analysis = get_llm_analysis(capability_id)
    
    if llm_analysis:
        return jsonify(llm_analysis)
    else:
        return jsonify(None), 404

@app.route('/api/capability/<capability_id>/analyze', methods=['POST'])
def api_analyze_capability(capability_id):
    """API برای تحلیل لاگ‌های یک قابلیت با LLM"""
    logs = get_capability_logs(capability_id, limit=20)
    
    if not logs:
        return jsonify({'success': False, 'message': 'لاگی برای تحلیل وجود ندارد'}), 404
    
    analysis = analyze_with_llm(capability_id, logs)
    
    if analysis:
        return jsonify({'success': True, 'analysis': analysis})
    else:
        return jsonify({'success': False, 'message': 'خطا در تحلیل LLM'}), 500


@app.route('/api/simulate', methods=['POST'])
def api_simulate():
    """API برای شبیه‌سازی فعالیت قابلیت‌ها"""
    simulate_capability_activity()
    return jsonify({'success': True, 'message': 'فعالیت شبیه‌سازی شد'})


@app.route('/api/llm/config', methods=['GET', 'POST'])
def api_llm_config():
    """API برای مدیریت پیکربندی LLM"""
    global LLM_API_URL, LLM_MODEL
    if request.method == 'GET':
        return jsonify({
            'llm_api_url': LLM_API_URL,
            'llm_model': LLM_MODEL
        })
    elif request.method == 'POST':
        data = request.json
        if 'llm_api_url' in data:
            LLM_API_URL = data['llm_api_url']
        if 'llm_model' in data:
            LLM_MODEL = data['llm_model']
        return jsonify({'success': True, 'message': 'پیکربندی بروزرسانی شد'})


if __name__ == '__main__':
    print("🚀 راه‌اندازی سرور وب API...")
    print(f"📂 مسیر پروژه: {PROJECT_DIR}")
    print(f"📝 پوشه لاگ قابلیت‌ها: {CAPABILITIES_LOG_DIR}")
    print(f"🧠 پوشه تحلیل LLM: {LLM_ANALYSIS_DIR}")
    print(f"🔗 آدرس LLM API: {LLM_API_URL}")
    print(f"🤖 مدل LLM: {LLM_MODEL}")
    
    # ایجاد چند لاگ نمونه برای شروع
    print("\n📝 ایجاد لاگ‌های نمونه برای قابلیت‌ها...")
    simulate_capability_activity()
    
    app.run(host='0.0.0.0', port=5000, debug=False)
