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
    price_usd = float(product["price"])
    price_toman = service.digital_price_toman(price_usd)
    stock_line = (
        f"📦 موجودی: <b>{avail}</b> عدد آماده‌ی تحویل" if avail > 0 else "📦 موجودی: <b>ناموجود</b> ⛔️"
    )
    parts = [
        f"🧩 <b>{escape(product['title'])}</b>",
    ]
    if product["subtitle"]:
        parts.append(f"<i>{escape(product['subtitle'])}</i>")
    parts.append("")
    parts.append(product["description"] or "")
    parts.append("")
    parts.append(f"💵 قیمت: <b>{price_usd:g} USDT</b>  (≈ {price_toman:g} {service.currency})")
    parts.append(stock_line)
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
        reply_markup=digital_detail_kb(pid, in_stock=avail > 0),
    )


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
    if db.count_available_stock(pid) <= 0:
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
        f"💵 مبلغ: <b>{float(product['price']):g} USDT</b> (≈ {price_toman:g} {service.currency})"
        f"{wallet_line}\n\n"
        "روش پرداخت را انتخاب کنید:",
        reply_markup=digital_pay_kb(order_id, methods, wallet=wallet_ok),
    )


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
    if db.count_available_stock(int(product["id"])) <= 0:
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
