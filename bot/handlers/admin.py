"""پنل مدیریت ادمین: گزارش، سرویس‌ها، درخواست‌های همکاری، نقش‌ها، شارژ دستی،
قیمت‌ها و تنظیمات سرور."""
from __future__ import annotations

import asyncio
import logging
from html import escape

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from ..config import Settings
from ..database import (
    Database,
    ROLE_RESIDENTIAL_RESELLER,
    ROLE_USER,
    ROLE_V2RAY_RESELLER,
)
from ..crypto import is_valid_address
from ..keyboards import (
    admin_panel_menu,
    configs_list_keyboard,
    custbot_menu,
    payments_admin_menu,
    prices_menu,
    request_decision_keyboard,
    settings_menu,
    setrole_keyboard,
    toggles_menu,
    users_menu,
)
from ..service import (
    S_BSC_RPC,
    S_CRYPTO_CONFIRMATIONS,
    S_CRYPTO_WALLET,
    S_HOST,
    S_IPROYAL_HOST,
    S_IPROYAL_PASSWORD,
    S_IPROYAL_PORT,
    S_IPROYAL_USERNAME,
    S_MIN_VOLUME,
    S_PAY_CRYPTO_ENABLED,
    S_PAY_NOWPAYMENTS_ENABLED,
    S_PRICE,
    S_RENEW_MIN_VOLUME,
    S_RESELLER_MIN_BALANCE,
    S_RESELLER_PRICE,
    S_RESIDENTIAL2_PRICE,
    S_RESIDENTIAL2_RESELLER_PRICE,
    S_SERVER_IP,
    S_SHOW_PARTNERSHIP,
    S_SHOW_RESIDENTIAL,
    S_SHOW_RESIDENTIAL2,
    S_SHOW_V2RAY,
    S_SNI,
    S_TOMAN_PER_USD,
    S_V2RAY_INBOUND_ID,
    S_V2RAY_PLAN_PRICE,
    S_V2RAY_PLAN_RESELLER_PRICE,
    S_V2RAY_PRICE,
    S_V2RAY_RESELLER_PRICE,
    Service,
)
from ..states import AdminStates

logger = logging.getLogger("resibot.admin")
router = Router(name="admin")

ROLE_LABEL = {
    ROLE_RESIDENTIAL_RESELLER: "همکار رزیدنتال",
    ROLE_V2RAY_RESELLER: "همکار V2Ray",
    ROLE_USER: "کاربر عادی",
}


# ====================================================================== #
#  ورود به پنل
# ====================================================================== #
@router.message(F.text == "🛠 پنل مدیریت")
async def panel_root(message: Message, state: FSMContext, db: Database) -> None:
    await state.clear()
    pending = len(db.list_pending_requests())
    await message.answer("🛠 <b>پنل مدیریت</b>", reply_markup=admin_panel_menu(pending))


@router.callback_query(F.data == "menu:admin")
async def panel_root_cb(call: CallbackQuery, state: FSMContext, db: Database) -> None:
    await state.clear()
    await call.answer()
    pending = len(db.list_pending_requests())
    await call.message.answer("🛠 <b>پنل مدیریت</b>", reply_markup=admin_panel_menu(pending))


@router.callback_query(F.data == "adm:report")
async def adm_report(call: CallbackQuery, service: Service) -> None:
    await call.answer()
    await call.message.answer(service.build_report())


@router.callback_query(F.data == "adm:configs")
async def adm_configs(call: CallbackQuery, db: Database) -> None:
    await call.answer()
    rows = db.list_all_configs()
    if not rows:
        await call.message.answer("هیچ سرویس فعالی وجود ندارد.")
        return
    await call.message.answer(
        f"🧾 سرویس‌های فعال (<b>{len(rows)}</b>) — یکی را انتخاب کنید:",
        reply_markup=configs_list_keyboard(rows[:50], show_owner=True),
    )


# ====================================================================== #
#  درخواست‌های همکاری
# ====================================================================== #
@router.callback_query(F.data == "adm:requests")
async def adm_requests(call: CallbackQuery, db: Database) -> None:
    await call.answer()
    rows = db.list_pending_requests()
    if not rows:
        await call.message.answer("درخواست همکاری در انتظاری وجود ندارد.")
        return
    for r in rows[:20]:
        bal = db.get_balance(r["tg_id"])
        ptype = "رزیدنتال" if r["ptype"] == "residential" else "V2Ray عادی"
        await call.message.answer(
            f"🤝 درخواست <code>#{r['id']}</code>\n"
            f"👤 <code>{r['tg_id']}</code>\n"
            f"📦 نوع: <b>{ptype}</b>\n"
            f"💰 موجودی: <b>{bal:g}</b>\n"
            f"📝 {escape(r['description'])}",
            reply_markup=request_decision_keyboard(r["id"]),
        )


@router.callback_query(F.data.startswith("preq_ok:"))
async def approve_request(call: CallbackQuery, db: Database, service: Service) -> None:
    req_id = int(call.data.split(":", 1)[1])
    req = db.get_request(req_id)
    if not req or req["status"] != "pending":
        await call.answer("این درخواست قبلاً بررسی شده.", show_alert=True)
        return
    tg_id = int(req["tg_id"])
    if req["ptype"] == "v2ray":
        bal = db.get_balance(tg_id)
        if bal < service.reseller_min_balance:
            await call.answer(
                f"⚠️ موجودی کاربر ({bal:g}) کمتر از حداقل ({service.reseller_min_balance:g}) است. "
                "ابتدا باید شارژ کند.",
                show_alert=True,
            )
            return
        role = ROLE_V2RAY_RESELLER
    else:
        role = ROLE_RESIDENTIAL_RESELLER
    db.set_role(tg_id, role)
    db.set_request_status(req_id, "approved")
    await call.answer("تأیید شد.")
    await call.message.edit_text(call.message.html_text + f"\n\n✅ تأیید شد ({ROLE_LABEL[role]}).")
    try:
        await call.bot.send_message(
            tg_id,
            f"🎉 درخواست همکاری شما تأیید شد!\nنقش شما: <b>{ROLE_LABEL[role]}</b>\n"
            "برای دیدن منوی جدید /start را بزنید.",
        )
    except Exception:  # noqa: BLE001
        logger.warning("notify approved user failed")


@router.callback_query(F.data.startswith("preq_no:"))
async def reject_request(call: CallbackQuery, db: Database) -> None:
    req_id = int(call.data.split(":", 1)[1])
    req = db.get_request(req_id)
    if not req or req["status"] != "pending":
        await call.answer("این درخواست قبلاً بررسی شده.", show_alert=True)
        return
    db.set_request_status(req_id, "rejected")
    await call.answer("رد شد.")
    await call.message.edit_text(call.message.html_text + "\n\n❌ رد شد.")
    try:
        await call.bot.send_message(int(req["tg_id"]), "متأسفانه درخواست همکاری شما رد شد.")
    except Exception:  # noqa: BLE001
        logger.warning("notify rejected user failed")


# ====================================================================== #
#  مدیریت کاربران/نقش‌ها
# ====================================================================== #
@router.callback_query(F.data == "adm:users")
async def adm_users(call: CallbackQuery) -> None:
    await call.answer()
    await call.message.answer("👤 مدیریت کاربران/نقش‌ها:", reply_markup=users_menu())


@router.callback_query(F.data == "usr:list_res")
async def usr_list_res(call: CallbackQuery, db: Database) -> None:
    await call.answer()
    rows = db.list_users_by_role(ROLE_RESIDENTIAL_RESELLER)
    await _send_user_list(call, rows, "همکاران رزیدنتال")


@router.callback_query(F.data == "usr:list_v2")
async def usr_list_v2(call: CallbackQuery, db: Database) -> None:
    await call.answer()
    rows = db.list_users_by_role(ROLE_V2RAY_RESELLER)
    await _send_user_list(call, rows, "همکاران V2Ray")


async def _send_user_list(call: CallbackQuery, rows, title: str) -> None:
    if not rows:
        await call.message.answer(f"هیچ {title} ثبت نشده است.")
        return
    lines = [f"📋 <b>{title}:</b>"]
    for r in rows[:50]:
        lines.append(f"• <code>{r['tg_id']}</code> — موجودی {float(r['balance']):g} — {escape(r['name'] or '')}")
    await call.message.answer("\n".join(lines))


@router.callback_query(F.data == "usr:setrole")
async def usr_setrole(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminStates.setrole_id)
    await call.answer()
    await call.message.answer("آیدی عددی کاربر را بفرستید:")


@router.message(AdminStates.setrole_id)
async def setrole_id(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text.isdigit():
        await message.answer("⛔️ آیدی باید عددی باشد.")
        return
    await state.clear()
    await message.answer(
        f"نقش کاربر <code>{text}</code> را انتخاب کنید:",
        reply_markup=setrole_keyboard(int(text)),
    )


@router.callback_query(F.data.startswith("role:"))
async def set_role_cb(call: CallbackQuery, db: Database) -> None:
    parts = call.data.split(":", 2)
    if len(parts) != 3:
        await call.answer("نامعتبر", show_alert=True)
        return
    _, tg_s, role = parts
    if not tg_s.isdigit() or role not in (ROLE_RESIDENTIAL_RESELLER, ROLE_V2RAY_RESELLER, ROLE_USER):
        await call.answer("نامعتبر", show_alert=True)
        return
    tg_id = int(tg_s)
    db.set_role(tg_id, role)
    await call.answer("نقش تنظیم شد.")
    await call.message.edit_text(f"✅ نقش کاربر <code>{tg_id}</code> به <b>{ROLE_LABEL[role]}</b> تغییر کرد.")
    try:
        await call.bot.send_message(tg_id, f"نقش شما به <b>{ROLE_LABEL[role]}</b> تغییر کرد. /start")
    except Exception:  # noqa: BLE001
        pass


# ====================================================================== #
#  شارژ دستی کیف پول
# ====================================================================== #
@router.callback_query(F.data == "adm:credit")
async def adm_credit(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminStates.credit_id)
    await call.answer()
    await call.message.answer("آیدی عددی کاربری که می‌خواهید شارژ کنید را بفرستید:")


@router.message(AdminStates.credit_id)
async def credit_id(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text.isdigit():
        await message.answer("⛔️ آیدی باید عددی باشد.")
        return
    await state.update_data(credit_id=int(text))
    await state.set_state(AdminStates.credit_amount)
    await message.answer("مبلغ شارژ را وارد کنید (می‌تواند منفی هم باشد برای کسر):")


@router.message(AdminStates.credit_amount)
async def credit_amount(message: Message, state: FSMContext, db: Database, service: Service) -> None:
    raw = (message.text or "").strip().replace(",", ".")
    try:
        amount = round(float(raw), 2)
    except ValueError:
        await message.answer("⛔️ یک عدد معتبر بفرستید.")
        return
    data = await state.get_data()
    await state.clear()
    tg_id = int(data.get("credit_id", 0))
    new_bal = db.add_balance(tg_id, amount)
    await message.answer(
        f"✅ کیف پول <code>{tg_id}</code> به‌روزرسانی شد.\n"
        f"💰 موجودی فعلی: <b>{new_bal:g} {service.currency}</b>"
    )
    try:
        await message.bot.send_message(
            tg_id,
            f"💰 کیف پول شما توسط ادمین {amount:g} {service.currency} تغییر کرد.\n"
            f"موجودی فعلی: <b>{new_bal:g} {service.currency}</b>",
        )
    except Exception:  # noqa: BLE001
        pass


# ====================================================================== #
#  پیام همگانی
# ====================================================================== #
@router.callback_query(F.data == "adm:broadcast")
async def adm_broadcast(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminStates.broadcast_text)
    await call.answer()
    await call.message.answer(
        "📣 متن پیام همگانی را بفرستید.\n"
        "این پیام برای همه‌ی کاربران ربات ارسال می‌شود. (برای لغو /start بزنید)"
    )


@router.message(AdminStates.broadcast_text)
async def do_broadcast(message: Message, state: FSMContext, db: Database) -> None:
    await state.clear()
    text = message.html_text if message.text else (message.caption or "")
    if not text:
        await message.answer("⛔️ متن خالی است.")
        return
    user_ids = db.all_user_ids()
    await message.answer(f"⏳ در حال ارسال به <b>{len(user_ids)}</b> کاربر...")
    ok = 0
    fail = 0
    for i, uid in enumerate(user_ids):
        try:
            await message.bot.send_message(uid, text)
            ok += 1
        except Exception:  # noqa: BLE001
            fail += 1
        # جلوگیری از محدودیت نرخ تلگرام
        if (i + 1) % 25 == 0:
            await asyncio.sleep(1)
    await message.answer(f"✅ ارسال شد.\n✔️ موفق: <b>{ok}</b> | ✖️ ناموفق: <b>{fail}</b>")


# ====================================================================== #
#  قیمت‌ها و تنظیمات
# ====================================================================== #
@router.callback_query(F.data == "adm:prices")
async def adm_prices(call: CallbackQuery, service: Service) -> None:
    await call.answer()
    usd = service.residential_currency
    tmn = service.currency
    text = (
        "💵 <b>قیمت‌ها (هر گیگابایت)</b>\n"
        f"• رزیدنتال عادی: <b>{service.price_per_gb:g} {usd}</b>\n"
        f"• رزیدنتال همکار: <b>{service.reseller_price_per_gb:g} {usd}</b>\n"
        f"• رزیدنتال ۲ عادی: <b>{service.residential2_price_per_gb:g} {usd}</b>\n"
        f"• رزیدنتال ۲ همکار: <b>{service.residential2_reseller_price_per_gb:g} {usd}</b>\n"
        f"• V2Ray عادی: <b>{service.v2ray_price_per_gb:g} {tmn}</b>\n"
        f"• V2Ray همکار: <b>{service.v2ray_reseller_price_per_gb:g} {tmn}</b>\n"
        f"• حداقل موجودی همکار v2ray: <b>{service.reseller_min_balance:g} {tmn}</b>\n"
        f"• نرخ تتر/تومان: <b>{service.toman_per_usd:g} {tmn}</b> به ازای هر دلار\n\n"
        "برای تغییر یکی را انتخاب کنید:"
    )
    await call.message.answer(text, reply_markup=prices_menu())


# ====================================================================== #
#  روش‌های پرداخت + تنظیمات کریپتو و پلن V2Ray
# ====================================================================== #
def _pay_kb(service: Service):
    return payments_admin_menu(
        crypto_on=service.feature_enabled(S_PAY_CRYPTO_ENABLED),
        nowpayments_on=service.feature_enabled(S_PAY_NOWPAYMENTS_ENABLED),
    )


def _pay_text(service: Service) -> str:
    wallet = service.crypto_wallet_address or "—"
    wallet_ok = "✅ معتبر" if is_valid_address(wallet) else "⛔️ نامعتبر"
    return (
        "💳 <b>روش‌های پرداخت</b>\n\n"
        f"• پرداخت مستقیم USDT: {'فعال ✅' if service.feature_enabled(S_PAY_CRYPTO_ENABLED) else 'غیرفعال ❌'}\n"
        f"• درگاه NowPayments: {'فعال ✅' if service.feature_enabled(S_PAY_NOWPAYMENTS_ENABLED) else 'غیرفعال ❌'}\n\n"
        "💠 <b>پرداخت مستقیم (USDT روی BEP20)</b>\n"
        f"👛 ولت مقصد: <code>{escape(wallet)}</code> ({wallet_ok})\n"
        f"🔗 RPC اصلی: <code>{escape(service.bsc_rpc_url or '—')}</code>\n"
        f"♻️ استخر RPC: <b>{len(service.bsc_rpc_urls)}</b> نود (failover خودکار)\n"
        f"🤖 تأیید خودکار: getLogs + اسکن بلاک (رایگان، چنداستراتژی)\n"
        f"🔒 تأیید لازم: <b>{service.crypto_confirmations}</b>\n\n"
        "🛡 <b>پلن V2Ray (یک‌ماهه نامحدود)</b>\n"
        f"• شناسه اینباند: <b>{service.v2ray_inbound_id}</b>\n"
        f"• قیمت عادی: <b>{service.v2ray_plan_price:g} USDT</b>\n"
        f"• قیمت همکار: <b>{service.v2ray_plan_reseller_price:g} USDT</b>\n\n"
        "برای تغییر، یکی را انتخاب کنید:"
    )


@router.callback_query(F.data == "adm:pay")
async def adm_pay(call: CallbackQuery, service: Service) -> None:
    await call.answer()
    await call.message.answer(_pay_text(service), reply_markup=_pay_kb(service))


_PAY_TOGGLE_KEYS = {
    "crypto": (S_PAY_CRYPTO_ENABLED, "پرداخت مستقیم USDT"),
    "nowpayments": (S_PAY_NOWPAYMENTS_ENABLED, "درگاه NowPayments"),
}


@router.callback_query(F.data.startswith("paytgl:"))
async def adm_pay_toggle(call: CallbackQuery, service: Service) -> None:
    key = call.data.split(":", 1)[1]
    entry = _PAY_TOGGLE_KEYS.get(key)
    if not entry:
        await call.answer("نامعتبر", show_alert=True)
        return
    setting_key, label = entry
    new_val = service.toggle_feature(setting_key)
    await call.answer(f"{label}: {'فعال شد ✅' if new_val else 'غیرفعال شد ❌'}")
    try:
        await call.message.edit_text(_pay_text(service), reply_markup=_pay_kb(service))
    except Exception:  # noqa: BLE001
        pass


@router.callback_query(F.data == "adm:settings")
async def adm_settings(call: CallbackQuery, service: Service) -> None:
    await call.answer()
    iproyal_pass = service.iproyal_password
    iproyal_pass_txt = ("••••" + iproyal_pass[-4:]) if iproyal_pass else "—"
    text = (
        "⚙️ <b>تنظیمات سرور</b>\n"
        f"• IP/دامنه: <code>{service.server_ip or '—'}</code>\n"
        f"• SNI: <code>{escape(service.sni)}</code>\n"
        f"• Host: <code>{escape(service.host)}</code>\n"
        f"• حداقل حجم خرید: <b>{service.min_volume_gb} GB</b>\n"
        f"• حداقل حجم تمدید: <b>{service.renew_min_volume_gb} GB</b>\n\n"
        "🌍 <b>سرور رزیدنتال ۲</b>\n"
        f"• هاست: <code>{escape(service.iproyal_host or '—')}</code>\n"
        f"• پورت: <code>{service.iproyal_port}</code>\n"
        f"• یوزرنیم: <code>{escape(service.iproyal_username or '—')}</code>\n"
        f"• پسورد: <code>{escape(iproyal_pass_txt)}</code>\n\n"
        "برای تغییر یکی را انتخاب کنید:"
    )
    await call.message.answer(text, reply_markup=settings_menu())


# نگاشت callback ← (state, prompt)
_SETTING_PROMPTS = {
    "server_ip": (AdminStates.set_server_ip, "IP یا دامنه‌ی جدید سرور را بفرستید:"),
    "sni": (AdminStates.set_sni, "مقدار جدید SNI را بفرستید:"),
    "host": (AdminStates.set_host, "مقدار جدید Host Header را بفرستید:"),
    "min_volume": (AdminStates.set_min_volume, "حداقل حجم خرید (گیگابایت) را بفرستید:"),
    "renew_min_volume": (AdminStates.set_renew_min_volume, "حداقل حجم تمدید (گیگابایت) را بفرستید:"),
    "price": (AdminStates.set_price, "قیمت رزیدنتال عادی (هر گیگ) را بفرستید:"),
    "reseller_price": (AdminStates.set_reseller_price, "قیمت رزیدنتال همکار (هر گیگ) را بفرستید:"),
    "residential2_price": (AdminStates.set_residential2_price, "قیمت رزیدنتال ۲ عادی (هر گیگ، دلار) را بفرستید:"),
    "residential2_reseller_price": (AdminStates.set_residential2_reseller_price, "قیمت رزیدنتال ۲ همکار (هر گیگ، دلار) را بفرستید:"),
    "v2ray_price": (AdminStates.set_v2ray_price, "قیمت V2Ray عادی (هر گیگ) را بفرستید:"),
    "v2ray_reseller_price": (AdminStates.set_v2ray_reseller_price, "قیمت V2Ray همکار (هر گیگ) را بفرستید:"),
    "reseller_min_balance": (AdminStates.set_reseller_min_balance, "حداقل موجودی همکار v2ray را بفرستید:"),
    "toman_rate": (AdminStates.set_toman_rate, "نرخ هر دلار/تتر به تومان را بفرستید (مثلاً 175000):"),
    "iproyal_host": (AdminStates.set_iproyal_host, "هاست سرور رزیدنتال ۲ را بفرستید:"),
    "iproyal_port": (AdminStates.set_iproyal_port, "پورت سرور رزیدنتال ۲ را بفرستید:"),
    "iproyal_username": (AdminStates.set_iproyal_username, "یوزرنیم سرور رزیدنتال ۲ را بفرستید:"),
    "iproyal_password": (AdminStates.set_iproyal_password, "پسورد پایه‌ی سرور رزیدنتال ۲ را بفرستید:"),
    "crypto_wallet": (AdminStates.set_crypto_wallet, "آدرس ولت مقصد USDT (شبکه BEP20) را بفرستید — فرمت 0x و ۴۰ رقم هگز:"),
    "bsc_rpc": (AdminStates.set_bsc_rpc, "آدرس RPC شبکه BSC را بفرستید (مثل https://bsc-dataseed.binance.org):"),
    "crypto_conf": (AdminStates.set_crypto_conf, "تعداد تأیید لازم قبل از تحویل را بفرستید (مثلاً 12):"),
    "v2ray_inbound": (AdminStates.set_v2ray_inbound, "شناسه عددی اینباند V2Ray در پنل را بفرستید (مثلاً 6):"),
    "v2ray_plan_price": (AdminStates.set_v2ray_plan_price, "قیمت پلن V2Ray عادی (USDT) را بفرستید:"),
    "v2ray_plan_reseller": (AdminStates.set_v2ray_plan_reseller, "قیمت پلن V2Ray همکار (USDT) را بفرستید:"),
}


@router.callback_query(F.data.startswith("set:"))
async def settings_choose(call: CallbackQuery, state: FSMContext) -> None:
    key = call.data.split(":", 1)[1]
    prompt = _SETTING_PROMPTS.get(key)
    if not prompt:
        await call.answer("نامعتبر", show_alert=True)
        return
    st, text = prompt
    await state.set_state(st)
    await call.answer()
    await call.message.answer(text)


def _save_text(service: Service, key: str, value: str, *, maxlen: int = 253) -> None:
    service.set_setting(key, value.strip()[:maxlen])


@router.message(AdminStates.set_server_ip)
async def s_server_ip(message: Message, state: FSMContext, service: Service) -> None:
    _save_text(service, S_SERVER_IP, message.text or "")
    await state.clear()
    await message.answer("✅ IP/دامنه‌ی سرور به‌روزرسانی شد.")


@router.message(AdminStates.set_sni)
async def s_sni(message: Message, state: FSMContext, service: Service) -> None:
    _save_text(service, S_SNI, message.text or "")
    await state.clear()
    await message.answer("✅ SNI به‌روزرسانی شد.")


@router.message(AdminStates.set_host)
async def s_host(message: Message, state: FSMContext, service: Service) -> None:
    _save_text(service, S_HOST, message.text or "")
    await state.clear()
    await message.answer("✅ Host به‌روزرسانی شد.")


async def _save_int(message: Message, state: FSMContext, service: Service, key: str, label: str) -> None:
    text = (message.text or "").strip()
    if not text.isdigit() or int(text) < 1:
        await message.answer("⛔️ یک عدد صحیح مثبت بفرستید.")
        return
    service.set_setting(key, text)
    await state.clear()
    await message.answer(f"✅ {label} به <b>{text}</b> تغییر کرد.")


async def _save_float(message: Message, state: FSMContext, service: Service, key: str, label: str) -> None:
    raw = (message.text or "").strip().replace(",", ".")
    try:
        val = float(raw)
        if val < 0:
            raise ValueError
    except ValueError:
        await message.answer("⛔️ یک عدد معتبر و نامنفی بفرستید.")
        return
    service.set_setting(key, str(val))
    await state.clear()
    await message.answer(f"✅ {label} به <b>{val:g}</b> تغییر کرد.")


@router.message(AdminStates.set_min_volume)
async def s_min_volume(message: Message, state: FSMContext, service: Service) -> None:
    await _save_int(message, state, service, S_MIN_VOLUME, "حداقل حجم خرید")


@router.message(AdminStates.set_renew_min_volume)
async def s_renew_min_volume(message: Message, state: FSMContext, service: Service) -> None:
    await _save_int(message, state, service, S_RENEW_MIN_VOLUME, "حداقل حجم تمدید")


@router.message(AdminStates.set_price)
async def s_price(message: Message, state: FSMContext, service: Service) -> None:
    await _save_float(message, state, service, S_PRICE, "قیمت رزیدنتال عادی")


@router.message(AdminStates.set_reseller_price)
async def s_reseller_price(message: Message, state: FSMContext, service: Service) -> None:
    await _save_float(message, state, service, S_RESELLER_PRICE, "قیمت رزیدنتال همکار")


@router.message(AdminStates.set_residential2_price)
async def s_residential2_price(message: Message, state: FSMContext, service: Service) -> None:
    await _save_float(message, state, service, S_RESIDENTIAL2_PRICE, "قیمت رزیدنتال ۲ عادی")


@router.message(AdminStates.set_residential2_reseller_price)
async def s_residential2_reseller_price(message: Message, state: FSMContext, service: Service) -> None:
    await _save_float(message, state, service, S_RESIDENTIAL2_RESELLER_PRICE, "قیمت رزیدنتال ۲ همکار")


@router.message(AdminStates.set_iproyal_host)
async def s_iproyal_host(message: Message, state: FSMContext, service: Service) -> None:
    _save_text(service, S_IPROYAL_HOST, message.text or "")
    await state.clear()
    await message.answer("✅ هاست رزیدنتال ۲ به‌روزرسانی شد.")


@router.message(AdminStates.set_iproyal_port)
async def s_iproyal_port(message: Message, state: FSMContext, service: Service) -> None:
    await _save_int(message, state, service, S_IPROYAL_PORT, "پورت رزیدنتال ۲")


@router.message(AdminStates.set_iproyal_username)
async def s_iproyal_username(message: Message, state: FSMContext, service: Service) -> None:
    _save_text(service, S_IPROYAL_USERNAME, message.text or "")
    await state.clear()
    await message.answer("✅ یوزرنیم رزیدنتال ۲ به‌روزرسانی شد.")


@router.message(AdminStates.set_iproyal_password)
async def s_iproyal_password(message: Message, state: FSMContext, service: Service) -> None:
    _save_text(service, S_IPROYAL_PASSWORD, message.text or "")
    await state.clear()
    await message.answer("✅ پسورد پایه‌ی رزیدنتال ۲ به‌روزرسانی شد.")


@router.message(AdminStates.set_crypto_wallet)
async def s_crypto_wallet(message: Message, state: FSMContext, service: Service) -> None:
    addr = (message.text or "").strip()
    if not is_valid_address(addr):
        await message.answer(
            "⛔️ آدرس نامعتبر است. باید با <code>0x</code> شروع شود و دقیقاً ۴۰ رقم هگز داشته باشد.\n"
            "دوباره بفرستید:"
        )
        return
    service.set_setting(S_CRYPTO_WALLET, addr)
    await state.clear()
    await message.answer(
        "✅ آدرس ولت مقصد به‌روزرسانی شد.\n"
        f"👛 <code>{escape(addr)}</code>\n\n"
        "فاکتورهای جدید به همین آدرس هدایت می‌شوند."
    )


@router.message(AdminStates.set_bsc_rpc)
async def s_bsc_rpc(message: Message, state: FSMContext, service: Service) -> None:
    url = (message.text or "").strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        await message.answer("⛔️ آدرس RPC باید با http:// یا https:// شروع شود. دوباره بفرستید:")
        return
    service.set_setting(S_BSC_RPC, url[:253])
    await state.clear()
    await message.answer("✅ آدرس RPC شبکه BSC به‌روزرسانی شد.")


@router.message(AdminStates.set_crypto_conf)
async def s_crypto_conf(message: Message, state: FSMContext, service: Service) -> None:
    await _save_int(message, state, service, S_CRYPTO_CONFIRMATIONS, "تعداد تأیید لازم")


@router.message(AdminStates.set_v2ray_inbound)
async def s_v2ray_inbound(message: Message, state: FSMContext, service: Service) -> None:
    await _save_int(message, state, service, S_V2RAY_INBOUND_ID, "شناسه اینباند V2Ray")


@router.message(AdminStates.set_v2ray_plan_price)
async def s_v2ray_plan_price(message: Message, state: FSMContext, service: Service) -> None:
    await _save_float(message, state, service, S_V2RAY_PLAN_PRICE, "قیمت پلن V2Ray عادی")


@router.message(AdminStates.set_v2ray_plan_reseller)
async def s_v2ray_plan_reseller(message: Message, state: FSMContext, service: Service) -> None:
    await _save_float(message, state, service, S_V2RAY_PLAN_RESELLER_PRICE, "قیمت پلن V2Ray همکار")


@router.message(AdminStates.set_v2ray_price)
async def s_v2ray_price(message: Message, state: FSMContext, service: Service) -> None:
    await _save_float(message, state, service, S_V2RAY_PRICE, "قیمت V2Ray عادی")


@router.message(AdminStates.set_v2ray_reseller_price)
async def s_v2ray_reseller_price(message: Message, state: FSMContext, service: Service) -> None:
    await _save_float(message, state, service, S_V2RAY_RESELLER_PRICE, "قیمت V2Ray همکار")


@router.message(AdminStates.set_reseller_min_balance)
async def s_reseller_min_balance(message: Message, state: FSMContext, service: Service) -> None:
    await _save_float(message, state, service, S_RESELLER_MIN_BALANCE, "حداقل موجودی همکار v2ray")


@router.message(AdminStates.set_toman_rate)
async def s_toman_rate(message: Message, state: FSMContext, service: Service) -> None:
    raw = (message.text or "").strip().replace(",", ".")
    try:
        val = float(raw)
        if val <= 0:
            raise ValueError
    except ValueError:
        await message.answer("⛔️ یک عدد مثبت معتبر بفرستید.")
        return
    service.set_setting(S_TOMAN_PER_USD, str(val))
    await state.clear()
    await message.answer(f"✅ نرخ تتر/تومان به <b>{val:g}</b> تغییر کرد.")



# ====================================================================== #
#  نمایش/مخفی‌سازی بخش‌ها (همکاری و محصولات)
# ====================================================================== #
_TOGGLE_KEYS = {
    "partnership": (S_SHOW_PARTNERSHIP, "همکاری"),
    "residential": (S_SHOW_RESIDENTIAL, "رزیدنتال"),
    "residential2": (S_SHOW_RESIDENTIAL2, "رزیدنتال ۲"),
    "v2ray": (S_SHOW_V2RAY, "V2Ray"),
}


def _toggles_kb(service: Service):
    return toggles_menu(
        partnership=service.feature_enabled(S_SHOW_PARTNERSHIP),
        residential=service.feature_enabled(S_SHOW_RESIDENTIAL),
        residential2=service.feature_enabled(S_SHOW_RESIDENTIAL2),
        v2ray=service.feature_enabled(S_SHOW_V2RAY),
    )


@router.callback_query(F.data == "adm:toggles")
async def adm_toggles(call: CallbackQuery, service: Service) -> None:
    await call.answer()
    await call.message.answer(
        "🔀 <b>نمایش/مخفی‌سازی بخش‌ها</b>\n\n"
        "با زدن هر گزینه، نمایش آن در ربات روشن/خاموش می‌شود:\n"
        "• «همکاری»: دکمه‌ی درخواست همکاری در منوی اصلی\n"
        "• «رزیدنتال / رزیدنتال ۲ / V2Ray»: نمایش محصول در منوی خرید\n\n"
        "✅ = نمایش داده می‌شود | ❌ = مخفی است",
        reply_markup=_toggles_kb(service),
    )


@router.callback_query(F.data.startswith("tgl:"))
async def adm_toggle_flip(call: CallbackQuery, service: Service) -> None:
    key = call.data.split(":", 1)[1]
    entry = _TOGGLE_KEYS.get(key)
    if not entry:
        await call.answer("نامعتبر", show_alert=True)
        return
    setting_key, label = entry
    new_val = service.toggle_feature(setting_key)
    await call.answer(f"{label}: {'فعال شد ✅' if new_val else 'مخفی شد ❌'}")
    # به‌روزرسانی کیبورد با وضعیت جدید
    try:
        await call.message.edit_reply_markup(reply_markup=_toggles_kb(service))
    except Exception:  # noqa: BLE001
        pass


# ====================================================================== #
#  ربات کمکی مشتری (تغییر IP و بررسی تنظیمات توسط خود مشتری)
# ====================================================================== #
def _custbot_info_text() -> str:
    return (
        "🤖 <b>ربات کمکی مشتری</b>\n\n"
        "این یک ربات تلگرام جداگانه است که هر مشتری می‌تواند خودش استارت کند "
        "و بدون نیاز به دسترسی به این ربات اصلی، IP سرویسش را تغییر دهد و "
        "تنظیمات IP را بررسی کند.\n\n"
        "📌 <b>تعیین مشتری از این منو انجام نمی‌شود.</b>\n"
        "هر همکار/فروشنده باید از داخل <b>مدیریت سرویس‌ها</b> (روی همان کانفیگی "
        "که فروخته)، دکمه‌ی «🤖 تعیین مشتری (ربات کمکی)» را بزند و آیدی عددی "
        "تلگرام مشتریِ آن سفارش مشخص را وارد کند.\n\n"
        "به این ترتیب هر مشتری فقط همان سرویسی را می‌بیند و مدیریت می‌کند که "
        "برایش خریداری شده — نه سرویس‌های مشتریان دیگر همان همکار."
    )


@router.callback_query(F.data == "adm:custbot")
async def adm_custbot(call: CallbackQuery) -> None:
    await call.answer()
    await call.message.answer(_custbot_info_text(), reply_markup=custbot_menu())


@router.callback_query(F.data == "custbot:help")
async def custbot_help(call: CallbackQuery) -> None:
    await call.answer()
    await call.message.answer(
        "ℹ️ <b>راهنمای راه‌اندازی ربات کمکی مشتری</b>\n\n"
        "1️⃣ توکن ربات کمکی را در فایل <code>.env</code> با کلید "
        "<code>CUSTOMER_BOT_TOKEN</code> تنظیم کنید (یک‌بار، در نصب).\n"
        "2️⃣ سرویس <code>resibot-customer</code> را راه‌اندازی کنید.\n"
        "3️⃣ برای هر سرویس، از «🧾 همه‌ی سرویس‌ها» → انتخاب سرویس → "
        "«🤖 تعیین مشتری (ربات کمکی)» آیدی عددی مشتری را وارد کنید.\n"
        "4️⃣ مشتری ربات کمکی را /start می‌کند و فقط همان سرویس را می‌بیند."
    )
