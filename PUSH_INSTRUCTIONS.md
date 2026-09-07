# راهنمای پوش کردن تغییرات به GitHub

## وضعیت فعلی
تمامی فایل‌های Web API با موفقیت ایجاد و commit شده‌اند. تغییرات در برنچ `main` قرار دارند.

## فایل‌های اضافه شده:
- ✅ web_api.py (702 خطوط)
- ✅ requirements.txt (به‌روزرسانی شده)
- ✅ start_web_api.sh
- ✅ README_WEB_API.md
- ✅ check_security_group.py
- ✅ .github/workflows/deploy.yml (به‌روزرسانی شده)
- ✅ .gitignore (به‌روزرسانی شده)

## روش‌های پوش کردن:

### روش 1: استفاده از GitHub Personal Access Token (توصیه می‌شود)

1. ساخت توکن:
   - به https://github.com/settings/tokens بروید
   - روی "Generate new token (classic)" کلیک کنید
   - دسترسی‌های لازم: `repo` (تمام گزینه‌ها را انتخاب کنید)
   - توکن تولید شده را کپی کنید (مثلاً: `ghp_xxxxxxxxxxxxxxxxxxxx`)

2. اجرای دستورات:
```bash
cd /workspace
git remote set-url origin https://ahmadreza0012:YOUR_TOKEN_HERE@github.com/ahmadreza0012/agent.git
git push -u origin main
```

جای `YOUR_TOKEN_HERE` توکن خود را قرار دهید.

### روش 2: استفاده از SSH Key

1. اگر کلید SSH ندارید، بسازید:
```bash
ssh-keygen -t ed25519 -C "your_email@example.com"
cat ~/.ssh/id_ed25519.pub
```

2. کلید عمومی را به GitHub اضافه کنید:
   - به https://github.com/settings/keys بروید
   - روی "New SSH key" کلیک کنید
   - خروجی دستور `cat` بالا را پیست کنید

3. اجرای دستورات:
```bash
cd /workspace
git remote set-url origin git@github.com:ahmadreza0012/agent.git
git push -u origin main
```

### روش 3: استفاده از Git Credential Helper

```bash
cd /workspace
git config --global credential.helper store
git remote set-url origin https://github.com/ahmadreza0012/agent.git
git push -u origin main
```
سپس وقتی از شما نام کاربری و رمز خواسته شد:
- Username: `ahmadreza0012`
- Password: GitHub Personal Access Token خود را وارد کنید (نه رمز عبور معمولی)

## بررسی پس از پوش:
بعد از پوش موفقیت‌آمیز، می‌توانید تغییرات را در GitHub مشاهده کنید:
https://github.com/ahmadreza0012/agent/commits/main

## نکات مهم:
- هرگز رمز عبور اصلی GitHub خود را استفاده نکنید
- همیشه از Personal Access Token استفاده کنید
- توکن‌ها را در جایی امن ذخیره کنید
- برای امنیت بیشتر، برای توکن تاریخ انقضا تنظیم کنید
