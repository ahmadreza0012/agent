#!/bin/bash
# اسکریپت ساده برای پوش کردن تغییرات به گیت‌هاب

echo "🚀 در حال پوش کردن تغییرات به گیت‌هاب..."

git add app.py Procfile requirements.txt
git commit -m "Fix Railway 502: Add Flask web server with smart Gunicorn switching" || echo "No changes to commit"
git push origin main

echo ""
echo "✅ اگر پیام بالا موفقیت‌آمیز بود، به Railway بروید:"
echo "   https://railway.app/project/agent"
echo ""
echo "🔄 Railway به صورت خودکار دیپلوی مجدد انجام می‌دهد."
echo "⏱️ حدود ۲-۳ دقیقه صبر کنید تا اپلیکیشن بالا بیاید."
echo ""
echo "🧪 سپس تست کنید:"
echo "   curl https://agent-production-99ce.up.railway.app/health"
