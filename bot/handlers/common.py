"""هندلرهای عمومی: /start، /id، منوی اصلی (شیشه‌ای) و منوی محصولات."""
from __future__ import annotations

from html import escape

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

from ..config import Settings
from ..database import (
    Database,
    PRODUCT_RESIDENTIAL,
    PRODUCT_RESIDENTIAL2,
    PRODUCT_V2RAY,
    ROLE_RESIDENTIAL_RESELLER,
    ROLE_V2RAY_RESELLER,
)
from ..keyboards import back_to_menu_kb, main_menu, products_menu
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
    message: Message, state: FSMContext, cfg: Settings, service: Service,
    db: Database, command: CommandObject, role: str, is_admin: bool,
) -> None:
    await state.clear()
    # پردازش لینک رفرال: /start ref<آیدی معرف>
    args = (command.args or "").strip()
    if args.startswith("ref"):
        try:
            ref_id = int(args[3:])
        except ValueError:
            ref_id = 0
        if ref_id and ref_id != message.from_user.id:
            if db.set_referrer(message.from_user.id, ref_id):
                try:
                    await message.bot.send_message(
                        ref_id,
                        f"🎉 یک نفر با لینک دعوت شما وارد ربات شد (<code>{message.from_user.id}</code>).\n"
                        "اگر خرید کند، درصد پاداش رفرال به کیف پول شما اضافه می‌شود.",
                    )
                except Exception:  # noqa: BLE001
                    pass
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
async def _send_products(target: Message, state: FSMContext, service: Service, db: Database) -> None:
    await state.clear()
    res = service.product_enabled(PRODUCT_RESIDENTIAL)
    res2 = service.product_enabled(PRODUCT_RESIDENTIAL2)
    v2 = service.product_enabled(PRODUCT_V2RAY)
    dig = service.digital_enabled and bool(db.list_digital_products(active_only=True))
    if not (res or res2 or v2 or dig):
        await target.answer("در حال حاضر هیچ محصولی برای فروش فعال نیست.")
        return
    await target.answer(
        "🛍 <b>محصولات</b>\nیکی از سرویس‌های زیر را انتخاب کنید:",
        reply_markup=products_menu(residential=res, residential2=res2, v2ray=v2, digital=dig),
    )


@router.callback_query(F.data == "menu:buy")
async def menu_buy(call: CallbackQuery, state: FSMContext, service: Service, db: Database) -> None:
    await call.answer()
    await _send_products(call.message, state, service, db)


@router.message(F.text == "🛒 خرید سرویس")
async def show_products(message: Message, state: FSMContext, service: Service, db: Database) -> None:
    await _send_products(message, state, service, db)


GUIDE_TEXT = (
    "📖 <b>راهنمای خرید و استفاده</b>\n"
    "سلام رفیق 👋 نگران نباش، خیلی ساده‌تر از چیزیه که فکر می‌کنی. بریم قدم‌به‌قدم:\n\n"

    "🛒 <b>۱) چطور بخرم؟</b>\n"
    "روی «🛒 خرید سرویس» بزن و سرویس دلخواهت رو انتخاب کن:\n"
    "• <b>رزیدنتال</b> و <b>رزیدنتال ۲</b>: پروکسی با آی‌پی خونگی واقعی؛ کشور/شهر رو خودت انتخاب می‌کنی و هر وقت خواستی آی‌پی رو عوض می‌کنی. بر اساس حجم (گیگ) حساب می‌شه.\n"
    "• <b>V2Ray</b>: یه پلن یک‌ماهه‌ی <b>نامحدود</b> (بدون محدودیت حجم). ساده و بی‌دردسر.\n\n"

    "💳 <b>۲) پرداخت چطوریه؟</b>\n"
    "بعد از انتخاب، روش پرداخت رو می‌بینی:\n"
    "• <b>پرداخت مستقیم تتر (USDT شبکه BEP20)</b>: یه مبلغ و یه آدرس بهت نشون داده می‌شه. "
    "همون مبلغ رو به همون آدرس بفرست، بعد <b>کد رهگیری تراکنش (TxID) یا لینک BscScan</b> رو همین‌جا برام بفرست "
    "(حتی لازم نیست دکمه بزنی، فقط لینک/هش رو پیست کن). خودم بررسی و تأیید می‌کنم و سرویس رو تحویل می‌دم. تمام! ✅\n"
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


# ---------------------------------------------------------------------- #
#  رفرال (دعوت دوستان)
# ---------------------------------------------------------------------- #
@router.callback_query(F.data == "menu:referral")
async def menu_referral(call: CallbackQuery, service: Service, db: Database) -> None:
    await call.answer()
    uid = call.from_user.id
    username = (db.get_setting("bot_username", "") or "").lstrip("@")
    count = db.count_referrals(uid)
    earn = db.ref_earnings(uid)
    pct = service.referral_percent
    if username:
        link = f"https://t.me/{username}?start=ref{uid}"
        link_line = f"🔗 لینک دعوت شما:\n<code>{escape(link)}</code>"
    else:
        link_line = f"🔗 کد دعوت شما: <code>ref{uid}</code>\n(لینک کامل به‌زودی فعال می‌شود)"
    text = (
        "👥 <b>دعوت دوستان (رفرال)</b>\n\n"
        f"با هر خریدی که دعوت‌شده‌های شما انجام دهند، <b>{pct:g}%</b> مبلغ خرید به‌صورت "
        f"اعتبار به کیف پول شما اضافه می‌شود. 🎁\n\n"
        f"{link_line}\n\n"
        f"👤 تعداد دعوت‌شده‌ها: <b>{count}</b>\n"
        f"💰 مجموع پاداش دریافتی: <b>{earn:g} {service.currency}</b>\n\n"
        "این لینک را برای دوستانتان بفرستید — وقتی از طریق آن وارد شوند و خرید کنند، سهم شما واریز می‌شود."
    )
    await call.message.answer(text, reply_markup=back_to_menu_kb())


# ---------------------------------------------------------------------- #
#  وضعیت سرویس‌ها (ادمین/همکار)
# ---------------------------------------------------------------------- #
def _status_report(st: dict) -> str:
    lines = ["📊 <b>وضعیت سرویس‌ها</b>", ""]
    if st.get("server_ok"):
        lines.append(f"🖥 سرور / پنل: ✅ <b>اوکی</b> ({st.get('inbounds', 0)} اینباند)")
    else:
        lines.append("🖥 سرور / پنل: ❌ <b>در دسترس نیست</b>")
        if st.get("server_err"):
            lines.append(f"   └ <code>{escape(str(st['server_err']))}</code>")
    r1 = st.get("res1", {})
    if r1.get("ok"):
        lines.append(f"🌐 رزیدنتال ۱: ✅ <b>اوکی</b> (پینگ {r1.get('delay', '?')} ms)")
    else:
        lines.append("🌐 رزیدنتال ۱: ❌ <b>آف</b> — پینگ نداد، یعنی سرویس‌های رزیدنتال ۱ خاموش‌اند")
    r2 = st.get("res2", {})
    if r2.get("configured") is False:
        lines.append("🌍 رزیدنتال ۲: ⚪️ تنظیم نشده")
    elif r2.get("ok"):
        lines.append(f"🌍 رزیدنتال ۲: ✅ <b>اوکی</b> (پینگ {r2.get('delay', '?')} ms)")
    else:
        lines.append("🌍 رزیدنتال ۲: ❌ <b>آف</b> — پینگ نداد، یعنی سرویس‌های رزیدنتال ۲ خاموش‌اند")
    lines.append(f"🛡 اینباند V2Ray: {'✅ اوکی' if st.get('v2ray_inbound_ok') else '❌ پیدا نشد'}")
    return "\n".join(lines)


@router.callback_query(F.data == "menu:status")
async def menu_status(call: CallbackQuery, service: Service, role: str, is_admin: bool) -> None:
    if not (is_admin or _is_reseller(role)):
        await call.answer("این بخش فقط برای همکاران و ادمین است.", show_alert=True)
        return
    await call.answer()
    wait = await call.message.answer("⏳ در حال بررسی وضعیت سرور و سرویس‌ها... (چند لحظه)")
    try:
        st = await service.service_status()
    except Exception as exc:  # noqa: BLE001
        await wait.edit_text(f"❌ خطا در بررسی وضعیت:\n<code>{escape(str(exc))}</code>")
        return
    await wait.edit_text(_status_report(st), reply_markup=back_to_menu_kb())


@router.callback_query(F.data == "noop")
async def noop(call: CallbackQuery) -> None:
    await call.answer()
