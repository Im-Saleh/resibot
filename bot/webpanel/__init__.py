"""پنل وب مدیریتی امن ResiBot (aiohttp).

این بسته یک پنل وب سبک، خودکفا و «ضدنفوذ» ارائه می‌دهد که در کنار ربات اجرا
می‌شود و امکان مدیریت محصولات دیجیتال، مشاهده‌ی آمار و لاگ حسابرسی را می‌دهد.

اجزا:
  - security.py  : هش پسورد (PBKDF2)، سشن امضاشده (HMAC)، CSRF، محدودسازی لاگین
  - templates.py : صفحات HTML با ظاهر شیشه‌ای (glassmorphism)، بدون وابستگی بیرونی
  - app.py       : اپلیکیشن aiohttp، مسیرها و میدلورهای امنیتی
"""
from .app import WebPanelManager, start_web_panel, make_web_app  # noqa: F401
