"""انتخاب روش پرداخت، نمایش فاکتور کریپتو، و ثبت/بررسی تراکنش.

هر دو روش (پرداخت مستقیم USDT روی BEP20 و درگاه NowPayments) اینجا مدیریت
می‌شوند. تحویل محصول از طریق ماژول مشترک fulfillment انجام می‌شود تا رفتار با
مسیر IPN و رصدگر خودکار کاملاً یکسان بماند.
"""
from __future__ import annotations

import logging
from html import escape

from aiogram import F, Router
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
from ..keyboards import crypto_paid_keyboard
from ..service import Service
from ..states import CryptoPayStates

logger = logging.getLogger("resibot.payments")
router = Router(name="payments")


def _fmt_amount(x: float) -> str:
    return f"{x:.3f}".rstrip("0").rstrip(".")


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
        await call.message.edit_text("❌ پرداخت لغو شد.")
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
        "مبلغ زیر را به آدرس مقصد واریز کنید:\n\n"
        f"💵 مبلغ: <b>{amount_txt} USDT</b>\n"
        f"🌐 شبکه: <b>BEP20 (BSC)</b>\n"
        "👛 آدرس مقصد:\n"
        f"<code>{escape(info['address'])}</code>\n\n"
        f"⏳ اعتبار فاکتور: <b>{info['ttl_min']} دقیقه</b>\n\n"
        "✅ <b>بعد از واریز، دکمه‌ی «🧾 ارسال هش تراکنش / لینک» را بزنید</b> و کد رهگیری "
        "(TxID) یا لینک BscScan تراکنش را بفرستید تا بررسی و سرویس تحویل داده شود.\n\n"
        "⚠️ <b>هشدار امنیتی:</b> فقط <b>USDT واقعی روی شبکه‌ی BEP20</b> بفرستید. "
        "توکن تقلبی یا شبکه‌ی دیگر پذیرفته نمی‌شود."
    )
    await call.message.answer(text, reply_markup=crypto_paid_keyboard(order_id))
    png = make_qr_png(info["address"])
    if png:
        try:
            await call.message.answer_photo(
                BufferedInputFile(png, filename="wallet-qr.png"),
                caption=f"📷 QR آدرس ولت — مبلغ دقیق: {amount_txt} USDT",
            )
        except Exception:  # noqa: BLE001
            pass


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
        "ℹ️ برای تأیید پرداخت، بعد از واریز دکمه‌ی «🧾 ارسال هش تراکنش / لینک» را بزنید و "
        "کد رهگیری تراکنش را بفرستید.",
        show_alert=True,
    )


@router.message(CryptoPayStates.entering_tx)
async def crypto_tx_submit(
    message: Message, state: FSMContext, db: Database, service: Service, cfg: Settings
) -> None:
    data = await state.get_data()
    order_id = str(data.get("order_id", ""))
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
    if db.tx_hash_used(tx_hash):
        await message.answer("⛔️ این هش تراکنش قبلاً برای یک سفارش استفاده شده است.")
        return

    await state.clear()
    wait = await message.answer("⏳ در حال بررسی تراکنش روی شبکه‌ی BSC...")
    rpc = service.make_rpc_pool()
    ok, msg, received = await verify_deposit_tx(
        rpc,
        tx_hash,
        to_address=row["pay_address"],
        min_amount=float(row["pay_amount"]),
        required_conf=service.crypto_confirmations,
        min_block=int(row["start_block"] or 0),
    )
    if not ok:
        await wait.edit_text(
            f"⛔️ تأیید نشد:\n{escape(msg)}\n\n"
            "پس از رفع مشکل، دوباره از دکمه‌ی «🧾 ارسال هش تراکنش» اقدام کنید."
        )
        return
    credited = service.settle_crypto_payment(order_id, tx_hash)
    if credited is None:
        await wait.edit_text(
            "ℹ️ این پرداخت قبلاً پردازش شده یا این هش برای سفارش دیگری ثبت شده است."
        )
        return
    await wait.edit_text("✅ پرداخت تأیید شد! در حال تحویل سرویس...")
    await deliver_paid_order(message.bot, cfg, db, service, credited)
