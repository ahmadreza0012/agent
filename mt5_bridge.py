import time
import requests
import MetaTrader5 as mt5

# ==========================================
# تنظیمات حساب شما در لایت‌فایننس (LiteFinance)
# ==========================================
SERVER_URL = "https://ais-dev-mcyrxojl6ieifg2g7jwrq4-642489029202.europe-west2.run.app"
ACCOUNT_ID = 91447058  # شماره حساب شما در تصویر
PASSWORD = "YOUR_MT5_PASSWORD"  # رمز عبور متاتریدر شما (Master Password)
SERVER = "LiteFinance-MT5-Demo"  # سرور شما در لایت‌فایننس

def connect_mt5():
    # راه‌اندازی ارتباط با نرم‌افزار متاتریدر ۵ در ویندوز
    if not mt5.initialize():
        print("❌ خطا در اتصال اولیه به متاتریدر ۵. کد خطا =", mt5.last_error())
        print("💡 لطفاً نرم‌افزار MetaTrader 5 را در سیستم خود باز نگه دارید.")
        return False
    
    # لاگین خودکار به حساب LiteFinance
    authorized = mt5.login(ACCOUNT_ID, password=PASSWORD, server=SERVER)
    if authorized:
        account_info = mt5.account_info()
        print(f"✅ با موفقیت به حساب #{ACCOUNT_ID} متاتریدر متصل شد!")
        print(f"🏢 بروکر: {account_info.company} | سرور: {account_info.server}")
        print(f"💰 موجودی (Balance): ${account_info.balance:.2f} | ارزش کل (Equity): ${account_info.equity:.2f}")
        return True
    else:
        print(f"❌ اتصال به حساب #{ACCOUNT_ID} در سرور '{SERVER}' ناموفق بود.")
        print("🔍 علت احتمالی: رمز عبور اشتباه است یا نرم‌افزار متاتریدر لاگین نشده است. کد خطا:", mt5.last_error())
        return False

def sync_loop():
    print("\n🚀 پل ارتباطی هوش مصنوعی و متاتریدر ۵ فعال شد! در حال همگام‌سازی لحظه‌ای...")
    while True:
        try:
            # دریافت وضعیت زنده از متاتریدر ۵
            account_info = mt5.account_info()
            positions = mt5.positions_get()
            
            payload = {
                "account_number": str(ACCOUNT_ID),
                "server_name": SERVER,
                "balance": account_info.balance if account_info else 0.0,
                "equity": account_info.equity if account_info else 0.0,
                "margin": account_info.margin if account_info else 0.0,
                "free_margin": account_info.margin_free if account_info else 0.0,
                "leverage": f"1:{account_info.leverage}" if account_info else "1:100",
                "positions_count": len(positions) if positions else 0
            }
            
            # ارسال به داشبورد وب
            res = requests.post(f"{SERVER_URL}/api/v1/mt5/sync", json=payload, timeout=5)
            if res.status_code == 200:
                print(f"🔄 همگام‌سازی موفق | موجودی: ${payload['balance']:.2f} | پوزیشن‌های باز: {payload['positions_count']}")
            time.sleep(3)
        except Exception as e:
            print(f"⚠️ خطای موقت در اتصال به سرور: {e}")
            time.sleep(5)

if __name__ == "__main__":
    if connect_mt5():
        sync_loop()

