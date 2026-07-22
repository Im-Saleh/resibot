"""انتخاب روش پرداخت، نمایش فاکتور کریپتو، و ثبت/بررسی تراکنش.

هر دو روش (پرداخت مستقیم USDT روی BEP20 و درگاه NowPayments) اینجا مدیریت
می‌شوند. تحویل محصول از طریق ماژول مشترک fulfillment انجام می‌شود تا رفتار با
مسیر IPN و رصدگر خودکار کاملاً یکسان بماند.
"""
from __future__ import annotations

import logging
from html import escape

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from ..config import Settings
from ..crypto import extract_tx_hash, verify_deposit_tx
from ..database import Database
from ..fulfillment import deliver_paid_order, make_qr_png
from ..keyboards import back_to_menu_kb, crypto_paid_keyboard
from ..service import Service
from ..states import CryptoPayStates

logger = logging.getLogger("resibot.payments")
router = Router(name="payments")


def _fmt_amount(x: float) -> str:
    return f"{x:.6f}".rstrip("0").rstrip(".")


async def _owned_waiting_payment(order_id: str, uid: int, db: Database):
    row = db.get_payment_by_order(order_id)
    if not row or int(row["tg_id"]) != uid:
        return None
    return row


# ====================================================================== #
#  انتخاب روش پرداخت
# ====================================================================== #
@router.callback_query(F.data.startswith("pm:cancel:"))
async def pm_cancel(call: CallbackQuery, db: Database) -> None:
    order_id = call.data.split(":", 2)[2]
    row = await _owned_waiting_payment(order_id, call.from_user.id, db)
    if row and not int(row["credited"] or 0):
        db.set_payment_status(order_id, "cancelled")
    await call.answer("لغو شد.")
    try:
        await call.message.answer(
            "❌ پرداخت لغو شد.\nبرای ادامه از منوی اصلی استفاده کنید:",
            reply_markup=back_to_menu_kb(),
        )
    except Exception:  # noqa: BLE001
        pass


@router.callback_query(F.data.startswith("pm:crypto:"))
async def pm_crypto(call: CallbackQuery, service: Service, db: Database) -> None:
    order_id = call.data.split(":", 2)[2]
    row = await _owned_waiting_payment(order_id, call.from_user.id, db)
    if not row:
        await call.answer("فاکتور پیدا نشد.", show_alert=True)
        return
    if int(row["credited"] or 0):
        await call.answer("این فاکتور قبلاً پرداخت شده است.", show_alert=True)
        return
    await call.answer()
    try:
        info = await service.prepare_crypto_payment(order_id)
    except ValueError as exc:
        await call.message.answer(f"⛔️ {escape(str(exc))}")
        return
    except Exception as exc:  # noqa: BLE001
        logger.exception("prepare crypto failed")
        await call.message.answer(f"❌ خطا در آماده‌سازی پرداخت:\n<code>{escape(str(exc))}</code>")
        return

    amount_txt = _fmt_amount(float(info["pay_amount"]))
    text = (
        "💠 <b>پرداخت مستقیم USDT — شبکه BEP20 (BSC)</b>\n\n"
        "لطفاً <b>دقیقاً همین مبلغ</b> را به آدرس مقصد واریز کنید (این مبلغ یکتاست و "
        "برای شناسایی خودکار پرداخت شما لازم است):\n\n"
        f"💵 مبلغ دقیق: <b>{amount_txt} USDT</b>\n"
        f"🌐 شبکه: <b>BEP20 (BSC)</b>\n"
        "👛 آدرس مقصد:\n"
        f"<code>{escape(info['address'])}</code>\n\n"
        f"⏳ اعتبار فاکتور: <b>{info['ttl_min']} دقیقه</b>\n\n"
        "🤖 پرداخت شما <b>خودکار</b> و هر چند ثانیه یک‌بار بررسی می‌شود؛ به‌محض تأیید، "
        "سرویس تحویل داده می‌شود.\n"
        "🧾 اگر بعد از چند دقیقه خودکار تأیید نشد، کافی است <b>هش تراکنش (TxID) یا لینک BscScan</b> "
        "را همین‌جا بفرستید (حتی بدون زدن دکمه) تا فوری با آن بررسی و تأیید شود.\n\n"
        "⚠️ <b>امنیتی:</b> فقط <b>USDT واقعی روی شبکه‌ی BEP20</b> بفرستید؛ توکن تقلبی یا شبکه‌ی دیگر پذیرفته نمی‌شود."
    )
    # QR آدرس ولت را به‌صورت کپشن به همین پیام ضمیمه می‌کنیم (نه پیام جدا).
    kb = crypto_paid_keyboard(order_id)
    png = make_qr_png(info["address"])
    if png:
        try:
            await call.message.answer_photo(
                BufferedInputFile(png, filename="wallet-qr.png"),
                caption=text,
                reply_markup=kb,
            )
            return
        except Exception:  # noqa: BLE001
            logger.warning("ارسال عکس QR پرداخت ناموفق بود؛ متن ساده ارسال می‌شود")
    await call.message.answer(text, reply_markup=kb)


@router.callback_query(F.data.startswith("pm:hoosh:"))
async def pm_hooshpay(call: CallbackQuery, service: Service, db: Database) -> None:
    order_id = call.data.split(":", 2)[2]
    row = await _owned_waiting_payment(order_id, call.from_user.id, db)
    if not row:
        await call.answer("فاکتور پیدا نشد.", show_alert=True)
        return
    if int(row["credited"] or 0):
        await call.answer("این فاکتور قبلاً پرداخت شده است.", show_alert=True)
        return
    await call.answer()
    wait = await call.message.answer("⏳ در حال ساخت لینک پرداخت ریالی...")
    try:
        info = await service.prepare_hooshpay_payment(order_id)
    except ValueError as exc:
        await wait.edit_text(f"⛔️ {escape(str(exc))}")
        return
    except Exception as exc:  # noqa: BLE001
        logger.exception("prepare hooshpay failed")
        await wait.edit_text(f"❌ خطا در ساخت لینک پرداخت:\n<code>{escape(str(exc))}</code>")
        return
    payable = info.get("payable_amount") or info.get("amount_toman")
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="💳 پرداخت ریالی (کارت‌به‌کارت)", url=info["payment_url"])]]
    )
    await wait.edit_text(
        f"🧾 فاکتور ریالی به مبلغ <b>{int(payable):,} تومان</b> ساخته شد.\n"
        "روی دکمه‌ی زیر بزنید، کارت‌به‌کارت کنید و منتظر تأیید آنی بمانید. "
        "پس از پرداخت، سرویس/شارژ شما به‌صورت خودکار انجام می‌شود. ✅",
        reply_markup=kb,
    )


@router.callback_query(F.data.startswith("pm:now:"))
async def pm_nowpayments(call: CallbackQuery, service: Service, db: Database) -> None:
    order_id = call.data.split(":", 2)[2]
    row = await _owned_waiting_payment(order_id, call.from_user.id, db)
    if not row:
        await call.answer("فاکتور پیدا نشد.", show_alert=True)
        return
    if int(row["credited"] or 0):
        await call.answer("این فاکتور قبلاً پرداخت شده است.", show_alert=True)
        return
    await call.answer()
    wait = await call.message.answer("⏳ در حال ساخت لینک پرداخت درگاه...")
    try:
        info = await service.prepare_nowpayments_payment(order_id)
    except ValueError as exc:
        await wait.edit_text(f"⛔️ {escape(str(exc))}")
        return
    except Exception as exc:  # noqa: BLE001
        logger.exception("prepare nowpayments failed")
        await wait.edit_text(f"❌ خطا در ساخت لینک پرداخت:\n<code>{escape(str(exc))}</code>")
        return
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="💳 پرداخت با درگاه", url=info["invoice_url"])]]
    )
    await wait.edit_text(
        f"🧾 فاکتور به مبلغ <b>{info['usd']:g} USDT</b> (BEP20) ساخته شد.\n"
        "روی دکمه‌ی زیر بزنید و پرداخت را انجام دهید. پس از تأیید، سرویس/شارژ "
        "به‌صورت خودکار انجام می‌شود.",
        reply_markup=kb,
    )


# ====================================================================== #
#  ثبت دستی هش تراکنش
# ====================================================================== #
@router.callback_query(F.data.startswith("cx:tx:"))
async def crypto_tx_start(call: CallbackQuery, state: FSMContext, db: Database) -> None:
    order_id = call.data.split(":", 2)[2]
    row = await _owned_waiting_payment(order_id, call.from_user.id, db)
    if not row:
        await call.answer("فاکتور پیدا نشد.", show_alert=True)
        return
    if int(row["credited"] or 0):
        await call.answer("این فاکتور قبلاً پرداخت شده است.", show_alert=True)
        return
    await call.answer()
    await state.set_state(CryptoPayStates.entering_tx)
    await state.update_data(order_id=order_id)
    await call.message.answer(
        "🧾 هش تراکنش (TxID) یا لینک BscScan آن را بفرستید.\n"
        "مثال هش: <code>0x1234...abcd</code>"
    )


@router.callback_query(F.data.startswith("cx:chk:"))
async def crypto_check(call: CallbackQuery, db: Database, service: Service) -> None:
    order_id = call.data.split(":", 2)[2]
    row = await _owned_waiting_payment(order_id, call.from_user.id, db)
    if not row:
        await call.answer("فاکتور پیدا نشد.", show_alert=True)
        return
    if int(row["credited"] or 0):
        await call.answer("✅ پرداخت شما قبلاً تأیید و تحویل شده است.", show_alert=True)
        return
    status = str(row["status"] or "")
    if status == "expired":
        await call.answer("⛔️ این فاکتور منقضی شده است. لطفاً دوباره سفارش دهید.", show_alert=True)
        return
    await call.answer(
        "⏳ هنوز واریز تأییدشده‌ای دیده نشده. سیستم هر چند ثانیه یک‌بار خودکار بررسی می‌کند. "
        "اگر عجله دارید، هش تراکنش یا لینک BscScan را بفرستید تا فوری بررسی شود.",
        show_alert=True,
    )


async def _verify_and_settle(bot, db: Database, service: Service, cfg: Settings, row, tx_hash: str) -> tuple[bool, str]:
    """راستی‌آزمایی هش تراکنش برای یک فاکتور و در صورت تأیید، تسویه و تحویل.

    برمی‌گرداند (موفق، پیام). ضدجعل: قرارداد رسمی USDT، آدرس مقصد، مبلغ، تأیید،
    یکتایی هش، و بلاک بعد از ساخت فاکتور.
    """
    if db.tx_hash_used(tx_hash):
        return (False, "این هش تراکنش قبلاً برای یک سفارش استفاده شده است.")
    rpc = service.make_rpc_pool()
    # هنگام بررسی با هش، مبلغ پایه (قیمت واقعی) ملاک است؛ پس چه کاربر مبلغ رند
    # (مثل 1) و چه مبلغ یکتا (1.000021) را فرستاده باشد، هر دو پذیرفته می‌شود.
    base_amount = service._payment_usd(row)
    min_amount = base_amount if base_amount > 0 else float(row["pay_amount"])
    ok, msg, _received = await verify_deposit_tx(
        rpc,
        tx_hash,
        to_address=row["pay_address"],
        min_amount=min_amount,
        required_conf=service.crypto_confirmations,
        min_block=int(row["start_block"] or 0),
    )
    if not ok:
        return (False, msg)
    credited = service.settle_crypto_payment(row["order_id"], tx_hash)
    if credited is None:
        return (False, "این پرداخت قبلاً پردازش شده یا این هش برای سفارش دیگری ثبت شده است.")
    await deliver_paid_order(bot, cfg, db, service, credited)
    return (True, "ok")


@router.message(CryptoPayStates.entering_tx)
async def crypto_tx_submit(
    message: Message, state: FSMContext, db: Database, service: Service, cfg: Settings
) -> None:
    order_id = str((await state.get_data()).get("order_id", ""))
    tx_hash = extract_tx_hash(message.text or "")
    if not tx_hash:
        await message.answer("⛔️ هش تراکنش معتبر پیدا نشد. یک TxID یا لینک BscScan بفرستید:")
        return
    row = await _owned_waiting_payment(order_id, message.from_user.id, db)
    if not row:
        await state.clear()
        await message.answer("⛔️ فاکتور پیدا نشد.")
        return
    if int(row["credited"] or 0):
        await state.clear()
        await message.answer("✅ این فاکتور قبلاً تأیید و تحویل شده است.")
        return
    await state.clear()
    wait = await message.answer("⏳ در حال بررسی تراکنش روی شبکه‌ی BSC...")
    ok, msg = await _verify_and_settle(message.bot, db, service, cfg, row, tx_hash)
    if ok:
        await wait.edit_text("✅ پرداخت تأیید شد! سرویس در حال تحویل است...")
    else:
        await wait.edit_text(
            f"⛔️ تأیید نشد:\n{escape(msg)}\n\n"
            "پس از رفع مشکل، دوباره هش/لینک تراکنش را بفرستید."
        )


# ثبت مستقیم: کاربر بدون کلیک روی دکمه، هش یا لینک BscScan را می‌فرستد و
# خودکار برای آخرین فاکتور بازش بررسی و تأیید می‌شود.
@router.message(StateFilter(None), F.text.func(lambda t: bool(extract_tx_hash(t or ""))))
async def crypto_tx_direct(message: Message, db: Database, service: Service, cfg: Settings) -> None:
    tx_hash = extract_tx_hash(message.text or "")
    if not tx_hash:
        return
    row = db.latest_waiting_crypto_payment(message.from_user.id)
    if not row:
        await message.answer(
            "ℹ️ هش تراکنش دریافت شد، اما فاکتور پرداخت بازی برای شما پیدا نکردم.\n"
            "ابتدا از «🛒 خرید سرویس» سفارش ثبت کنید و روش «پرداخت مستقیم USDT» را انتخاب کنید.",
            reply_markup=back_to_menu_kb(),
        )
        return
    if int(row["credited"] or 0):
        await message.answer("✅ این فاکتور قبلاً تأیید و تحویل شده است.")
        return
    wait = await message.answer("⏳ در حال بررسی تراکنش روی شبکه‌ی BSC...")
    ok, msg = await _verify_and_settle(message.bot, db, service, cfg, row, tx_hash)
    if ok:
        await wait.edit_text("✅ پرداخت تأیید شد! سرویس در حال تحویل است...")
    else:
        await wait.edit_text(f"⛔️ تأیید نشد:\n{escape(msg)}\n\nپس از رفع مشکل، دوباره هش/لینک را بفرستید.")
