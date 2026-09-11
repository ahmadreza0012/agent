#!/bin/bash
# Permanent Production Setup Script for Crypto Trading Bot (PM2 + Auto-restart)
set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

echo "=================================================="
echo "🚀 راه‌اندازی دائمی و خودکار سرور تولید (Production PM2 Setup)"
echo "=================================================="

# 1. ساخت پوشه لاگ‌ها
mkdir -p logs data

# 2. نصب پکیج‌ها در صورت نیاز
if [ ! -d "node_modules" ]; then
    echo "📦 در حال نصب وابستگی‌های Node.js..."
    npm install
fi

# 3. بررسی و نصب PM2 (مدیریت پردازش دائم)
if ! command -v pm2 &> /dev/null; then
    echo "⚙️ در حال نصب PM2 برای مدیریت دائمی سرویس..."
    sudo npm install -g pm2 || npm install -g pm2
fi

# 4. متوقف کردن نمونه‌های قبلی پایتون یا نود
echo "🛑 پاکسازی سرویس‌های قبلی..."
pkill -f "python.*web_api.py" 2>/dev/null || true
pkill -f "node.*server.js" 2>/dev/null || true
pm2 delete crypto-trading-bot 2>/dev/null || true

# 5. راه‌اندازی ربات با PM2 روی پورت 5000
echo "🚀 در حال اجرای ربات معاملاتی روی PM2 (پورت 5000)..."
PORT=5000 pm2 start ecosystem.config.cjs

# 6. ذخیره وضعیت PM2 برای بازگشت خودکار بعد از ریبوت سرور
pm2 save
sudo pm2 startup systemd -u $(whoami) --hp $HOME 2>/dev/null || true

# 7. تنظیم ریدایرکت پورت 80 به 5000
if command -v sudo &> /dev/null && command -v iptables &> /dev/null; then
    sudo iptables -t nat -A PREROUTING -p tcp --dport 80 -j REDIRECT --to-port 5000 2>/dev/null || true
    echo "🔗 ریدایرکت پورت 80 به 5000 فعال شد."
fi

echo "=================================================="
echo "🎉 سرور تولید با موفقیت و به‌صورت 24/7 راه‌اندازی شد!"
echo "   - از این پس تمامی معاملات و محاسبات مستقیماً روی همین سرور انجام می‌شود."
echo "   - آدرس پنل: http://52.23.157.88"
echo "   - دستور مشاهده وضعیت: pm2 status"
echo "   - دستور مشاهده لاگ زنده: pm2 logs crypto-trading-bot"
echo "=================================================="
