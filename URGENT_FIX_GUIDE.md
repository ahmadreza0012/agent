# 🚨 راهنمای فوری رفع خطای 502 Railway

## 🔴 مشکل فعلی
سایت https://agent-production-99ce.up.railway.app بالا نمی‌آید چون:
1. کدهای جدید (app.py) هنوز به GitHub پوش نشده‌اند
2. Railway نسخه قدیمی را اجرا می‌کند که وب‌سرور ندارد

## ✅ راه حل سریع (۵ دقیقه)

### مرحله ۱: پوش دستی به GitHub

در ترمینال محلی خود اجرا کنید:

```bash
# کلون کردن مخزن
git clone https://github.com/ahmadreza0012/agent.git
cd agent

# کپی کردن فایل‌های جدید از workspace
# (فایل‌های app.py, Procfile, requirements.txt را از جایی که هستید کپی کنید)

# اضافه کردن به git
git add app.py Procfile requirements.txt

# کامیت و پوش
git commit -m "Fix Railway 502: Add Flask web server"
git push origin main
```

### مرحله ۲: تنظیم Railway

1. وارد https://railway.app شوید
2. پروژه `agent` را انتخاب کنید
3. به تب **Deployments** بروید
4. روی **Redeploy** کلیک کنید
5. صبر کنید تا وضعیت به **Running** تغییر کند

### مرحله ۳: بررسی لاگ‌ها

در Railway Dashboard:
1. به تب **Logs** بروید
2. باید این لاگ‌ها را ببینید:
   ```
   Starting Crypto Portfolio Optimization Web Server
   Host: 0.0.0.0
   Port: <PORT>
   Running in production mode with gunicorn...
   ```

### مرحله ۴: تست سلامت

```bash
curl https://agent-production-99ce.up.railway.app/health
```

باید پاسخ دهد:
```json
{"status": "healthy", "timestamp": "..."}
```

---

## 🔧 عیب‌یابی

### اگر هنوز خطای 502 دارید:

#### ۱. بررسی Procfile
مطمئن شوید فایل `Procfile` در ریشه مخزن باشد با محتوای:
```
web: gunicorn app:app
```

#### ۲. بررسی requirements.txt
باید شامل باشد:
```txt
flask>=2.3
gunicorn>=21.0
requests>=2.31
```

#### ۳. بررسی Environment Variables
در Railway > Settings > Variables:
```
PORT = 8000 (یا خالی بگذارید، Railway خودکار تنظیم می‌کند)
SLEEP_MODE = false
DEBUG = false
```

#### ۴. بررسی Python Version
در Railway > Settings > Build:
```
Python Version: 3.12
```

---

## 📊 چک‌لیست نهایی

- [ ] فایل `app.py` در ریشه مخزن باشد
- [ ] فایل `Procfile` در ریشه مخزن باشد  
- [ ] فایل `requirements.txt` آپدیت شده باشد
- [ ] به GitHub پوش شده باشد
- [ ] در Railway Redeploy انجام شده باشد
- [ ] لاگ‌ها نشان دهند "Starting Crypto Portfolio Optimization Web Server"
- [ ] endpoint `/health` پاسخ 200 بدهد

---

## 💡 نکته مهم

اگر از GitHub CLI استفاده می‌کنید:

```bash
gh auth login
git add app.py Procfile requirements.txt
git commit -m "Fix Railway 502"
git push origin main
```

---

## 🆘 اگر هنوز مشکل دارید

لاگ‌های Railway را چک کنید:
1. Railway Dashboard > Logs
2. دنبال خطاهای زیر بگردید:
   - `No module named 'flask'` → requirements.txt آپدیت نیست
   - `Error: No such file or directory: 'Procfile'` → Procfile نیست
   - `ModuleNotFoundError: No module named 'app'` → app.py نیست
   - `Address already in use` → PORT تکراری است

---

## ✨ بعد از رفع مشکل

برای UptimeRobot تنظیم کنید:
- URL: `https://agent-production-99ce.up.railway.app/health`
- Interval: 5 minutes
- Timeout: 30 seconds

برای Sleep Mode (اختیاری):
```bash
# در Railway Variables:
SLEEP_MODE=true

# Cron job هر ۶ ساعت:
0 */6 * * * curl -X POST https://agent-production-99ce.up.railway.app/wake
```

---

**موفق باشید! 🚀**
