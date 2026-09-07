# راهنمای راه‌اندازی CI/CD برای استقرار خودکار روی Amazon EC2

## 📋 مراحل راه‌اندازی

### 1. آماده‌سازی سرور EC2

ابتدا باید پروژه را یکبار به صورت دستی روی سرور کپی کنید:

```bash
# اتصال به سرور
ssh -i agentkey.pem ec2-user@52.23.157.88

# ایجاد پوشه پروژه
mkdir -p ~/trading-agent
cd ~/trading-agent

# کپی فایل‌ها از سیستم محلی (در ترمینال جدید)
# scp -i agentkey.pem -r * ec2-user@52.23.157.88:~/trading-agent/

# مقداردهی اولیه git روی سرور
git init
git remote add origin <YOUR_GITHUB_REPO_URL>

# نصب پیش‌نیازها
sudo yum update -y
sudo yum install -y python3 python3-pip git tmux

# ایجاد محیط مجازی
python3 -m venv venv
source venv/bin/activate

# نصب dependencies
pip install -r requirements.txt

# کپی فایل .env
cp .env.example .env
nano .env  # وارد کردن API Keyها
```

### 2. تنظیم GitHub Secrets

به ریپازیتوری GitHub خود بروید و Secrets زیر را اضافه کنید:

**Settings → Secrets and variables → Actions → New repository secret**

| نام Secret | مقدار | توضیحات |
|-----------|-------|---------|
| `EC2_HOST` | `52.23.157.88` | آدرس IP سرور EC2 |
| `EC2_USER` | `ec2-user` یا `ubuntu` | نام کاربری سرور (بسته به AMI) |
| `SSH_PRIVATE_KEY` | محتوای فایل `agentkey.pem` | کلید خصوصی SSH |

#### روش دریافت محتوای کلید SSH:

```bash
# نمایش محتوای کلید
cat agentkey.pem

# کپی کامل محتوا (شامل -----BEGIN OPENSSH PRIVATE KEY----- و -----END...)
```

### 3. کامیت و پوش کردن فایل‌های CI/CD

```bash
# افزودن فایل‌های جدید
git add .github/workflows/deploy.yml
git add .github/workflows/README_CI_CD.md

# کامیت
git commit -m "Add CI/CD pipeline for EC2 deployment"

# پوش به گیت‌هاب
git push origin main
```

### 4. بررسی وضعیت Deployment

پس از push کردن:

1. به تب **Actions** در GitHub بروید
2. workflow **Deploy to Amazon EC2** را انتخاب کنید
3. وضعیت اجرای خودکار را مشاهده کنید

## 🔧 نحوه کار Pipeline

### مرحله Test:
- ✅ Checkout کد
- ✅ نصب Python 3.11
- ✅ نصب dependencies
- ✅ اجرای تست‌ها
- ✅ اعتبارسنجی ساختار پروژه

### مرحله Deploy:
- ✅ اتصال به EC2 با SSH
- ✅ Pull کردن آخرین تغییرات
- ✅ Backup از فایل .env
- ✅ نصب dependencies جدید
- ✅ بازیابی فایل .env
- ✅ تأیید موفقیت‌آمیز بودن deployment

## 🚀 Deployment دستی

می‌توانید به صورت دستی هم deployment را اجرا کنید:

1. به تب **Actions** بروید
2. workflow **Deploy to Amazon EC2** را انتخاب کنید
3. دکمه **Run workflow** را بزنید
4. Branch مورد نظر را انتخاب کنید
5. **Run workflow** را کلیک کنید

## 📝 نکات مهم

### امنیت:
- ⚠️ هرگز فایل `.env` را commit نکنید
- ⚠️ فایل `agentkey.pem` در `.gitignore` قرار دارد
- ⚠️ SSH Private Key فقط در GitHub Secrets ذخیره شود
- ⚠️ Security Group EC2 باید فقط به GitHub Actions IP اجازه دهد (اختیاری)

### اگر Deployment شکست خورد:

1. **بررسی لاگ‌ها**: به تب Actions → آخرین run → لاگ‌ها را بررسی کنید
2. **اتصال دستی**: 
   ```bash
   ssh -i agentkey.pem ec2-user@52.23.157.88
   cd ~/trading-agent
   git status
   git pull
   ```
3. **بررسی سرویس**:
   ```bash
   tmux attach -s trading-agent
   # یا
   ps aux | grep python
   ```

### به‌روزرسانی Dependencies:

اگر `requirements.txt` تغییر کند، به طور خودکار در deployment بعدی نصب می‌شود.

### مدیریت Process:

برای اجرای دائمی برنامه از `tmux` استفاده کنید:

```bash
# ایجاد session جدید
tmux new -s trading-agent

# اجرای برنامه
source venv/bin/activate
python main.py

# Detach کردن (Ctrl+B, D)

# Attach مجدد
tmux attach -s trading-agent
```

## 🎯 Workflow‌های اضافی (اختیاری)

می‌توانید workflow‌های دیگری هم اضافه کنید:

- **Auto-restart**: راه‌اندازی مجدد خودکار برنامه پس از deployment
- **Health check**: بررسی سلامت سرویس پس از deployment
- **Rollback**: بازگشت به نسخه قبلی در صورت شکست
- **Notification**: ارسال نوتیفیکیشن به Telegram/Discord/Email

---

## 📞 پشتیبانی

در صورت بروز مشکل:
1. لاگ‌های GitHub Actions را بررسی کنید
2. لاگ‌های سرور EC2 را بررسی کنید
3. به صورت دستی به سرور متصل شوید و وضعیت را بررسی کنید
