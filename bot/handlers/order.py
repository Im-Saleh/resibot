"""فلوی ثبت سفارش جدید (مشترک بین ادمین و نماینده).

از دو محصول رزیدنتال پشتیبانی می‌کند:
  - رزیدنتال (SmartProxy): کشور → استان → شهر → زمان تعویض IP (تا ۲۴ ساعت)
  - رزیدنتال ۲ (IPRoyal):  کشور → شهر → زمان تعویض IP (تا ۷ روز)
انتخاب لوکیشن و بازه‌ی زمانی بر اساس محصولِ ذخیره‌شده در state تعیین می‌شود.
"""
from __future__ import annotations

import logging
from html import escape

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from .. import countries, iproyal_locations, locations
from ..config import Settings
from ..database import (
    PRODUCT_RESIDENTIAL,
    PRODUCT_RESIDENTIAL2,
    ROLE_ADMIN,
    ROLE_RESIDENTIAL_RESELLER,
)
from ..keyboards import (
    LIFE_PRESETS_RES2,
    confirm_purchase_keyboard,
    country_keyboard,
    country_results_keyboard,
    life_keyboard,
    options_keyboard,
    pay_methods_keyboard,
)
from ..proxy import ProxyLocation, normalize_code, validate_code
from ..service import InsufficientBalance, Service
from ..states import OrderStates
from ..utils import provision_message

logger = logging.getLogger("resibot.order")
router = Router(name="order")


def _is_res2(data: dict) -> bool:
    return data.get("product") == PRODUCT_RESIDENTIAL2


def _max_life(product: str) -> int:
    return Service.max_life_for(product)


# ---------------------------------------------------------------------- #
#  شروع سفارش از منوی محصولات
# ---------------------------------------------------------------------- #
async def _start_residential(call: CallbackQuery, state: FSMContext, product: str, service: Service) -> None:
    if not service.product_enabled(product):
        await call.answer("این محصول در حال حاضر غیرفعال است.", show_alert=True)
        return
    await state.clear()
    await state.set_state(OrderStates.choosing_country)
    await state.update_data(product=product)
    await call.answer()
    if product == PRODUCT_RESIDENTIAL2:
        kb = country_keyboard("ord_country", popular=iproyal_locations.popular())
    else:
        kb = country_keyboard("ord_country")
    await call.message.answer("🌍 لطفاً کشور (لوکیشن) موردنظر را انتخاب کنید:", reply_markup=kb)


@router.callback_query(F.data == "buy:residential")
async def buy_residential(call: CallbackQuery, state: FSMContext, service: Service) -> None:
    await _start_residential(call, state, PRODUCT_RESIDENTIAL, service)


@router.callback_query(F.data == "buy:residential2")
async def buy_residential2(call: CallbackQuery, state: FSMContext, service: Service) -> None:
    await _start_residential(call, state, PRODUCT_RESIDENTIAL2, service)


@router.callback_query(F.data == "buy:v2ray")
async def buy_v2ray(
    call: CallbackQuery, service: Service, cfg: Settings, role: str, is_admin: bool
) -> None:
    await call.answer()
    if not service.product_enabled("v2ray"):
        await call.message.answer("🛡 محصول V2Ray در حال حاضر غیرفعال است.")
        return

    # ادمین: ساخت فوری و رایگان
    if is_admin:
        wait = await call.message.answer("⏳ در حال ساخت سرویس V2Ray (نامحدود)...")
        try:
            info = await service.provision_v2ray(call.from_user.id, price=0.0, payer="admin")
        except Exception as exc:  # noqa: BLE001
            logger.exception("v2ray provision (admin) failed")
            await wait.edit_text(f"❌ خطا در ساخت سرویس V2Ray:\n<code>{exc}</code>")
            return
        await wait.delete()
        from ..fulfillment import send_v2ray_delivery
        await send_v2ray_delivery(call.bot, call.from_user.id, info)
        return

    methods = service.enabled_pay_methods()
    if not methods:
        await call.message.answer("⛔️ در حال حاضر هیچ روش پرداختی فعال نیست. با ادمین هماهنگ کنید.")
        return
    price = service.v2ray_plan_price_for_user(call.from_user.id, role)
    if price <= 0:
        await call.message.answer("⛔️ قیمت پلن V2Ray تنظیم نشده است. با ادمین هماهنگ کنید.")
        return
    order_id = service.create_order_payment(
        call.from_user.id, product="v2ray", usd=price, meta_extra={}
    )
    await call.message.answer(
        "🛡 <b>پلن V2Ray — یک‌ماهه نامحدود</b>\n\n"
        "📦 حجم: <b>نامحدود</b> ♾\n"
        f"⏳ مدت: <b>{service.v2ray_plan_days} روز</b>\n"
        f"💵 مبلغ: <b>{price:g} USDT</b>\n\n"
        "روش پرداخت را انتخاب کنید:",
        reply_markup=pay_methods_keyboard(order_id, methods),
    )


@router.callback_query(F.data == "ord_cancel")
async def order_cancel(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await call.answer("لغو شد.")
    await call.message.edit_text("❌ سفارش لغو شد.")


# ---------------------------------------------------------------------- #
#  انتخاب کشور
# ---------------------------------------------------------------------- #
@router.callback_query(
    StateFilter(OrderStates.choosing_country, OrderStates.searching_country),
    F.data.startswith("ord_country:"),
)
async def order_country(call: CallbackQuery, state: FSMContext, service: Service) -> None:
    value = call.data.split(":", 1)[1]
    await call.answer()
    if value == "__custom__":
        await state.set_state(OrderStates.entering_country)
        await call.message.answer("کد کشور را وارد کنید (مثلاً US یا GB):")
        return
    if value == "__search__":
        await state.set_state(OrderStates.searching_country)
        await call.message.answer("🔍 نام یا کد کشور را بفرستید (مثلاً: Germany یا DE):")
        return
    area = "" if value == "__skip__" else value
    await state.update_data(area=area)
    await _ask_state(call.message, state, service)


@router.message(OrderStates.searching_country)
async def order_country_search(message: Message, state: FSMContext) -> None:
    results = countries.search(message.text or "")
    if not results:
        await message.answer("کشوری پیدا نشد. دوباره نام یا کد کشور را بفرستید:")
        return
    await message.answer(
        "یکی را انتخاب کنید:",
        reply_markup=country_results_keyboard("ord_country", results),
    )


@router.message(OrderStates.entering_country)
async def order_country_text(message: Message, state: FSMContext, service: Service) -> None:
    code = normalize_code(message.text or "")
    if not validate_code(code) or not code:
        await message.answer("⛔️ کد نامعتبر است. فقط حروف/عدد/خط‌تیره. دوباره بفرستید:")
        return
    await state.update_data(area=code)
    await _ask_state(message, state, service)


# ---------------------------------------------------------------------- #
#  انتخاب استان (state) از لیست — فقط رزیدنتال ۱
# ---------------------------------------------------------------------- #
async def _ask_state(message: Message, state: FSMContext, service: Service) -> None:
    data = await state.get_data()
    area = data.get("area", "")
    # رزیدنتال ۲ (IPRoyal) لایه‌ی استان ندارد؛ مستقیم به انتخاب شهر می‌رود
    if _is_res2(data):
        await state.update_data(state="")
        await _ask_city(message, state, service)
        return
    if locations.has_states(area):
        await state.set_state(OrderStates.choosing_state)
        await message.answer(
            f"🗺 استان موردنظر در {countries.display_name(area)} را انتخاب کنید:",
            reply_markup=options_keyboard("ord_state", locations.states(area)),
        )
    else:
        await state.update_data(state="", city="")
        await _ask_life(message, state, service)


@router.callback_query(OrderStates.choosing_state, F.data.startswith("ord_state:"))
async def order_state(call: CallbackQuery, state: FSMContext, service: Service) -> None:
    value = call.data.split(":", 1)[1]
    await call.answer()
    st = "" if value == "__rand__" else value
    await state.update_data(state=st)
    await _ask_city(call.message, state, service)


# ---------------------------------------------------------------------- #
#  انتخاب شهر (city) از لیست
# ---------------------------------------------------------------------- #
async def _ask_city(message: Message, state: FSMContext, service: Service) -> None:
    data = await state.get_data()
    area = data.get("area", "")
    st = data.get("state", "")
    if _is_res2(data):
        city_list = iproyal_locations.cities(area) if area else []
    else:
        city_list = locations.cities(area, st) if st else []
    if city_list:
        await state.set_state(OrderStates.choosing_city)
        loc_label = countries.display_name(area) if _is_res2(data) else locations.prettify(st)
        await message.answer(
            f"🏙 شهر موردنظر در {loc_label} را انتخاب کنید:",
            reply_markup=options_keyboard("ord_city", city_list),
        )
    else:
        await state.update_data(city="")
        await _ask_life(message, state, service)


@router.callback_query(OrderStates.choosing_city, F.data.startswith("ord_city:"))
async def order_city(call: CallbackQuery, state: FSMContext, service: Service) -> None:
    value = call.data.split(":", 1)[1]
    await call.answer()
    city = "" if value == "__rand__" else value
    await state.update_data(city=city)
    await _ask_life(call.message, state, service)


# ---------------------------------------------------------------------- #
#  انتخاب زمان تعویض IP (life)
# ---------------------------------------------------------------------- #
async def _ask_life(message: Message, state: FSMContext, service: Service) -> None:
    data = await state.get_data()
    await state.set_state(OrderStates.choosing_life)
    if _is_res2(data):
        max_h = _max_life(PRODUCT_RESIDENTIAL2) // 60
        await message.answer(
            "⏱ هر چند وقت یک‌بار IP خودکار عوض شود؟\n"
            f"(«بدون تعویض خودکار» یا مقداری بین ۱ تا {max_h*60} دقیقه — حداکثر ۷ روز)",
            reply_markup=life_keyboard("ord_life", presets=LIFE_PRESETS_RES2),
        )
    else:
        await message.answer(
            "⏱ هر چند وقت یک‌بار IP خودکار عوض شود؟\n"
            "(می‌توانید «بدون تعویض خودکار» یا یک مقدار دلخواه بین ۱ تا ۱۴۴۰ دقیقه انتخاب کنید)",
            reply_markup=life_keyboard("ord_life"),
        )


@router.callback_query(OrderStates.choosing_life, F.data.startswith("ord_life:"))
async def order_life(call: CallbackQuery, state: FSMContext, service: Service) -> None:
    value = call.data.split(":", 1)[1]
    await call.answer()
    if value == "__custom__":
        await state.set_state(OrderStates.entering_life)
        data = await state.get_data()
        max_min = _max_life(data.get("product", PRODUCT_RESIDENTIAL))
        await call.message.answer(f"عدد دلخواه را بفرستید (دقیقه، بین ۱ تا {max_min}):")
        return
    try:
        life = int(value)
    except ValueError:
        life = 0
    await state.update_data(life=life)
    await _ask_volume(call.message, state, service)


@router.message(OrderStates.entering_life)
async def order_life_text(message: Message, state: FSMContext, service: Service) -> None:
    data = await state.get_data()
    max_min = _max_life(data.get("product", PRODUCT_RESIDENTIAL))
    text = (message.text or "").strip()
    if not text.isdigit() or not (1 <= int(text) <= max_min):
        await message.answer(f"⛔️ یک عدد بین ۱ تا {max_min} بفرستید:")
        return
    await state.update_data(life=int(text))
    await _ask_volume(message, state, service)


async def _ask_volume(message: Message, state: FSMContext, service: Service) -> None:
    await state.set_state(OrderStates.entering_volume)
    await message.answer(
        f"📦 حجم موردنظر را به گیگابایت وارد کنید:\n"
        f"• حداقل خرید: <b>{service.min_volume_gb} GB</b> (سقف ندارد)\n"
        f"• مدت اعتبار: <b>{service.cfg.config_duration_days} روز</b>"
    )


# ---------------------------------------------------------------------- #
#  حجم → تأیید (با قیمت بر اساس نقش)
# ---------------------------------------------------------------------- #
@router.message(OrderStates.entering_volume)
async def order_volume(message: Message, state: FSMContext, service: Service, role: str) -> None:
    text = (message.text or "").strip()
    if not text.isdigit():
        await message.answer("⛔️ لطفاً فقط یک عدد صحیح (گیگابایت) بفرستید:")
        return
    volume = int(text)
    if volume < service.min_volume_gb:
        await message.answer(
            f"⛔️ حداقل حجم خرید <b>{service.min_volume_gb} GB</b> است. عدد بزرگتری بفرستید:"
        )
        return
    if volume > 100000:
        await message.answer("⛔️ حجم بیش از حد بزرگ است.")
        return

    data = await state.get_data()
    product = data.get("product", PRODUCT_RESIDENTIAL)
    await state.update_data(volume=volume)
    await state.set_state(OrderStates.confirming)

    price = service.quote_for(message.from_user.id, role, product, volume)
    payer = service._payer_for(role, product)
    cur = service.product_currency(product)
    loc_txt = _loc_text(data)
    life = data.get("life", None)
    life_txt = "بدون تعویض خودکار" if not life else f"هر {life} دقیقه"
    product_txt = "رزیدنتال ۲" if product == PRODUCT_RESIDENTIAL2 else "رزیدنتال"

    if payer == "postpaid":
        pay_line = "💳 پرداخت: <b>پس‌پرداخت</b> (تسویه با ادمین)"
    elif payer == "admin":
        pay_line = "💳 پرداخت: <b>رایگان (ادمین)</b>"
    elif payer == "nowpayments":
        pay_line = "💳 پرداخت: <b>آنلاین (USDT)</b> — روش پرداخت را پس از تأیید انتخاب می‌کنید"
    else:
        bal = service.db.get_balance(message.from_user.id)
        pay_line = f"💳 پرداخت: از کیف پول | موجودی شما: <b>{bal:g} {service.currency}</b>"

    await message.answer(
        "🧾 <b>خلاصه‌ی سفارش</b>\n\n"
        f"🧩 محصول: <b>{product_txt}</b>\n"
        f"🌍 لوکیشن: {loc_txt}\n"
        f"⏱ تعویض IP: {life_txt}\n"
        f"📦 حجم: <b>{volume} GB</b>\n"
        f"⏳ مدت: <b>{service.cfg.config_duration_days} روز</b>\n"
        f"💵 مبلغ: <b>{price:g} {cur}</b>\n"
        f"{pay_line}",
        reply_markup=confirm_purchase_keyboard(),
    )


def _loc_text(data: dict) -> str:
    parts = []
    if data.get("area"):
        parts.append(f"کشور {data['area']}")
    if data.get("state"):
        parts.append(f"استان {locations.prettify(data['state'])}")
    if data.get("city"):
        parts.append(f"شهر {locations.prettify(data['city'])}")
    return " | ".join(parts) if parts else "تصادفی"


@router.callback_query(OrderStates.confirming, F.data == "ord_confirm")
async def order_confirm(call: CallbackQuery, state: FSMContext, service: Service, cfg: Settings, role: str) -> None:
    data = await state.get_data()
    await state.clear()
    await call.answer()
    volume = int(data.get("volume", 0))
    product = data.get("product", PRODUCT_RESIDENTIAL)
    location = ProxyLocation(
        area=data.get("area", ""),
        state=data.get("state", ""),
        city=data.get("city", ""),
    )
    life = data.get("life", None)
    payer = service._payer_for(role, product)
    product_txt = "رزیدنتال ۲" if product == PRODUCT_RESIDENTIAL2 else "رزیدنتال"

    # کاربر عادی غیرهمکار: انتخاب روش پرداخت (اول پرداخت، بعد ساخت خودکار)
    if payer == "nowpayments":
        methods = service.enabled_pay_methods()
        if not methods:
            await call.message.answer("⛔️ در حال حاضر هیچ روش پرداختی فعال نیست. با ادمین هماهنگ کنید.")
            return
        try:
            price_usd = service.quote_for(call.from_user.id, role, product, volume)
            order_id = service.create_order_payment(
                call.from_user.id,
                product=product,
                usd=price_usd,
                meta_extra={
                    "area": location.area, "state": location.state, "city": location.city,
                    "life": int(life or 0), "volume": int(volume),
                },
            )
        except ValueError as exc:
            await call.message.answer(f"⛔️ {escape(str(exc))}")
            return
        except Exception as exc:  # noqa: BLE001
            logger.exception("create order failed")
            await call.message.answer(f"❌ خطا در ساخت سفارش:\n<code>{escape(str(exc))}</code>")
            return
        await call.message.answer(
            f"🧾 <b>فاکتور {product_txt}</b>\n"
            f"📦 حجم: <b>{volume} GB</b>\n"
            f"💵 مبلغ: <b>{price_usd:g} USDT</b>\n\n"
            "روش پرداخت را انتخاب کنید:",
            reply_markup=pay_methods_keyboard(order_id, methods),
        )
        return

    # ادمین (رایگان) یا همکار رزیدنتال (پس‌پرداخت): ساخت فوری
    wait = await call.message.answer("⏳ در حال ساخت سرویس... لطفاً چند لحظه صبر کنید.")
    try:
        result = await service.purchase_residential(
            call.from_user.id, role, location, volume, life, product=product
        )
    except ValueError as exc:
        await wait.edit_text(f"⛔️ {exc}")
        return
    except Exception as exc:  # noqa: BLE001
        logger.exception("provision failed")
        await wait.edit_text(f"❌ خطا در ساخت سرویس:\n<code>{exc}</code>")
        return

    await wait.delete()
    await call.message.answer(provision_message(result))

    if call.from_user.id != cfg.admin_id:
        u = call.from_user
        uname = f"@{u.username}" if u.username else (u.full_name or "—")
        cur = service.product_currency(product)
        pay_note = {"postpaid": "پس‌پرداخت", "admin": "ادمین"}.get(payer, payer)
        try:
            await call.bot.send_message(
                cfg.admin_id,
                "🛒 <b>سفارش جدید</b>\n"
                f"🧩 محصول: <b>{product_txt}</b>\n"
                f"👤 کاربر: {escape(uname)} (<code>{u.id}</code>)\n"
                f"📦 حجم: <b>{result.volume_gb} GB</b>\n"
                f"💵 مبلغ: <b>{result.price:g} {cur}</b> ({pay_note})\n"
                f"🆔 سرویس: <code>#{result.config_id}</code>",
            )
        except Exception:  # noqa: BLE001
            logger.warning("notify admin failed")
