#!/bin/bash
# 🚀 اسکریپت تست محلی وب‌سرور قبل از دیپلوی
# این اسکریپت را اجرا کنید تا مطمئن شوید app.py درست کار می‌کند

echo "🔍 در حال تست app.py..."
echo ""

# تست ۱: ایمپورت
echo "✅ تست ۱: بررسی ایمپورت"
python -c "from app import app; print('   app.py با موفقیت ایمپورت شد')" || exit 1
echo ""

# تست ۲: بررسی endpointها
echo "✅ تست ۲: بررسی endpointهای ثبت شده"
python -c "
from app import app
rules = [str(rule) for rule in app.url_map.iter_rules()]
expected = ['/', '/health', '/status', '/run', '/wake', '/metrics']
for exp in expected:
    if exp in rules:
        print(f'   ✅ {exp} ثبت شده است')
    else:
        print(f'   ❌ {exp} یافت نشد!')
        exit(1)
" || exit 1
echo ""

# تست ۳: اجرای سرور برای ۵ ثانیه
echo "✅ تست ۳: اجرای موقت سرور (۵ ثانیه)"
timeout 5 python -c "
import threading
import time
from app import app

def run_server():
    app.run(host='0.0.0.0', port=8765, debug=False, threaded=True)

server_thread = threading.Thread(target=run_server, daemon=True)
server_thread.start()
time.sleep(3)

import requests
try:
    resp = requests.get('http://localhost:8765/health', timeout=2)
    if resp.status_code == 200:
        print('   ✅ Health check پاسخ داد')
        print(f'   Response: {resp.json()}')
    else:
        print(f'   ❌ Health check کد {resp.status_code} داد')
        exit(1)
except Exception as e:
    print(f'   ❌ خطا در health check: {e}')
    exit(1)
" || exit 1
echo ""

# تست ۴: بررسی فایل‌های ضروری
echo "✅ تست ۴: بررسی فایل‌های ضروری"
for file in app.py Procfile requirements.txt; do
    if [ -f "$file" ]; then
        echo "   ✅ $file موجود است"
    else
        echo "   ❌ $file یافت نشد!"
        exit 1
    fi
done
echo ""

# تست ۵: بررسی محتوای Procfile
echo "✅ تست ۵: بررسی محتوای Procfile"
if grep -q "gunicorn app:app" Procfile; then
    echo "   ✅ Procfile صحیح است"
else
    echo "   ❌ Procfile نادرست است!"
    exit 1
fi
echo ""

# تست ۶: بررسی requirements.txt
echo "✅ تست ۶: بررسی کتابخانه‌های ضروری"
for pkg in flask gunicorn requests; do
    if grep -qi "$pkg" requirements.txt; then
        echo "   ✅ $pkg در requirements.txt هست"
    else
        echo "   ❌ $pkg در requirements.txt نیست!"
        exit 1
    fi
done
echo ""

echo "🎉 همه تست‌ها با موفقیت گذشتند!"
echo ""
echo "📝 حالا می‌توانید دیپلوی کنید:"
echo "   git add app.py Procfile requirements.txt"
echo "   git commit -m 'Fix Railway 502: Add Flask web server'"
echo "   git push origin main"
echo ""
echo "سپس در Railway Redeploy کنید."
