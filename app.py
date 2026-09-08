import os
import sqlite3
import logging
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string, send_from_directory
from flask_cors import CORS
import threading
import time
import random
import json
import requests
from concurrent.futures import ThreadPoolExecutor

# Configuration
app = Flask(__name__)
CORS(app)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'your-secret-key')
app.config['DATABASE'] = 'trading_system.db'
app.config['LOG_DIR'] = 'capabilities_logs'
app.config['LLM_API_KEY'] = os.getenv('GROQ_API_KEY')  # Load from environment variable
app.config['LLM_API_URL'] = 'https://api.groq.com/openai/v1/chat/completions'
app.config['LLM_MODEL'] = 'groq/compound'

if not app.config['LLM_API_KEY']:
    logger.warning("GROQ_API_KEY not found in environment variables. LLM features will be disabled.")

# Ensure log directory exists
os.makedirs(app.config['LOG_DIR'], exist_ok=True)

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Thread pool for async LLM calls
executor = ThreadPoolExecutor(max_workers=10)

# Capabilities Definition
CAPABILITIES = [
    # Core Trading
    {"id": 1, "name": "الگوریتم ترید کریپتو", "category": "ترید الگوریتمی", "status": "active"},
    {"id": 2, "name": "پشتیبانی چند صرافی", "category": "ترید الگوریتمی", "status": "active"},
    {"id": 3, "name": "دریافت داده بازار", "category": "ترید الگوریتمی", "status": "active"},
    {"id": 4, "name": "تحلیل چند تایم‌فریمی", "category": "ترید الگوریتمی", "status": "active"},
    {"id": 5, "name": "استراتژی‌های تکنیکال", "category": "ترید الگوریتمی", "status": "active"},
    {"id": 6, "name": "تشخیص Market Regime", "category": "ترید الگوریتمی", "status": "active"},
    {"id": 7, "name": "ترکیب استراتژی (Ensemble)", "category": "ترید الگوریتمی", "status": "active"},
    {"id": 8, "name": "بهینه‌سازی پورتفولیو", "category": "ترید الگوریتمی", "status": "active"},
    
    # Risk Management
    {"id": 9, "name": "مدیریت ریسک کلی", "category": "مدیریت ریسک", "status": "active"},
    {"id": 10, "name": "تعیین اندازه پوزیشن", "category": "مدیریت ریسک", "status": "active"},
    {"id": 11, "name": "Stop Loss / Take Profit", "category": "مدیریت ریسک", "status": "active"},
    {"id": 12, "name": "Trailing Stop", "category": "مدیریت ریسک", "status": "active"},
    {"id": 13, "name": "Breakeven Logic", "category": "مدیریت ریسک", "status": "active"},
    {"id": 14, "name": "Partial Take Profit", "category": "مدیریت ریسک", "status": "active"},
    {"id": 15, "name": "محدودیت Exposure", "category": "مدیریت ریسک", "status": "active"},
    {"id": 16, "name": "Circuit Breaker", "category": "مدیریت ریسک", "status": "active"},
    {"id": 17, "name": "Kill Switch", "category": "مدیریت ریسک", "status": "active"},
    {"id": 18, "name": "Live Safety Engine", "category": "مدیریت ریسک", "status": "active"},

    # Order & Position Mgmt
    {"id": 19, "name": "Order Manager", "category": "اجرای سفارشات", "status": "active"},
    {"id": 20, "name": "Idempotency Check", "category": "اجرای سفارشات", "status": "active"},
    {"id": 21, "name": "Fill Manager", "category": "اجرای سفارشات", "status": "active"},
    {"id": 22, "name": "Position Manager", "category": "اجرای سفارشات", "status": "active"},
    {"id": 23, "name": "Exchange Reconciliation", "category": "اجرای سفارشات", "status": "active"},
    {"id": 24, "name": "Crash Recovery", "category": "اجرای سفارشات", "status": "active"},
    {"id": 25, "name": "Persistence/DB", "category": "اجرای سفارشات", "status": "active"},

    # Backtesting & Quant
    {"id": 26, "name": "Walk-Forward Backtest", "category": "بک‌تست و کوانت", "status": "active"},
    {"id": 27, "name": "Out-of-Sample Test", "category": "بک‌تست و کوانت", "status": "active"},
    {"id": 28, "name": "Transaction Cost Model", "category": "بک‌تست و کوانت", "status": "active"},
    {"id": 29, "name": "Slippage Model", "category": "بک‌تست و کوانت", "status": "active"},
    {"id": 30, "name": "No-Trade Zone", "category": "بک‌تست و کوانت", "status": "active"},
    {"id": 31, "name": "Benchmarking", "category": "بک‌تست و کوانت", "status": "active"},
    {"id": 32, "name": "Performance Metrics", "category": "بک‌تست و کوانت", "status": "active"},
    {"id": 33, "name": "Monte Carlo Analysis", "category": "بک‌تست و کوانت", "status": "active"},

    # AI / ML
    {"id": 34, "name": "ML Pipeline", "category": "هوش مصنوعی (ML)", "status": "active"},
    {"id": 35, "name": "Feature Engineering", "category": "هوش مصنوعی (ML)", "status": "active"},
    {"id": 36, "name": "Causal Features", "category": "هوش مصنوعی (ML)", "status": "active"},
    {"id": 37, "name": "Purged Walk-Forward", "category": "هوش مصنوعی (ML)", "status": "active"},
    {"id": 38, "name": "ML Prediction", "category": "هوش مصنوعی (ML)", "status": "active"},
    {"id": 39, "name": "Model Registry", "category": "هوش مصنوعی (ML)", "status": "active"},
    {"id": 40, "name": "Drift Monitoring", "category": "هوش مصنوعی (ML)", "status": "active"},
    {"id": 41, "name": "ML Strategy Integration", "category": "هوش مصنوعی (ML)", "status": "active"},

    # AI / Sentiment
    {"id": 42, "name": "Sentiment Analysis", "category": "هوش مصنوعی (Sentiment)", "status": "active"},
    {"id": 43, "name": "News/Context Analysis", "category": "هوش مصنوعی (Sentiment)", "status": "active"},
    {"id": 44, "name": "LLM Integration", "category": "هوش مصنوعی (Sentiment)", "status": "active"},
    {"id": 45, "name": "Sentiment as Signal", "category": "هوش مصنوعی (Sentiment)", "status": "active"},

    # Infrastructure
    {"id": 46, "name": "FastAPI Core", "category": "زیرساخت", "status": "active"},
    {"id": 47, "name": "Trading API", "category": "زیرساخت", "status": "active"},
    {"id": 48, "name": "Health Monitoring", "category": "زیرساخت", "status": "active"},
    {"id": 49, "name": "Logging System", "category": "زیرساخت", "status": "active"},
    {"id": 50, "name": "Observability", "category": "زیرساخت", "status": "active"},
    {"id": 51, "name": "Config Management", "category": "زیرساخت", "status": "active"},
    {"id": 52, "name": "Database (SQLite/PG)", "category": "زیرساخت", "status": "active"},
    {"id": 53, "name": "Docker Support", "category": "زیرساخت", "status": "active"},
    {"id": 54, "name": "CI/CD Pipeline", "category": "زیرساخت", "status": "active"},
    {"id": 55, "name": "Paper Trading", "category": "زیرساخت", "status": "active"},
    {"id": 56, "name": "Shadow Trading", "category": "زیرساخت", "status": "active"},
    {"id": 57, "name": "Live Trading Arch", "category": "زیرساخت", "status": "active"},
    {"id": 58, "name": "Security Module", "category": "زیرساخت", "status": "active"},
    {"id": 59, "name": "Alert System", "category": "زیرساخت", "status": "active"},
    {"id": 60, "name": "Admin Dashboard", "category": "زیرساخت", "status": "active"},
]

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>داشبورد سیستم ترید الگوریتمی</title>
    <style>
        body { font-family: Tahoma, Arial, sans-serif; background: #f5f5f5; margin: 0; padding: 20px; }
        .container { max-width: 1400px; margin: 0 auto; }
        h1 { text-align: center; color: #333; margin-bottom: 30px; }
        .category { background: white; border-radius: 8px; padding: 20px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .category h2 { color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; margin-top: 0; }
        .capabilities-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 15px; }
        .capability-card { background: #f8f9fa; border: 1px solid #e9ecef; border-radius: 6px; padding: 15px; transition: all 0.3s; }
        .capability-card:hover { box-shadow: 0 4px 8px rgba(0,0,0,0.15); transform: translateY(-2px); }
        .capability-name { font-weight: bold; color: #2c3e50; margin-bottom: 10px; }
        .capability-status { display: inline-block; padding: 3px 8px; border-radius: 4px; font-size: 12px; }
        .status-active { background: #d4edda; color: #155724; }
        .btn-simulate { background: #3498db; color: white; border: none; padding: 8px 15px; border-radius: 4px; cursor: pointer; margin-top: 10px; width: 100%; }
        .btn-simulate:hover { background: #2980b9; }
        .logs-section { margin-top: 15px; padding-top: 15px; border-top: 1px solid #dee2e6; }
        .log-entry { background: #fff; padding: 10px; margin: 8px 0; border-radius: 4px; border-right: 4px solid #3498db; font-size: 13px; }
        .log-info { border-right-color: #3498db; }
        .log-warning { border-right-color: #f39c12; }
        .log-error { border-right-color: #e74c3c; }
        .llm-analysis { background: #e8f4f8; padding: 8px; margin-top: 8px; border-radius: 4px; font-size: 12px; color: #2c3e50; }
        .llm-label { font-weight: bold; color: #2980b9; }
        .loading { color: #7f8c8d; font-style: italic; }
        .summary-bar { background: white; padding: 15px; border-radius: 8px; margin-bottom: 20px; display: flex; justify-content: space-around; }
        .summary-item { text-align: center; }
        .summary-number { font-size: 24px; font-weight: bold; color: #3498db; }
        .summary-label { font-size: 14px; color: #7f8c8d; }
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 داشبورد نظارت بر قابلیت‌های سیستم ترید</h1>
        
        <div class="summary-bar">
            <div class="summary-item">
                <div class="summary-number" id="total-caps">60</div>
                <div class="summary-label">کل قابلیت‌ها</div>
            </div>
            <div class="summary-item">
                <div class="summary-number" id="total-logs">0</div>
                <div class="summary-label">کل لاگ‌ها</div>
            </div>
            <div class="summary-item">
                <div class="summary-number" id="total-analyzed">0</div>
                <div class="summary-label">تحلیل شده با LLM</div>
            </div>
        </div>

        <button onclick="simulateAll()" style="background: #27ae60; color: white; border: none; padding: 12px 25px; border-radius: 6px; cursor: pointer; font-size: 16px; margin-bottom: 20px;">
            🎲 شبیه‌سازی فعالیت همه قابلیت‌ها
        </button>

        <div id="dashboard"></div>
    </div>

    <script>
        let capabilitiesData = {};
        
        async function loadCapabilities() {
            const response = await fetch('/api/capabilities');
            capabilitiesData = await response.json();
            renderDashboard();
        }
        
        async function loadLogs(capId) {
            const response = await fetch(`/api/logs/${capId}`);
            return await response.json();
        }
        
        function renderDashboard() {
            const dashboard = document.getElementById('dashboard');
            dashboard.innerHTML = '';
            
            for (const [category, caps] of Object.entries(capabilitiesData)) {
                const catDiv = document.createElement('div');
                catDiv.className = 'category';
                catDiv.innerHTML = `<h2>${category}</h2>`;
                
                const grid = document.createElement('div');
                grid.className = 'capabilities-grid';
                
                caps.forEach(cap => {
                    const card = document.createElement('div');
                    card.className = 'capability-card';
                    card.id = `cap-${cap.id}`;
                    card.innerHTML = `
                        <div class="capability-name">${cap.name}</div>
                        <span class="capability-status status-active">فعال</span>
                        <button class="btn-simulate" onclick="simulateCapability(${cap.id})">🎲 شبیه‌سازی</button>
                        <div class="logs-section" id="logs-${cap.id}">
                            <div class="loading">در حال بارگذاری لاگ‌ها...</div>
                        </div>
                    `;
                    grid.appendChild(card);
                    
                    // Load logs for this capability
                    loadLogs(cap.id).then(logs => renderLogs(cap.id, logs));
                });
                
                catDiv.appendChild(grid);
                dashboard.appendChild(catDiv);
            }
            
            updateSummary();
        }
        
        function renderLogs(capId, logs) {
            const logsDiv = document.getElementById(`logs-${capId}`);
            if (!logsDiv) return;
            
            if (logs.length === 0) {
                logsDiv.innerHTML = '<div style="color: #95a5a6; font-size: 13px;">هنوز لاگی ثبت نشده است.</div>';
                return;
            }
            
            logsDiv.innerHTML = '';
            logs.forEach(log => {
                const logDiv = document.createElement('div');
                logDiv.className = `log-entry log-${log.level.toLowerCase()}`;
                
                let llmHtml = '';
                if (log.llm_status === 'pending') {
                    llmHtml = `<div class="llm-analysis"><span class="llm-label">🤖 تحلیل LLM:</span> <span class="loading">${log.llm_analysis || 'در حال تحلیل...'}</span></div>`;
                } else if (log.llm_status === 'success') {
                    llmHtml = `<div class="llm-analysis"><span class="llm-label">🤖 تحلیل LLM:</span> ${log.llm_analysis}</div>`;
                } else if (log.llm_status === 'error') {
                    llmHtml = `<div class="llm-analysis" style="background: #fdeaea;"><span class="llm-label">⚠️ خطا در تحلیل:</span> ${log.llm_analysis}</div>`;
                }
                
                logDiv.innerHTML = `
                    <div style="margin-bottom: 5px;">
                        <strong>[${log.level}]</strong> ${log.message}
                    </div>
                    <div style="color: #7f8c8d; font-size: 11px;">${new Date(log.timestamp).toLocaleString('fa-IR')}</div>
                    ${llmHtml}
                `;
                logsDiv.appendChild(logDiv);
            });
        }
        
        async function simulateCapability(capId) {
            await fetch('/api/simulate', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({capability_id: capId})
            });
            setTimeout(() => loadLogs(capId).then(logs => renderLogs(capId, logs)), 1000);
        }
        
        async function simulateAll() {
            for (let i = 1; i <= 60; i++) {
                setTimeout(() => simulateCapability(i), i * 100);
            }
        }
        
        function updateSummary() {
            // Count total logs from all loaded capabilities
            let totalLogs = 0;
            let analyzedLogs = 0;
            
            document.querySelectorAll('.log-entry').forEach(log => {
                totalLogs++;
                if (log.querySelector('.llm-analysis')) analyzedLogs++;
            });
            
            document.getElementById('total-logs').textContent = totalLogs;
            document.getElementById('total-analyzed').textContent = analyzedLogs;
        }
        
        // Initial load
        loadCapabilities();
        
        // Auto-refresh every 30 seconds
        setInterval(loadCapabilities, 30000);
    </script>
</body>
</html>
'''

def get_db_connection():
    conn = sqlite3.connect(app.config['DATABASE'])
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            capability_id INTEGER,
            timestamp TEXT,
            level TEXT,
            message TEXT,
            data TEXT,
            llm_analysis TEXT,
            llm_status TEXT
        )
    ''')
    conn.commit()
    conn.close()

def call_llm_analysis(capability_name, log_message, log_level, log_data):
    """Calls Groq API to analyze the log"""
    try:
        headers = {
            "Authorization": f"Bearer {app.config['LLM_API_KEY']}",
            "Content-Type": "application/json"
        }
        
        prompt = f"""
        You are an expert Trading System Auditor. 
        Capability: {capability_name}
        Log Level: {log_level}
        Log Message: {log_message}
        Data: {log_data}
        
        Task: Analyze this log entry. Is this behavior normal? Does it indicate a risk? 
        Provide a concise 1-sentence conclusion in Persian.
        """
        
        payload = {
            "model": app.config['LLM_MODEL'],
            "messages": [
                {"role": "system", "content": "You are a helpful trading system auditor assistant speaking Persian."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3,
            "max_tokens": 150
        }
        
        response = requests.post(app.config['LLM_API_URL'], json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        result = response.json()
        analysis = result['choices'][0]['message']['content']
        return analysis, "success"
    
    except Exception as e:
        logger.error(f"LLM API Error: {str(e)}")
        return f"خطا در تحلیل: {str(e)}", "error"

def process_log_async(capability_id, level, message, data_json):
    """Background task to save log and call LLM"""
    cap_name = next((c['name'] for c in CAPABILITIES if c['id'] == capability_id), "Unknown")
    
    # Initial Save
    conn = get_db_connection()
    c = conn.cursor()
    timestamp = datetime.now().isoformat()
    c.execute('''
        INSERT INTO logs (capability_id, timestamp, level, message, data, llm_analysis, llm_status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (capability_id, timestamp, level, message, json.dumps(data_json), "در حال تحلیل...", "pending"))
    log_id = c.lastrowid
    conn.commit()
    conn.close()
    
    # Call LLM
    analysis, status = call_llm_analysis(cap_name, message, level, data_json)
    
    # Update DB with LLM result
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
        UPDATE logs SET llm_analysis = ?, llm_status = ? WHERE id = ?
    ''', (analysis, status, log_id))
    conn.commit()
    conn.close()

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/capabilities', methods=['GET'])
def get_capabilities():
    # Group by category
    categories = {}
    for cap in CAPABILITIES:
        cat = cap['category']
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(cap)
    return jsonify(categories)

@app.route('/api/logs/<int:cap_id>', methods=['GET'])
def get_logs(cap_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM logs WHERE capability_id = ? ORDER BY timestamp DESC LIMIT 20', (cap_id,))
    rows = c.fetchall()
    conn.close()
    
    logs = []
    for row in rows:
        logs.append({
            "id": row['id'],
            "timestamp": row['timestamp'],
            "level": row['level'],
            "message": row['message'],
            "data": json.loads(row['data']) if row['data'] else {},
            "llm_analysis": row['llm_analysis'],
            "llm_status": row['llm_status']
        })
    return jsonify(logs)

@app.route('/api/log', methods=['POST'])
def add_log():
    data = request.json
    cap_id = data.get('capability_id')
    level = data.get('level', 'INFO')
    message = data.get('message')
    log_data = data.get('data', {})
    
    if not cap_id or not message:
        return jsonify({"error": "Missing fields"}), 400
    
    # Run in background thread
    executor.submit(process_log_async, cap_id, level, message, log_data)
    
    return jsonify({"status": "Log received, analysis in progress"}), 202

@app.route('/api/simulate', methods=['POST'])
def simulate_activity():
    data = request.json
    cap_id = data.get('capability_id')
    
    if not cap_id:
        # Pick random if no ID provided
        cap = random.choice(CAPABILITIES)
        cap_id = cap['id']
    else:
        cap = next((c for c in CAPABILITIES if c['id'] == cap_id), random.choice(CAPABILITIES))
    
    levels = ['INFO', 'WARNING', 'ERROR']
    level = random.choices(levels, weights=[70, 20, 10])[0]
    
    messages = {
        'INFO': f"عملیات {cap['name']} با موفقیت انجام شد.",
        'WARNING': f"هشدار: تاخیر در {cap['name']} مشاهده شد.",
        'ERROR': f"خطا: شکست در اجرای {cap['name']}."
    }
    
    payload_data = {"random_value": random.random(), "timestamp": datetime.now().isoformat()}
    
    # Trigger log creation directly
    executor.submit(process_log_async, cap_id, level, messages[level], payload_data)
    
    return jsonify({"status": "Simulation triggered", "capability": cap['name'], "level": level})

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=False)
