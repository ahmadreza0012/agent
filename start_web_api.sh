#!/bin/bash
# اسکریپت راه‌اندازی سرور پورت 5000 (پشتیبانی هوشمند از Node.js و Python/Flask)
# Guaranteed Port 5000 Launcher for Crypto Trading Bot Dashboard

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

echo "========================================="
echo "🚀 راه‌اندازی داشبورد روی پورت 5000..."
echo "========================================="

# 1. متوقف کردن پردازش‌های قبلی
echo "🛑 در حال بستن سرویس‌های قبلی روی پورت 5000 و 80..."
pkill -f "python.*web_api.py" 2>/dev/null || true
pkill -f "node.*server.js" 2>/dev/null || true
fuser -k 5000/tcp 2>/dev/null || true
sleep 1

# فعال‌سازی ریدایرکت پورت 80 به 5000 با iptables در صورت دسترسی sudo
if command -v sudo &> /dev/null && command -v iptables &> /dev/null; then
    sudo iptables -t nat -A PREROUTING -p tcp --dport 80 -j REDIRECT --to-port 5000 2>/dev/null || true
fi

STARTED=0

# 2. اولویت اول: اجرای سرور Node.js (server.js) برای تطابق ۱۰۰٪ با محیط پیش‌نمایش
if command -v node &> /dev/null && [ -f "server.js" ]; then
    echo "⚡ در حال راه‌اندازی سرور Node.js (server.js)..."
    PORT=5000 nohup node server.js > server.log 2>&1 &
    SERVER_PID=$!
    echo $SERVER_PID > .server.pid
    sleep 2

    if ps -p $SERVER_PID > /dev/null 2>&1; then
        echo "✅ سرور Node.js با PID $SERVER_PID با موفقیت اجرا شد"
        STARTED=1
    fi
fi

# 3. اولویت دوم: در صورت عدم وجود Node.js، اجرای پایتون (web_api.py)
if [ $STARTED -eq 0 ] && command -v python3 &> /dev/null && [ -f "web_api.py" ]; then
    echo "🐍 در حال راه‌اندازی سرور پایتون (web_api.py)..."
    PORT=5000 nohup python3 web_api.py > server.log 2>&1 &
    SERVER_PID=$!
    echo $SERVER_PID > .server.pid
    sleep 2

    if ps -p $SERVER_PID > /dev/null 2>&1; then
        echo "✅ سرور پایتون با PID $SERVER_PID با موفقیت اجرا شد"
        STARTED=1
    fi
fi

# 4. بررسی نهایی وضعیت پاسخ‌دهی پورت 5000
echo "🔍 در حال تست پاسخ‌دهی پورت 5000..."
if curl -s -I http://127.0.0.1:5000/ > /dev/null 2>&1; then
    SERVER_IP=$(curl -s --max-time 2 https://api.ipify.org 2>/dev/null || echo "52.23.157.88")
    echo "========================================="
    echo "🎉 سرور پورت 5000 با موفقیت آنلاین شد!"
    echo "========================================="
    echo "📍 آدرس دسترسی در مرورگر:"
    echo "   http://$SERVER_IP:5000"
    echo ""
    echo "📄 لاگ زنده سرور:"
    echo "   tail -f server.log"
    echo "========================================="
else
    echo "⚠️ اخطار: پورت 5000 به curl پاسخ نداد. بررسی لاگ:"
    cat server.log 2>/dev/null || true
fi
