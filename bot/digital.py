"""محصولات دیجیتال (اکانت/اشتراک آماده) — منطق و متن‌های فروش.

این ماژول محصولات دیجیتال مثل «اشتراک Gemini» و «اشتراک ChatGPT» را مدیریت
می‌کند. برخلاف رزیدنتال/V2Ray که سرویس روی پنل ساخته می‌شود، این‌ها از یک
«انبار موجودی» (اکانت/کد آماده) تحویل داده می‌شوند.

- تعریف محصول (عنوان، متن فروش، قیمت، مدت، وضعیت) در جدول digital_products است
  و از ربات و پنل وب قابل ویرایش است.
- خرید از طریق همان مسیر پرداخت موجود (کریپتو/درگاه/کیف پول) انجام و پس از تأیید،
  یک قلم از انبار به‌صورت اتمیک به خریدار تحویل داده می‌شود.

قیمت‌ها بر حسب USD ذخیره می‌شوند (مثل رزیدنتال) و برای پرداخت با کیف پول به تومان
تبدیل می‌شوند.
"""
from __future__ import annotations

import re
from typing import Any

from .database import Database

# پیشوند شناسه‌ی محصول دیجیتال در meta پرداخت‌ها؛ مثل: "digital:gemini_18m"
DIGITAL_META_PREFIX = "digital:"


def is_digital_meta(product: str) -> bool:
    return bool(product) and product.startswith(DIGITAL_META_PREFIX)


def slug_from_meta(product: str) -> str:
    return product[len(DIGITAL_META_PREFIX):] if is_digital_meta(product) else ""


def meta_for_slug(slug: str) -> str:
    return f"{DIGITAL_META_PREFIX}{slug}"


_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,40}$")


def valid_slug(slug: str) -> bool:
    return bool(_SLUG_RE.match(slug or ""))


# ---------------------------------------------------------------------- #
#  متن‌های فروش پیش‌فرض (انسانی، حرفه‌ای، فارسی)
# ---------------------------------------------------------------------- #
# این متن‌ها فقط «مقدار اولیه» هستند و ادمین می‌تواند از ربات یا پنل وب کاملاً
# عوضشان کند. عمداً محاوره‌ای و صمیمی نوشته شده‌اند تا حس تبلیغِ ماشینی ندهند.

GEMINI_18M_TITLE = "اشتراک هوش مصنوعی Gemini — ۱۸ ماهه"
GEMINI_18M_SUBTITLE = "پلن کامل Google Gemini Advanced • یک سال و نیم دسترسی بی‌دغدغه"
GEMINI_18M_DESCRIPTION = (
    "🌟 <b>Gemini Advanced، این‌بار برای یک سال و نیم کامل</b>\n\n"
    "بیایید رک باشیم: خرید ماه‌به‌ماه اشتراک هوش مصنوعی هم خرج بیشتری دارد، هم "
    "دردسر تمدید هر ماه. این پلن ۱۸ ماهه دقیقاً برای همین است — یک‌بار می‌گیری و "
    "تا مدت‌ها اصلاً یادت می‌رود که اشتراک داری، فقط ازش کار می‌کشی.\n\n"
    "با Gemini پیشرفته چه کارهایی می‌شود کرد؟\n"
    "• جدیدترین مدل‌های گوگل برای نوشتن، کدنویسی و تحلیل، بدون صف و محدودیت خسته‌کننده\n"
    "• پنجره‌ی متنی خیلی بزرگ؛ می‌توانی کل یک گزارش یا چند فایل را یک‌جا بدهی و جمع‌بندی بگیری\n"
    "• کمک واقعی در Google Docs و Gmail و بقیه‌ی ابزارهای گوگل\n"
    "• ساخت و تحلیل تصویر، و پاسخ‌های به‌روز و دقیق‌تر\n\n"
    "چرا از ما؟\n"
    "• تحویل سریع و آنی بعد از پرداخت\n"
    "• راهنمایی کامل برای فعال‌سازی؛ اگر جایی گیر کردی، تنهایت نمی‌گذاریم\n"
    "• قیمت ۱۸ ماهه‌اش وقتی تقسیم بر ماه کنی، واقعاً می‌ارزد\n\n"
    "اگر کارت با هوش مصنوعی جدی است و نمی‌خواهی هر ماه فکر تمدید باشی، این همان "
    "گزینه‌ای است که دنبالش بودی. 🚀"
)

CHATGPT_1M_TITLE = "اشتراک ChatGPT Plus — یک‌ماهه"
CHATGPT_1M_SUBTITLE = "دسترسی کامل به ChatGPT Plus برای ۳۰ روز • فعال‌سازی فوری"
CHATGPT_1M_DESCRIPTION = (
    "⚡️ <b>ChatGPT Plus، یک ماه تمام و بی‌دردسر</b>\n\n"
    "همه شنیده‌ایم ChatGPT چه‌کارها می‌کند؛ ولی نسخه‌ی Plus یک دنیای دیگر است. "
    "این پلن یک‌ماهه برای کسی است که می‌خواهد بدون تعهد بلندمدت، حرفه‌ای‌ترین حالت "
    "ChatGPT را امتحان کند یا برای یک پروژه‌ی مشخص از آن استفاده کند.\n\n"
    "با ChatGPT Plus چه چیزی گیرت می‌آید؟\n"
    "• دسترسی به مدل‌های پیشرفته و سریع‌تر، حتی وقتی سرورها شلوغ‌اند\n"
    "• پاسخ‌های دقیق‌تر برای کدنویسی، ترجمه، نوشتن و ایده‌پردازی\n"
    "• کار با فایل و تصویر، تحلیل داده و امکانات پیشرفته‌ی دیگر\n"
    "• سرعت و پایداری بیشتر نسبت به نسخه‌ی رایگان\n\n"
    "چرا از ما بخری؟\n"
    "• فعال‌سازی فوری بعد از پرداخت؛ معطل نمی‌مانی\n"
    "• راهنمای قدم‌به‌قدم ورود و استفاده\n"
    "• پشتیبانی واقعی، نه ربات\n\n"
    "یک ماه وقت داری تا ببینی چطور کارهایت را سریع‌تر و تمیزتر جلو می‌برد. "
    "امتحانش ضرر ندارد. 😉"
)


# ساختار محصولات پیش‌فرض. قیمت‌ها به USD و «مقدار اولیه»‌اند؛ در ربات/پنل قابل تغییر.
DEFAULT_PRODUCTS: list[dict[str, Any]] = [
    {
        "slug": "gemini_18m",
        "title": GEMINI_18M_TITLE,
        "subtitle": GEMINI_18M_SUBTITLE,
        "description": GEMINI_18M_DESCRIPTION,
        "price": 45.0,
        "currency": "USD",
        "duration_days": 540,
        "delivery_type": "stock",
        "sort_order": 10,
    },
    {
        "slug": "chatgpt_1m",
        "title": CHATGPT_1M_TITLE,
        "subtitle": CHATGPT_1M_SUBTITLE,
        "description": CHATGPT_1M_DESCRIPTION,
        "price": 8.0,
        "currency": "USD",
        "duration_days": 30,
        "delivery_type": "stock",
        "sort_order": 20,
    },
]


def seed_default_products(db: Database) -> None:
    """محصولات دیجیتال پیش‌فرض را فقط اگر وجود نداشته باشند اضافه می‌کند (idempotent).

    هرگز محصول موجود را بازنویسی نمی‌کند تا تغییرات ادمین حفظ شود.
    """
    for p in DEFAULT_PRODUCTS:
        db.seed_digital_product(
            p["slug"],
            title=p["title"],
            subtitle=p["subtitle"],
            description=p["description"],
            price=p["price"],
            currency=p["currency"],
            duration_days=p["duration_days"],
            delivery_type=p["delivery_type"],
            active=True,
            sort_order=p["sort_order"],
        )
