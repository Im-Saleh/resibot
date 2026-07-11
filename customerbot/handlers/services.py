"""هندلرهای سرویس‌ها در ربات کمکی مشتری.

قابلیت‌ها (برای سرویس‌هایی که همکار به این مشتری سپرده است):
  - لیست سرویس‌ها، تغییر IP، اطلاعات IP، مصرف، تست اتصال، لینک‌ها
  - تغییر کشور/استان/شهر (رزیدنتال و رزیدنتال ۲/IPRoyal)
  - تنظیم زمان تعویض خودکار IP (تا ۲۴ ساعت برای رزیدنتال، تا ۷ روز برای رزیدنتال ۲)
"""
from __future__ import annotations

import logging
from html import escape

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot import countries, iproyal_locations, locations
from bot.database import Database
from bot.keyboards import (
    LIFE_PRESETS_RES2,
    country_keyboard,
    country_results_keyboard,
    life_keyboard,
    options_keyboard,
)
from bot.proxy import normalize_code, validate_code
from bot.service import Service
from bot.utils import config_summary, fmt_bytes, fmt_expiry, life_str

from ..keyboards import main_menu, service_actions, services_keyboard
from ..states import CustomerLifeStates, CustomerLocationStates

logger = logging.getLogger("customerbot.services")
router = Router(name="cust_services")


def _get_customer_config(config_id: int, customer_id: int, db: Database):
    """دریافت کانفیگ فقط اگر همکار/مالک، آن را صریحاً به این مشتری سپرده باشد."""
    return db.get_config_for_customer(config_id, customer_id)


def _is_res2(row) -> bool:
    return (row["product_type"] or "residential") == "residential2"


# ------------------------------------------------------------------ #
#  لیست سرویس‌ها
# ------------------------------------------------------------------ #
@router.message(F.text == "📋 سرویس‌های من")
async def my_services(message: Message, db: Database, customer_id: int) -> None:
    rows = db.list_configs_by_customer(customer_id)
    if not rows:
        await message.answer(
            "در حال حاضر هیچ سرویسی برای شما تعریف نشده است.\n"
            "برای فعال‌سازی، با همکارتان تماس بگیرید.",
            reply_markup=main_menu(),
        )
        return
    await message.answer(
        f"📋 <b>سرویس‌های شما</b> ({len(rows)} عدد):\nیکی را انتخاب کنید:",
        reply_markup=services_keyboard(rows[:50]),
    )


@router.callback_query(F.data == "cs_back")
async def back_to_list(call: CallbackQuery, db: Database, customer_id: int) -> None:
    await call.answer()
    rows = db.list_configs_by_customer(customer_id)
    if not rows:
        await call.message.edit_text("سرویسی برای شما تعریف نشده است.")
        return
    await call.message.edit_text(
        f"📋 <b>سرویس‌های شما</b> ({len(rows)} عدد):\nیکی را انتخاب کنید:",
        reply_markup=services_keyboard(rows[:50]),
    )


@router.callback_query(F.data.startswith("cs_open:"))
async def open_service(call: CallbackQuery, db: Database, customer_id: int) -> None:
    config_id = int(call.data.split(":", 1)[1])
    row = _get_customer_config(config_id, customer_id, db)
    if not row:
        await call.answer("سرویس پیدا نشد یا دسترسی ندارید.", show_alert=True)
        return
    await call.answer()
    await call.message.edit_text(
        config_summary(row, show_owner=False),
        reply_markup=service_actions(config_id),
    )


# ------------------------------------------------------------------ #
#  تغییر IP
# ------------------------------------------------------------------ #
@router.callback_query(F.data.startswith("cs_ip:"))
async def change_ip(call: CallbackQuery, service: Service, db: Database, customer_id: int) -> None:
    config_id = int(call.data.split(":", 1)[1])
    row = _get_customer_config(config_id, customer_id, db)
    if not row:
        await call.answer("سرویس پیدا نشد یا دسترسی ندارید.", show_alert=True)
        return
    await call.answer("در حال تغییر IP...")
    msg = await call.message.answer("⏳ در حال تغییر IP، لطفاً صبر کنید...")
    try:
        new_session = await service.change_ip(config_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("change_ip failed for config %s", config_id)
        await msg.edit_text(f"❌ خطا در تغییر IP:\n<code>{escape(str(exc))}</code>")
        return
    await msg.edit_text(
        f"✅ <b>IP با موفقیت تغییر کرد!</b>\n\n"
        f"🔑 Session جدید: <code>{escape(new_session)}</code>\n\n"
        "چند ثانیه صبر کنید تا IP جدید فعال شود."
    )


# ------------------------------------------------------------------ #
#  اطلاعات IP فعلی
# ------------------------------------------------------------------ #
@router.callback_query(F.data.startswith("cs_info:"))
async def ip_info(call: CallbackQuery, db: Database, customer_id: int) -> None:
    config_id = int(call.data.split(":", 1)[1])
    row = _get_customer_config(config_id, customer_id, db)
    if not row:
        await call.answer("سرویس پیدا نشد یا دسترسی ندارید.", show_alert=True)
        return
    await call.answer()
    area = row["area"] or "تصادفی"
    state = row["state"] or "تصادفی"
    city = row["city"] or "تصادفی"
    session = row["session"] or "—"
    life = int(row["life"] or 0)
    text = (
        f"🌍 <b>اطلاعات IP سرویس #{config_id}</b>\n\n"
        f"🏳 کشور: <b>{escape(area)}</b>\n"
        f"🗺 استان: <b>{escape(state)}</b>\n"
        f"🏙 شهر: <b>{escape(city)}</b>\n"
        f"🔑 Session: <code>{escape(session)}</code>\n"
        f"⏱ تعویض خودکار: <b>{life_str(life)}</b>\n\n"
        "💡 برای تغییر IP دکمه «🔄 تغییر IP» را بزنید."
    )
    await call.message.answer(text)


# ------------------------------------------------------------------ #
#  مصرف سرویس
# ------------------------------------------------------------------ #
@router.callback_query(F.data.startswith("cs_usage:"))
async def show_usage(call: CallbackQuery, service: Service, db: Database, customer_id: int) -> None:
    config_id = int(call.data.split(":", 1)[1])
    row = _get_customer_config(config_id, customer_id, db)
    if not row:
        await call.answer("سرویس پیدا نشد یا دسترسی ندارید.", show_alert=True)
        return
    await call.answer("در حال دریافت اطلاعات مصرف...")
    try:
        traffic = await service.get_traffic(row["client_email"])
    except Exception as exc:  # noqa: BLE001
        logger.exception("get_traffic failed for config %s", config_id)
        await call.message.answer(f"❌ خطا در دریافت اطلاعات مصرف:\n<code>{escape(str(exc))}</code>")
        return
    up = int(traffic.get("up", 0) or 0)
    down = int(traffic.get("down", 0) or 0)
    total = int(traffic.get("total", 0) or 0)
    used = up + down
    remaining = max(0, total - used) if total else 0
    quota = fmt_bytes(total) if total else "نامحدود"
    remaining_txt = fmt_bytes(remaining) if total else "نامحدود"
    expiry_ms = int(traffic.get("expiryTime", row["expiry_ms"]) or row["expiry_ms"])
    text = (
        f"📊 <b>مصرف سرویس #{config_id}</b>\n\n"
        f"⬆️ آپلود: <b>{fmt_bytes(up)}</b>\n"
        f"⬇️ دانلود: <b>{fmt_bytes(down)}</b>\n"
        f"📈 مجموع مصرف: <b>{fmt_bytes(used)}</b>\n"
        f"📦 سهمیه کل: <b>{quota}</b>\n"
        f"💾 باقیمانده: <b>{remaining_txt}</b>\n"
        f"⏳ انقضا: <b>{fmt_expiry(expiry_ms)}</b>"
    )
    await call.message.answer(text)


# ------------------------------------------------------------------ #
#  تست اتصال
# ------------------------------------------------------------------ #
@router.callback_query(F.data.startswith("cs_ping:"))
async def ping_service(call: CallbackQuery, service: Service, db: Database, customer_id: int) -> None:
    config_id = int(call.data.split(":", 1)[1])
    row = _get_customer_config(config_id, customer_id, db)
    if not row:
        await call.answer("سرویس پیدا نشد یا دسترسی ندارید.", show_alert=True)
        return
    await call.answer("در حال تست اتصال...")
    msg = await call.message.answer("📡 در حال تست اتصال سرویس...")
    try:
        res = await service.test_outbound_for(config_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("ping failed for config %s", config_id)
        await msg.edit_text(f"❌ خطا در تست اتصال:\n<code>{escape(str(exc))}</code>")
        return
    ok = bool(res.get("success"))
    delay = res.get("delay")
    if ok:
        await msg.edit_text(f"✅ <b>اتصال برقرار است!</b>\n⏱ تأخیر: <b>{delay} ms</b>")
    else:
        await msg.edit_text(
            "⚠️ اتصال ناموفق بود.\n\n"
            "💡 پیشنهاد: دکمه «🔄 تغییر IP» را بزنید تا IP جدیدی اختصاص یابد."
        )


# ------------------------------------------------------------------ #
#  لینک‌های سرویس
# ------------------------------------------------------------------ #
@router.callback_query(F.data.startswith("cs_links:"))
async def show_links(call: CallbackQuery, service: Service, db: Database, customer_id: int) -> None:
    config_id = int(call.data.split(":", 1)[1])
    row = _get_customer_config(config_id, customer_id, db)
    if not row:
        await call.answer("سرویس پیدا نشد یا دسترسی ندارید.", show_alert=True)
        return
    await call.answer("در حال دریافت لینک‌ها...")
    try:
        sub_link, vless_links = await service.config_links(row)
    except Exception as exc:  # noqa: BLE001
        logger.exception("config_links failed for config %s", config_id)
        await call.message.answer(f"❌ خطا در دریافت لینک‌ها:\n<code>{escape(str(exc))}</code>")
        return
    lines = [
        f"🔗 <b>لینک‌های سرویس #{config_id}</b>\n",
        "📡 <b>لینک ساب (Subscription):</b>",
        f"<code>{escape(sub_link)}</code>",
    ]
    if vless_links:
        lines.append("\n📋 <b>لینک مستقیم VLESS:</b>")
        for vl in vless_links:
            lines.append(f"<code>{escape(vl)}</code>")
    lines.append("\n💡 لینک ساب را در اپلیکیشن خود import کنید تا بصورت خودکار به‌روز شود.")
    await call.message.answer("\n".join(lines))


# ====================================================================== #
#  تغییر کشور / استان / شهر (کامل، با انتخاب از لیست، مثل ربات اصلی)
# ====================================================================== #
@router.callback_query(F.data.startswith("cs_loc:"))
async def loc_start(call: CallbackQuery, state: FSMContext, db: Database, customer_id: int) -> None:
    config_id = int(call.data.split(":", 1)[1])
    row = _get_customer_config(config_id, customer_id, db)
    if not row:
        await call.answer("سرویس پیدا نشد یا دسترسی ندارید.", show_alert=True)
        return
    await call.answer()
    await state.clear()
    product = row["product_type"] or "residential"
    await state.set_state(CustomerLocationStates.choosing_country)
    await state.update_data(config_id=config_id, product=product)
    if product == "residential2":
        kb = country_keyboard("csloc_country", popular=iproyal_locations.popular())
    else:
        kb = country_keyboard("csloc_country")
    await call.message.answer("🌍 کشور جدید را انتخاب کنید:", reply_markup=kb)


@router.callback_query(
    StateFilter(CustomerLocationStates.choosing_country, CustomerLocationStates.searching_country),
    F.data.startswith("csloc_country:"),
)
async def loc_country(call: CallbackQuery, state: FSMContext, service: Service) -> None:
    value = call.data.split(":", 1)[1]
    await call.answer()
    if value == "__custom__":
        await state.set_state(CustomerLocationStates.entering_country)
        await call.message.answer("کد کشور را وارد کنید (مثلاً US):")
        return
    if value == "__search__":
        await state.set_state(CustomerLocationStates.searching_country)
        await call.message.answer("🔍 نام یا کد کشور را بفرستید (مثلاً: Germany یا DE):")
        return
    area = "" if value == "__skip__" else value
    await state.update_data(area=area)
    await _loc_ask_state(call.message, state, service)


@router.message(CustomerLocationStates.searching_country)
async def loc_country_search(message: Message, state: FSMContext) -> None:
    results = countries.search(message.text or "")
    if not results:
        await message.answer("کشوری پیدا نشد. دوباره نام یا کد کشور را بفرستید:")
        return
    await message.answer(
        "یکی را انتخاب کنید:",
        reply_markup=country_results_keyboard("csloc_country", results),
    )


@router.message(CustomerLocationStates.entering_country)
async def loc_country_text(message: Message, state: FSMContext, service: Service) -> None:
    code = normalize_code(message.text or "")
    if not validate_code(code) or not code:
        await message.answer("⛔️ کد نامعتبر است. دوباره بفرستید:")
        return
    await state.update_data(area=code)
    await _loc_ask_state(message, state, service)


async def _loc_ask_state(message: Message, state: FSMContext, service: Service) -> None:
    data = await state.get_data()
    area = data.get("area", "")
    if data.get("product") == "residential2":
        await state.update_data(state="")
        await _loc_ask_city(message, state, service)
        return
    if locations.has_states(area):
        await state.set_state(CustomerLocationStates.choosing_state)
        await message.answer(
            f"🗺 استان موردنظر در {countries.display_name(area)} را انتخاب کنید:",
            reply_markup=options_keyboard("csloc_state", locations.states(area)),
        )
    else:
        await state.update_data(state="", city="")
        await _loc_finish(message, state, service)


@router.callback_query(CustomerLocationStates.choosing_state, F.data.startswith("csloc_state:"))
async def loc_state(call: CallbackQuery, state: FSMContext, service: Service) -> None:
    value = call.data.split(":", 1)[1]
    await call.answer()
    st = "" if value == "__rand__" else value
    await state.update_data(state=st)
    await _loc_ask_city(call.message, state, service)


async def _loc_ask_city(message: Message, state: FSMContext, service: Service) -> None:
    data = await state.get_data()
    area = data.get("area", "")
    st = data.get("state", "")
    if data.get("product") == "residential2":
        city_list = iproyal_locations.cities(area) if area else []
        loc_label = countries.display_name(area)
    else:
        city_list = locations.cities(area, st) if st else []
        loc_label = locations.prettify(st)
    if city_list:
        await state.set_state(CustomerLocationStates.choosing_city)
        await message.answer(
            f"🏙 شهر موردنظر در {loc_label} را انتخاب کنید:",
            reply_markup=options_keyboard("csloc_city", city_list),
        )
    else:
        await state.update_data(city="")
        await _loc_finish(message, state, service)


@router.callback_query(CustomerLocationStates.choosing_city, F.data.startswith("csloc_city:"))
async def loc_city(call: CallbackQuery, state: FSMContext, service: Service) -> None:
    value = call.data.split(":", 1)[1]
    await call.answer()
    city = "" if value == "__rand__" else value
    await state.update_data(city=city)
    await _loc_finish(call.message, state, service)


async def _loc_finish(message: Message, state: FSMContext, service: Service) -> None:
    """اعمال نهایی تغییر لوکیشن.

    نکته‌ی امنیتی: config_id از خودِ state خوانده می‌شود که فقط توسط loc_start
    (بعد از تأیید مالکیت مشتری) مقداردهی شده است؛ بنابراین این تابع نیازی به
    بررسی مجدد customer_id ندارد — دسترسی از قبل احراز شده.
    """
    data = await state.get_data()
    await state.clear()
    config_id = int(data.get("config_id", 0))
    msg = await message.answer("⏳ در حال تغییر لوکیشن...")
    try:
        loc = await service.change_location(
            config_id,
            area=data.get("area", ""),
            state=data.get("state", ""),
            city=data.get("city", ""),
            regenerate_session=True,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("change_location failed for config %s", config_id)
        await msg.edit_text(f"❌ خطا در تغییر لوکیشن:\n<code>{escape(str(exc))}</code>")
        return
    loc_text = " | ".join(
        p for p in [
            f"کشور: {loc.area}" if loc.area else "",
            f"استان: {locations.prettify(loc.state)}" if loc.state else "",
            f"شهر: {locations.prettify(loc.city)}" if loc.city else "",
        ] if p
    ) or "تصادفی"
    await msg.edit_text(
        f"✅ لوکیشن تغییر کرد.\n🌍 {loc_text}\n🔑 session: <code>{escape(loc.session)}</code>"
    )


# ====================================================================== #
#  زمان تعویض خودکار IP (life)
# ====================================================================== #
@router.callback_query(F.data.startswith("cs_life:"))
async def life_pick(call: CallbackQuery, db: Database, customer_id: int) -> None:
    config_id = int(call.data.split(":", 1)[1])
    row = _get_customer_config(config_id, customer_id, db)
    if not row:
        await call.answer("سرویس پیدا نشد یا دسترسی ندارید.", show_alert=True)
        return
    current = int(row["life"] or 0)
    cur_txt = "بدون تعویض خودکار" if current <= 0 else f"هر {current} دقیقه"
    presets = LIFE_PRESETS_RES2 if _is_res2(row) else None
    await call.answer()
    await call.message.answer(
        f"⏱ زمان تعویض خودکار IP (فعلی: <b>{cur_txt}</b>) را انتخاب کنید:",
        reply_markup=life_keyboard(f"csl:{config_id}", presets=presets),
    )


@router.callback_query(F.data.startswith("csl:"))
async def life_set(
    call: CallbackQuery, state: FSMContext, service: Service, db: Database, customer_id: int
) -> None:
    _, sid, value = call.data.split(":", 2)
    config_id = int(sid)
    row = _get_customer_config(config_id, customer_id, db)
    if not row:
        await call.answer("دسترسی ندارید.", show_alert=True)
        return
    if value == "__custom__":
        await state.set_state(CustomerLifeStates.entering_life)
        await state.update_data(config_id=config_id)
        max_min = Service.max_life_for(row["product_type"] or "residential")
        await call.answer()
        await call.message.answer(f"عدد دلخواه را بفرستید (دقیقه، بین ۱ تا {max_min}):")
        return
    await call.answer("در حال اعمال...")
    msg = await call.message.answer("⏳ در حال تنظیم زمان تعویض IP...")
    try:
        life = await service.set_life(config_id, int(value))
    except Exception as exc:  # noqa: BLE001
        logger.exception("set_life failed for config %s", config_id)
        await msg.edit_text(f"❌ خطا:\n<code>{escape(str(exc))}</code>")
        return
    txt = "بدون تعویض خودکار (تا تغییر دستی ثابت می‌ماند)" if life <= 0 else f"هر <b>{life}</b> دقیقه"
    await msg.edit_text(f"✅ زمان تعویض IP تنظیم شد: {txt}")


@router.message(CustomerLifeStates.entering_life)
async def life_custom(
    message: Message, state: FSMContext, service: Service, db: Database, customer_id: int
) -> None:
    data = await state.get_data()
    config_id = int(data.get("config_id", 0))
    row = _get_customer_config(config_id, customer_id, db)
    if not row:
        await state.clear()
        await message.answer("⛔️ دسترسی ندارید یا سرویس یافت نشد.")
        return
    max_min = Service.max_life_for(row["product_type"] or "residential")
    text = (message.text or "").strip()
    if not text.isdigit() or not (1 <= int(text) <= max_min):
        await message.answer(f"⛔️ یک عدد بین ۱ تا {max_min} بفرستید:")
        return
    await state.clear()
    msg = await message.answer("⏳ در حال تنظیم زمان تعویض IP...")
    try:
        life = await service.set_life(config_id, int(text))
    except Exception as exc:  # noqa: BLE001
        logger.exception("set_life custom failed for config %s", config_id)
        await msg.edit_text(f"❌ خطا:\n<code>{escape(str(exc))}</code>")
        return
    await msg.edit_text(f"✅ زمان تعویض IP تنظیم شد: هر <b>{life}</b> دقیقه")
