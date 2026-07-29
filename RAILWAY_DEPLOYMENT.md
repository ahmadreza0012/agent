# راهنمای استقرار روی Railway

## 📋 خلاصه تغییرات

### فایل‌های جدید:
1. **`app.py`** - وب‌سرور Flask با endpointهای زیر:
   - `GET /health` - بررسی سلامت (برای UptimeRobot)
   - `POST /wake` - بیدار کردن سیستم از حالت خواب
   - `GET /status` - دریافت وضعیت فعلی
   - `POST /run` - اجرای پایپ‌لاین معاملاتی
   - `GET /metrics` - دریافت متریک‌های کامل

2. **`Procfile`** - دستور اجرای برنامه برای Railway

### فایل‌های تغییر یافته:
1. **`requirements.txt`** - اضافه شدن Flask و gunicorn

---

## 🚀 مراحل استقرار

### مرحله ۱: آپدیت مخزن GitHub
```bash
cd /workspace
git add app.py Procfile requirements.txt
git commit -m "Add Flask web server for Railway deployment"
git push origin main
```

### مرحله ۲: تنظیمات Railway

#### گزینه A: اتصال به GitHub (توصیه می‌شود)
1. وارد [Railway](https://railway.app) شوید
2. روی **"New Project"** کلیک کنید
3. **"Deploy from GitHub repo"** را انتخاب کنید
4. مخزن `ahmadreza0012/agent` را انتخاب کنید
5. Railway به طور خودکار `Procfile` را تشخیص می‌دهد

#### گزینه B: Deploy مستقیم
1. Railway CLI را نصب کنید:
   ```bash
   npm install -g @railway/cli
   ```
2. لاگین کنید:
   ```bash
   railway login
   ```
3. پروژه را ایجاد کنید:
   ```bash
   railway init
   railway up
   ```

### مرحله ۳: تنظیم Environment Variables

در پنل Railway، به بخش **Variables** بروید و متغیرهای زیر را اضافه کنید:

| Variable | Value | توضیح |
|----------|-------|-------|
| `PORT` | `8000` | پورت پیش‌فرض (Railway به طور خودکار تنظیم می‌کند) |
| `GROQ_API_KEY` | `your_key_here` | کلید API اختیاری برای تحلیل احساسات واقعی |
| `SLEEP_MODE` | `false` | حالت خواب (`true` برای صرفه‌جویی در منابع) |
| `DEBUG` | `false` | حالت دیباگ (در production false باشد) |

برای دریافت GROQ_API_KEY رایگان:
1. به https://console.groq.com بروید
2. ثبت‌نام کنید
3. یک API Key جدید بسازید

---

## 🔧 پیکربندی UptimeRobot

### تنظیم Monitor جدید:
1. وارد [UptimeRobot](https://uptimerobot.com) شوید
2. **"Add New Monitor"** را بزنید
3. تنظیمات:
   - **Monitor Type**: HTTP(s)
   - **Friendly Name**: Crypto Portfolio API
   - **URL**: `https://your-app.railway.app/health`
   - **Monitoring Interval**: 5 minutes
   - **HTTP Method**: GET

### نکته مهم درباره Sleep Mode:
اگر `SLEEP_MODE=true` تنظیم کرده‌اید:
- UptimeRobot فقط `/health` را چک می‌کند (همیشه پاسخ می‌دهد)
- برای اجرای پایپ‌لاین، باید ابتدا `/wake` را صدا بزنید
- یا `SLEEP_MODE=false` بگذارید تا همیشه فعال باشد

---

## 📡 استفاده از API

### ۱. بررسی سلامت
```bash
curl https://your-app.railway.app/health
```

پاسخ نمونه:
```json
{
  "status": "healthy",
  "timestamp": "2026-07-29T16:00:00.000000",
  "uptime_since": "2026-07-29T10:00:00.000000",
  "sleep_mode": false,
  "version": "2.0"
}
```

### ۲. بیدار کردن سیستم (اگر Sleep Mode فعال است)
```bash
curl -X POST https://your-app.railway.app/wake
```

### ۳. اجرای پایپ‌لاین معاملاتی
```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{"since_days": 365, "n_folds": 1}' \
  https://your-app.railway.app/run
```

پاسخ نمونه:
```json
{
  "status": "success",
  "message": "Pipeline executed successfully",
  "duration_seconds": 15.32,
  "timestamp": "2026-07-29T16:05:00.000000",
  "results": {
    "mean_monthly_return": -0.0102,
    "median_monthly_return": 0.0116,
    "worst_monthly_return": -0.1926,
    "pct_months_positive": 0.67,
    "worst_max_drawdown": -0.1972,
    "mean_sharpe": -4.23,
    "target_achieved_on_average": false,
    "target_achieved_every_month": false,
    "drawdown_within_limit": false,
    "n_calendar_months_observed": 3
  },
  "data_points": 366,
  "warning": true
}
```

### ۴. دریافت وضعیت
```bash
curl https://your-app.railway.app/status
```

### ۵. دریافت متریک‌ها
```bash
curl https://your-app.railway.app/metrics
```

---

## 💡 بهینه‌سازی مصرف (Free Tier)

### استراتژی ۱: Sleep Mode هوشمند
```bash
# تنظیم SLEEP_MODE=true در Railway
# سپس از یک cron job برای بیدار کردن دوره‌ای استفاده کنید:

# هر ۶ ساعت یکبار بیدار شود و ۱ ساعت فعال بماند
0 */6 * * * curl -X POST https://your-app.railway.app/wake
```

### استراتژی ۲: اجرای زمان‌بندی شده
به جای روشن ماندن دائمی:
1. `SLEEP_MODE=true` بگذارید
2. از GitHub Actions یا cron job استفاده کنید:
   ```yaml
   # .github/workflows/run-pipeline.yml
   name: Run Trading Pipeline
   
   on:
     schedule:
       - cron: '0 0 * * *'  # هر روز ساعت ۰۰:۰۰ UTC
   
   jobs:
     run:
       runs-on: ubuntu-latest
       steps:
         - name: Wake and Run
           run: |
             curl -X POST ${{ secrets.RAILWAY_URL }}/wake
             sleep 5
             curl -X POST \
               -H "Content-Type: application/json" \
               -d '{"since_days": 365, "n_folds": 1}' \
               ${{ secrets.RAILWAY_URL }}/run
   ```

### استراتژی ۳: کاهش فرکانس داده
برای تست و توسعه:
```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{"since_days": 90, "n_folds": 1}' \
  https://your-app.railway.app/run
```

---

## 🐛 عیب‌یابی

### خطای 502 Bad Gateway
**علت**: برنامه بلافاصله بعد از اجرا تمام می‌شود
**راه حل**: 
- مطمئن شوید `Procfile` وجود دارد
- بررسی کنید `app.py` در حال اجرای Flask server است
- لاگ‌های Railway را چک کنید

### خطای 409 Conflict
**علت**: پایپ‌لاین قبلاً در حال اجراست
**راه حل**: صبر کنید تا اجرای فعلی تمام شود

### خطای 503 Service Unavailable
**علت**: سیستم در Sleep Mode است
**راه حل**: ابتدا `POST /wake` را صدا بزنید

### مصرف بالای منابع
**راه حل**:
1. `SLEEP_MODE=true` تنظیم کنید
2. از استراتژی‌های بهینه‌سازی بالا استفاده کنید
3. `since_days` را کاهش دهید

---

## 📊 مانیتورینگ

### لاگ‌های Railway
```bash
railway logs --follow
```

### بررسی وضعیت از طریق API
```bash
# هر ۵ دقیقه چک کنید
watch -n 300 'curl -s https://your-app.railway.app/status | jq'
```

---

## ⚠️ نکات مهم

1. **پلن رایگان Railway**: ۵ دلار اعتبار ماهانه (~۵۰۰ ساعت runtime)
   - با Sleep Mode می‌توانید تا ۳۰ روز دوام بیاورید
   - بدون Sleep Mode حدود ۲۰ روز

2. **محدودیت‌های CoinGecko**:
   - API رایگان: ۱۰-۵۰ درخواست در دقیقه
   - برای استفاده سنگین، API Key پولی بگیرید

3. **محدودیت‌های Groq**:
   - رایگان: ۳۰ درخواست در دقیقه
   - برای تولید واقعی، پلن پولی考虑 کنید

4. **امنیت**:
   - GROQ_API_KEY را هرگز commit نکنید
   - از Railway Secrets استفاده کنید
   - CORS را برای domainهای خاص محدود کنید (در صورت نیاز)

---

## 🎯 گام بعدی

بعد از استقرار موفق:
1. UptimeRobot را تنظیم کنید
2. اولین اجرای تستی انجام دهید
3. لاگ‌ها را بررسی کنید
4. در صورت نیاز پارامترها را تنظیم کنید
5. برای production، SSL و authentication اضافه کنید

موفق باشید! 🚀
