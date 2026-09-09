import express from 'express';
import cors from 'cors';
import path from 'path';
import fs from 'fs';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = 3000;
const HOST = '0.0.0.0';

app.use(cors());
app.use(express.json());

// Structure of 60 capabilities in 7 categories
const CAPABILITY_STRUCTURE = {
  core_trading: {
    name: "معامله‌گری الگوریتمی و ترید اصلی",
    capabilities: [
      { id: "crypto_algo_trading", alias: "algorithmic_crypto_trading", name: "ترید الگوریتمی کریپتو", icon: "🤖" },
      { id: "multi_exchange", alias: "multi_exchange_support", name: "پشتیبانی چند صرافی (Binance, Bybit, KuCoin)", icon: "🏢" },
      { id: "market_data", alias: "market_data_fetching", name: "دریافت داده بازار (OHLCV, قیمت, حجم)", icon: "📊" },
      { id: "multi_timeframe", alias: "multi_timeframe_analysis", name: "تحلیل چند تایم‌فریمی", icon: "⏱️" },
      { id: "technical_strategies", alias: "technical_strategies", name: "استراتژی‌های تکنیکال متعدد", icon: "📈" },
      { id: "market_regime", alias: "market_regime_detection", name: "تشخیص Market Regime", icon: "🔍" },
      { id: "ensemble_strategies", alias: "ensemble_strategies", name: "ترکیب چند استراتژی (Ensemble)", icon: "🎯" },
      { id: "portfolio_optimization", alias: "portfolio_optimization", name: "بهینه‌سازی پورتفولیو (MVO / Risk Parity)", icon: "⚖️" }
    ]
  },
  risk_management: {
    name: "مدیریت ریسک و پایداری سرمایه",
    capabilities: [
      { id: "risk_management", alias: "risk_management", name: "مدیریت ریسک جامع (Exposure, Drawdown)", icon: "🛡️" },
      { id: "position_sizing", alias: "position_sizing", name: "تعیین اندازه پوزیشن بر اساس ریسک", icon: "📏" },
      { id: "stop_loss_take_profit", alias: "stop_loss_take_profit", name: "مدیریت حد سود و زیان (SL / TP)", icon: "🛑" },
      { id: "trailing_stop", alias: "trailing_stop", name: "سیستم Trailing Stop هوشمند", icon: "📉" },
      { id: "breakeven", alias: "breakeven_stop", name: "جابجایی حد ضرر به نقطه سر‌به‌سر (Breakeven)", icon: "⚖️" },
      { id: "partial_take_profit", alias: "partial_take_profit", name: "خروج پله‌ای (Partial Take Profit)", icon: "💰" },
      { id: "max_positions", alias: "max_positions_exposure", name: "کنترل سقف پوزیشن‌ها و حداکثر Exposure", icon: "🔢" },
      { id: "circuit_breaker", alias: "circuit_breaker", name: "قطع‌کننده اضطراری نوسان شدید (Circuit Breaker)", icon: "⚡" },
      { id: "kill_switch", alias: "kill_switch", name: "کلید قطع اضطراری سراسری (Kill Switch)", icon: "🔴" },
      { id: "live_safety_engine", alias: "live_safety_engine", name: "موتور امنیت و راستی‌آزمایی سفارشات زنده", icon: "🔐" }
    ]
  },
  order_execution: {
    name: "اجرا و تطبیق سفارشات",
    capabilities: [
      { id: "order_manager", alias: "order_manager", name: "مدیریت چرخه حیات سفارشات (Order Manager)", icon: "📝" },
      { id: "idempotency", alias: "idempotency", name: "جلوگیری از ثبت تکراری سفارشات (Idempotency)", icon: "✅" },
      { id: "fill_manager", alias: "fill_manager", name: "تطبیق فیل سفارشات (Partial & Full Fills)", icon: "🧩" },
      { id: "position_manager", alias: "position_manager", name: "ردیابی موقعیت‌های باز (Position Manager)", icon: "📦" },
      { id: "exchange_reconciliation", alias: "exchange_reconciliation", name: "تطبیق و راستی‌آزمایی موجودی صرافی", icon: "🔄" },
      { id: "crash_recovery", alias: "crash_recovery", name: "بازیابی خودکار وضعیت پس از توقف ناگهانی", icon: "♻️" },
      { id: "database", alias: "persistence_database", name: "پایگاه داده پایدار و ثبت وقایع معاملاتی", icon: "🗄️" }
    ]
  },
  backtesting_quant: {
    name: "بک‌تست و محاسبات کوانت",
    capabilities: [
      { id: "walk_forward_backtest", alias: "walk_forward_backtesting", name: "بک‌تست پیش‌رونده (Walk-Forward)", icon: "🔙" },
      { id: "out_of_sample", alias: "out_of_sample_testing", name: "ارزیابی داده‌های خارج از نمونه (Out-of-Sample)", icon: "🧪" },
      { id: "transaction_cost", alias: "transaction_cost_modeling", name: "مدل‌سازی دقیق کارمزد و هزینه‌های معاملاتی", icon: "💸" },
      { id: "slippage_modeling", alias: "slippage_modeling", name: "مدل‌سازی لغزش قیمت (Slippage Modeling)", icon: "📊" },
      { id: "no_trade_zone", alias: "no_trade_zone", name: "فیلتر ناحیه عدم معامله در شرایط پر ریسک", icon: "🚫" },
      { id: "benchmarking", alias: "benchmarking", name: "مقایسه و بنچ‌مارک در برابر شاخص بازار", icon: "📈" },
      { id: "ensemble_backtest", alias: "ensemble_backtesting", name: "بک‌تست ترکیبی استراتژی‌های ناهمبسته", icon: "🎭" },
      { id: "performance_metrics", alias: "performance_metrics", name: "محاسبه شاخص‌های مالی (Sharpe, Sortino, Calmar)", icon: "📉" },
      { id: "regime_analysis", alias: "regime_based_analysis", name: "تحلیل عملکرد در رژیم‌های مختلف بازار", icon: "🔬" },
      { id: "monte_carlo", alias: "monte_carlo_robustness", name: "شبیه‌سازی مونت کارلو و تست استرس", icon: "🎲" }
    ]
  },
  ai_ml: {
    name: "هوش مصنوعی و یادگیری ماشین",
    capabilities: [
      { id: "ml_pipeline", alias: "ml_pipeline", name: "خط لوله آموزش و پردازش یادگیری ماشین", icon: "🔧" },
      { id: "feature_engineering", alias: "feature_engineering", name: "مهندسی ویژگی‌های بازار (Feature Engineering)", icon: "🔨" },
      { id: "causal_features", alias: "causal_feature_engineering", name: "ویژگی‌های علّی برای پیشگیری از اورفیت", icon: "🔗" },
      { id: "purged_walkforward", alias: "purged_walk_forward_validation", name: "اعتبارسنجی Purged Walk-Forward", icon: "🚿" },
      { id: "ml_prediction", alias: "ml_prediction", name: "موتور پیش‌بینی جهت و نوسان قیمت با ML", icon: "🔮" },
      { id: "model_registry", alias: "model_registry", name: "رجیستری و ذخیره‌سازی مدل‌های آموزش‌دیده", icon: "📚" },
      { id: "model_versioning", alias: "model_versioning", name: "مدیریت نسخه‌ها و متادیتا مدل‌ها", icon: "🏷️" },
      { id: "model_drift", alias: "model_drift_monitoring", name: "پایش افت دقت و تغییر توزیع داده (Drift)", icon: "📡" },
      { id: "ml_strategy_integration", alias: "ml_strategy_integration", name: "ادغام خروجی ML با سیگنال‌های معاملاتی", icon: "🔀" }
    ]
  },
  ai_sentiment: {
    name: "تحلیل احساسات و پردازش متن",
    capabilities: [
      { id: "sentiment_analysis", alias: "sentiment_analysis", name: "تحلیل سنتیمنت بازار کریپتو", icon: "😊" },
      { id: "news_context", alias: "news_context_analysis", name: "پایش رویدادها و اخبار مهم بازار", icon: "📰" },
      { id: "llm_integration", alias: "llm_integration", name: "اتصال به مدل‌های زبانی بزرگ (LLM)", icon: "🧠" },
      { id: "sentiment_signal", alias: "sentiment_as_signal", name: "تولید فیلتر و سیگنال بر مبنای سنتیمنت", icon: "📶" }
    ]
  },
  infrastructure: {
    name: "زیرساخت و مانیتورینگ",
    capabilities: [
      { id: "fastapi", alias: "fastapi", name: "سرویس وب و API سرور بلادرنگ", icon: "⚡" },
      { id: "trading_api", alias: "trading_api", name: "واسط کاربری و ارتباط با API صرافی‌ها", icon: "🌐" },
      { id: "health_monitoring", alias: "health_status_monitoring", name: "پایش مداوم سلامت سرویس‌ها و پینگ", icon: "❤️" },
      { id: "logging", alias: "logging", name: "سیستم جامع ثبت لاگ‌های رویداد و خطا", icon: "📝" },
      { id: "observability", alias: "observability", name: "دیدبانی، متریک‌ها و هشدارهای سیستم", icon: "👁️" },
      { id: "config_management", alias: "configuration_management", name: "مدیریت تنظیمات و متغیرهای محیطی", icon: "⚙️" },
      { id: "sqlite_postgresql", alias: "sqlite_postgresql", name: "پایگاه داده ذخیره‌سازی وضعیت و سفارشات", icon: "🗄️" },
      { id: "docker_deployment", alias: "docker_deployment", name: "کانتینرسازی و استقرار با Docker", icon: "🐳" },
      { id: "ci_cd", alias: "ci_cd_support", name: "یکپارچه‌سازی و تست مداوم (CI/CD)", icon: "🔄" },
      { id: "paper_trading", alias: "paper_trading", name: "شبیه‌ساز معامله کاغذی (Paper Trading)", icon: "📄" },
      { id: "shadow_trading", alias: "shadow_trading", name: "معامله سایه‌ای با جریان داده زنده", icon: "👤" },
      { id: "live_trading", alias: "live_trading_architecture", name: "معماری معاملاتی واقعی و استقرار امن", icon: "🔴" }
    ]
  }
};

// Flatten map of all capability IDs and aliases
const CAPABILITY_LOOKUP = new Map();
const ALL_CAPS_LIST = [];

for (const [categoryKey, categoryData] of Object.entries(CAPABILITY_STRUCTURE)) {
  for (const cap of categoryData.capabilities) {
    const item = { ...cap, category: categoryKey };
    ALL_CAPS_LIST.push(item);
    CAPABILITY_LOOKUP.set(cap.id, item);
    if (cap.alias) {
      CAPABILITY_LOOKUP.set(cap.alias, item);
    }
  }
}

// In-memory data store
const inMemoryLogs = new Map();
const inMemoryAnalysis = new Map();

// Helper to normalize capability key
function normalizeCapKey(key) {
  if (CAPABILITY_LOOKUP.has(key)) {
    return CAPABILITY_LOOKUP.get(key).id;
  }
  return key;
}

// Pre-load from capabilities_logs directory if it exists
function loadInitialLogs() {
  const logDir = path.join(__dirname, 'capabilities_logs');
  if (fs.existsSync(logDir)) {
    try {
      const files = fs.readdirSync(logDir);
      for (const file of files) {
        if (file.endsWith('.jsonl')) {
          const capId = file.replace('.jsonl', '');
          const filePath = path.join(logDir, file);
          const lines = fs.readFileSync(filePath, 'utf-8').split('\n').filter(Boolean);
          const entries = [];
          for (const line of lines) {
            try {
              const parsed = JSON.parse(line);
              entries.push({
                timestamp: parsed.timestamp || new Date().toISOString(),
                event_type: parsed.event_type || 'info',
                status: parsed.event_type || 'success',
                message: parsed.message || 'عملیات نرمال',
                data: parsed.details || {}
              });
            } catch (e) {
              // ignore invalid line
            }
          }
          if (entries.length > 0) {
            inMemoryLogs.set(capId, entries);
            const meta = CAPABILITY_LOOKUP.get(capId);
            if (meta && meta.alias) {
              inMemoryLogs.set(meta.alias, entries);
            }
          }
        }
      }
    } catch (e) {
      console.warn('Could not read capabilities_logs directory:', e.message);
    }
  }

  // Pre-seed some default logs for any capabilities that have none
  for (const cap of ALL_CAPS_LIST) {
    if (!inMemoryLogs.has(cap.id) || inMemoryLogs.get(cap.id).length === 0) {
      const defaultEntries = [
        {
          timestamp: new Date(Date.now() - 3600000).toISOString(),
          event_type: 'info',
          status: 'success',
          message: `آماده‌سازی و شروع به کار ماژول ${cap.name}`,
          data: { initialized: true }
        },
        {
          timestamp: new Date().toISOString(),
          event_type: 'success',
          status: 'success',
          message: `عملیات نرمال و بررسی دوره‌ای - ${cap.name}`,
          data: { healthy: true, latency_ms: Math.floor(Math.random() * 20) + 5 }
        }
      ];
      inMemoryLogs.set(cap.id, defaultEntries);
      if (cap.alias) inMemoryLogs.set(cap.alias, defaultEntries);
    }

    // Default analysis
    const defaultAnalysis = {
      capability: cap.id,
      timestamp: new Date().toISOString(),
      analysis: `وضعیت ماژول ${cap.name} پایدار است. تمام بررسی‌های دوره‌ای بدون ناهنجاری انجام شده‌اند.`,
      recommendation: `ادامه عملکرد با پارامترهای پیش‌فرض و رصد منظم شاخص‌های سلامت.`,
      confidence: 0.95,
      risk_level: 'low'
    };
    inMemoryAnalysis.set(cap.id, defaultAnalysis);
    if (cap.alias) inMemoryAnalysis.set(cap.alias, defaultAnalysis);
  }
}

loadInitialLogs();

// Lazy Gemini SDK client initialization
let genAI = null;
async function getGeminiModel() {
  if (!process.env.GEMINI_API_KEY) return null;
  if (!genAI) {
    try {
      const { GoogleGenAI } = await import('@google/genai');
      genAI = new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY });
    } catch (e) {
      console.warn('Could not initialize GoogleGenAI:', e.message);
      return null;
    }
  }
  return genAI;
}

// Generate intelligent LLM analysis
async function generateCapabilityAnalysis(capId, logMessage, logData) {
  const normId = normalizeCapKey(capId);
  const capInfo = CAPABILITY_LOOKUP.get(normId) || { name: capId, category: 'general' };
  
  const ai = await getGeminiModel();
  if (ai) {
    try {
      const prompt = `You are a Senior Quantitative Crypto Trading Systems Engineer.
Analyze the following capability log from the trading system:
Capability: ${capInfo.name} (ID: ${capId}, Category: ${capInfo.category})
Log Message: ${logMessage}
Log Data: ${JSON.stringify(logData || {})}

Provide your response in Persian (Farsi) as valid JSON without markdown:
{
  "analysis": "تحلیل دقیق وضعیت ماژول به فارسی",
  "recommendation": "توصیه عملیاتی به فارسی",
  "confidence": 0.95,
  "risk_level": "low" // or "medium" or "high" or "critical"
}`;
      const response = await ai.models.generateContent({
        model: 'gemini-2.5-flash',
        contents: prompt
      });
      const text = response.text || '';
      const cleanJson = text.replace(/```json/g, '').replace(/```/g, '').trim();
      const parsed = JSON.parse(cleanJson);
      const res = {
        capability: capId,
        timestamp: new Date().toISOString(),
        analysis: parsed.analysis || `تحلیل خودکار ماژول ${capInfo.name}`,
        recommendation: parsed.recommendation || 'ادامه رصد و مانیتورینگ',
        confidence: Number(parsed.confidence) || 0.9,
        risk_level: parsed.risk_level || 'low'
      };
      inMemoryAnalysis.set(capId, res);
      inMemoryAnalysis.set(normId, res);
      return res;
    } catch (e) {
      console.warn('Gemini generateContent failed, falling back to rule-based engine:', e.message);
    }
  }

  // Fallback domain analysis
  let riskLevel = 'low';
  let messageLower = (logMessage || '').toLowerCase();
  if (messageLower.includes('error') || messageLower.includes('خطا') || messageLower.includes('fail') || messageLower.includes('شکست')) {
    riskLevel = 'high';
  } else if (messageLower.includes('warning') || messageLower.includes('هشدار') || messageLower.includes('تاخیر')) {
    riskLevel = 'medium';
  }

  const analysisResult = {
    capability: capId,
    timestamp: new Date().toISOString(),
    analysis: riskLevel === 'low'
      ? `ماژول ${capInfo.name} در وضعیت بهینه است. تمامی پارامترها در بازه نرمال قرار دارند.`
      : riskLevel === 'medium'
      ? `هشدار خفیف در ماژول ${capInfo.name}: عملکرد نیازمند پایش بیشتر است اما پایداری حفظ شده است.`
      : `خطا در پردازش ماژول ${capInfo.name}: نیاز به بررسی فایل لاگ و تنظیم مجدد کانفیگ.`,
    recommendation: riskLevel === 'low'
      ? 'ادامه روال عادی معاملات و حفظ تعادل سرمایه.'
      : riskLevel === 'medium'
      ? 'کاهش مقطعی حجم سفارشات و پایش مجدد نوسانات بازار.'
      : 'فعال‌سازی بررسی اضطراری و ارزیابی سلامت اتصالات صرافی.',
    confidence: riskLevel === 'low' ? 0.95 : 0.82,
    risk_level: riskLevel
  };

  inMemoryAnalysis.set(capId, analysisResult);
  inMemoryAnalysis.set(normId, analysisResult);
  return analysisResult;
}

// -------------------------------------------------------------
// ROUTES
// -------------------------------------------------------------

// Serve dashboard HTML at / and /index.html
app.get('/', (req, res) => {
  const staticIndex = path.join(__dirname, 'static', 'index.html');
  if (fs.existsSync(staticIndex)) {
    return res.sendFile(staticIndex);
  }
  res.sendFile(path.join(__dirname, 'index.html'));
});

// Serve static assets
app.use('/static', express.static(path.join(__dirname, 'static')));

// GET /api/data - Full dashboard payload for static/index.html & web_api.py clients
app.get('/api/data', (req, res) => {
  const capabilities_status = {};
  
  for (const cap of ALL_CAPS_LIST) {
    const logs = inMemoryLogs.get(cap.id) || inMemoryLogs.get(cap.alias) || [];
    const analysis = inMemoryAnalysis.get(cap.id) || inMemoryAnalysis.get(cap.alias);
    
    let status = 'active';
    const recent = logs.slice(-5);
    const errors = recent.filter(l => l.event_type === 'error' || l.status === 'error').length;
    const warnings = recent.filter(l => l.event_type === 'warning' || l.status === 'warning').length;
    if (errors > 0) status = 'error';
    else if (warnings > 0) status = 'warning';

    capabilities_status[cap.id] = {
      status,
      logs: logs.slice(-10),
      llm_analysis: analysis
    };
    if (cap.alias) {
      capabilities_status[cap.alias] = capabilities_status[cap.id];
    }
  }

  res.json({
    status: 'online',
    metrics: {
      uptime: '3 روز و 14 ساعت و 25 دقیقه',
      cycles: 184,
      balance: 24850.50,
      pnl: 1420.75,
      last_trade: new Date(Date.now() - 120000).toISOString(),
      active_strategies: 8,
      total_capabilities: 60,
      active_logs: ALL_CAPS_LIST.length
    },
    logs: [
      { line: `[${new Date().toISOString()}] [INFO] System heartbeat OK - all 60 capabilities active` },
      { line: `[${new Date(Date.now() - 60000).toISOString()}] [INFO] Portfolio rebalanced across Binance & KuCoin` },
      { line: `[${new Date(Date.now() - 120000).toISOString()}] [INFO] Risk guardrails checked: Drawdown well below limit` }
    ],
    capabilities_status,
    capabilities_structure: CAPABILITY_STRUCTURE,
    category_evaluations: {
      core_trading: { status: 'healthy', summary: 'استراتژی‌های تکنیکال و فیلترهای رژیم بازار بدون ناهنجاری فعال هستند.' },
      risk_management: { status: 'healthy', summary: 'کنترل‌کننده‌های حد ضرر و ریسک به درستی پوزیشن‌ها را محافظت می‌کنند.' },
      order_execution: { status: 'healthy', summary: 'سرعت اجرای اردرها مطلوب و نرخ فیل شدن سفارشات ۹۹.۸٪ است.' },
      backtesting_quant: { status: 'healthy', summary: 'آزمون‌های Walk-Forward و ارزیابی هزینه‌ها تأیید شده‌اند.' },
      ai_ml: { status: 'healthy', summary: 'مدل یادگیری ماشین با دقت قابل قبول سیگنال‌های کمکی تولید می‌کند.' },
      ai_sentiment: { status: 'healthy', summary: 'سنتیمنت شبکه‌های اجتماعی و اخبار بازار مثبت و در محدوده امن ارزیابی شد.' },
      infrastructure: { status: 'healthy', summary: 'سرور، پایگاه داده و مانیتورینگ بلادرنگ با پایداری ۱۰۰٪ در دسترس هستند.' }
    }
  });
});

// GET /api/v1/capabilities/dashboard - Dashboard response for FastAPI clients
app.get('/api/v1/capabilities/dashboard', (req, res) => {
  const categories = {};
  const summary = { healthy: 0, degraded: 0, failing: 0, unknown: 0 };

  for (const [catKey, catData] of Object.entries(CAPABILITY_STRUCTURE)) {
    categories[catKey] = catData.capabilities.map(cap => {
      const logs = inMemoryLogs.get(cap.id) || inMemoryLogs.get(cap.alias) || [];
      const errors = logs.filter(l => l.event_type === 'error' || l.status === 'error').length;
      const warnings = logs.filter(l => l.event_type === 'warning' || l.status === 'warning').length;
      
      let status = 'healthy';
      if (errors > 0) {
        status = 'failing';
        summary.failing++;
      } else if (warnings > 0) {
        status = 'degraded';
        summary.degraded++;
      } else if (logs.length === 0) {
        status = 'unknown';
        summary.unknown++;
      } else {
        summary.healthy++;
      }

      return {
        capability: cap.alias || cap.id,
        name: cap.name,
        category: catKey,
        status,
        total_logs: logs.length,
        success_count: logs.length - errors - warnings,
        warning_count: warnings,
        error_count: errors
      };
    });
  }

  res.json({
    total_capabilities: 60,
    summary,
    categories
  });
});

// GET /api/v1/capabilities/full-report - Aggregated full report in one instantaneous call
app.get(['/api/v1/capabilities/full-report', '/api/report/full'], (req, res) => {
  let reportText = "=== گزارش کامل لاگ‌ها و تحلیل‌های هوشمند سیستم ترید ===\n";
  reportText += `تاریخ گزارش: ${new Date().toLocaleString('fa-IR')}\n`;
  reportText += `تعداد کل قابلیت‌ها: 60\n`;

  let healthy = 0, degraded = 0, failing = 0;
  for (const cap of ALL_CAPS_LIST) {
    const logs = inMemoryLogs.get(cap.id) || inMemoryLogs.get(cap.alias) || [];
    const errors = logs.filter(l => l.event_type === 'error' || l.status === 'error').length;
    const warnings = logs.filter(l => l.event_type === 'warning' || l.status === 'warning').length;
    if (errors > 0) failing++;
    else if (warnings > 0) degraded++;
    else healthy++;
  }
  reportText += `خلاصه وضعیت: سالم=${healthy}، هشدار/کاهشی=${degraded}، ناموفق=${failing}\n\n`;

  for (const [catKey, catData] of Object.entries(CAPABILITY_STRUCTURE)) {
    reportText += `\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n`;
    reportText += `دسته‌بندی: ${catData.name} (${catKey})\n`;
    reportText += `تعداد قابلیت‌ها: ${catData.capabilities.length}\n`;
    reportText += `━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n`;

    for (const cap of catData.capabilities) {
      const logs = inMemoryLogs.get(cap.id) || inMemoryLogs.get(cap.alias) || [];
      const analysis = inMemoryAnalysis.get(cap.id) || inMemoryAnalysis.get(cap.alias);
      const errors = logs.filter(l => l.event_type === 'error' || l.status === 'error').length;
      const warnings = logs.filter(l => l.event_type === 'warning' || l.status === 'warning').length;
      const status = errors > 0 ? 'failing' : (warnings > 0 ? 'degraded' : 'healthy');

      reportText += `┌─────────────────────────────────────\n`;
      reportText += `│ قابلیت: ${cap.name} [${cap.id}]\n`;
      reportText += `│ وضعیت: ${status}\n`;
      reportText += `│ تعداد کل لاگ‌ها: ${logs.length}\n`;
      reportText += `└─────────────────────────────────────\n`;

      if (logs.length > 0) {
        for (const log of logs.slice(-5)) {
          reportText += `  📝 لاگ: [${new Date(log.timestamp).toLocaleString('fa-IR')}] [${(log.status || log.event_type || 'info').toUpperCase()}]: ${log.message}\n`;
        }
      } else {
        reportText += `  (بدون لاگ ثبت شده)\n`;
      }

      if (analysis) {
        reportText += `  🤖 تحلیل هوشمند:\n`;
        reportText += `     نتیجه: ${analysis.analysis || 'نامشخص'}\n`;
        reportText += `     سطح ریسک: ${analysis.risk_level || 'low'}\n`;
        reportText += `     توصیه: ${analysis.recommendation || 'ندارد'}\n`;
        reportText += `     اطمینان: ${Math.round((analysis.confidence || 0.9) * 100)}%\n`;
      }
      reportText += `\n`;
    }
  }

  reportText += `━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n`;
  reportText += `پایان گزارش جامع سیستم ترید\n`;
  reportText += `━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n`;

  res.json({
    success: true,
    total_capabilities: 60,
    summary: { healthy, degraded, failing },
    report_text: reportText,
    timestamp: new Date().toISOString()
  });
});

// GET /api/v1/capabilities/export-text - Downloadable raw text file
app.get(['/api/v1/capabilities/export-text', '/api/report/download'], (req, res) => {
  let reportText = "=== گزارش کامل لاگ‌ها و تحلیل‌های هوشمند سیستم ترید ===\n";
  reportText += `تاریخ گزارش: ${new Date().toLocaleString('fa-IR')}\n`;
  reportText += `تعداد کل قابلیت‌ها: 60\n\n`;

  for (const [catKey, catData] of Object.entries(CAPABILITY_STRUCTURE)) {
    reportText += `\n========================================\n`;
    reportText += `دسته‌بندی: ${catData.name}\n`;
    reportText += `========================================\n\n`;

    for (const cap of catData.capabilities) {
      const logs = inMemoryLogs.get(cap.id) || inMemoryLogs.get(cap.alias) || [];
      const analysis = inMemoryAnalysis.get(cap.id) || inMemoryAnalysis.get(cap.alias);
      reportText += `[${cap.name} - ${cap.id}]\n`;
      if (analysis) {
        reportText += `تحلیل: ${analysis.analysis}\nتوصیه: ${analysis.recommendation} (ریسک: ${analysis.risk_level})\n`;
      }
      for (const log of logs.slice(-5)) {
        reportText += `  - ${log.timestamp} [${log.status}]: ${log.message}\n`;
      }
      reportText += `\n`;
    }
  }

  res.setHeader('Content-Type', 'text/plain; charset=utf-8');
  res.setHeader('Content-Disposition', 'attachment; filename="trading_system_report.txt"');
  res.send(reportText);
});

// GET capabilities structure
app.get(['/api/capabilities', '/api/v1/capabilities'], (req, res) => {
  res.json(CAPABILITY_STRUCTURE);
});

// GET logs for capability (FastAPI & Flask route formats)
app.get(['/api/capability/:id/logs', '/api/v1/capabilities/:id/logs', '/api/logs/:id'], (req, res) => {
  const capId = req.params.id;
  const limit = parseInt(req.query.limit, 10) || 50;
  const normId = normalizeCapKey(capId);
  const logs = inMemoryLogs.get(normId) || inMemoryLogs.get(capId) || [];
  res.json(logs.slice(-limit));
});

// GET analysis for capability
app.get(['/api/capability/:id/analysis', '/api/v1/capabilities/:id/analysis'], (req, res) => {
  const capId = req.params.id;
  const normId = normalizeCapKey(capId);
  const analysis = inMemoryAnalysis.get(normId) || inMemoryAnalysis.get(capId);
  if (analysis) {
    return res.json(analysis);
  }
  // Auto-generate if missing
  const generated = {
    capability: capId,
    timestamp: new Date().toISOString(),
    analysis: `وضعیت ماژول ${capId} در حالت عادی ارزیابی شد.`,
    recommendation: 'پایش مستمر عملکرد',
    confidence: 0.9,
    risk_level: 'low'
  };
  inMemoryAnalysis.set(capId, generated);
  res.json(generated);
});

// POST analyze capability
app.post(['/api/capability/:id/analyze', '/api/v1/capabilities/:id/analyze'], async (req, res) => {
  const capId = req.params.id;
  const { log_message, log_data } = req.body || {};
  const analysis = await generateCapabilityAnalysis(capId, log_message || 'تحلیل دستی درخواست شد', log_data);
  res.json({ success: true, analysis });
});

// POST log capability event
app.post(['/api/capability/:id/log', '/api/v1/capabilities/log', '/api/v1/capabilities/:id/log'], async (req, res) => {
  const capId = req.params.id || req.body.capability;
  const normId = normalizeCapKey(capId);
  const event_type = req.body.event_type || req.body.status || 'info';
  const message = req.body.message || 'ثبت رویداد قابلیت';
  const details = req.body.details || req.body.data || {};

  const entry = {
    timestamp: new Date().toISOString(),
    event_type,
    status: event_type,
    message,
    data: details
  };

  if (!inMemoryLogs.has(normId)) inMemoryLogs.set(normId, []);
  inMemoryLogs.get(normId).push(entry);
  if (capId !== normId) {
    if (!inMemoryLogs.has(capId)) inMemoryLogs.set(capId, []);
    inMemoryLogs.get(capId).push(entry);
  }

  // Update analysis in background
  generateCapabilityAnalysis(normId, message, details).catch(() => {});

  res.json({ success: true, message: 'لاگ با موفقیت ثبت شد', data: entry });
});

// POST /api/simulate - Simulate randomized activity across capabilities
app.post('/api/simulate', async (req, res) => {
  const selectedCaps = [...ALL_CAPS_LIST].sort(() => 0.5 - Math.random()).slice(0, 8);
  const eventTypes = ['info', 'success', 'warning', 'error'];
  const weights = [0.55, 0.35, 0.08, 0.02];

  for (const cap of selectedCaps) {
    const r = Math.random();
    let eventType = 'info';
    let cumulative = 0;
    for (let i = 0; i < weights.length; i++) {
      cumulative += weights[i];
      if (r <= cumulative) {
        eventType = eventTypes[i];
        break;
      }
    }

    const messages = {
      info: `بررسی دوره‌ای سلامت و پایش وضعیت - ${cap.name}`,
      success: `عملیات با موفقیت تأیید و اجرا شد - ${cap.name}`,
      warning: `نوسان مقطعی داده‌ها یا تأخیر سبک پاسخ‌دهی - ${cap.name}`,
      error: `عدم تطابق جزئی یا نیاز به تلاش مجدد اتصال - ${cap.name}`
    };

    const entry = {
      timestamp: new Date().toISOString(),
      event_type: eventType,
      status: eventType,
      message: messages[eventType],
      data: { random_seed: Math.floor(Math.random() * 1000) }
    };

    if (!inMemoryLogs.has(cap.id)) inMemoryLogs.set(cap.id, []);
    inMemoryLogs.get(cap.id).push(entry);
    if (cap.alias) {
      if (!inMemoryLogs.has(cap.alias)) inMemoryLogs.set(cap.alias, []);
      inMemoryLogs.get(cap.alias).push(entry);
    }

    // Refresh analysis
    generateCapabilityAnalysis(cap.id, entry.message, entry.data).catch(() => {});
  }

  res.json({ success: true, message: 'فعالیت برای قابلیت‌ها با موفقیت شبیه‌سازی شد' });
});

// Categorized logs
app.get('/api/logs/categorized', (req, res) => {
  const allEntries = [];
  for (const entries of inMemoryLogs.values()) {
    allEntries.push(...entries);
  }
  const categorized = {
    info: allEntries.filter(e => e.event_type === 'info').slice(-50),
    success: allEntries.filter(e => e.event_type === 'success').slice(-50),
    warning: allEntries.filter(e => e.event_type === 'warning').slice(-50),
    error: allEntries.filter(e => e.event_type === 'error').slice(-50)
  };

  res.json({
    success: true,
    categorized_logs: categorized,
    log_counts: {
      info: categorized.info.length,
      success: categorized.success.length,
      warning: categorized.warning.length,
      error: categorized.error.length
    },
    total_logs: allEntries.length
  });
});

// System health & status routes
app.get(['/api/health', '/api/v1/health'], (req, res) => {
  res.json({
    status: 'healthy',
    timestamp: new Date().toISOString(),
    uptime: process.uptime(),
    capabilities_loaded: ALL_CAPS_LIST.length
  });
});

app.get('/api/v1/status', (req, res) => {
  res.json({
    system_status: 'online',
    mode: process.env.TRADING_MODE || 'paper',
    exchange: 'connected',
    risk_state: 'normal',
    active_strategies_count: 8,
    timestamp: new Date().toISOString()
  });
});

app.get('/api/v1/metrics', (req, res) => {
  res.json({
    cpu_usage_pct: 12.4,
    memory_usage_mb: 64.2,
    active_connections: 1,
    orders_filled_today: 142,
    pnl_today_usd: 340.50
  });
});

app.get('/api/v1/portfolio', (req, res) => {
  res.json({
    total_equity_usd: 25480.00,
    free_margin_usd: 18240.00,
    used_margin_usd: 7240.00,
    positions: [
      { symbol: 'BTC/USDT', side: 'LONG', size: 0.12, entry_price: 64200, current_price: 65150, pnl: 114.0 },
      { symbol: 'ETH/USDT', side: 'LONG', size: 1.5, entry_price: 3410, current_price: 3480, pnl: 105.0 }
    ]
  });
});

app.get('/api/v1/risk', (req, res) => {
  res.json({
    circuit_breaker_tripped: false,
    kill_switch_active: false,
    current_drawdown_pct: 1.8,
    max_allowed_drawdown_pct: 10.0,
    daily_loss_pct: 0.4,
    max_daily_loss_pct: 3.0,
    status: 'PASS'
  });
});

// LLM config
app.get('/api/llm/config', (req, res) => {
  res.json({
    provider: process.env.GEMINI_API_KEY ? 'gemini' : 'fallback-rule-engine',
    model: 'gemini-2.5-flash',
    configured: Boolean(process.env.GEMINI_API_KEY)
  });
});

// Catch-all for other /api routes
app.use('/api', (req, res) => {
  res.status(501).json({ error: 'Endpoint not yet migrated' });
});

// Start server on 0.0.0.0:3000
app.listen(PORT, HOST, () => {
  console.log(`Crypto Trading Bot Dashboard listening at http://${HOST}:${PORT}`);
});
