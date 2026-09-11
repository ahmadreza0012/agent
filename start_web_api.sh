#!/bin/bash
# اسکریپت راه‌اندازی تک داشبورد معاملاتی روی پورت 5000
# Crypto Trading Bot Unified Dashboard Startup Script (Port 5000)

set -e

echo "========================================="
echo "🚀 راه‌اندازی داشبورد یکپارچه معاملاتی روی پورت 5000"
echo "========================================="

# تعیین مسیر پروژه
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# 1. نصب پیش‌نیازهای Node.js (در صورت نیاز)
echo "📦 بررسی وابستگی‌های داشبورد..."
if [ ! -d "node_modules" ]; then
    if command -v npm &> /dev/null; then
        npm install --omit=dev || npm install || true
    fi
fi

# 2. توقف پردازش‌های قبلی پورت 5000
echo "🛑 در حال بررسی و توقف سرویس‌های قبلی..."
pkill -f "python.*web_api.py" || true
pkill -f "node.*server.js" || true
sleep 1

# 3. اجرای تک داشبورد کامل روی پورت 5000 در پس‌زمینه
echo "🚀 در حال راه‌اندازی داشبورد یکپارچه روی پورت 5000..."
PORT=5000 nohup node server.js > server.log 2>&1 &
SERVER_PID=$!
echo $SERVER_PID > .server.pid

# انتظار برای اجرای موفق
sleep 2

# بررسی وضعیت اجرا
if ps -p $SERVER_PID > /dev/null 2>&1; then
    SERVER_IP=$(curl -s --max-time 2 https://api.ipify.org || echo "52.23.157.88")
    echo "========================================="
    echo "✅ داشبورد یکپارچه با موفقیت روی پورت 5000 راه‌اندازی شد!"
    echo "========================================="
    echo ""
    echo "📊 اطلاعات:"
    echo "   PID: $SERVER_PID"
    echo "   آدرس داشبورد: http://$SERVER_IP:5000"
    echo "   فایل لاگ: $PROJECT_DIR/server.log"
    echo ""
    echo "📝 دستورات مفید:"
    echo "   مشاهده لاگ: tail -f server.log"
    echo "   توقف داشبورد: pkill -f 'node.*server.js'"
    echo "   بررسی وضعیت: ps aux | grep server.js"
    echo ""
else
    echo "❌ خطا: داشبورد اجرا نشد!"
    echo "📝 لاگ خطا:"
    cat server.log 2>/dev/null || true
    exit 1
fi

echo "========================================="
echo "✨ دسترسی به پنل وب:"
echo "   مرورگر خود را باز کنید و به آدرس زیر بروید:"
echo "   http://$SERVER_IP:5000"
echo "========================================="
