"""کیف پول (شارژ با روش‌های پرداخت) و درخواست همکاری."""
from __future__ import annotations

import logging
from html import escape

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from ..config import Settings
from ..database import (
    Database,
    ROLE_RESIDENTIAL_RESELLER,
    ROLE_V2RAY_RESELLER,
)
from ..keyboards import (
    back_to_menu_kb,
    pay_methods_keyboard,
    partnership_menu,
    request_decision_keyboard,
    wallet_menu,
)
from ..service import S_SHOW_PARTNERSHIP, Service
from ..states import PartnershipStates, WalletStates

logger = logging.getLogger("resibot.wallet")
router = Router(name="wallet")

PTYPE_LABEL = {"residential": "رزیدنتال", "v2ray": "V2Ray عادی"}
MAX_TOPUP = 1_000_000_000.0


# ====================================================================== #
#  کیف پول
# ====================================================================== #
async def _send_wallet(target: Message, db: Database, service: Service) -> None:
    bal = db.get_balance(target.chat.id)
    methods = service.enabled_pay_methods()
    text = (
        "💼 <b>کیف پول شما</b>\n\n"
        f"💰 موجودی: <b>{bal:g} {service.currency}</b>\n"
    )
    if not methods:
        text += "\n⚠️ شارژ آنلاین فعلاً غیرفعال است. برای شارژ با ادمین هماهنگ کنید."
    await target.answer(text, reply_markup=wallet_menu(topup_enabled=bool(methods)))


@router.message(F.text == "💼 کیف پول")
async def wallet_view(message: Message, state: FSMContext, db: Database, service: Service) -> None:
    await state.clear()
    await _send_wallet(message, db, service)


@router.callback_query(F.data == "menu:wallet")
async def wallet_view_cb(call: CallbackQuery, state: FSMContext, db: Database, service: Service) -> None:
    await state.clear()
    await call.answer()
    await _send_wallet(call.message, db, service)


@router.callback_query(F.data == "wallet:topup")
async def wallet_topup_start(call: CallbackQuery, state: FSMContext, service: Service) -> None:
    if not service.enabled_pay_methods():
        await call.answer("هیچ روش پرداختی فعال نیست.", show_alert=True)
        return
    await call.answer()
    await state.set_state(WalletStates.entering_amount)
    await call.message.answer(
        f"💳 مبلغ شارژ را به <b>{service.currency}</b> وارد کنید (فقط عدد):\n"
        f"• حداقل شارژ: <b>{service.min_topup:g} {service.currency}</b>\n"
        f"• نرخ تبدیل: هر دلار/تتر = <b>{service.toman_per_usd:g} {service.currency}</b>",
        reply_markup=back_to_menu_kb(),
    )


@router.message(WalletStates.entering_amount)
async def wallet_topup_amount(message: Message, state: FSMContext, service: Service) -> None:
    raw = (message.text or "").strip().replace(",", ".")
    try:
        amount = round(float(raw), 2)
    except ValueError:
        await message.answer("⛔️ یک عدد معتبر بفرستید.")
        return
    if amount <= 0 or amount > MAX_TOPUP:
        await message.answer(f"⛔️ مبلغ باید بین ۰ و {MAX_TOPUP:g} باشد.")
        return
    if amount < service.min_topup:
        await message.answer(
            f"⛔️ حداقل مبلغ شارژ <b>{service.min_topup:g} {service.currency}</b> است. "
            "مبلغ بیشتری وارد کنید:",
            reply_markup=back_to_menu_kb(),
        )
        return
    methods = service.enabled_pay_methods()
    if not methods:
        await state.clear()
        await message.answer("⛔️ هیچ روش پرداختی فعال نیست.")
        return
    await state.clear()
    try:
        order_id, usd = service.create_topup_payment(message.from_user.id, amount)
    except ValueError as exc:
        await message.answer(f"⛔️ {escape(str(exc))}")
        return
    await message.answer(
        f"🧾 <b>شارژ کیف پول</b>\n"
        f"💰 مبلغ: <b>{amount:g} {service.currency}</b> (≈ {usd:g} USDT)\n\n"
        "روش پرداخت را انتخاب کنید:",
        reply_markup=pay_methods_keyboard(order_id, methods),
    )


# ====================================================================== #
#  درخواست همکاری
# ====================================================================== #
async def _send_partnership(target: Message, db: Database, service: Service, role: str, is_admin: bool) -> None:
    if is_admin:
        await target.answer("شما ادمین هستید.")
        return
    if not service.feature_enabled(S_SHOW_PARTNERSHIP):
        await target.answer("بخش همکاری در حال حاضر غیرفعال است.")
        return
    if role in (ROLE_RESIDENTIAL_RESELLER, ROLE_V2RAY_RESELLER):
        await target.answer("شما در حال حاضر همکار هستید. ✅")
        return
    if db.has_pending_request(target.chat.id):
        await target.answer("⏳ یک درخواست همکاری در انتظار بررسی دارید.")
        return
    await target.answer(
        "🤝 <b>درخواست همکاری</b>\n\n"
        "• همکاری <b>رزیدنتال</b> فقط توسط ادمین تعیین می‌شود (قابل درخواست نیست).\n"
        "• همکاری <b>V2Ray</b> با پیش‌پرداخت و داشتن حداقل موجودی امکان‌پذیر است.\n\n"
        "برای درخواست همکاری V2Ray دکمه‌ی زیر را بزنید:",
        reply_markup=partnership_menu(),
    )


@router.message(F.text == "🤝 همکاری")
async def partnership_root(message: Message, state: FSMContext, db: Database, service: Service, role: str, is_admin: bool) -> None:
    await state.clear()
    await _send_partnership(message, db, service, role, is_admin)


@router.callback_query(F.data == "menu:partner")
async def partnership_root_cb(call: CallbackQuery, state: FSMContext, db: Database, service: Service, role: str, is_admin: bool) -> None:
    await state.clear()
    await call.answer()
    await _send_partnership(call.message, db, service, role, is_admin)


@router.callback_query(F.data.startswith("partner:"))
async def partnership_choose(call: CallbackQuery, state: FSMContext, db: Database, service: Service, role: str, is_admin: bool) -> None:
    if is_admin or role in (ROLE_RESIDENTIAL_RESELLER, ROLE_V2RAY_RESELLER):
        await call.answer("نیازی به درخواست ندارید.", show_alert=True)
        return
    if not service.feature_enabled(S_SHOW_PARTNERSHIP):
        await call.answer("بخش همکاری غیرفعال است.", show_alert=True)
        return
    if db.has_pending_request(call.from_user.id):
        await call.answer("یک درخواست در انتظار دارید.", show_alert=True)
        return
    ptype = call.data.split(":", 1)[1]
    if ptype != "v2ray":
        # همکاری رزیدنتال فقط توسط ادمین تعیین می‌شود؛ قابل درخواست نیست.
        await call.answer("همکاری رزیدنتال فقط توسط ادمین تعیین می‌شود.", show_alert=True)
        return
    await state.set_state(PartnershipStates.entering_description)
    await state.update_data(ptype=ptype)
    await call.answer()
    extra = (
        f"\n\n⚠️ همکاری V2Ray پیش‌پرداخت است و باید حداقل موجودی "
        f"<b>{service.reseller_min_balance:g} {service.currency}</b> در کیف پول داشته باشید."
    )
    await call.message.answer(
        f"📝 لطفاً توضیح کوتاهی درباره‌ی خودتان و درخواست همکاری ({PTYPE_LABEL[ptype]}) بنویسید:{extra}"
    )


@router.message(PartnershipStates.entering_description)
async def partnership_submit(message: Message, state: FSMContext, db: Database, cfg: Settings) -> None:
    desc = (message.text or "").strip()
    if len(desc) < 5:
        await message.answer("⛔️ توضیح خیلی کوتاه است. کمی بیشتر بنویسید:")
        return
    desc = desc[:1000]
    data = await state.get_data()
    await state.clear()
    ptype = data.get("ptype", "residential")
    req_id = db.add_partnership_request(message.from_user.id, ptype, desc)
    await message.answer("✅ درخواست شما ثبت شد و پس از بررسی ادمین به شما اطلاع داده می‌شود.")
    u = message.from_user
    uname = f"@{u.username}" if u.username else (u.full_name or "—")
    bal = db.get_balance(u.id)
    try:
        await message.bot.send_message(
            cfg.admin_id,
            "🤝 <b>درخواست همکاری جدید</b>\n"
            f"🆔 شناسه: <code>#{req_id}</code>\n"
            f"👤 کاربر: {escape(uname)} (<code>{u.id}</code>)\n"
            f"📦 نوع: <b>{PTYPE_LABEL.get(ptype, ptype)}</b>\n"
            f"💰 موجودی کیف پول: <b>{bal:g}</b>\n"
            f"📝 توضیح:\n{escape(desc)}",
            reply_markup=request_decision_keyboard(req_id),
        )
    except Exception:  # noqa: BLE001
        logger.warning("notify admin (partnership) failed")
