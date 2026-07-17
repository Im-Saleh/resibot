"""تحویل یکپارچه‌ی محصول پس از تأیید پرداخت.

این ماژول توسط هر سه مسیر تأیید پرداخت استفاده می‌شود تا رفتار کاملاً یکسان
باشد و هیچ باگی بین مسیرها تکرار نشود:
  - IPN درگاه NowPayments
  - رصدگر خودکار پرداخت کریپتو (BSC)
  - ثبت دستی هش تراکنش توسط کاربر

قاعده‌ی مهم: تابع credit (اتمیک و idempotent) باید قبل از فراخوانی این ماژول
انجام شده باشد؛ پس تحویل دقیقاً یک‌بار رخ می‌دهد حتی اگر چند مسیر هم‌زمان تلاش کنند.
"""
from __future__ import annotations

import io
import json
import logging
from html import escape
from typing import Any

from .config import Settings
from .database import Database, PRODUCT_V2RAY
from .utils import fmt_expiry, provision_message

logger = logging.getLogger("resibot.fulfillment")


def make_qr_png(data: str) -> bytes | None:
    """یک تصویر QR (PNG) از داده می‌سازد. در صورت نبود کتابخانه None برمی‌گرداند."""
    try:
        import segno  # وابستگی سبک و کاملاً پایتونی (بدون Pillow)
    except Exception:  # noqa: BLE001
        logger.warning("segno نصب نیست؛ QR ارسال نمی‌شود.")
        return None
    try:
        buf = io.BytesIO()
        segno.make(data, error="m").save(buf, kind="png", scale=6, border=2)
        return buf.getvalue()
    except Exception:  # noqa: BLE001
        logger.exception("ساخت QR ناموفق بود")
        return None


def _v2ray_message(info: dict[str, Any]) -> str:
    lines = [
        "✅ <b>سرویس V2Ray شما ساخته شد</b>",
        "",
        "📦 حجم: <b>نامحدود</b> ♾",
        f"⏳ اعتبار: <b>{info.get('days', 30)} روز</b>",
        f"📅 انقضا: {fmt_expiry(info.get('expiry_ms', 0))}",
        f"🆔 شناسه سرویس: <code>#{info.get('config_id')}</code>",
        "",
        "🔗 <b>لینک ساب (Subscription):</b>",
        f"<code>{escape(info.get('sub_link', ''))}</code>",
    ]
    links = info.get("vless_links") or []
    if links:
        lines.append("")
        lines.append("📋 <b>لینک کانفیگ:</b>")
        for vl in links:
            lines.append(f"<code>{escape(str(vl))}</code>")
    lines.append("")
    lines.append("📷 QR‌کد ساب در پیام بعدی ارسال می‌شود.")
    return "\n".join(lines)


async def _send_v2ray(bot: Any, tg_id: int, info: dict[str, Any]) -> None:
    await bot.send_message(tg_id, _v2ray_message(info))
    sub_link = info.get("sub_link", "")
    png = make_qr_png(sub_link) if sub_link else None
    if png:
        try:
            from aiogram.types import BufferedInputFile

            await bot.send_photo(
                tg_id,
                BufferedInputFile(png, filename="sub-qr.png"),
                caption="📷 QR‌کد لینک ساب — در کلاینت اسکن کنید.",
            )
        except Exception:  # noqa: BLE001
            logger.warning("ارسال QR به کاربر %s ناموفق بود", tg_id)


async def send_v2ray_delivery(bot: Any, tg_id: int, info: dict[str, Any]) -> None:
    """تحویل پیام + QR سرویس V2Ray (برای مسیر رایگان ادمین یا فراخوانی مستقیم)."""
    await _send_v2ray(bot, tg_id, info)


async def deliver_paid_order(
    bot: Any, cfg: Settings, db: Database, service: Any, credited_row: Any
) -> None:
    """محصول یک پرداختِ credit‌شده را تحویل می‌دهد و به کاربر/ادمین اطلاع می‌دهد."""
    purpose = credited_row["purpose"]
    tg_id = int(credited_row["tg_id"])
    method = (credited_row["method"] or "").strip() if "method" in credited_row.keys() else ""
    method_label = "پرداخت مستقیم USDT (BEP20)" if method == "crypto" else "درگاه پرداخت"

    if purpose != "order":
        # شارژ کیف پول
        amount = float(credited_row["amount"])
        new_balance = db.add_balance(tg_id, amount)
        cur = credited_row["currency"]
        try:
            await bot.send_message(
                tg_id,
                "✅ پرداخت شما تأیید شد.\n"
                f"💰 مبلغ <b>{amount:g} {cur}</b> به کیف پول شما اضافه شد.\n"
                f"💼 موجودی فعلی: <b>{new_balance:g} {cur}</b>\n"
                f"💳 روش: {method_label}",
            )
        except Exception:  # noqa: BLE001
            logger.warning("اطلاع‌رسانی شارژ به کاربر %s ناموفق بود", tg_id)
        return

    # سفارش محصول
    try:
        meta = json.loads(credited_row["meta"] or "{}")
    except (TypeError, ValueError):
        meta = {}
    product = meta.get("product", "residential")
    usd = float(meta.get("usd", credited_row["amount"] or 0))

    try:
        if product == PRODUCT_V2RAY:
            renew_id = meta.get("renew_config_id")
            if renew_id:
                info = await service.renew_v2ray(int(renew_id), price=usd)
                await bot.send_message(
                    tg_id,
                    "✅ <b>تمدید V2Ray انجام شد</b>\n"
                    f"📦 حجم: <b>نامحدود</b> ♾\n"
                    f"📅 انقضای جدید: {fmt_expiry(info['new_expiry_ms'])} "
                    f"(از همین لحظه {info['days']} روز)\n"
                    f"🆔 سرویس: <code>#{info['config_id']}</code>\n"
                    f"💳 روش: {method_label}",
                )
                _notify_admin_sale(bot, cfg, tg_id, "تمدید V2Ray", usd, method_label)
            else:
                info = await service.provision_v2ray(tg_id, price=usd, payer=method or "paid")
                await _send_v2ray(bot, tg_id, info)
                _notify_admin_sale(bot, cfg, tg_id, "V2Ray یک‌ماهه نامحدود", usd, method_label)
        else:
            res = await service.provision_paid_order(credited_row)
            await bot.send_message(
                tg_id,
                "✅ پرداخت شما تأیید شد و سرویس ساخته شد:\n\n" + provision_message(res),
            )
            _notify_admin_sale(bot, cfg, tg_id, f"رزیدنتال ({product})", usd, method_label)
    except Exception:  # noqa: BLE001
        logger.exception("ساخت سرویس پس از پرداخت ناموفق بود (order=%s)", credited_row["order_id"])
        try:
            await bot.send_message(
                tg_id,
                "✅ پرداخت شما تأیید شد، اما در ساخت خودکار سرویس خطایی رخ داد. "
                "لطفاً چند دقیقه صبر کنید یا به ادمین اطلاع دهید (پرداخت شما ثبت شده است).",
            )
            await bot.send_message(
                cfg.admin_id,
                f"⚠️ پرداخت <code>{escape(str(credited_row['order_id']))}</code> تأیید شد ولی "
                f"ساخت سرویس برای <code>{tg_id}</code> ناموفق بود. دستی بررسی کنید.",
            )
        except Exception:  # noqa: BLE001
            pass


def _notify_admin_sale(
    bot: Any, cfg: Settings, tg_id: int, product_txt: str, usd: float, method_label: str
) -> None:
    """اطلاع فروش به ادمین (بدون توقف مسیر اصلی در صورت خطا)."""
    import asyncio

    async def _send() -> None:
        try:
            await bot.send_message(
                cfg.admin_id,
                "🛒 <b>فروش جدید (پرداخت‌شده)</b>\n"
                f"🧩 محصول: <b>{escape(product_txt)}</b>\n"
                f"👤 کاربر: <code>{tg_id}</code>\n"
                f"💵 مبلغ: <b>{usd:g} USDT</b>\n"
                f"💳 روش: {method_label}",
            )
        except Exception:  # noqa: BLE001
            logger.warning("اطلاع فروش به ادمین ناموفق بود")

    try:
        asyncio.create_task(_send())
    except RuntimeError:
        pass
