# 🚀 راه‌اندازی سریع CI/CD برای Amazon EC2

## خلاصه ۵ دقیقه‌ای

### مرحله ۱: آماده‌سازی سرور (یکبار انجام می‌شود)

```bash
# اتصال به سرور
ssh -i agentkey.pem ec2-user@52.23.157.88

# اجرای اسکریپت آماده‌سازی
curl -O https://raw.githubusercontent.com/YOUR_USERNAME/YOUR_REPO/main/setup_ec2_server.sh
chmod +x setup_ec2_server.sh
./setup_ec2_server.sh

# افزودن remote git
git remote add origin <YOUR_GITHUB_REPO_URL>

# pull اولیه
git pull origin main
```

### مرحله ۲: تنظیم GitHub Secrets

به آدرس زیر بروید:
```
https://github.com/YOUR_USERNAME/YOUR_REPO/settings/secrets/actions
```

سه Secret اضافه کنید:

| نام | مقدار |
|-----|-------|
| `EC2_HOST` | `52.23.157.88` |
| `EC2_USER` | `ec2-user` |
| `SSH_PRIVATE_KEY` | محتوای فایل `agentkey.pem` |

### مرحله ۳: کامیت و پوش

```bash
git add .github/workflows/deploy.yml
git commit -m "Add CI/CD pipeline"
git push origin main
```

### مرحله ۴: بررسی

- به تب **Actions** در GitHub بروید
- workflow را مشاهده کنید
- پس از اتمام، کد شما روی سرور deploy شده است!

---

## 📁 فایل‌های ایجاد شده

```
.github/workflows/
├── deploy.yml              # Pipeline اصلی CI/CD
└── README_CI_CD.md         # راهنمای کامل

setup_ec2_server.sh         # اسکریپت آماده‌سازی سرور
QUICK_START_CI_CD.md        # این فایل
```

## 🔑 دریافت SSH Private Key

```bash
cat agentkey.pem
# کل خروجی را کپی کنید (از -----BEGIN تا -----END)
```

## 🎯 بعد از هر Push

به طور خودکار:
1. ✅ تست‌ها اجرا می‌شوند
2. ✅ کد به EC2 deploy می‌شود
3. ✅ dependencies نصب می‌شوند
4. ✅ فایل .env حفظ می‌شود

## ⚠️ نکات مهم

- فایل `.env` هرگز commit نمی‌شود
- فایل `agentkey.pem` در `.gitignore` هست
- برای اجرای برنامه از `tmux` استفاده کنید

## 📞 مشکل دارید؟

1. لاگ Actions را بررسی کنید
2. مستند کامل: `.github/workflows/README_CI_CD.md`
