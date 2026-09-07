#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Web API برای نمایش وضعیت ربات معاملاتی کریپتو
Crypto Trading Bot Web API

این فایل یک رابط وب زیبا و فارسی برای مانیتورینگ و کنترل ربات معاملاتی فراهم می‌کند.
"""

import os
import sys
import glob
import subprocess
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
]

# فایل ذخیره وضعیت ربات
BOT_STATE_FILE = os.path.join(PROJECT_DIR, '.bot_state')


def get_bot_state():
    """دریافت وضعیت ربات از فایل یا بررسی فرآیند در حال اجرا"""
    try:
        # اول بررسی می‌کنیم آیا فایل وضعیت وجود دارد
        if os.path.exists(BOT_STATE_FILE):
            with open(BOT_STATE_FILE, 'r', encoding='utf-8') as f:
                state = f.read().strip()
                return state if state in ['online', 'offline'] else 'unknown'
        
        # اگر فایل نبود، بررسی می‌کنیم آیا پروسه ربات در حال اجراست
        result = subprocess.run(
            ['pgrep', '-f', 'python.*main.py'],
            capture_output=True,
            text=True
        )
        if result.returncode == 0 and result.stdout.strip():
            return 'online'
        
        # بررسی screen session
        result = subprocess.run(
            ['screen', '-ls'],
            capture_output=True,
            text=True
        )
        if 'bot' in result.stdout and 'Attached' in result.stdout or len(result.stdout.split('\n')) > 2:
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
    
    # مرتب‌سازی بر اساس زمان (آخرین‌ها اول)
    all_logs.reverse()
    return all_logs[:30]  # فقط ۳۰ خط آخر


def get_metrics():
    """دریافت متریک‌های ربات"""
    metrics = {
        'uptime': 'نامشخص',
        'cycles': 0,
        'balance': 0.0,
        'pnl': 0.0,
        'last_trade': None,
        'active_strategies': 0
    }
    
    try:
        # بررسی uptime از طریق process
        result = subprocess.run(
            ['pgrep', '-f', 'python.*main.py'],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            pids = result.stdout.strip().split('\n')
            if pids:
                pid = pids[0]
                # دریافت زمان شروع پروسس
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
        # خواندن تعداد سیکل‌ها از لاگ
        all_logs = ''.join([log['line'] for log in get_all_logs()])
        cycle_count = all_logs.count('cycle') + all_logs.count('Cycle') + all_logs.count('سیکل')
        metrics['cycles'] = max(cycle_count, 0)
    except Exception as e:
        app.logger.error(f"Error getting cycles: {e}")
    
    try:
        # تلاش برای خواندن موجودی از فایل‌های مختلف
        balance_files = [
            os.path.join(PROJECT_DIR, 'balance.json'),
            os.path.join(PROJECT_DIR, 'portfolio.json'),
            os.path.join(PROJECT_DIR, 'data', 'balance.json'),
        ]
        
        for bf in balance_files:
            if os.path.exists(bf):
                import json
                with open(bf, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        metrics['balance'] = data.get('total_balance', data.get('balance', 0.0))
                        break
    except Exception as e:
        app.logger.error(f"Error getting balance: {e}")
    
    try:
        # خواندن سود/زیان از لاگ یا فایل
        pnl_file = os.path.join(PROJECT_DIR, 'pnl.json')
        if os.path.exists(pnl_file):
            import json
            with open(pnl_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                metrics['pnl'] = data.get('total_pnl', 0.0)
    except Exception as e:
        app.logger.error(f"Error getting PnL: {e}")
    
    return metrics


# قالب HTML
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ربات معاملاتی کریپتو | Crypto Trading Bot</title>
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
            max-width: 1200px;
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
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .metric-card {
            background: rgba(255, 255, 255, 0.15);
            padding: 20px;
            border-radius: 15px;
            backdrop-filter: blur(10px);
            transition: transform 0.3s ease;
        }
        
        .metric-card:hover {
            transform: translateY(-5px);
        }
        
        .metric-title {
            font-size: 0.9em;
            opacity: 0.9;
            margin-bottom: 10px;
        }
        
        .metric-value {
            font-size: 1.8em;
            font-weight: bold;
        }
        
        .controls {
            display: flex;
            gap: 15px;
            justify-content: center;
            margin-bottom: 30px;
            flex-wrap: wrap;
        }
        
        .btn {
            padding: 12px 30px;
            border: none;
            border-radius: 10px;
            font-size: 1em;
            cursor: pointer;
            transition: all 0.3s ease;
            font-family: inherit;
        }
        
        .btn-restart {
            background: linear-gradient(135deg, #fbbf24, #f59e0b);
            color: #000;
        }
        
        .btn-stop {
            background: linear-gradient(135deg, #ef4444, #dc2626);
            color: #fff;
        }
        
        .btn:hover {
            transform: scale(1.05);
            box-shadow: 0 5px 15px rgba(0,0,0,0.3);
        }
        
        .btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
            transform: none;
        }
        
        .logs-section {
            background: rgba(0, 0, 0, 0.3);
            border-radius: 15px;
            padding: 20px;
            backdrop-filter: blur(10px);
        }
        
        .logs-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }
        
        .logs-container {
            background: rgba(0, 0, 0, 0.5);
            border-radius: 10px;
            padding: 15px;
            max-height: 400px;
            overflow-y: auto;
            font-family: 'Courier New', monospace;
            font-size: 0.85em;
            line-height: 1.6;
        }
        
        .log-line {
            padding: 5px 0;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }
        
        .log-source {
            color: #fbbf24;
            font-weight: bold;
        }
        
        .refresh-info {
            text-align: center;
            margin-top: 20px;
            opacity: 0.8;
            font-size: 0.9em;
        }
        
        .loading {
            text-align: center;
            padding: 40px;
        }
        
        .spinner {
            border: 4px solid rgba(255,255,255,0.3);
            border-top: 4px solid #fff;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto 20px;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        .alert {
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 20px;
            text-align: center;
        }
        
        .alert-success {
            background: rgba(74, 222, 128, 0.3);
            border: 1px solid #4ade80;
        }
        
        .alert-error {
            background: rgba(248, 113, 113, 0.3);
            border: 1px solid #f87171;
        }
        
        @media (max-width: 768px) {
            h1 { font-size: 1.5em; }
            .metric-value { font-size: 1.4em; }
            .controls { flex-direction: column; }
            .btn { width: 100%; }
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🤖 ربات معاملاتی کریپتو</h1>
            <p>وضعیت: <span id="status-text">در حال بارگذاری...</span></h1>
        </header>
        
        <div id="alert-container"></div>
        
        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-title">⏱️ زمان اجرا</div>
                <div class="metric-value" id="uptime">-</div>
            </div>
            <div class="metric-card">
                <div class="metric-title">🔄 تعداد سیکل‌ها</div>
                <div class="metric-value" id="cycles">-</div>
            </div>
            <div class="metric-card">
                <div class="metric-title">💰 موجودی</div>
                <div class="metric-value" id="balance">-</div>
            </div>
            <div class="metric-card">
                <div class="metric-title">📊 سود/زیان</div>
                <div class="metric-value" id="pnl">-</div>
            </div>
        </div>
        
        <div class="controls">
            <button class="btn btn-restart" onclick="restartBot()" id="restart-btn">
                🔄 راه‌اندازی مجدد
            </button>
            <button class="btn btn-stop" onclick="stopBot()" id="stop-btn">
                ⏹️ توقف ربات
            </button>
        </div>
        
        <div class="logs-section">
            <div class="logs-header">
                <h2>📝 آخرین لاگ‌ها (۳۰ خط)</h2>
                <span id="last-update">آخرین به‌روزرسانی: -</span>
            </div>
            <div class="logs-container" id="logs-container">
                <div class="loading">
                    <div class="spinner"></div>
                    <p>در حال بارگذاری لاگ‌ها...</p>
                </div>
            </div>
        </div>
        
        <div class="refresh-info">
            🔁 به‌روزرسانی خودکار هر ۱۰ ثانیه
        </div>
    </div>
    
    <script>
        let updateInterval;
        
        async function fetchStatus() {
            try {
                const response = await fetch('/api/status');
                const data = await response.json();
                
                // بروزرسانی وضعیت
                const statusIndicator = document.getElementById('status-text');
                if (data.status === 'online') {
                    statusIndicator.innerHTML = '<span class="status-indicator status-online"></span>آنلاین';
                    document.body.style.background = 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)';
                } else {
                    statusIndicator.innerHTML = '<span class="status-indicator status-offline"></span>آفلاین';
                    document.body.style.background = 'linear-gradient(135deg, #764ba2 0%, #667eea 100%)';
                }
                
                // بروزرسانی متریک‌ها
                document.getElementById('uptime').textContent = data.metrics.uptime || '-';
                document.getElementById('cycles').textContent = data.metrics.cycles || 0;
                document.getElementById('balance').textContent = (data.metrics.balance || 0).toLocaleString('fa-IR') + ' $';
                
                const pnl = data.metrics.pnl || 0;
                const pnlElement = document.getElementById('pnl');
                pnlElement.textContent = (pnl >= 0 ? '+' : '') + pnl.toFixed(2) + ' $';
                pnlElement.style.color = pnl >= 0 ? '#4ade80' : '#f87171';
                
                // بروزرسانی لاگ‌ها
                updateLogs(data.logs);
                
                // بروزرسانی زمان
                const now = new Date();
                document.getElementById('last-update').textContent = 
                    'آخرین به‌روزرسانی: ' + now.toLocaleTimeString('fa-IR');
                    
            } catch (error) {
                console.error('Error fetching status:', error);
                showAlert('خطا در دریافت وضعیت: ' + error.message, 'error');
            }
        }
        
        function updateLogs(logs) {
            const container = document.getElementById('logs-container');
            if (!logs || logs.length === 0) {
                container.innerHTML = '<p style="text-align: center; opacity: 0.7;">لاگی یافت نشد</p>';
                return;
            }
            
            container.innerHTML = logs.map(log => `
                <div class="log-line">
                    <span class="log-source">[${log.source}]</span> ${escapeHtml(log.line)}
                </div>
            `).join('');
        }
        
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
        
        async function restartBot() {
            if (!confirm('آیا مطمئن هستید که می‌خواهید ربات را راه‌اندازی مجدد کنید؟')) {
                return;
            }
            
            const btn = document.getElementById('restart-btn');
            btn.disabled = true;
            btn.textContent = '⏳ در حال پردازش...';
            
            try {
                const response = await fetch('/api/restart', { method: 'POST' });
                const data = await response.json();
                
                if (data.success) {
                    showAlert('✅ ربات با موفقیت راه‌اندازی مجدد شد', 'success');
                    setTimeout(fetchStatus, 2000);
                } else {
                    showAlert('❌ خطا: ' + (data.error || 'عملیات ناموفق بود'), 'error');
                }
            } catch (error) {
                showAlert('❌ خطا در ارتباط با سرور: ' + error.message, 'error');
            } finally {
                btn.disabled = false;
                btn.textContent = '🔄 راه‌اندازی مجدد';
            }
        }
        
        async function stopBot() {
            if (!confirm('⚠️ آیا مطمئن هستید که می‌خواهید ربات را متوقف کنید؟')) {
                return;
            }
            
            const btn = document.getElementById('stop-btn');
            btn.disabled = true;
            btn.textContent = '⏳ در حال پردازش...';
            
            try {
                const response = await fetch('/api/stop', { method: 'POST' });
                const data = await response.json();
                
                if (data.success) {
                    showAlert('✅ ربات با موفقیت متوقف شد', 'success');
                    setTimeout(fetchStatus, 2000);
                } else {
                    showAlert('❌ خطا: ' + (data.error || 'عملیات ناموفق بود'), 'error');
                }
            } catch (error) {
                showAlert('❌ خطا در ارتباط با سرور: ' + error.message, 'error');
            } finally {
                btn.disabled = false;
                btn.textContent = '⏹️ توقف ربات';
            }
        }
        
        function showAlert(message, type) {
            const container = document.getElementById('alert-container');
            const alert = document.createElement('div');
            alert.className = `alert alert-${type}`;
            alert.textContent = message;
            container.appendChild(alert);
            
            setTimeout(() => {
                alert.remove();
            }, 5000);
        }
        
        // شروع به‌روزرسانی خودکار
        fetchStatus();
        updateInterval = setInterval(fetchStatus, 10000);
        
        // توقف به‌روزرسانی هنگام بستن صفحه
        window.addEventListener('beforeunload', () => {
            clearInterval(updateInterval);
        });
    </script>
</body>
</html>
'''


@app.route('/')
def index():
    """صفحه اصلی با رابط کاربری فارسی"""
    return render_template_string(HTML_TEMPLATE)


@app.route('/api/status', methods=['GET'])
def api_status():
    """API endpoint برای دریافت وضعیت ربات"""
    try:
        status = get_bot_state()
        metrics = get_metrics()
        logs = get_all_logs()
        
        return jsonify({
            'success': True,
            'status': status,
            'metrics': metrics,
            'logs': logs,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        app.logger.error(f"Error in /api/status: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/restart', methods=['POST'])
def api_restart():
    """API endpoint برای راه‌اندازی مجدد ربات"""
    try:
        # توقف ربات فعلی
        subprocess.run(['pkill', '-f', 'python.*main.py'], capture_output=True)
        subprocess.run(['screen', '-S', 'bot', '-X', 'quit'], capture_output=True)
        
        # راه‌اندازی مجدد
        cmd = f"cd {PROJECT_DIR} && nohup python3 main.py > /dev/null 2>&1 &"
        subprocess.run(cmd, shell=True)
        
        # ذخیره وضعیت
        set_bot_state('online')
        
        app.logger.info("Bot restarted successfully")
        
        return jsonify({
            'success': True,
            'message': 'ربات با موفقیت راه‌اندازی مجدد شد'
        })
    except Exception as e:
        app.logger.error(f"Error restarting bot: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/stop', methods=['POST'])
def api_stop():
    """API endpoint برای توقف ربات"""
    try:
        # توقف ربات
        subprocess.run(['pkill', '-f', 'python.*main.py'], capture_output=True)
        subprocess.run(['screen', '-S', 'bot', '-X', 'quit'], capture_output=True)
        
        # ذخیره وضعیت
        set_bot_state('offline')
        
        app.logger.info("Bot stopped successfully")
        
        return jsonify({
            'success': True,
            'message': 'ربات با موفقیت متوقف شد'
        })
    except Exception as e:
        app.logger.error(f"Error stopping bot: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


if __name__ == '__main__':
    print("=" * 60)
    print("🚀 راه‌اندازی Web API ربات معاملاتی")
    print("=" * 60)
    print(f"📁 مسیر پروژه: {PROJECT_DIR}")
    print("🌐 آدرس دسترسی: http://0.0.0.0:5000")
    print("🔗 آدرس خارجی: http://52.23.157.88:5000")
    print("=" * 60)
    
    # ایجاد فایل وضعیت اولیه
    if not os.path.exists(BOT_STATE_FILE):
        set_bot_state('unknown')
    
    app.run(host='0.0.0.0', port=5000, debug=False)
