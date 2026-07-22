"""خرید محصولات دیجیتال (اکانت/اشتراک آماده) توسط کاربر.

جریان کار:
  menu:digital           → لیست محصولات فعال (هرکدام یک دکمه‌ی شیشه‌ای)
  dg:open:<id>           → نمایش متن فروش، قیمت و موجودی + دکمه‌ی خرید
  dg:buy:<id>            → ساخت فاکتور و نمایش روش‌های پرداخت (کیف پول/کریپتو/درگاه)
  dg:wallet:<order_id>   → پرداخت آنی از کیف پول و تحویل فوری از انبار

تحویل پس از پرداخت کریپتو/درگاه از طریق ماژول مشترک fulfillment انجام می‌شود.
"""
from __future__ import annotations

import logging
from html import escape

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from ..config import Settings
from ..database import Database
from ..fulfillment import _deliver_digital
from ..keyboards import back_to_menu_kb, digital_detail_kb, digital_products_menu, digital_pay_kb
from ..service import Service
from ..states import DigitalManualStates

logger = logging.getLogger("resibot.digital")
router = Router(name="digital")


async def _send_digital_list(target: Message, service: Service, db: Database) -> None:
    if not service.digital_enabled:
        await target.answer("این بخش در حال حاضر غیرفعال است.", reply_markup=back_to_menu_kb())
        return
    products = db.list_digital_products(active_only=True)
    if not products:
        await target.answer(
            "فعلاً هیچ اشتراکی برای فروش نداریم. کمی بعد دوباره سر بزنید. 🙏",
            reply_markup=back_to_menu_kb(),
        )
        return
    await target.answer(
        "🤖 <b>اشتراک‌های هوش مصنوعی</b>\n"
        "یکی را انتخاب کنید تا جزئیات و قیمتش را ببینید:",
        reply_markup=digital_products_menu(products, db.stock_counts()),
    )


@router.callback_query(F.data == "menu:digital")
async def menu_digital(call: CallbackQuery, state: FSMContext, service: Service, db: Database) -> None:
    await state.clear()
    await call.answer()
    await _send_digital_list(call.message, service, db)


def _detail_text(service: Service, product, avail: int) -> str:
    from ..digital import DELIVERY_LABELS, normalize_delivery, uses_stock
    price_usd = float(product["price"])
    dtype = normalize_delivery(product["delivery_type"])
    parts = [
        f"🧩 <b>{escape(product['title'])}</b>",
    ]
    if product["subtitle"]:
        parts.append(f"<i>{escape(product['subtitle'])}</i>")
    parts.append("")
    parts.append(product["description"] or "")
    parts.append("")
    parts.append(f"💵 قیمت: <b>{price_usd:g} دلار</b>")
    parts.append(f"🚚 تحویل: {DELIVERY_LABELS.get(dtype, dtype)}")
    if uses_stock(dtype):
        parts.append(
            f"📦 موجودی: <b>{avail}</b> عدد آماده‌ی تحویل" if avail > 0
            else "📦 موجودی: <b>ناموجود</b> ⛔️"
        )
    return "\n".join(parts)


@router.callback_query(F.data.startswith("dg:open:"))
async def dg_open(call: CallbackQuery, service: Service, db: Database) -> None:
    await call.answer()
    try:
        pid = int(call.data.split(":")[2])
    except (ValueError, IndexError):
        await call.answer("نامعتبر", show_alert=True)
        return
    product = db.get_digital_product(pid)
    if not product or not int(product["active"]):
        await call.message.answer("این محصول دیگر در دسترس نیست.", reply_markup=back_to_menu_kb())
        return
    avail = db.count_available_stock(pid)
    await call.message.answer(
        _detail_text(service, product, avail),
        reply_markup=digital_detail_kb(pid, in_stock=_available(db, product)),
    )


def _available(db: Database, product) -> bool:
    """آیا محصول قابل خرید است؟ محصولات تحویل‌دستی همیشه موجودند؛ بقیه به انبار نیاز دارند."""
    from ..digital import uses_stock
    if not uses_stock(product["delivery_type"]):
        return True
    return db.count_available_stock(int(product["id"])) > 0


@router.callback_query(F.data.startswith("dg:notify:"))
async def dg_notify(call: CallbackQuery) -> None:
    await call.answer(
        "باشه! به‌محض موجود شدن این محصول، همین‌جا اطلاع‌رسانی می‌کنیم. 🔔",
        show_alert=True,
    )


@router.callback_query(F.data.startswith("dg:buy:"))
async def dg_buy(
    call: CallbackQuery, service: Service, db: Database, cfg: Settings, is_admin: bool
) -> None:
    await call.answer()
    try:
        pid = int(call.data.split(":")[2])
    except (ValueError, IndexError):
        await call.answer("نامعتبر", show_alert=True)
        return
    product = db.get_digital_product(pid)
    if not product or not int(product["active"]):
        await call.message.answer("این محصول دیگر در دسترس نیست.", reply_markup=back_to_menu_kb())
        return
    if not _available(db, product):
        await call.message.answer(
            "متأسفانه موجودی این محصول همین حالا تمام شد. کمی بعد دوباره امتحان کنید. 🙏",
            reply_markup=back_to_menu_kb(),
        )
        return

    # ادمین: تحویل فوری و رایگان (برای تست/استفاده‌ی شخصی)
    if is_admin:
        order_id = f"{cfg.brand_name}-adm-dg-{call.from_user.id}-{pid}"
        ok = await _deliver_digital(
            call.bot, cfg, db, service, call.from_user.id,
            product["slug"], 0.0, "ادمین (رایگان)", order_id=order_id,
        )
        if not ok:
            await call.message.answer("⛔️ تحویل ناموفق بود (احتمالاً موجودی تمام شد).")
        return

    methods = service.enabled_pay_methods()
    balance = db.get_balance(call.from_user.id)
    price_toman = service.digital_price_toman(float(product["price"]))
    wallet_ok = balance >= price_toman > 0
    if not methods and not wallet_ok:
        await call.message.answer(
            "⛔️ در حال حاضر هیچ روش پرداختی فعال نیست و موجودی کیف پول هم کافی نیست. "
            "با ادمین هماهنگ کنید.",
            reply_markup=back_to_menu_kb(),
        )
        return

    order_id = service.create_digital_order(call.from_user.id, product)
    wallet_line = (
        f"\n💼 موجودی کیف پول شما: <b>{balance:g} {service.currency}</b>"
        + ("" if wallet_ok else " (کافی نیست)")
    )
    await call.message.answer(
        f"🧾 <b>فاکتور خرید</b>\n"
        f"🧩 محصول: <b>{escape(product['title'])}</b>\n"
        f"💵 مبلغ: <b>{float(product['price']):g} دلار</b>"
        f"{wallet_line}\n\n"
        "روش پرداخت را انتخاب کنید:",
        reply_markup=digital_pay_kb(order_id, methods, wallet=wallet_ok),
    )


# ---------------------------------------------------------------------- #
#  تحویل دستی: دریافت ایمیل و رمز از مشتری
# ---------------------------------------------------------------------- #
@router.callback_query(F.data.startswith("dgm:info:"))
async def dgm_info_start(call: CallbackQuery, state: FSMContext, db: Database) -> None:
    order_id = call.data.split(":", 2)[2]
    mo = db.get_manual_order_by_order(order_id)
    if not mo or int(mo["buyer_tg_id"]) != call.from_user.id:
        await call.answer("این سفارش پیدا نشد.", show_alert=True)
        return
    if mo["status"] not in ("awaiting_info", "pending"):
        await call.answer("این سفارش قبلاً پردازش شده است.", show_alert=True)
        return
    await state.set_state(DigitalManualStates.entering_email)
    await state.update_data(manual_order_id=order_id)
    await call.answer()
    await call.message.answer(
        "📧 لطفاً <b>ایمیل اکانتت</b> رو بفرست (همون اکانتی که می‌خوای سرویس روش فعال بشه):"
    )


@router.message(DigitalManualStates.entering_email)
async def dgm_email(message: Message, state: FSMContext) -> None:
    email = (message.text or "").strip()
    if len(email) < 4 or " " in email:
        await message.answer("⛔️ ایمیل معتبر نیست. دوباره بفرست:")
        return
    await state.update_data(manual_email=email[:200])
    await state.set_state(DigitalManualStates.entering_password)
    await message.answer("🔑 حالا <b>رمز عبور اکانت</b> رو بفرست:")


@router.message(DigitalManualStates.entering_password)
async def dgm_password(message: Message, state: FSMContext, db: Database, cfg: Settings) -> None:
    password = (message.text or "").strip()
    if len(password) < 3:
        await message.answer("⛔️ رمز خیلی کوتاهه. دوباره بفرست:")
        return
    data = await state.get_data()
    await state.clear()
    order_id = data.get("manual_order_id", "")
    email = data.get("manual_email", "")
    mo = db.get_manual_order_by_order(order_id)
    if not mo or int(mo["buyer_tg_id"]) != message.from_user.id:
        await message.answer("⛔️ سفارش پیدا نشد.")
        return
    db.set_manual_credentials(order_id, f"{email} | {password}")
    await message.answer(
        "✅ اطلاعاتت دریافت شد! 🙌\n"
        "کارشناس ما در سریع‌ترین زمان ممکن سرویس رو روی اکانتت فعال می‌کنه و همین‌جا "
        "بهت خبر می‌ده. ممنون از صبرت. 🌟"
    )
    # اطلاع به ادمین با دکمه‌ی «انجام شد»
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    product = db.get_digital_product(int(mo["product_id"]))
    title = product["title"] if product else mo["slug"]
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ انجام شد و به مشتری خبر بده", callback_data=f"dgm:done:{mo['id']}")
    ]])
    try:
        await message.bot.send_message(
            cfg.admin_id,
            "🙋 <b>اطلاعات اکانت مشتری رسید</b>\n"
            f"🧩 محصول: <b>{escape(title)}</b>\n"
            f"👤 خریدار: <code>{mo['buyer_tg_id']}</code>\n"
            f"🧾 سفارش: <code>{escape(order_id)}</code>\n\n"
            f"📧 ایمیل: <code>{escape(email)}</code>\n"
            f"🔑 رمز: <code>{escape(password)}</code>\n\n"
            "کار رو انجام بده و بعد دکمه‌ی زیر رو بزن تا به مشتری خبر داده بشه. 👇",
            reply_markup=kb,
        )
    except Exception:  # noqa: BLE001
        logger.warning("notify admin manual order failed")


@router.callback_query(F.data.startswith("dg:wallet:"))
async def dg_wallet(call: CallbackQuery, service: Service, db: Database, cfg: Settings) -> None:
    order_id = call.data.split(":", 2)[2]
    row = db.get_payment_by_order(order_id)
    if not row or int(row["tg_id"]) != call.from_user.id:
        await call.answer("فاکتور پیدا نشد.", show_alert=True)
        return
    if int(row["credited"] or 0):
        await call.answer("این فاکتور قبلاً پرداخت شده است.", show_alert=True)
        return
    await call.answer()

    import json
    try:
        meta = json.loads(row["meta"] or "{}")
        slug = meta.get("digital_slug", "")
    except (TypeError, ValueError):
        slug = ""
    if not slug:
        await call.message.answer("⛔️ این فاکتور برای محصول دیجیتال نیست.")
        return
    product = db.get_digital_product_by_slug(slug)
    if not product:
        await call.message.answer("⛔️ محصول دیگر موجود نیست.")
        return

    price_toman = service.digital_price_toman(float(product["price"]))
    if not _available(db, product):
        await call.message.answer("متأسفانه موجودی همین حالا تمام شد. مبلغی از شما کسر نشد.")
        return

    # کسر اتمیک از کیف پول (فقط اگر کافی باشد)
    if not db.try_deduct_balance(call.from_user.id, price_toman):
        await call.message.answer(
            f"⛔️ موجودی کیف پول شما کافی نیست. لازم: <b>{price_toman:g} {service.currency}</b>",
            reply_markup=back_to_menu_kb(),
        )
        return

    # ثبت روش و credit اتمیک (idempotent)
    db.update_payment(order_id, method="wallet", pay_currency=service.currency)
    credited = db.credit_payment_once(order_id)
    if credited is None:
        # قبلاً credit شده بود؛ پول را برگردان تا کسر دوباره نشود
        db.add_balance(call.from_user.id, price_toman)
        await call.answer("این فاکتور قبلاً پردازش شده است.", show_alert=True)
        return

    usd = float(product["price"])
    ok = await _deliver_digital(
        call.bot, cfg, db, service, call.from_user.id,
        slug, usd, "کیف پول", order_id=order_id,
    )
    if not ok:
        # تحویل ناموفق (موجودی تمام شد پس از کسر) — عودت وجه
        db.add_balance(call.from_user.id, price_toman)
        await call.message.answer(
            "⛔️ تحویل ناموفق بود و مبلغ به کیف پول شما بازگردانده شد. لطفاً بعداً امتحان کنید."
        )
        return
    # پاداش رفرال برای خرید از کیف پول
    try:
        ref = service.credit_referral(call.from_user.id, usd)
        if ref:
            from ..fulfillment import _notify_referral
            await _notify_referral(call.bot, ref, call.from_user.id)
    except Exception:  # noqa: BLE001
        logger.warning("referral credit (digital wallet) failed")
