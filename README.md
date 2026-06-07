# resibot

ربات تلگرام مدیریت فروش کانفیگ روی پنل **3x-ui** برای نماینده‌ها.
هر کانفیگ یک اینباند **VLESS xHTTP TLS** با پورت تصادفی می‌سازد و آن را از طریق
یک **اوتباند اختصاصی SmartProxy** (با روتینگ‌رول مخصوص همان کاربر) خارج می‌کند؛
بنابراین هر نماینده/مشتری IP و لوکیشن مستقل دارد و می‌تواند IP یا لوکیشن خود را
هر زمان تغییر دهد.

## نصب با یک دستور

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/W2F-Sa/resibot/main/install.sh)
```

نصب‌کننده مقادیر لازم (توکن ربات، آیدی ادمین، اطلاعات پنل، SmartProxy، قیمت و ...)
را به‌صورت تعاملی می‌پرسد، سرویس `systemd` می‌سازد و ربات را اجرا می‌کند.

## آپدیت بدون از دست رفتن دیتابیس

```bash
bash /opt/resibot/update.sh
```

دیتابیس در `data/` و تنظیمات در `.env` نگه داشته می‌شوند (در `.gitignore` هستند) و
قبل از هر آپدیت یک نسخه‌ی پشتیبان در `backups/` ساخته می‌شود. مهاجرت اسکیمای
دیتابیس به‌صورت additive و با `PRAGMA user_version` انجام می‌شود.

## امکانات

- دسترسی فقط برای **ادمین** و **نماینده‌های مجاز** (افزودن/حذف نماینده توسط ادمین)
- ثبت سفارش با انتخاب **کشور/استان/شهر** دلخواه (بدون نیاز به پرداخت؛ تسویه با ادمین)
- نمایش **قیمت** بر اساس `PRICE_PER_GB` و ارسال **گزارش سفارش به ادمین**
- حداقل حجم خرید قابل تنظیم (پیش‌فرض ۵ گیگ، بدون سقف) و مدت اعتبار ۳۰ روزه روی کلاینت
- **تغییر IP** (با عوض‌کردن `session`) و **تغییر لوکیشن** (area/state/city) بعد از خرید
- لینک **Subscription** + لینک مستقیم برای هر کانفیگ
- استفاده از گواهی پنل برای TLS («Set as panel») تا اتصال بدون خطای SSL باشد
- SNI و Host از `.env` (و قابل تغییر از داخل ربات)

## مدیریت سرویس

```bash
journalctl -u resibot -f        # لاگ زنده
systemctl restart resibot       # ری‌استارت
systemctl status resibot        # وضعیت
```

## اجرای محلی (توسعه)

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # مقادیر را پر کنید
python -m bot
```

## ساختار

```
bot/
  config.py     بارگذاری env و اعتبارسنجی
  database.py   SQLite + مهاجرت additive
  panel.py      کلاینت API پنل 3x-ui
  proxy.py      ساخت username اسمارت‌پروکسی + لوکیشن
  xray_config.py اوتباند + روتینگ‌رول هر کاربر
  inbound.py    payload اینباند VLESS xhttp tls + لینک ساب
  service.py    منطق اصلی (provision / change ip / change location / delete)
  handlers/     هندلرهای تلگرام (common/admin/order/configs)
  main.py       نقطه‌ی ورود
install.sh      نصب تعاملی یک‌دستوری
update.sh       آپدیت با حفظ دیتابیس
```
