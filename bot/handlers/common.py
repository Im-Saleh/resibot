"""هندلرهای عمومی: /start، /id، منوی اصلی (شیشه‌ای) و منوی محصولات."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

from ..config import Settings
from ..database import (
    PRODUCT_RESIDENTIAL,
    PRODUCT_RESIDENTIAL2,
    PRODUCT_V2RAY,
    ROLE_RESIDENTIAL_RESELLER,
    ROLE_V2RAY_RESELLER,
)
from ..keyboards import main_menu, products_menu
from ..service import S_SHOW_PARTNERSHIP, Service

router = Router(name="common")


def _is_reseller(role: str) -> bool:
    return role in (ROLE_RESIDENTIAL_RESELLER, ROLE_V2RAY_RESELLER)


def _intro_text(cfg: Settings, role: str, is_admin: bool) -> str:
    title = f"<b>{cfg.brand_name}</b> — {cfg.brand_full}"
    if is_admin:
        return f"👋 سلام ادمین گرامی!\nبه پنل مدیریت {title} خوش آمدید."
    if _is_reseller(role):
        return f"👋 سلام همکار گرامی!\nبه {title} خوش آمدید."
    return (
        f"👋 به {title} خوش آمدید!\n\n"
        "از منوی زیر می‌توانید سرویس بخرید، سرویس‌هایتان را مدیریت کنید، "
        "کیف پولتان را شارژ کنید یا درخواست همکاری بدهید."
    )


def _menu_kb(service: Service, role: str, is_admin: bool):
    return main_menu(
        is_admin=is_admin,
        is_reseller=_is_reseller(role),
        show_partnership=service.feature_enabled(S_SHOW_PARTNERSHIP),
    )


@router.message(CommandStart())
async def cmd_start(
    message: Message, state: FSMContext, cfg: Settings, service: Service, role: str, is_admin: bool
) -> None:
    await state.clear()
    # کیبورد قدیمی پایین صفحه (reply) را حذف می‌کنیم تا فقط دکمه‌های شیشه‌ای بماند.
    try:
        await message.answer("⌛️", reply_markup=ReplyKeyboardRemove())
    except Exception:  # noqa: BLE001
        pass
    await message.answer(
        _intro_text(cfg, role, is_admin),
        reply_markup=_menu_kb(service, role, is_admin),
    )


@router.callback_query(F.data == "menu:home")
async def menu_home(
    call: CallbackQuery, state: FSMContext, cfg: Settings, service: Service, role: str, is_admin: bool
) -> None:
    await state.clear()
    await call.answer()
    await call.message.answer(
        _intro_text(cfg, role, is_admin),
        reply_markup=_menu_kb(service, role, is_admin),
    )


@router.message(Command("id"))
async def cmd_id(message: Message) -> None:
    await message.answer(f"🆔 آیدی عددی شما: <code>{message.from_user.id}</code>")


# ---------------------------------------------------------------------- #
#  منوی محصولات
# ---------------------------------------------------------------------- #
async def _send_products(target: Message, state: FSMContext, service: Service) -> None:
    await state.clear()
    res = service.product_enabled(PRODUCT_RESIDENTIAL)
    res2 = service.product_enabled(PRODUCT_RESIDENTIAL2)
    v2 = service.product_enabled(PRODUCT_V2RAY)
    if not (res or res2 or v2):
        await target.answer("در حال حاضر هیچ محصولی برای فروش فعال نیست.")
        return
    await target.answer(
        "🛍 <b>محصولات</b>\nیکی از سرویس‌های زیر را انتخاب کنید:",
        reply_markup=products_menu(residential=res, residential2=res2, v2ray=v2),
    )


@router.callback_query(F.data == "menu:buy")
async def menu_buy(call: CallbackQuery, state: FSMContext, service: Service) -> None:
    await call.answer()
    await _send_products(call.message, state, service)


@router.message(F.text == "🛒 خرید سرویس")
async def show_products(message: Message, state: FSMContext, service: Service) -> None:
    await _send_products(message, state, service)


GUIDE_TEXT = (
    "📖 <b>راهنمای خرید و استفاده</b>\n"
    "سلام رفیق 👋 نگران نباش، خیلی ساده‌تر از چیزیه که فکر می‌کنی. بریم قدم‌به‌قدم:\n\n"

    "🛒 <b>۱) چطور بخرم؟</b>\n"
    "روی «🛒 خرید سرویس» بزن و سرویس دلخواهت رو انتخاب کن:\n"
    "• <b>رزیدنتال</b> و <b>رزیدنتال ۲</b>: پروکسی با آی‌پی خونگی واقعی؛ کشور/شهر رو خودت انتخاب می‌کنی و هر وقت خواستی آی‌پی رو عوض می‌کنی. بر اساس حجم (گیگ) حساب می‌شه.\n"
    "• <b>V2Ray</b>: یه پلن یک‌ماهه‌ی <b>نامحدود</b> (بدون محدودیت حجم). ساده و بی‌دردسر.\n\n"

    "💳 <b>۲) پرداخت چطوریه؟</b>\n"
    "بعد از انتخاب، روش پرداخت رو می‌بینی:\n"
    "• <b>پرداخت مستقیم تتر (USDT شبکه BEP20)</b>: یه مبلغ دقیق و یه آدرس بهت نشون داده می‌شه. "
    "دقیقاً همون مبلغ رو به همون آدرس بفرست. تأیید معمولاً <b>خودکار</b> انجام می‌شه؛ "
    "اگه خواستی سریع‌تر بشه، دکمه‌ی «🧾 ارسال هش تراکنش» رو بزن و کد رهگیری (TxID) یا لینک BscScan تراکنشت رو بفرست. تمام! ✅\n"
    "• <b>درگاه</b>: روی دکمه‌ی پرداخت می‌زنی و طبق مراحل درگاه پیش می‌ری.\n"
    "⚠️ فقط <b>تتر واقعی روی شبکه‌ی BEP20</b> بفرست؛ شبکه یا توکن اشتباه قابل‌برگشت نیست.\n\n"

    "📦 <b>۳) سرویسم رو تحویل گرفتم، حالا چی؟</b>\n"
    "بعد از پرداخت، این‌ها رو بهت می‌دیم:\n"
    "• <b>لینک ساب (Subscription)</b> — بهترین گزینه\n"
    "• <b>QRکد</b> برای اسکن سریع\n"
    "• <b>لینک مستقیم کانفیگ</b>\n"
    "کافیه لینک ساب یا کانفیگ رو توی یه برنامه‌ی کلاینت اضافه کنی:\n"
    "• 📱 اندروید: <b>v2rayNG</b> یا <b>NekoBox</b>\n"
    "• 🍏 آیفون: <b>Streisand</b> یا <b>Shadowrocket</b>\n"
    "• 💻 ویندوز: <b>v2rayN</b> | مک: <b>V2Box</b>\n"
    "توی برنامه دنبال گزینه‌ی «Import from clipboard/URL» یا «افزودن از لینک ساب» بگرد، لینک رو پیست کن و وصل شو 🚀\n\n"

    "🔄 <b>۴) مدیریت سرویس</b>\n"
    "از «🧾 سرویس‌های من» روی هر سرویس بزن تا:\n"
    "• آی‌پی رو عوض کنی، کشور/شهر یا زمان تعویض خودکار آی‌پی رو تنظیم کنی (رزیدنتال)\n"
    "• مصرف و تاریخ انقضا رو ببینی\n"
    "• سرویس رو <b>تمدید</b> کنی\n\n"

    "💼 <b>۵) کیف پول</b>\n"
    "می‌تونی کیف پولت رو شارژ کنی و بعضی سرویس‌ها رو ازش پرداخت کنی.\n\n"

    "❓ <b>مشکلی بود؟</b>\n"
    "اگه یه جا گیر کردی یا سؤالی داشتی، به پشتیبانی پیام بده — کمکت می‌کنیم. موفق باشی! 🌟"
)


@router.callback_query(F.data == "menu:guide")
async def menu_guide(call: CallbackQuery) -> None:
    from ..keyboards import back_to_menu_kb
    await call.answer()
    await call.message.answer(GUIDE_TEXT, reply_markup=back_to_menu_kb())


@router.message(Command("guide"))
async def cmd_guide(message: Message) -> None:
    from ..keyboards import back_to_menu_kb
    await message.answer(GUIDE_TEXT, reply_markup=back_to_menu_kb())


@router.callback_query(F.data == "noop")
async def noop(call: CallbackQuery) -> None:
    await call.answer()
