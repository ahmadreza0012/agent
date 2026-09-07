# 🚀 راهنمای نهایی رفع مشکل Railway 502

## ❌ مشکل فعلی
اپلیکیشن شما در آدرس https://agent-production-99ce.up.railway.app/ بالا نمی‌آید و خطای 502 می‌دهد.

## ✅ راه حل کامل

### وضعیت فعلی کدها:
- ✅ فایل `app.py` با وب‌سرور Flask آماده است
- ✅ فایل `Procfile` برای اجرای Gunicorn وجود دارد  
- ✅ فایل `requirements.txt` آپدیت شده
- ⚠️ **این فایل‌ها هنوز به GitHub پوش نشده‌اند!**

---

## 📝 مراحل دستی (باید خودتان انجام دهید)

### مرحله ۱: پوش کردن تغییرات به GitHub

در ترمینال محلی خود (روی سیستم خودتان):

```bash
# کلون کردن مخزن (اگر ندارید)
git clone https://github.com/ahmadreza0012/agent.git
cd agent

# یا اگر از قبل دارید
cd agent
git pull origin main

# بررسی تغییرات
git status

# اضافه کردن و کامیت
git add app.py Procfile requirements.txt
git commit -m "Fix Railway 502: Add Flask web server with smart Gunicorn switching"

# پوش کردن با استفاده از GitHub Token
# اول یک توکن بسازید: https://github.com/settings/tokens
# دسترسی‌های لازم: repo (Full control)

git push origin main
```

### روش جایگزین با SSH (اگر تنظیم کرده‌اید):
```bash
git remote set-url origin git@github.com:ahmadreza0012/agent.git
git push origin main
```

---

### مرحله ۲: دیپلوی مجدد در Railway

1. وارد https://railway.app شوید
2. پروژه `agent` را انتخاب کنید
3. به صورت خودکار دیپلوی شروع می‌شود
4. صبر کنید تا وضعیت به **"Running"** تغییر کند (۲-۳ دقیقه)

---

### مرحله ۳: تست سلامت

```bash
# بررسی سلامت اپلیکیشن
curl https://agent-production-99ce.up.railway.app/health

# باید پاسخ دهد:
# {"status": "healthy", "service": "crypto-portfolio-agent"}
```

---

### مرحله ۴: تنظیم UptimeRobot

1. وارد https://uptimerobot.com شوید
2. Monitor جدید بسازید:
   - Type: HTTP(s)
   - URL: `https://agent-production-99ce.up.railway.app/health`
   - Interval: 5 minutes

---

## 🔧 عیب‌یابی

### اگر هنوز 502 می‌گیرید:

#### ۱. بررسی لاگ‌های Railway
```
Dashboard > Deployments > View Logs
```

به دنبال این پیام‌ها باشید:
- ✅ `Listening on 0.0.0.0:{PORT}`
- ✅ `Worker spawned`
- ❌ `Application failed to respond`

#### ۲. بررسی Environment Variables
در Railway Dashboard:
```
Variables > Add Variable
```

مقادیر ضروری:
```
SLEEP_MODE=false
DEBUG=false
GROQ_API_KEY=your_key_here
```

#### ۳. بررسی Procfile
مطمئن شوید فایل `Procfile` دقیقاً این محتوا را دارد:
```
web: gunicorn app:app
```

#### ۴. افزایش Timeout
```
Settings > Advanced > Timeout = 120s
```

---

## 💡 بهینه‌سازی مصرف (Sleep Mode)

برای ماندن در پلن رایگان Railway:

### گزینه ۱: Sleep Mode فعال
```bash
# در Railway Variables
SLEEP_MODE=true
```

سپس هر ۶ ساعت بیدار کنید:
```bash
# Cron job (مثلاً در GitHub Actions یا سرور دیگر)
0 */6 * * * curl -X POST https://agent-production-99ce.up.railway.app/wake
```

### گزینه ۲: UptimeRobot + Sleep Mode
UptimeRobot هر ۵ دقیقه `/health` را صدا می‌زند که باعث بیدار ماندن می‌شود.

---

## 📊 endpointهای موجود

| Endpoint | Method | کاربرد |
|----------|--------|---------|
| `/` | GET | مستندات API |
| `/health` | GET | ✅ سلامت (برای UptimeRobot) |
| `/wake` | POST | بیدار کردن از Sleep |
| `/status` | GET | وضعیت فعلی سیستم |
| `/run` | POST | اجرای پایپ‌لاین معاملاتی |
| `/metrics` | GET | متریک‌های کامل |

---

## ✅ چک‌لیست نهایی

- [ ] فایل‌های `app.py`, `Procfile`, `requirements.txt` به GitHub پوش شدند
- [ ] در Railway دیپلوی مجدد انجام شد
- [ ] وضعیت به "Running" تغییر کرد
- [ ] `/health` پاسخ می‌دهد
- [ ] UptimeRobot تنظیم شد
- [ ] Environment Variables تنظیم هستند

---

## 🆘 اگر هنوز مشکل دارید

### لاگ‌های Railway را بفرستید:
```
Dashboard > Deployments > Click on latest deployment > View Logs
```

### یا این دستورات را اجرا کنید:
```bash
# تست محلی
python app.py

# سپس در ترمینال دیگر:
curl http://localhost:8000/health
```

---

## 📞 پشتیبانی

اگر بعد از انجام تمام مراحل هنوز مشکل دارید:
1. اسکرین‌شات از Railway Dashboard
2. لاگ‌های آخرین دیپلوی
3. خروجی `curl https://agent-production-99ce.up.railway.app/health`

را ارسال کنید تا بررسی شود.

---

**موفق باشید! 🚀**
