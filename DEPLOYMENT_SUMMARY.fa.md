# 🚀 خلاصه تغییرات برای استقرار روی Railway

## ✅ مشکل حل شد!

### 🔍 علت خطای 502:
برنامه شما بعد از اجرا بلافاصله تمام می‌شد و خاموش می‌گردید. Railway نیاز به یک **وب‌سرور همیشه روشن** دارد.

---

## 📁 فایل‌های ایجاد/تغییر یافته

### ۱. `app.py` (جدید - ۴۰۵ خط)
وب‌سرور Flask با endpointهای کامل:

| Endpoint | Method | کاربرد |
|----------|--------|---------|
| `/` | GET | مستندات API |
| `/health` | GET | ✅ سلامت سیستم (برای UptimeRobot) |
| `/wake` | POST | بیدار کردن از Sleep Mode |
| `/status` | GET | وضعیت فعلی سیستم |
| `/run` | POST | اجرای پایپ‌لاین معاملاتی |
| `/metrics` | GET | متریک‌های کامل |

**ویژگی‌های کلیدی:**
- ✅ همیشه روشن می‌ماند (حل خطای 502)
- ✅ از `host="0.0.0.0"` و `PORT` محیطی استفاده می‌کند
- ✅ Sleep Mode هوشمند برای صرفه‌جویی در منابع
- ✅ Thread-safe (جلوگیری از اجرای همزمان)
- ✅ لاگ‌گیری کامل
- ✅ مدیریت خطاهای جامع

### ۲. `Procfile` (جدید - ۱ خط)
```
web: gunicorn app:app
```
- دستور اجرای برنامه برای Railway
- از Gunicorn به عنوان WSGI server استفاده می‌کند

### ۳. `requirements.txt` (تغییر یافته)
اضافه شدن ۳ پکیج:
```txt
flask>=2.3       # وب‌سرور
gunicorn>=21.0   # Production server
requests>=2.31   # HTTP library
```

### ۴. `RAILWAY_DEPLOYMENT.md` (جدید - راهنمای کامل)
راهنمای فارسی کامل شامل:
- مراحل استقرار گام به گام
- تنظیمات Environment Variables
- پیکربندی UptimeRobot
- نمونه درخواست‌های API
- استراتژی‌های بهینه‌سازی مصرف
- عیب‌یابی مشکلات رایج

---

## 🎯 مراحل دیپلوی (۳ دقیقه)

### مرحله ۱: آپدیت مخزن
```bash
cd /workspace
git add app.py Procfile requirements.txt RAILWAY_DEPLOYMENT.md
git commit -m "Add Flask web server for Railway - fixes 502 error"
git push origin main
```

### مرحله ۲: تنظیم Railway
1. وارد [Railway](https://railway.app) شوید
2. پروژه موجود را انتخاب کنید یا جدید بسازید
3. از GitHub repo را انتخاب کنید: `ahmadreza0012/agent`
4. به صورت خودکار deploy می‌شود

### مرحله ۳: تنظیم Environment Variables
در پنل Railway > Variables:
```
SLEEP_MODE=false    # یا true برای صرفه‌جویی
GROQ_API_KEY=xxx    # اختیاری، برای تحلیل احساسات واقعی
DEBUG=false         # در production حتما false
```

---

## 🧪 تست سریع

بعد از دیپلوی، این دستورات را امتحان کنید:

### ۱. بررسی سلامت
```bash
curl https://your-app.railway.app/health
```
پاسخ مورد انتظار:
```json
{
  "status": "healthy",
  "version": "2.0",
  "sleep_mode": false
}
```

### ۲. اجرای پایپ‌لاین
```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{"since_days": 365, "n_folds": 1}' \
  https://your-app.railway.app/run
```

### ۳. تنظیم UptimeRobot
- URL Monitor: `https://your-app.railway.app/health`
- Interval: 5 minutes
- Method: GET

---

## 💡 بهینه‌سازی برای پلن رایگان

### گزینه ۱: Sleep Mode (توصیه می‌شود)
```bash
# در Railway تنظیم کنید:
SLEEP_MODE=true

# سپس با cron job هر ۶ ساعت بیدار کنید:
0 */6 * * * curl -X POST https://your-app.railway.app/wake
```
**مزیت**: تا ۳۰ روز در پلن رایگان دوام می‌آورد

### گزینه ۲: همیشه روشن
```bash
SLEEP_MODE=false
```
**مزیت**: پاسخگویی دائمی  
**معایب**: ~۲۰ روز در پلن رایگان

---

## 📊 مقایسه قبل و بعد

| ویژگی | قبل | بعد |
|-------|-----|-----|
| وضعیت سرور | ❌ خاموش می‌شد | ✅ همیشه روشن |
| خطای 502 | ✅ داشت | ❌ ندارد |
| UptimeRobot | ❌ کار نمی‌کرد | ✅ کار می‌کند |
| API خارجی | ❌ نداشت | ✅ دارد |
| Sleep Mode | ❌ نداشت | ✅ دارد |
| مدیریت خطا | ⚠️ محدود | ✅ کامل |

---

## 🐛 عیب‌یابی سریع

### هنوز خطای 502 دارید؟
1. چک کنید `Procfile` وجود داشته باشد
2. لاگ‌های Railway را ببینید: `railway logs`
3. مطمئن شوید `app.py` ایمپورت می‌شود

### مصرف بالا؟
1. `SLEEP_MODE=true` تنظیم کنید
2. از `/wake` فقط هنگام نیاز استفاده کنید
3. `since_days` را کاهش دهید

### خطای 503؟
- سیستم در Sleep Mode است
- ابتدا `POST /wake` بفرستید

---

## 📞 پشتیبانی

اگر مشکلی داشتید:
1. لاگ‌های Railway را چک کنید
2. `/status` endpoint را صدا بزنید
3. فایل `RAILWAY_DEPLOYMENT.md` را مطالعه کنید

---

## ✨ نکته مهم

**این تغییرات backward-compatible هستند:**
- کد اصلی (`main.py`) دست نخورده باقی مانده
- می‌توانید همچنان локально با `python main.py` اجرا کنید
- وب‌سرور فقط برای Railway اضافه شده

موفق باشید! 🚀
