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
from html import escape as _esc
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
#  روش‌های تحویل محصول دیجیتال
# ---------------------------------------------------------------------- #
# سه روش تحویل که ادمین می‌تواند برای هر محصول انتخاب کند:
#   link    → یک «لینک فعال‌سازی» از انبار تحویل داده می‌شود؛ مشتری بازش می‌کند و
#             روی دکمه‌ی فعال‌سازی/عضویت می‌زند (مثل عضویت در فمیلی Gemini).
#   account → یک «اکانت آماده» از انبار تحویل می‌شود (ایمیل/پسورد/۲FA).
#   manual  → پس از پرداخت، ایمیل و پسورد از خود مشتری گرفته می‌شود؛ ادمین کار را
#             انجام می‌دهد و به مشتری خبر می‌دهد (بدون نیاز به انبار).
DELIVERY_LINK = "link"
DELIVERY_ACCOUNT = "account"
DELIVERY_MANUAL = "manual"

DELIVERY_TYPES = (DELIVERY_LINK, DELIVERY_ACCOUNT, DELIVERY_MANUAL)

DELIVERY_LABELS = {
    DELIVERY_LINK: "🔗 لینک فعال‌سازی",
    DELIVERY_ACCOUNT: "🔐 اکانت آماده",
    DELIVERY_MANUAL: "🙋 دریافت اطلاعات از مشتری",
}

# راهنمای کوتاه هر روش برای پنل ادمین
DELIVERY_HINTS = {
    DELIVERY_LINK: "هر خط انبار یک لینک دعوت/فعال‌سازی است. مشتری بازش می‌کند و فعال می‌شود.",
    DELIVERY_ACCOUNT: "هر خط انبار یک اکانت است. قالب پیشنهادی: «ایمیل | پسورد | کد ۲FA».",
    DELIVERY_MANUAL: "انبار لازم نیست. پس از پرداخت، ایمیل و پسورد از مشتری گرفته می‌شود.",
}


def normalize_delivery(dt: str) -> str:
    """روش تحویل را نرمال می‌کند. مقدار قدیمی «stock» را به «account» نگاشت می‌دهد."""
    dt = (dt or "").strip().lower()
    if dt in DELIVERY_TYPES:
        return dt
    # سازگاری با نسخه‌ی قبل که فقط «stock» داشت
    return DELIVERY_ACCOUNT


def uses_stock(dt: str) -> bool:
    """آیا این روش تحویل از انبار موجودی استفاده می‌کند؟ (فقط manual نه)"""
    return normalize_delivery(dt) != DELIVERY_MANUAL


def format_account_payload(payload: str) -> str:
    """اکانت آماده را برای نمایش به مشتری قالب‌بندی می‌کند.

    اگر با «|» جدا شده باشد (ایمیل | پسورد | ۲FA) به‌صورت برچسب‌دار نمایش می‌دهد؛
    وگرنه همان متن خام را برمی‌گرداند.
    """
    parts = [p.strip() for p in payload.split("|")]
    if len(parts) >= 2:
        labels = ["📧 ایمیل", "🔑 پسورد", "🔐 کد ۲FA", "ℹ️ توضیح"]
        lines = []
        for i, val in enumerate(parts):
            if not val:
                continue
            label = labels[i] if i < len(labels) else "•"
            lines.append(f"{label}: <code>{_esc(val)}</code>")
        return "\n".join(lines)
    return f"<code>{_esc(payload)}</code>"


# ---------------------------------------------------------------------- #
#  متن‌های فروش پیش‌فرض (انسانی، حرفه‌ای، فارسی)
# ---------------------------------------------------------------------- #
# این متن‌ها فقط «مقدار اولیه» هستند و ادمین می‌تواند از ربات یا پنل وب کاملاً
# عوضشان کند. عمداً محاوره‌ای و صمیمی نوشته شده‌اند تا حس تبلیغِ ماشینی ندهند.

GEMINI_18M_TITLE = "🤖 جمینای ۱۸ ماهه (Gemini Advanced)"
GEMINI_18M_SUBTITLE = "🎁 یک سال و نیم دسترسی کامل، روی اکانت خودت"
GEMINI_18M_DESCRIPTION = (
    "✨ <b>جمینای پیشرفته، اون هم برای یک سال و نیم تمام!</b> ✨\n\n"
    "بذار رک بگم 😅 خرید ماه‌به‌ماهِ هوش مصنوعی هم پول بیشتری آب می‌خوره، هم هر "
    "ماه باید فکر تمدیدش باشی. این پلن ۱۸ ماهه دقیقاً واسه همینه: یه بار می‌گیری "
    "و خیالت تا مدت‌ها راحته، فقط می‌شینی ازش کار می‌کشی. 💪\n\n"
    "🔥 <b>با جمینای پیشرفته چی گیرت میاد؟</b>\n"
    "• 🧠 جدیدترین مدل‌های گوگل برای نوشتن، کدزدن و تحلیل، بدون صف و محدودیت\n"
    "• 📚 حافظه‌ی متنی خیلی بزرگ؛ کل یه گزارش یا چند فایل رو یه‌جا بده، جمع‌بندی بگیر\n"
    "• 📩 کمک واقعی توی Google Docs و Gmail و بقیه‌ی ابزارهای گوگل\n"
    "• 🖼 ساخت و تحلیل عکس، جواب‌های به‌روز و خیلی دقیق‌تر\n\n"
    "💎 <b>چرا از ما؟</b>\n"
    "• ⚡️ تحویل آنی بعد از پرداخت\n"
    "• 🤝 راهنمایی کامل واسه فعال‌سازی؛ هرجا گیر کردی، تنهات نمی‌ذاریم\n"
    "• 💰 وقتی قیمت ۱۸ ماهه رو تقسیم بر ماه کنی، تازه می‌فهمی چقدر می‌ارزه\n\n"
    "🎯 <b>فعال‌سازی خیلی راحته:</b> یه لینک دعوت بهت می‌دیم، بازش می‌کنی و روی "
    "«پیوستن» می‌زنی؛ تمام! اشتراک روی همون اکانت گوگل خودت فعال می‌شه.\n\n"
    "اگه کارت با هوش مصنوعی جدیه و حوصله‌ی تمدید هر ماه رو نداری، همینه که دنبالش بودی. 🚀"
)

CHATGPT_1M_TITLE = "⚡️ چت‌جی‌پی‌تی پلاس ۱ ماهه (ChatGPT Plus)"
CHATGPT_1M_SUBTITLE = "🚀 اکانت آماده با ایمیل و رمز، تحویل فوری"
CHATGPT_1M_DESCRIPTION = (
    "🌟 <b>چت‌جی‌پی‌تی پلاس، یک ماه کامل و بدون دردسر!</b> 🌟\n\n"
    "همه می‌دونیم ChatGPT چه‌کارایی می‌کنه، ولی نسخه‌ی پلاس (Plus) یه دنیای دیگه‌ست 🤯 "
    "این پلن یک‌ماهه واسه کسیه که می‌خواد بدون تعهد بلندمدت، حرفه‌ای‌ترین حالتِ "
    "ChatGPT رو تجربه کنه یا واسه یه پروژه‌ی مشخص ازش استفاده کنه.\n\n"
    "🔥 <b>با نسخه‌ی پلاس چی گیرت میاد؟</b>\n"
    "• 🧠 دسترسی به مدل‌های پیشرفته و سریع‌تر، حتی وقتی سرورها شلوغن\n"
    "• ✍️ جواب‌های دقیق‌تر واسه کدنویسی، ترجمه، نوشتن و ایده‌پردازی\n"
    "• 📎 کار با فایل و عکس، تحلیل داده و کلی امکانات پیشرفته‌ی دیگه\n"
    "• ⚡️ سرعت و پایداری خیلی بیشتر از نسخه‌ی رایگان\n\n"
    "💎 <b>چرا از ما بخری؟</b>\n"
    "• 🚀 تحویل فوری بعد از پرداخت؛ معطل نمی‌مونی\n"
    "• 🔐 اکانت آماده با ایمیل، رمز و کد ورود دو مرحله‌ای (۲FA) کامل بهت داده می‌شه\n"
    "• 🤝 پشتیبانی واقعی، نه جواب رباتی\n\n"
    "یه ماه وقت داری ببینی چطور کارهات رو سریع‌تر و تمیزتر جلو می‌بره. امتحانش ضرر نداره 😉"
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
        "delivery_type": DELIVERY_LINK,
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
        "delivery_type": DELIVERY_ACCOUNT,
        "sort_order": 20,
    },
]


def seed_default_products(db: Database) -> None:
    """محصولات دیجیتال پیش‌فرض را فقط اگر وجود نداشته باشند اضافه می‌کند (idempotent).

    هرگز عنوان/متن/قیمت محصول موجود را بازنویسی نمی‌کند تا تغییرات ادمین حفظ شود.
    فقط اگر روش تحویل هنوز مقدار قدیمیِ «stock» باشد (یعنی ادمین آن را تنظیم نکرده)،
    آن را به روش تحویل پیش‌فرضِ درست ارتقا می‌دهد.
    """
    for p in DEFAULT_PRODUCTS:
        existing = db.get_digital_product_by_slug(p["slug"])
        if existing is None:
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
        elif (existing["delivery_type"] or "").strip().lower() == "stock":
            # ارتقای نصب‌های قدیمی که هنوز روش تحویل مشخصی نداشتند
            db.update_digital_product(int(existing["id"]), delivery_type=p["delivery_type"])
