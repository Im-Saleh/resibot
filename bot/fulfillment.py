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

from . import digital
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


# سقف کپشن عکس در تلگرام
_CAPTION_LIMIT = 1024


def _v2ray_caption(info: dict[str, Any]) -> str:
    """بخش اصلی و کوتاه پیام (تضمیناً زیر سقف کپشن)."""
    return "\n".join([
        "✅ <b>سرویس V2Ray شما ساخته شد</b>",
        "",
        "📦 حجم: <b>نامحدود</b> ♾",
        f"⏳ اعتبار: <b>{info.get('days', 30)} روز</b>",
        f"📅 انقضا: {fmt_expiry(info.get('expiry_ms', 0))}",
        f"🆔 شناسه سرویس: <code>#{info.get('config_id')}</code>",
        "",
        "🔗 <b>لینک ساب (Subscription):</b>",
        f"<code>{escape(info.get('sub_link', ''))}</code>",
    ])


def _v2ray_links_text(info: dict[str, Any]) -> str:
    links = info.get("vless_links") or []
    if not links:
        return ""
    lines = ["📋 <b>لینک کانفیگ:</b>"]
    for vl in links:
        lines.append(f"<code>{escape(str(vl))}</code>")
    return "\n".join(lines)


async def _send_v2ray(bot: Any, tg_id: int, info: dict[str, Any]) -> None:
    """پیام تحویل V2Ray را همراه با QR (به‌صورت کپشن همان عکس) می‌فرستد.

    اگر متن کامل از سقف کپشن بیشتر شود، لینک‌های کانفیگ در یک پیام بعدی می‌آیند؛
    ولی QR همیشه ضمیمه‌ی پیام اصلی (اطلاعات + لینک ساب) است.
    """
    caption = _v2ray_caption(info)
    links_text = _v2ray_links_text(info)
    full = caption + (("\n\n" + links_text) if links_text else "")
    sub_link = info.get("sub_link", "")
    png = make_qr_png(sub_link) if sub_link else None

    if png:
        from aiogram.types import BufferedInputFile
        photo = BufferedInputFile(png, filename="sub-qr.png")
        try:
            if len(full) <= _CAPTION_LIMIT:
                await bot.send_photo(tg_id, photo, caption=full)
            else:
                await bot.send_photo(tg_id, photo, caption=caption)
                if links_text:
                    await bot.send_message(tg_id, links_text)
            return
        except Exception:  # noqa: BLE001
            logger.warning("ارسال عکس QR به کاربر %s ناموفق بود؛ متن ساده ارسال می‌شود", tg_id)
    # فالبک بدون QR
    await bot.send_message(tg_id, full)


async def send_v2ray_delivery(bot: Any, tg_id: int, info: dict[str, Any]) -> None:
    """تحویل پیام + QR سرویس V2Ray (برای مسیر رایگان ادمین یا فراخوانی مستقیم)."""
    await _send_v2ray(bot, tg_id, info)


async def _deliver_digital(
    bot: Any, cfg: Settings, db: Database, service: Any, tg_id: int,
    slug: str, usd: float, method_label: str, *, order_id: str,
) -> bool:
    """محصول دیجیتال را بر اساس روش تحویلِ تعیین‌شده به مشتری می‌رساند.

    سه روش:
      • link    → یک لینک فعال‌سازی از انبار تحویل می‌شود (مثل عضویت در فمیلی).
      • account → یک اکانت آماده (ایمیل/پسورد/۲FA) از انبار تحویل می‌شود.
      • manual  → از مشتری ایمیل/پسورد گرفته می‌شود و ادمین دستی انجام می‌دهد.

    خروجی True یعنی سفارش «پذیرفته و در جریان تحویل» است (برای manual)، یا تحویل
    از انبار موفق بود. اگر انبار خالی/محصول ناموجود باشد False برمی‌گردد و پول
    ثبت‌شده باقی می‌ماند تا ادمین دستی رسیدگی کند.
    """
    product = db.get_digital_product_by_slug(slug)
    if product is None:
        logger.warning("محصول دیجیتال %s برای تحویل پیدا نشد (order=%s)", slug, order_id)
        await _safe_send(
            bot, cfg.admin_id,
            f"⚠️ پرداخت <code>{escape(order_id)}</code> برای محصول دیجیتال "
            f"<code>{escape(slug)}</code> تأیید شد ولی محصول پیدا نشد. دستی بررسی کنید.",
        )
        return False

    title = product["title"]
    dtype = digital.normalize_delivery(product["delivery_type"])

    # --- روش دستی: اطلاعات از مشتری گرفته می‌شود ---
    if dtype == digital.DELIVERY_MANUAL:
        db.create_manual_order(order_id, int(product["id"]), slug, tg_id)
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="📝 ارسال ایمیل و رمز اکانت", callback_data=f"dgm:info:{order_id}")
        ]])
        await _safe_send(
            bot, tg_id,
            "✅ <b>پرداختت با موفقیت انجام شد!</b> 🎉\n\n"
            f"🧩 محصول: <b>{escape(title)}</b>\n"
            f"💳 روش پرداخت: {method_label}\n\n"
            "برای این محصول لازمه اطلاعات اکانت خودت رو بهمون بدی تا سرویس رو روش فعال کنیم. "
            "روی دکمه‌ی زیر بزن و ایمیل و رمز اکانتت رو بفرست. 👇\n"
            "به‌محض اینکه کار انجام شد، همین‌جا بهت خبر می‌دیم. 🙌",
            reply_markup=kb,
        )
        await _safe_send(
            bot, cfg.admin_id,
            "🆕 <b>سفارش تحویل دستی</b>\n"
            f"🧩 محصول: <b>{escape(title)}</b> (<code>{escape(slug)}</code>)\n"
            f"👤 خریدار: <code>{tg_id}</code>\n"
            f"🧾 سفارش: <code>{escape(order_id)}</code>\n"
            "⏳ منتظر ارسال اطلاعات اکانت از سمت مشتری هستیم.",
        )
        _notify_admin_sale(bot, cfg, tg_id, f"دیجیتال (دستی): {title}", usd, method_label)
        return True

    # --- روش‌های مبتنی بر انبار (link / account) ---
    result = service.deliver_digital(slug, tg_id, order_id)
    if result is None:
        await _safe_send(
            bot, cfg.admin_id,
            f"⚠️ محصول <code>{escape(slug)}</code> پیدا نشد (order {escape(order_id)}).",
        )
        return False

    if result["out_of_stock"] or result["item"] is None:
        await _safe_send(
            bot, tg_id,
            "✅ پرداختت تأیید شد.\n"
            f"🧩 محصول: <b>{escape(title)}</b>\n\n"
            "⏳ موجودی این محصول همین الان تموم شد، ولی نگران نباش — سفارشت ثبت شده و "
            "در سریع‌ترین زمان ممکن به‌صورت دستی برات ارسال می‌شه. اگه عجله داری به پشتیبانی پیام بده. 🙏",
        )
        await _safe_send(
            bot, cfg.admin_id,
            "🛑 <b>موجودی تمام شد!</b>\n"
            f"🧩 محصول: <b>{escape(title)}</b> (<code>{escape(slug)}</code>)\n"
            f"👤 خریدار: <code>{tg_id}</code>\n"
            f"🧾 سفارش: <code>{escape(order_id)}</code>\n"
            f"💵 مبلغ: <b>{usd:g} $</b>\n"
            "لطفاً دستی تحویل بده و انبار رو شارژ کن.",
        )
        return False

    payload = result["item"]["payload"]
    duration = int(product["duration_days"] or 0)
    duration_line = f"⏳ مدت اعتبار: <b>{duration} روز</b>\n" if duration else ""

    if dtype == digital.DELIVERY_LINK:
        body = (
            "🔗 <b>لینک فعال‌سازی شما:</b>\n"
            f"{escape(payload)}\n\n"
            "این لینک رو باز کن و روی گزینه‌ی <b>«پیوستن / فعال‌سازی»</b> بزن. "
            "اشتراک روی همون اکانت خودت فعال می‌شه. ✅"
        )
    else:  # account
        body = (
            "🔐 <b>اطلاعات اکانت شما:</b>\n"
            f"{digital.format_account_payload(payload)}\n\n"
            "این اطلاعات رو جای امنی ذخیره کن. توصیه می‌کنیم بعد از ورود، رمز رو عوض نکن "
            "تا دسترسی قطع نشه."
        )

    await _safe_send(
        bot, tg_id,
        "✅ <b>خریدت با موفقیت انجام شد!</b> 🎉\n\n"
        f"🧩 محصول: <b>{escape(title)}</b>\n"
        f"{duration_line}"
        f"💳 روش پرداخت: {method_label}\n\n"
        f"{body}\n\n"
        "اگه جایی گیر کردی یا سؤالی داشتی، به پشتیبانی پیام بده؛ کنارتیم. 🌟",
    )
    _notify_admin_sale(bot, cfg, tg_id, f"دیجیتال: {title}", usd, method_label)
    return True


async def _safe_send(bot: Any, chat_id: int, text: str, **kwargs: Any) -> None:
    """ارسال پیام با نادیده‌گرفتن خطا (مثلاً وقتی کاربر ربات را بلاک کرده)."""
    try:
        await bot.send_message(chat_id, text, **kwargs)
    except Exception:  # noqa: BLE001
        logger.warning("ارسال پیام به %s ناموفق بود", chat_id)


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

    delivered = False
    try:
        if digital.is_digital_meta(product):
            slug = digital.slug_from_meta(product)
            delivered = await _deliver_digital(
                bot, cfg, db, service, tg_id, slug, usd, method_label,
                order_id=str(credited_row["order_id"]),
            )
        elif product == PRODUCT_V2RAY:
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
        # برای محصول دیجیتال، وضعیت تحویل را همان تابع اختصاصی تعیین کرده است؛
        # برای بقیه محصولات اگر خطایی رخ نداده باشد یعنی تحویل موفق بوده.
        if not digital.is_digital_meta(product):
            delivered = True
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

    # پاداش رفرال (فقط پس از تحویل موفق خرید محصول)
    if delivered:
        try:
            ref = service.credit_referral(tg_id, usd)
            if ref:
                await _notify_referral(bot, ref, tg_id)
        except Exception:  # noqa: BLE001
            logger.warning("واریز پاداش رفرال ناموفق بود")


async def _notify_referral(bot: Any, ref: dict[str, Any], buyer_tg_id: int) -> None:
    """به معرف اطلاع می‌دهد که پاداش رفرال دریافت کرده است."""
    try:
        await bot.send_message(
            int(ref["referrer"]),
            "🎁 <b>پاداش رفرال</b>\n"
            f"یکی از دعوت‌شده‌های شما (<code>{buyer_tg_id}</code>) خرید کرد!\n"
            f"💰 <b>{ref['reward']:g} {ref['currency']}</b> ({ref['percent']:g}%) به کیف پول شما اضافه شد.\n"
            f"💼 موجودی فعلی: <b>{ref['new_balance']:g} {ref['currency']}</b>",
        )
    except Exception:  # noqa: BLE001
        logger.warning("اطلاع پاداش رفرال به معرف ناموفق بود")


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
