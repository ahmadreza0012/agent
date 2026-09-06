#!/bin/bash
# اسکریپت راه‌اندازی Web API ربات معاملاتی
# Crypto Trading Bot Web API Startup Script

set -e

echo "========================================="
echo "🚀 راه‌اندازی Web API ربات معاملاتی"
echo "========================================="

# مسیر پروژه
PROJECT_DIR="/home/ec2-user/agent"
cd "$PROJECT_DIR"

# 1. نصب پیش‌نیازها
echo "📦 در حال نصب پیش‌نیازهای Python..."
if command -v pip3 &> /dev/null; then
    pip3 install flask flask-cors --quiet
    echo "✅ Flask و Flask-CORS نصب شدند"
else
    echo "❌ pip3 یافت نشد. لطفاً ابتدا pip3 را نصب کنید."
    exit 1
fi

# 2. توقف API قبلی (اگر در حال اجراست)
echo "🛑 در حال بررسی و توقف Web API قبلی..."
pkill -f "python.*web_api.py" || true
echo "✅ API قبلی متوقف شد (اگر وجود داشت)"

# 3. اجرای Web API جدید در پس‌زمینه
echo "🚀 در حال راه‌اندازی Web API جدید..."
nohup python3 web_api.py > web_api.log 2>&1 &
WEB_API_PID=$!

# ذخیره PID
echo $WEB_API_PID > .web_api.pid

# انتظار برای اطمینان از اجرای موفق
sleep 3

# بررسی وضعیت اجرا
if ps -p $WEB_API_PID > /dev/null 2>&1; then
    echo "========================================="
    echo "✅ Web API با موفقیت راه‌اندازی شد!"
    echo "========================================="
    echo ""
    echo "📊 اطلاعات:"
    echo "   PID: $WEB_API_PID"
    echo "   آدرس: http://52.23.157.88:5000"
    echo "   لاگ: $PROJECT_DIR/web_api.log"
    echo ""
    echo "📝 دستورات مفید:"
    echo "   مشاهده لاگ: tail -f web_api.log"
    echo "   توقف API: pkill -f 'python.*web_api.py'"
    echo "   بررسی وضعیت: ps aux | grep web_api"
    echo ""
else
    echo "❌ خطا: Web API اجرا نشد!"
    echo "📝 لاگ خطا:"
    cat web_api.log
    exit 1
fi

echo "========================================="
echo "✨ برای دسترسی به پنل وب:"
echo "   1. مطمئن شوید پورت 5000 در AWS Security Group باز است"
echo "   2. مرورگر را باز کنید و به آدرس زیر بروید:"
echo "      http://52.23.157.88:5000"
echo "========================================="
