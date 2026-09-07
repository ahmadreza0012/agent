# راهنمای جامع Web API ربات معاملاتی کریپتو

## 📋 فهرست مطالب

- [معرفی](#معرفی)
- [ویژگی‌ها](#ویژگیها)
- [نصب و راه‌اندازی](#نصب-و-راهاندازی)
- [دسترسی به پنل وب](#دسترسی-به-پنل-وب)
- [API Endpoints](#api-endpoints)
- [عیب‌یابی](#عیب‌یابی)
- [دستورات مفید](#دستورات-مفید)
- [امنیت](#امنیت)

---

## معرفی

Web API یک رابط کاربری وب زیبا و فارسی برای مانیتورینگ و کنترل ربات معاملاتی کریپتو است. این امکان را به شما می‌دهد که از طریق مرورگر، وضعیت ربات را مشاهده کرده و آن را کنترل کنید.

**آدرس دسترسی:** http://52.23.157.88:5000

---

## ویژگی‌ها

### 🎯 امکانات اصلی

- **نمایش وضعیت ربات**: آنلاین/آفلاین با نشانگر بصری
- **متریک‌های زنده**:
  - ⏱️ زمان اجرا (Uptime)
  - 🔄 تعداد سیکل‌های معاملاتی
  - 💰 موجودی کل
  - 📊 سود/زیان (PnL)
- **لاگ‌های زنده**: نمایش ۳۰ خط آخر از فایل‌های مختلف لاگ
- **کنترل ربات**:
  - 🔄 راه‌اندازی مجدد
  - ⏹️ توقف ربات
- **به‌روزرسانی خودکار**: هر ۱۰ ثانیه بدون نیاز به رفرش صفحه
- **طراحی Responsive**: سازگار با موبایل، تبلت و دسکتاپ
- **رابط فارسی**: کاملاً فارسی‌سازی شده با جهت راست‌چین

### 🔌 API Endpoints

| Endpoint | Method | توضیحات |
|----------|--------|---------|
| `/` | GET | صفحه اصلی پنل کاربری |
| `/api/status` | GET | دریافت وضعیت ربات و متریک‌ها |
| `/api/restart` | POST | راه‌اندازی مجدد ربات |
| `/api/stop` | POST | توقف ربات |

---

## نصب و راه‌اندازی

### روش ۱: اجرای خودکار با اسکریپت

```bash
cd /home/ec2-user/agent
chmod +x start_web_api.sh
./start_web_api.sh
```

### روش ۲: اجرای دستی

```bash
# 1. نصب پیش‌نیازها
pip3 install flask flask-cors

# 2. اجرای Web API
cd /home/ec2-user/agent
nohup python3 web_api.py > web_api.log 2>&1 &

# 3. بررسی وضعیت
ps aux | grep web_api
```

### روش ۳: از طریق GitHub Actions

با هر بار push به شاخه main/master، Web API به صورت خودکار راه‌اندازی می‌شود.

---

## دسترسی به پنل وب

### مراحل دسترسی:

1. **باز کردن پورت 5000 در AWS Security Group** (در پایین توضیح داده شده)

2. **مرورگر را باز کنید** و به آدرس زیر بروید:
   ```
   http://52.23.157.88:5000
   ```

3. **وضعیت ربات را مشاهده کنید**:
   - نشانگر سبز = ربات آنلاین است
   - نشانگر قرمز = ربات آفلاین است

4. **از دکمه‌های کنترل استفاده کنید**:
   - راه‌اندازی مجدد: ربات را ری‌استارت می‌کند
   - توقف ربات: ربات را متوقف می‌کند

---

## API Endpoints

### 1. دریافت وضعیت - `/api/status`

**درخواست:**
```bash
curl http://52.23.157.88:5000/api/status
```

**پاسخ:**
```json
{
  "success": true,
  "status": "online",
  "metrics": {
    "uptime": "2روز و 5ساعت و 30دقیقه",
    "cycles": 150,
    "balance": 10000.50,
    "pnl": 250.75
  },
  "logs": [
    {
      "source": "detailed_trading.log",
      "line": "2024-01-15 10:30:00 - Cycle 150 completed",
      "timestamp": "2024-01-15T10:30:00"
    }
  ],
  "timestamp": "2024-01-15T10:30:00"
}
```

### 2. راه‌اندازی مجدد - `/api/restart`

**درخواست:**
```bash
curl -X POST http://52.23.157.88:5000/api/restart
```

**پاسخ:**
```json
{
  "success": true,
  "message": "ربات با موفقیت راه‌اندازی مجدد شد"
}
```

### 3. توقف ربات - `/api/stop`

**درخواست:**
```bash
curl -X POST http://52.23.157.88:5000/api/stop
```

**پاسخ:**
```json
{
  "success": true,
  "message": "ربات با موفقیت متوقف شد"
}
```

---

## عیب‌یابی

### مشکل 1: Web API اجرا نمی‌شود

**علت احتمالی:**
- Flask نصب نیست
- پورت 5000 اشغال است
- خطا در کد

**راه‌حل:**
```bash
# بررسی لاگ
tail -f /home/ec2-user/agent/web_api.log

# نصب مجدد Flask
pip3 install --upgrade flask flask-cors

# بررسی پورت
netstat -tulpn | grep 5000

# اگر پورت اشغال بود، پروسس را متوقف کنید
pkill -f "python.*web_api.py"

# راه‌اندازی مجدد
cd /home/ec2-user/agent
python3 web_api.py
```

### مشکل 2: نمی‌توان به پنل وب دسترسی پیدا کرد (ERR_EMPTY_RESPONSE)

**علت اصلی:** پورت 5000 در AWS Security Group باز نیست

**راه‌حل گام به گام برای باز کردن پورت 5000:**

#### روش 1: از طریق AWS Console (توصیه می‌شود)

1. وارد AWS Console شوید: https://console.aws.amazon.com/ec2/
2. از منوی سمت چپ، روی **Security Groups** کلیک کنید
3. Security Group مرتبط با اینستنس EC2 خود را پیدا و انتخاب کنید
   - می‌توانید بر اساس نام، تگ، یا ID اینستنس جستجو کنید
4. به تب **Inbound rules** بروید
5. روی دکمه **Edit inbound rules** کلیک کنید
6. روی **Add rule** کلیک کرده و مقادیر زیر را وارد کنید:
   - **Type**: Custom TCP
   - **Protocol**: TCP
   - **Port Range**: 5000
   - **Source**: 
     - `0.0.0.0/0` برای دسترسی عمومی
     - یا `My IP` برای دسترسی فقط از IP فعلی شما
7. روی **Save rules** کلیک کنید

چند ثانیه صبر کنید و دوباره مرورگر را باز کنید: http://52.23.157.88:5000

#### روش 2: استفاده از AWS CLI

اگر AWS CLI نصب دارید:

```bash
# ابتدا Security Group ID را پیدا کنید
aws ec2 describe-instances --instance-ids i-xxxxxxxxx --query 'Reservations[0].Instances[0].SecurityGroups[0].GroupId'

# سپس پورت را باز کنید
aws ec2 authorize-security-group-ingress \\
    --group-id sg-xxxxxxxxx \\
    --protocol tcp \\
    --port 5000 \\
    --cidr 0.0.0.0/0
```

#### بررسی پس از اعمال تغییرات

```bash
# تست اتصال از سیستم خودتان
curl -v http://52.23.157.88:5000/api/status

# یا در مرورگر
http://52.23.157.88:5000
```

**سایر علل احتمالی:**
- فایروال سرور مسدود کرده
- Web API در حال اجرا نیست

```bash
# 1. بررسی اجرای Web API
ps aux | grep web_api

# 2. بررسی گوش دادن به پورت 5000
netstat -tulpn | grep 5000

# 3. بررسی فایروال داخلی
sudo iptables -L -n | grep 5000
```

### مشکل 3: لاگ‌ها نمایش داده نمی‌شوند

**علت احتمالی:**
- فایل‌های لاگ وجود ندارند
- مسیر فایل‌ها اشتباه است

**راه‌حل:**
```bash
# بررسی وجود فایل‌های لاگ
ls -la /home/ec2-user/agent/*.log
ls -la /home/ec2-user/agent/logs/

# ایجاد فایل لاگ اگر وجود ندارد
touch /home/ec2-user/agent/detailed_trading.log
```

### مشکل 4: وضعیت ربات همیشه آفلاین است

**علت احتمالی:**
- ربات اصلی در حال اجرا نیست
- تشخیص وضعیت کار نمی‌کند

**راه‌حل:**
```bash
# بررسی اجرای ربات
screen -ls
ps aux | grep "python.*main.py"

# راه‌اندازی ربات اگر متوقف است
screen -S bot -dm bash -c "cd /home/ec2-user/agent && python3 main.py"
```

---

## دستورات مفید

### مدیریت Web API

```bash
# شروع Web API
cd /home/ec2-user/agent
nohup python3 web_api.py > web_api.log 2>&1 &

# توقف Web API
pkill -f "python.*web_api.py"

# بررسی وضعیت
ps aux | grep web_api

# مشاهده لاگ زنده
tail -f /home/ec2-user/agent/web_api.log

# مشاهده ۱۰۰ خط آخر لاگ
tail -n 100 /home/ec2-user/agent/web_api.log
```

### مدیریت ربات اصلی

```bash
# اتصال به session ربات
screen -r bot

# جدا شدن از screen (بدون توقف)
# Ctrl+A سپس D

# توقف ربات
screen -S bot -X quit

# راه‌اندازی مجدد
screen -S bot -dm bash -c "cd /home/ec2-user/agent && python3 main.py"
```

### بررسی لاگ‌ها

```bash
# مشاهده آخرین لاگ‌ها
tail -f /home/ec2-user/agent/detailed_trading.log

# جستجو در لاگ‌ها
grep "error" /home/ec2-user/agent/*.log

# شمارش سیکل‌ها
grep -c "cycle" /home/ec2-user/agent/*.log
```

---

## امنیت

### 🔐 باز کردن پورت 5000 در AWS Security Group

برای دسترسی به Web API از بیرون، باید پورت 5000 را در AWS Security Group باز کنید:

#### روش 1: از طریق AWS Console

1. وارد **AWS Console** شوید
2. به **EC2 Dashboard** بروید
3. از منوی سمت چپ، **Security Groups** را انتخاب کنید
4. Security Group مرتبط با实例 EC2 خود را انتخاب کنید
5. به تب **Inbound rules** بروید
6. روی **Edit inbound rules** کلیک کنید
7. **Add rule** را بزنید
8. مقادیر زیر را وارد کنید:
   - **Type**: Custom TCP
   - **Port range**: 5000
   - **Source**: 
     - برای دسترسی از همه: `0.0.0.0/0`
     - برای دسترسی فقط از IP خودتان: `Your_IP/32`
9. **Save rules** را بزنید

#### روش 2: از طریق AWS CLI

```bash
# جایگزینی sg-xxxxxxxx با Security Group ID شما
aws ec2 authorize-security-group-ingress \
  --group-id sg-xxxxxxxx \
  --protocol tcp \
  --port 5000 \
  --cidr 0.0.0.0/0
```

#### روش 3: توصیه امنیتی (فقط IP خاص)

```bash
# فقط IP خودتان را مجاز کنید
aws ec2 authorize-security-group-ingress \
  --group-id sg-xxxxxxxx \
  --protocol tcp \
  --port 5000 \
  --cidr YOUR.IP.ADDRESS.HERE/32
```

### 🔒 نکات امنیتی مهم

1. **محدود کردن دسترسی**: بهتر است فقط IP خودتان را مجاز کنید
2. **استفاده از HTTPS**: برای تولید، از reverse proxy با SSL استفاده کنید
3. **احراز هویت**: برای محیط تولید، احراز هویت اضافه کنید
4. **مانیتورینگ لاگ‌ها**: لاگ‌ها را به طور منظم بررسی کنید

---

## ساختار فایل‌ها

```
/home/ec2-user/agent/
├── web_api.py              # فایل اصلی Web API
├── web_api.log             # لاگ‌های Web API
├── .web_api.pid            # PID فرآیند Web API
├── .bot_state              # وضعیت فعلی ربات
├── start_web_api.sh        # اسکریپت راه‌اندازی
├── detailed_trading.log    # لاگ معاملات
├── logs/
│   └── trading.log         # لاگ ربات
└── .screenlog.0            # لاگ screen session
```

---

## پشتیبانی

برای گزارش مشکلات یا پیشنهاد ویژگی‌های جدید، لطفاً از طریق GitHub Issues اقدام کنید.

---

## نسخه‌ها

- **نسخه فعلی**: 1.0.0
- **تاریخ انتشار**: 2024
- **Python**: 3.9+
- **Flask**: 3.0.0+

---

## مجوز

این پروژه تحت همان مجوز پروژه اصلی ربات معاملاتی منتشر شده است.
