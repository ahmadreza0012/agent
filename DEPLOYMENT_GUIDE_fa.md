# راهنمای استقرار پروژه روی سرور آمازون EC2

## اطلاعات سرور
- **آدرس IP:** `52.23.157.88`
- **فایل کلید:** `agentkey.pem` (در پوشه اصلی پروژه)

## پیش‌نیازها

### 1. تنظیم دسترسی فایل کلید
```bash
chmod 600 agentkey.pem
```

### 2. اتصال به سرور
بسته به نوع سیستم عامل سرور، از یکی از کاربران زیر استفاده کنید:

```bash
# برای Amazon Linux
ssh -i agentkey.pem ec2-user@52.23.157.88

# برای Ubuntu
ssh -i agentkey.pem ubuntu@52.23.157.88

# برای سایر توزیع‌ها
ssh -i agentkey.pem admin@52.23.157.88
```

## مراحل استقرار دستی

### مرحله 1: بروزرسانی سیستم
```bash
# Amazon Linux
sudo yum update -y
sudo yum install -y python3 python3-pip git tmux htop

# Ubuntu/Debian
sudo apt-get update -y
sudo apt-get install -y python3 python3-pip git tmux htop
```

### مرحله 2: ایجاد پوشه پروژه
```bash
mkdir -p ~/trading-agent
cd ~/trading-agent
```

### مرحله 3: کپی کردن فایل‌های پروژه
از سیستم محلی خود:
```bash
# از پوشه پروژه
scp -i agentkey.pem -r * ec2-user@52.23.157.88:~/trading-agent/
```

یا کلون کردن از Git:
```bash
git clone <URL_ریپوزیتوری_شما> .
```

### مرحله 4: ایجاد محیط مجازی Python
```bash
python3 -m venv venv
source venv/bin/activate
```

### مرحله 5: نصب وابستگی‌ها
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### مرحله 6: تنظیم متغیرهای محیطی
```bash
cp .env.example .env
nano .env  # ویرایش و وارد کردن API Keyها و تنظیمات
```

### مرحله 7: اجرای برنامه
با استفاده از tmux (برای اجرای دائمی):
```bash
tmux new -s trading-agent
source venv/bin/activate
python main.py
```

برای جدایی از tmux: `Ctrl+B` سپس `D`
برای بازگشت به tmux: `tmux attach -t trading-agent`

## استفاده از اسکریپت خودکار

یک اسکریپت استقرار در پروژه وجود دارد:
```bash
./deploy_to_ec2.sh
```

این اسکریپت:
1. کاربر صحیح SSH را تشخیص می‌دهد
2. یک اسکریپت استقرار روی سرور ایجاد می‌کند
3. دستورالعمل‌های بعدی را نمایش می‌دهد

## بررسی وضعیت سرور

### بررسی اینکه سرور در دسترس است:
```bash
ping -c 4 52.23.157.88
```

### بررسی پورت‌های باز:
```bash
nmap -p 22,80,443 52.23.157.88
```

## عیب‌یابی

### مشکل در اتصال SSH:
1. مطمئن شوید فایل کلید دسترسی صحیح دارد: `chmod 600 agentkey.pem`
2. بررسی کنید Security Group اجازه پورت 22 را می‌دهد
3. مطمئن شوید Instance در حالت running است

### مشکل در اجرای برنامه:
```bash
# بررسی لاگ‌ها
tail -f nohup.out

# بررسی مصرف منابع
htop

# بررسی وضعیت Python
which python
python --version
```

## امنیت

- هرگز فایل `agentkey.pem` را commit نکنید
- پس از استقرار، دسترسی SSH را محدود کنید
- از Security Group برای محدود کردن IPها استفاده کنید
-定期 کلیدها را rotate کنید

## دستورات مفید

```bash
# مشاهده فرآیندهای در حال اجرا
ps aux | grep python

# ریستارت کردن برنامه در tmux
tmux kill-session -t trading-agent
tmux new -d -s trading-agent "cd ~/trading-agent && source venv/bin/activate && python main.py"

# مشاهده لاگ‌های سیستم
sudo journalctl -u your-service -f

# آپدیت پروژه
cd ~/trading-agent
git pull
source venv/bin/activate
pip install -r requirements.txt
tmux kill-session -t trading-agent
tmux new -d -s trading-agent "cd ~/trading-agent && source venv/bin/activate && python main.py"
```
