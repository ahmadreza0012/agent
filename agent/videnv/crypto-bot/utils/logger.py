"""
سیستم لاگ‌گیری برای ربات معاملاتی

این ماژول یک سیستم لاگ‌گیری ساختاریافته با قابلیت‌های زیر فراهم می‌کند:
- لاگ همزمان به کنسول و فایل
- چرخش خودکار فایل‌های لاگ (RotatingFileHandler)
- فرمت‌بندی یکپارچه در تمام ماژول‌ها
- سطوح مختلف لاگ (DEBUG, INFO, WARNING, ERROR)
"""

import logging
import os
from logging.handlers import RotatingFileHandler
from typing import Optional


def setup_logger(
    name: str,
    level: str = "INFO",
    log_directory: str = "logs",
    max_file_size_mb: int = 10,
    backup_count: int = 5,
    console_enabled: bool = True,
    file_enabled: bool = True,
    log_format: Optional[str] = None,
) -> logging.Logger:
    """
    تنظیم و پیکربندی یک logger با نام مشخص.
    
    Args:
        name: نام logger (معمولاً __name__ ماژول)
        level: سطح لاگ (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_directory: پوشه ذخیره فایل‌های لاگ
        max_file_size_mb: حداکثر حجم هر فایل لاگ بر حسب مگابایت
        backup_count: تعداد فایل‌های لاگ قدیمی که نگهداری می‌شوند
        console_enabled: آیا لاگ‌ها به کنسول هم چاپ شوند
        file_enabled: آیا لاگ‌ها در فایل ذخیره شوند
        log_format: فرمت سفارشی برای لاگ (اختیاری)
    
    Returns:
        یک instance از logging.Logger پیکربندی شده
    
    مثال استفاده:
        logger = setup_logger(__name__)
        logger.info("پیام اطلاعاتی")
        logger.error("خطا رخ داد", exc_info=True)
    """
    
    # تبدیل سطح لاگ از رشته به مقدار عددی
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    
    # ایجاد logger
    logger = logging.getLogger(name)
    logger.setLevel(numeric_level)
    
    # جلوگیری از اضافه کردن handlerهای تکراری
    if logger.handlers:
        return logger
    
    # فرمت پیش‌فرض لاگ
    if log_format is None:
        log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    formatter = logging.Formatter(log_format, datefmt="%Y-%m-%d %H:%M:%S")
    
    # Handler برای کنسول
    if console_enabled:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(numeric_level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    # Handler برای فایل با چرخش خودکار
    if file_enabled:
        # اطمینان از وجود پوشه لاگ
        os.makedirs(log_directory, exist_ok=True)
        
        log_filepath = os.path.join(log_directory, f"{name}.log")
        
        # RotatingFileHandler: وقتی فایل به حجم مشخص رسید، فایل جدید می‌سازد
        file_handler = RotatingFileHandler(
            log_filepath,
            maxBytes=max_file_size_mb * 1024 * 1024,  # تبدیل به بایت
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


# ایجاد یک logger پیش‌فرض برای استفاده عمومی
default_logger = setup_logger("crypto_bot")


def get_logger(name: str) -> logging.Logger:
    """
    دریافت یک logger با نام مشخص، با استفاده از تنظیمات پیش‌فرض.
    
    این تابع برای استفاده راحت در ماژول‌های مختلف طراحی شده است.
    
    مثال:
        # در هر ماژول:
        from utils.logger import get_logger
        logger = get_logger(__name__)
    """
    return setup_logger(name)


# نمونه استفاده
if __name__ == "__main__":
    # تست سیستم لاگ
    test_logger = get_logger("test_module")
    
    test_logger.debug("این یک پیام دیباگ است")
    test_logger.info("این یک پیام اطلاعاتی است")
    test_logger.warning("این یک هشدار است")
    test_logger.error("این یک خطا است")
    
    try:
        # تست لاگ با exception
        result = 10 / 0
    except ZeroDivisionError:
        test_logger.error("تقسیم بر صفر رخ داد", exc_info=True)
    
    print(f"\nلاگ‌ها در پوشه 'logs' ذخیره شده‌اند.")
    print(f"فایل لاگ: logs/{test_logger.name}.log")