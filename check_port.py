#!/usr/bin/env python3
"""
اسکریپت بررسی وضعیت پورت 5000 و اتصال به بایننس
"""
import socket
import requests
import sys

def check_port(ip, port, timeout=5):
    """بررسی باز بودن پورت"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    result = sock.connect_ex((ip, port))
    sock.close()
    return result == 0

def check_binance_access():
    """بررسی دسترسی به بایننس"""
    try:
        response = requests.get("https://api.binance.com/api/v3/exchangeInfo", timeout=10)
        if response.status_code == 200:
            return True, "دسترسی_OK"
        elif response.status_code == 451:
            return False, "محدودیت_جغرافیایی_451"
        else:
            return False, f"خطای_{response.status_code}"
    except Exception as e:
        return False, str(e)

if __name__ == "__main__":
    ip = "52.23.157.88"
    
    print("=" * 60)
    print("بررسی وضعیت سرور EC2")
    print("=" * 60)
    
    # بررسی پورت 5000
    print(f"\n📡 بررسی پورت 5000 روی {ip}...")
    if check_port(ip, 5000):
        print("✅ پورت 5000 باز است!")
        
        # تست API
        try:
            response = requests.get(f"http://{ip}:5000/api/status", timeout=10)
            if response.status_code == 200:
                print("✅ Web API در دسترس است!")
                print(f"   وضعیت: {response.json().get('status', 'unknown')}")
            else:
                print(f"❌ Web API پاسخ نداد: {response.status_code}")
        except Exception as e:
            print(f"❌ خطا در اتصال به Web API: {e}")
    else:
        print("❌ پورت 5000 بسته است!")
        print("\n🔧 راه‌حل:")
        print("   1. وارد AWS Console شوید")
        print("   2. به Security Group اینستنس بروید")
        print("   3. Inbound Rule جدید اضافه کنید:")
        print("      - Type: Custom TCP")
        print("      - Port: 5000")
        print("      - Source: 0.0.0.0/0 یا My IP")
    
    # بررسی دسترسی به بایننس
    print(f"\n🌐 بررسی دسترسی به بایننس از لوکال...")
    can_access, status = check_binance_access()
    if can_access:
        print("✅ دسترسی به بایننس OK است")
    else:
        print(f"❌ دسترسی به بایننس مشکل دارد: {status}")
        print("\n🔧 راه‌حل‌های ممکن:")
        print("   1. استفاده از صرافی جایگزین (Bybit, KuCoin)")
        print("   2. استفاده از پروکسی/VPN روی سرور")
        print("   3. تغییر منطقه سرور به اروپا یا آسیا")
    
    print("\n" + "=" * 60)
