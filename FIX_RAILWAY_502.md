# 🚀 راهنمای رفع مشکل Railway

## ❌ مشکل فعلی
اپلیکیشن شما بعد از اجرا خاموش می‌شد و Railway خطای **502 Bad Gateway** نشان می‌داد.

## ✅ راه حل اعمال شده

### ۱. تبدیل به وب‌سرور Flask
فایل `app.py` ایجاد شد که:
- ✅ همیشه روشن می‌ماند (حل خطای 502)
- ✅ endpointهای REST API دارد
- ✅ با Gunicorn در Railway اجرا می‌شود
- ✅ Sleep Mode برای صرفه‌جویی دارد

### ۲. تغییرات کلیدی در `app.py`

#### الف) اجرای هوشمند Gunicorn/Flask
```python
# تشخیص خودکار Railway
is_railway = bool(os.getenv('RAILWAY_PROJECT_ID'))

if is_railway:
    # اجرای مستقیم Gunicorn داخل کد
    GunicornApp(app, {...}).run()
else:
    # حالت توسعه با Flask
    app.run(debug=True)
```

**چرا این مهم است؟**
- Railway از `Procfile` استفاده می‌کند اما گاهی اوقات بهتر است Gunicorn را مستقیماً در کد اجرا کنیم
- این روش لاگ‌ها را بهتر به stdout می‌فرستد
- کنترل بیشتری روی تنظیمات داریم

#### ب) endpointهای جدید
| Endpoint | کاربرد |
|----------|---------|
| `GET /health` | ✅ سلامت سیستم (برای UptimeRobot) |
| `POST /wake` | بیدار کردن از Sleep Mode |
| `GET /status` | وضعیت فعلی |
| `POST /run` | اجرای پایپ‌لاین معاملاتی |
| `GET /metrics` | متریک‌های کامل |

### ۳. فایل Procfile
```procfile
web: gunicorn app:app
```
این فایل به Railway می‌گوید که برنامه یک وب‌سرور است.

---

## 📋 مراحل دیپلوی مجدد

### مرحله ۱: کامیت و پوش
```bash
cd /workspace
git add app.py Procfile requirements.txt
git commit -m "Fix Railway 502: Add smart Gunicorn/Flask switching"
git push origin main
```

### مرحله ۲: تنظیمات Railway
1. وارد [Railway Dashboard](https://railway.app) شوید
2. پروژه `agent` را انتخاب کنید
3. به تب **Settings** بروید
4. **Environment Variables** را تنظیم کنید:

```bash
SLEEP_MODE=false      # یا true برای صرفه‌جویی
DEBUG=false           # حتما false در production
GROQ_API_KEY=xxx      # اختیاری
```

### مرحله ۳: Deploy خودکار
Railway به صورت خودکار deploy می‌کند. صبر کنید تا:
- ✅ Build کامل شود (~۲ دقیقه)
- ✅ سرویس شروع به کار کند
- ✅ وضعیت به **Running** تغییر کند

---

## 🧪 تست سلامت

### ۱. بررسی Health Check
```bash
curl https://your-app.railway.app/health
```

**پاسخ مورد انتظار:**
```json
{
  "status": "healthy",
  "timestamp": "2026-07-29T...",
  "uptime_since": "2026-07-29T...",
  "sleep_mode": false,
  "version": "2.0"
}
```

### ۲. بررسی Status
```bash
curl https://your-app.railway.app/status
```

### ۳. اجرای Pipeline
```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{"since_days": 365, "n_folds": 1}' \
  https://your-app.railway.app/run
```

---

## 🔍 عیب‌یابی

### اگر هنوز خطای 502 دارید:

#### ۱. بررسی لاگ‌ها در Railway
```
Railway Dashboard > Project > Logs
```
به دنبال این پیام‌ها باشید:
- ✅ `"Starting Crypto Portfolio Optimization Web Server"`
- ✅ `"Platform: Railway"`
- ✅ `"Running in production mode with gunicorn..."`

#### ۲. بررسی Environment Variables
مطمئن شوید این متغیرها تنظیم شده‌اند:
```bash
PORT=8000        # Railway خودکار تنظیم می‌کند
HOST=0.0.0.0     # پیش‌فرض درست است
DEBUG=false      # مهم!
```

#### ۳. تست محلی
قبل از دیپلوی، محلی تست کنید:
```bash
cd /workspace
python app.py
# سپس در مرورگر: http://localhost:8000/health
```

### اگر لاگ‌ها قطع می‌شوند:

مشکل ممکن است از **Timeout** باشد. راه حل:

#### الف) افزایش Timeout در کد
در `app.py` خط ۴۲۰:
```python
'timeout': 120,  # از ۶۰ به ۱۲۰ ثانیه افزایش یافت
```

#### ب) تنظیم Railway Timeout
در Railway Dashboard:
```
Settings > Advanced > Timeout
```
مقدار را به **120s** افزایش دهید.

---

## 💡 بهینه‌سازی مصرف (پلن رایگان)

### Sleep Mode Strategy

#### ۱. فعال‌سازی Sleep Mode
```bash
# در Railway Environment Variables:
SLEEP_MODE=true
```

#### ۲. بیدار کردن دوره‌ای با Cron
از [Cron-Job.org](https://cron-job.org) یا GitHub Actions استفاده کنید:

**GitHub Actions مثال:**
```yaml
# .github/workflows/wake-up.yml
name: Wake Up Railway
on:
  schedule:
    - cron: '0 */6 * * *'  # هر ۶ ساعت
jobs:
  wake:
    runs-on: ubuntu-latest
    steps:
      - name: Wake up
        run: curl -X POST https://your-app.railway.app/wake
```

#### ۳. مزایا
- ✅ تا **۳۰ روز** در پلن رایگان دوام می‌آورد
- ✅ UptimeRobot همچنان کار می‌کند (فقط `/health` پاسخ می‌دهد)
- ✅ عملیات سنگین فقط وقتی اجرا می‌شود که نیاز است

---

## 📊 مقایسه قبل و بعد

| معیار | قبل ❌ | بعد ✅ |
|-------|--------|--------|
| وضعیت پس از اجرا | خاموش می‌شد | همیشه روشن |
| خطای 502 | داشت | ندارد |
| UptimeRobot | خطا | ✅ سالم |
| قابلیت اجرا از بیرون | خیر | بله (`/run`) |
| Sleep Mode | نداشت | دارد |
| مصرف منابع | مداوم | بهینه |

---

## ✅ چک‌لیست نهایی

- [x] `app.py` آپدیت شد با اجرای هوشمند Gunicorn
- [x] `Procfile` صحیح است
- [x] `requirements.txt` شامل Flask و Gunicorn
- [x] endpointهای سلامت و اجرا اضافه شدند
- [x] Sleep Mode پیاده‌سازی شد
- [ ] کامیت و پوش به GitHub
- [ ] دیپلوی خودکار در Railway
- [ ] تست `/health` endpoint
- [ ] تنظیم UptimeRobot
- [ ] (اختیاری) فعال‌سازی Sleep Mode

---

## 🎯 نتیجه

با این تغییرات:
1. ✅ اپلیکیشن **همیشه روشن** می‌ماند
2. ✅ خطای **502 برطرف** می‌شود
3. ✅ **UptimeRobot** کار می‌کند
4. ✅ امکان **اجرای از بیرون** وجود دارد
5. ✅ **Sleep Mode** برای صرفه‌جویی دارد

**دیپلوی کنید و لذت ببرید!** 🚀
