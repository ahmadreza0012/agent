
# 🔧 راهنمای رفع مشکل محدودیت بایننس (Error 451)

## ❌ مشکل:
ربات شما با خطای `451 - Service unavailable from a restricted location` مواجه است.
این یعنی IP سرور EC2 شما (آمریکا) توسط بایننس محدود شده است.

## ✅ راه‌حل‌ها:

### روش 1: تغییر به صرافی جایگزین (توصیه می‌شود)

#### گزینه A: استفاده از Bybit
1. در فایل `config.py` یا `.env`:
   ```python
   EXCHANGE = 'bybit'
   BYBIT_API_KEY = 'your_key'
   BYBIT_SECRET_KEY = 'your_secret'
   ```

2. نصب کتابخانه:
   ```bash
   pip install pybit
   ```

#### گزینه B: استفاده از KuCoin
```python
EXCHANGE = 'kucoin'
KUCOIN_API_KEY = 'your_key'
KUCOIN_SECRET_KEY = 'your_secret'
KUCOIN_PASSPHRASE = 'your_passphrase'
```

### روش 2: استفاده از پروکسی روی سرور EC2

1. اتصال به سرور:
   ```bash
   ssh -i agentkey.pem ec2-user@52.23.157.88
   ```

2. نصب و تنظیم پروکسی (مثلاً Tor):
   ```bash
   sudo yum install tor -y
   sudo systemctl start tor
   sudo systemctl enable tor
   ```

3. تنظیم پروکسی در ربات:
   ```python
   # در فایل config.py
   PROXY_URL = 'http://127.0.0.1:9050'
   ```

4. یا استفاده از proxy در سطح سیستم:
   ```bash
   export HTTP_PROXY="http://127.0.0.1:9050"
   export HTTPS_PROXY="http://127.0.0.1:9050"
   ```

### روش 3: تغییر منطقه سرور EC2

1. ساخت AMI از اینستنس فعلی
2. کپی AMI به منطقه دیگر (اروپا یا آسیا)
3. راه‌اندازی اینستنس جدید در منطقه مناسب

مناطق پیشنهادی:
- اروپا: `eu-west-1` (ایرلند), `eu-central-1` (فرانکفورت)
- آسیا: `ap-southeast-1` (سنگاپور), `ap-northeast-1` (توکیو)

### روش 4: استفاده از Binance.US (اگر واجد شرایط هستید)

```python
# در کانفیگ ربات
BINANCE_ENDPOINT = 'https://api.binance.us'
```

## 🎯 بهترین راه‌حل برای شما:

**استفاده از صرافی Bybit یا KuCoin** - سریع‌ترین و پایدارترین راه‌حل

## 📝 مراحل اجرا:

1. ثبت‌نام در Bybit یا KuCoin
2. دریافت API Key
3. به‌روزرسانی فایل config.py
4. ری‌استارت ربات:
   ```bash
   screen -S bot -X quit
   cd /home/ec2-user/agent
   screen -dmS bot python3 main.py
   ```

## 🔍 تست پس از اعمال تغییرات:

```bash
curl http://52.23.157.88:5000/api/status
```

باید خطاهای بایننس برطرف شده باشد.
