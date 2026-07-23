"""کیبوردهای inline و reply برای ربات."""
from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from . import countries, locations


# ---------------------------------------------------------------------- #
#  منوی اصلی — دکمه‌های شیشه‌ای (inline)
# ---------------------------------------------------------------------- #
def main_menu(
    *,
    is_admin: bool = False,
    is_reseller: bool = False,
    show_partnership: bool = True,
) -> InlineKeyboardMarkup:
    """منوی اصلی به‌صورت دکمه‌های شیشه‌ای (inline).

    چون inline است، هر بار وضعیت لحظه‌ای را نشان می‌دهد؛ پس مخفی‌کردن دکمه‌ی
    «همکاری» بلافاصله اعمال می‌شود (برخلاف کیبورد reply که روی گوشی باقی می‌ماند).
    """
    second_row = [InlineKeyboardButton(text="💼 کیف پول", callback_data="menu:wallet")]
    # دکمه‌ی همکاری فقط وقتی فعال باشد نمایش داده می‌شود (برای ادمین همیشه)
    if show_partnership or is_admin:
        second_row.append(InlineKeyboardButton(text="🤝 همکاری", callback_data="menu:partner"))
    rows = [
        [
            InlineKeyboardButton(text="🛒 خرید سرویس", callback_data="menu:buy"),
            InlineKeyboardButton(text="🧾 سرویس‌های من", callback_data="menu:configs"),
        ],
        second_row,
        [InlineKeyboardButton(text="👥 دعوت دوستان (رفرال)", callback_data="menu:referral")],
        [InlineKeyboardButton(text="📖 راهنمای خرید و استفاده", callback_data="menu:guide")],
    ]
    # وضعیت سرویس فقط برای ادمین/همکار
    if is_admin or is_reseller:
        rows.append([InlineKeyboardButton(text="📊 وضعیت سرویس‌ها", callback_data="menu:status")])
    if is_admin:
        rows.append([InlineKeyboardButton(text="🛠 پنل مدیریت", callback_data="menu:admin")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def discount_product_keyboard(tg_id: int) -> InlineKeyboardMarkup:
    """انتخاب محصولِ هدفِ تخفیف برای یک کاربر مشخص."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🌟 همه‌ی محصولات", callback_data=f"disc:{tg_id}:all")],
            [InlineKeyboardButton(text="🌐 رزیدنتال", callback_data=f"disc:{tg_id}:residential")],
            [InlineKeyboardButton(text="🌍 رزیدنتال ۲", callback_data=f"disc:{tg_id}:residential2")],
            [InlineKeyboardButton(text="🛡 V2Ray", callback_data=f"disc:{tg_id}:v2ray")],
            _panel_row(),
        ]
    )


def _home_row() -> list[InlineKeyboardButton]:
    return [InlineKeyboardButton(text="🏠 منوی اصلی", callback_data="menu:home")]


def _panel_row() -> list[InlineKeyboardButton]:
    return [InlineKeyboardButton(text="🔙 بازگشت به پنل", callback_data="menu:admin")]


def back_to_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[_home_row()])


def back_to_panel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[_panel_row()])


# ---------------------------------------------------------------------- #
#  انتخاب روش پرداخت (برای سفارش‌ها و شارژ کیف پول)
# ---------------------------------------------------------------------- #
def pay_methods_keyboard(order_id: str, methods: list[str]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if "hooshpay" in methods:
        rows.append([InlineKeyboardButton(
            text="💳 پرداخت ریالی (کارت‌به‌کارت)", callback_data=f"pm:hoosh:{order_id}"
        )])
    if "crypto" in methods:
        rows.append([InlineKeyboardButton(
            text="💠 پرداخت مستقیم USDT (BEP20)", callback_data=f"pm:crypto:{order_id}"
        )])
    if "nowpayments" in methods:
        rows.append([InlineKeyboardButton(
            text="🌐 پرداخت با درگاه", callback_data=f"pm:now:{order_id}"
        )])
    rows.append([InlineKeyboardButton(text="❌ انصراف", callback_data=f"pm:cancel:{order_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def crypto_paid_keyboard(order_id: str) -> InlineKeyboardMarkup:
    """دکمه‌های صفحه‌ی پرداخت کریپتو: ثبت هش و بررسی مجدد."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🧾 ارسال هش تراکنش / لینک", callback_data=f"cx:tx:{order_id}")],
            [InlineKeyboardButton(text="🔄 بررسی وضعیت پرداخت", callback_data=f"cx:chk:{order_id}")],
            [InlineKeyboardButton(text="❌ انصراف", callback_data=f"pm:cancel:{order_id}")],
        ]
    )


# ---------------------------------------------------------------------- #
#  محصولات
# ---------------------------------------------------------------------- #
def products_menu(
    *,
    residential: bool = True,
    residential2: bool = True,
    v2ray: bool = True,
    digital: bool = False,
) -> InlineKeyboardMarkup:
    """منوی محصولات؛ فقط محصولات فعال‌شده نمایش داده می‌شوند."""
    rows: list[list[InlineKeyboardButton]] = []
    if residential:
        rows.append([InlineKeyboardButton(text="🌐 کانفیگ رزیدنتال", callback_data="buy:residential")])
    if residential2:
        rows.append([InlineKeyboardButton(text="🌍 کانفیگ رزیدنتال ۲", callback_data="buy:residential2")])
    if v2ray:
        rows.append([InlineKeyboardButton(text="🛡 کانفیگ V2Ray (عادی)", callback_data="buy:v2ray")])
    if digital:
        rows.append([InlineKeyboardButton(text="🤖 اشتراک‌های هوش مصنوعی", callback_data="menu:digital")])
    if not rows:
        rows.append([InlineKeyboardButton(text="—", callback_data="noop")])
    rows.append(_home_row())
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ---------------------------------------------------------------------- #
#  محصولات دیجیتال (اکانت/اشتراک آماده)
# ---------------------------------------------------------------------- #
def digital_products_menu(products: list, stock: dict | None = None) -> InlineKeyboardMarkup:
    """لیست محصولات دیجیتال فعال؛ هر محصول یک دکمه‌ی شیشه‌ای."""
    stock = stock or {}
    rows: list[list[InlineKeyboardButton]] = []
    for p in products:
        avail = int(stock.get(int(p["id"]), 0))
        badge = "" if avail > 0 else " (ناموجود)"
        rows.append([InlineKeyboardButton(
            text=f"{p['title']}{badge}", callback_data=f"dg:open:{p['id']}"
        )])
    if not rows:
        rows.append([InlineKeyboardButton(text="فعلاً محصولی نیست", callback_data="noop")])
    rows.append(_home_row())
    return InlineKeyboardMarkup(inline_keyboard=rows)


def digital_detail_kb(product_id: int, *, in_stock: bool) -> InlineKeyboardMarkup:
    """صفحه‌ی جزئیات محصول دیجیتال: خرید + بازگشت."""
    rows: list[list[InlineKeyboardButton]] = []
    if in_stock:
        rows.append([InlineKeyboardButton(text="🛒 خرید این محصول", callback_data=f"dg:buy:{product_id}")])
    else:
        rows.append([InlineKeyboardButton(text="🔔 اطلاع هنگام موجود شدن", callback_data=f"dg:notify:{product_id}")])
    rows.append([InlineKeyboardButton(text="⬅️ بازگشت به لیست", callback_data="menu:digital")])
    rows.append(_home_row())
    return InlineKeyboardMarkup(inline_keyboard=rows)


def digital_pay_kb(order_id: str, methods: list[str], *, wallet: bool = False) -> InlineKeyboardMarkup:
    """انتخاب روش پرداخت برای محصول دیجیتال (کیف پول + کریپتو + درگاه)."""
    rows: list[list[InlineKeyboardButton]] = []
    if wallet:
        rows.append([InlineKeyboardButton(
            text="💼 پرداخت از کیف پول", callback_data=f"dg:wallet:{order_id}"
        )])
    if "hooshpay" in methods:
        rows.append([InlineKeyboardButton(
            text="💳 پرداخت ریالی (کارت‌به‌کارت)", callback_data=f"pm:hoosh:{order_id}"
        )])
    if "crypto" in methods:
        rows.append([InlineKeyboardButton(
            text="💠 پرداخت مستقیم USDT (BEP20)", callback_data=f"pm:crypto:{order_id}"
        )])
    if "nowpayments" in methods:
        rows.append([InlineKeyboardButton(
            text="🌐 پرداخت با درگاه", callback_data=f"pm:now:{order_id}"
        )])
    rows.append([InlineKeyboardButton(text="❌ انصراف", callback_data=f"pm:cancel:{order_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ---------------------------------------------------------------------- #
#  کیف پول و همکاری
# ---------------------------------------------------------------------- #
def wallet_menu(*, topup_enabled: bool = True) -> InlineKeyboardMarkup:
    rows = []
    if topup_enabled:
        rows.append([InlineKeyboardButton(text="💳 شارژ کیف پول", callback_data="wallet:topup")])
    rows.append(_home_row())
    return InlineKeyboardMarkup(inline_keyboard=rows)


def partnership_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🛡 درخواست همکاری V2Ray", callback_data="partner:v2ray")],
            _home_row(),
        ]
    )


def confirm_purchase_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ تأیید و ساخت", callback_data="ord_confirm"),
                InlineKeyboardButton(text="❌ انصراف", callback_data="ord_cancel"),
            ]
        ]
    )


def topup_after_insufficient_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 شارژ کیف پول", callback_data="wallet:topup")],
        ]
    )


def request_decision_keyboard(req_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ تأیید", callback_data=f"preq_ok:{req_id}"),
                InlineKeyboardButton(text="❌ رد", callback_data=f"preq_no:{req_id}"),
            ]
        ]
    )


# ---------------------------------------------------------------------- #
#  انتخاب کشور
# ---------------------------------------------------------------------- #
def country_keyboard(prefix: str, popular: list[tuple[str, str]] | None = None) -> InlineKeyboardMarkup:
    """دکمه‌های کشورهای پرکاربرد + جستجو + تصادفی + کد دلخواه.

    prefix: پیشوند callback مثل "ord_country" یا "loc_country".
    popular: لیست (code, label) دلخواه؛ اگر None باشد از countries.popular() استفاده می‌شود.
    """
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    popular_list = popular if popular is not None else countries.popular()
    for code, lbl in popular_list:
        row.append(InlineKeyboardButton(text=lbl, callback_data=f"{prefix}:{code}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([
        InlineKeyboardButton(text="🔍 جستجوی کشور", callback_data=f"{prefix}:__search__"),
    ])
    rows.append([
        InlineKeyboardButton(text="✍️ کد دلخواه", callback_data=f"{prefix}:__custom__"),
        InlineKeyboardButton(text="🎲 تصادفی", callback_data=f"{prefix}:__skip__"),
    ])
    rows.append(_home_row())
    return InlineKeyboardMarkup(inline_keyboard=rows)


def country_results_keyboard(prefix: str, results: list[tuple[str, str]]) -> InlineKeyboardMarkup:
    """نتایج جستجوی کشور را به‌صورت دکمه نشان می‌دهد."""
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for code, lbl in results:
        row.append(InlineKeyboardButton(text=lbl, callback_data=f"{prefix}:{code}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([
        InlineKeyboardButton(text="🔍 جستجوی دوباره", callback_data=f"{prefix}:__search__"),
        InlineKeyboardButton(text="🎲 تصادفی", callback_data=f"{prefix}:__skip__"),
    ])
    rows.append(_home_row())
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ---------------------------------------------------------------------- #
#  انتخاب state/city از لیست (با گزینه‌ی تصادفی)
# ---------------------------------------------------------------------- #
def options_keyboard(
    prefix: str,
    items: list[str],
    *,
    columns: int = 2,
    back_cb: str | None = None,
    allow_custom: bool = False,
    home: bool = True,
) -> InlineKeyboardMarkup:
    """کیبورد انتخاب از یک لیست. هر دکمه callback = f"{prefix}:{item}".

    گزینه‌ی «تصادفی» با مقدار __rand__، گزینه‌ی «دلخواه» (اختیاری) با __custom__،
    دکمه‌ی بازگشت اختیاری و دکمه‌ی منوی اصلی اضافه می‌شود.
    """
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for it in items:
        row.append(InlineKeyboardButton(text=locations.prettify(it), callback_data=f"{prefix}:{it}"))
        if len(row) == columns:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    last = [InlineKeyboardButton(text="🎲 تصادفی", callback_data=f"{prefix}:__rand__")]
    if allow_custom:
        last.append(InlineKeyboardButton(text="✍️ دلخواه", callback_data=f"{prefix}:__custom__"))
    rows.append(last)
    if back_cb:
        rows.append([InlineKeyboardButton(text="⬅️ بازگشت", callback_data=back_cb)])
    if home:
        rows.append(_home_row())
    return InlineKeyboardMarkup(inline_keyboard=rows)


def skip_keyboard(prefix: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎲 تصادفی", callback_data=f"{prefix}:__skip__")]
        ]
    )


# ---------------------------------------------------------------------- #
#  انتخاب زمان تعویض خودکار IP (life بر حسب دقیقه)
# ---------------------------------------------------------------------- #
LIFE_PRESETS = [10, 30, 60, 120, 360, 720, 1440]
# رزیدنتال ۲ (IPRoyal) تا ۷ روز: 1h, 6h, 12h, 1d, 2d, 3d, 7d
LIFE_PRESETS_RES2 = [60, 360, 720, 1440, 2880, 4320, 10080]


def life_label(m: int) -> str:
    """برچسب خوانا برای مقدار دقیقه (دقیقه/ساعت/روز)."""
    if m < 60:
        return f"{m} دقیقه"
    if m % 1440 == 0:
        return f"{m // 1440} روز"
    if m % 60 == 0:
        return f"{m // 60} ساعت"
    return f"{m} دقیقه"


def life_keyboard(prefix: str, presets: list[int] | None = None) -> InlineKeyboardMarkup:
    """دکمه‌های انتخاب زمان تعویض IP. مقدار 0 یعنی بدون تعویض خودکار."""
    preset_list = presets if presets is not None else LIFE_PRESETS
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for m in preset_list:
        row.append(InlineKeyboardButton(text=life_label(m), callback_data=f"{prefix}:{m}"))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="🔒 بدون تعویض خودکار", callback_data=f"{prefix}:0")])
    rows.append([InlineKeyboardButton(text="✍️ مقدار دلخواه (دقیقه)", callback_data=f"{prefix}:__custom__")])
    rows.append(_home_row())
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ---------------------------------------------------------------------- #
#  لیست کانفیگ‌ها (هر کدام یک دکمه)
# ---------------------------------------------------------------------- #
def configs_list_keyboard(rows: list, *, show_owner: bool = False) -> InlineKeyboardMarkup:
    kb: list[list[InlineKeyboardButton]] = []
    for r in rows:
        loc = r["area"] or "RND"
        if r["state"]:
            loc += f"/{r['state']}"
        label = f"#{r['id']} • {loc} • {r['volume_gb']}GB"
        if show_owner:
            label += f" • 👤{r['owner_tg_id']}"
        kb.append([InlineKeyboardButton(text=label, callback_data=f"cfg_open:{r['id']}")])
    kb.append(_home_row())
    return InlineKeyboardMarkup(inline_keyboard=kb)


# ---------------------------------------------------------------------- #
#  منوی جزئیات یک کانفیگ
# ---------------------------------------------------------------------- #
def config_actions(config_id: int, *, is_admin: bool = False, product: str = "residential") -> InlineKeyboardMarkup:
    if product == "v2ray":
        # منوی ساده برای V2Ray عادی
        rows = [
            [
                InlineKeyboardButton(text="📈 مصرف", callback_data=f"cfg_usage:{config_id}"),
                InlineKeyboardButton(text="🔗 لینک‌ها", callback_data=f"cfg_links:{config_id}"),
            ],
            [
                InlineKeyboardButton(text="♻️ تمدید / افزایش حجم", callback_data=f"cfg_renew:{config_id}"),
            ],
        ]
    elif product == "residential2":
        # رزیدنتال ۲ (IPRoyal): لایه‌ی استان ندارد؛ کشور و شهر یکجا تغییر می‌کنند
        rows = [
            [
                InlineKeyboardButton(text="🔄 تغییر IP", callback_data=f"cfg_ip:{config_id}"),
                InlineKeyboardButton(text="📡 تست اتصال", callback_data=f"cfg_ping:{config_id}"),
            ],
            [
                InlineKeyboardButton(text="🗺 تغییر کشور/شهر", callback_data=f"cfg_country:{config_id}"),
            ],
            [
                InlineKeyboardButton(text="⏱ زمان تعویض IP", callback_data=f"cfg_life:{config_id}"),
            ],
            [
                InlineKeyboardButton(text="📈 مصرف", callback_data=f"cfg_usage:{config_id}"),
                InlineKeyboardButton(text="🔗 لینک‌ها", callback_data=f"cfg_links:{config_id}"),
            ],
            [
                InlineKeyboardButton(text="♻️ تمدید / افزایش حجم", callback_data=f"cfg_renew:{config_id}"),
            ],
            [
                InlineKeyboardButton(text="🤖 تعیین مشتری (ربات کمکی)", callback_data=f"cfg_cust:{config_id}"),
            ],
        ]
    else:
        # منوی کامل برای رزیدنتال
        rows = [
            [
                InlineKeyboardButton(text="🔄 تغییر IP", callback_data=f"cfg_ip:{config_id}"),
                InlineKeyboardButton(text="📡 تست اتصال", callback_data=f"cfg_ping:{config_id}"),
            ],
            [
                InlineKeyboardButton(text="🌍 تغییر کشور", callback_data=f"cfg_country:{config_id}"),
            ],
            [
                InlineKeyboardButton(text="🗺 تغییر استان", callback_data=f"cfg_state:{config_id}"),
                InlineKeyboardButton(text="🏙 تغییر شهر", callback_data=f"cfg_city:{config_id}"),
            ],
            [
                InlineKeyboardButton(text="⏱ زمان تعویض IP", callback_data=f"cfg_life:{config_id}"),
            ],
            [
                InlineKeyboardButton(text="📈 مصرف", callback_data=f"cfg_usage:{config_id}"),
                InlineKeyboardButton(text="🔗 لینک‌ها", callback_data=f"cfg_links:{config_id}"),
            ],
            [
                InlineKeyboardButton(text="♻️ تمدید / افزایش حجم", callback_data=f"cfg_renew:{config_id}"),
            ],
            [
                InlineKeyboardButton(text="🤖 تعیین مشتری (ربات کمکی)", callback_data=f"cfg_cust:{config_id}"),
            ],
        ]
    if is_admin:
        rows.append([InlineKeyboardButton(text="🗑 حذف کانفیگ", callback_data=f"cfg_del:{config_id}")])
    rows.append([InlineKeyboardButton(text="⬅️ بازگشت به لیست", callback_data="cfg_back")])
    rows.append(_home_row())
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_config_actions(config_id: int) -> InlineKeyboardMarkup:
    return config_actions(config_id, is_admin=True)


def confirm_delete(config_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ بله، حذف کن", callback_data=f"cfg_delyes:{config_id}"),
                InlineKeyboardButton(text="❌ انصراف", callback_data=f"cfg_open:{config_id}"),
            ]
        ]
    )


# ---------------------------------------------------------------------- #
#  پنل مدیریت
# ---------------------------------------------------------------------- #
def admin_panel_menu(pending_count: int = 0, *, maintenance_on: bool = False) -> InlineKeyboardMarkup:
    """پنل مدیریت — چیدمان تمیز و گروه‌بندی‌شده؛ همه‌چیز دکمه‌ی شیشه‌ای."""
    pending_label = "🤝 درخواست‌های همکاری"
    if pending_count:
        pending_label += f" ({pending_count})"
    maint_label = ("🟢 حالت تعمیر: خاموش" if not maintenance_on else "🔧 حالت تعمیر: روشن")
    return InlineKeyboardMarkup(
        inline_keyboard=[
            # — نمای کلی —
            [InlineKeyboardButton(text="📊 گزارش و آمار", callback_data="adm:report")],
            # — فروش و محصولات —
            [
                InlineKeyboardButton(text="🧾 سرویس‌ها", callback_data="adm:configs"),
                InlineKeyboardButton(text="🤖 محصولات دیجیتال", callback_data="adm:digital"),
            ],
            [
                InlineKeyboardButton(text="💵 قیمت‌ها", callback_data="adm:prices"),
                InlineKeyboardButton(text="💳 روش‌های پرداخت", callback_data="adm:pay"),
            ],
            # — کاربران —
            [
                InlineKeyboardButton(text="🔎 پروفایل کاربر", callback_data="adm:userinfo"),
                InlineKeyboardButton(text="👤 مدیریت کاربران", callback_data="adm:users"),
            ],
            [
                InlineKeyboardButton(text="💳 شارژ دستی", callback_data="adm:credit"),
                InlineKeyboardButton(text="🧾 تراکنش‌ها", callback_data="adm:payments"),
            ],
            [
                InlineKeyboardButton(text=pending_label, callback_data="adm:requests"),
                InlineKeyboardButton(text="🎁 رفرال/تخفیف", callback_data="adm:refdisc"),
            ],
            [InlineKeyboardButton(text="📣 پیام همگانی", callback_data="adm:broadcast")],
            # — پیکربندی —
            [
                InlineKeyboardButton(text="⚙️ تنظیمات سرور", callback_data="adm:settings"),
                InlineKeyboardButton(text="🔀 نمایش بخش‌ها", callback_data="adm:toggles"),
            ],
            [
                InlineKeyboardButton(text="📡 وضعیت سرویس‌ها", callback_data="menu:status"),
                InlineKeyboardButton(text="🤖 ربات کمکی", callback_data="adm:custbot"),
            ],
            # — سیستم و امنیت —
            [
                InlineKeyboardButton(text="🌐 پنل وب مدیریتی", callback_data="adm:web"),
                InlineKeyboardButton(text="🛡 لاگ امنیتی", callback_data="adm:audit"),
            ],
            [
                InlineKeyboardButton(text="💾 پشتیبان دیتابیس", callback_data="adm:backup"),
                InlineKeyboardButton(text=maint_label, callback_data="adm:maint"),
            ],
            _home_row(),
        ]
    )


def user_actions_kb(tg_id: int, *, banned: bool, is_admin: bool = False) -> InlineKeyboardMarkup:
    """کیبورد اقدامات روی یک کاربر مشخص (پروفایل/مدیریت کاربر)."""
    ban_btn = (
        InlineKeyboardButton(text="✅ رفع مسدودی", callback_data=f"uinfo:unban:{tg_id}")
        if banned else
        InlineKeyboardButton(text="🚫 مسدود کردن", callback_data=f"uinfo:ban:{tg_id}")
    )
    admin_btn = (
        InlineKeyboardButton(text="⬇️ حذف از ادمین", callback_data=f"uinfo:rmadmin:{tg_id}")
        if is_admin else
        InlineKeyboardButton(text="👑 ادمین‌کردن", callback_data=f"uinfo:mkadmin:{tg_id}")
    )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="💳 تغییر موجودی", callback_data=f"uinfo:credit:{tg_id}"),
                InlineKeyboardButton(text="✏️ تغییر نقش", callback_data=f"uinfo:role:{tg_id}"),
            ],
            [
                ban_btn,
                InlineKeyboardButton(text="🏷 تخفیف", callback_data=f"disc:{tg_id}:all"),
            ],
            [
                InlineKeyboardButton(text="✉️ پیام مستقیم", callback_data=f"uinfo:dm:{tg_id}"),
                admin_btn,
            ],
            _panel_row(),
        ]
    )


def payments_admin_menu(*, crypto_on: bool, nowpayments_on: bool, hooshpay_on: bool = False) -> InlineKeyboardMarkup:
    """منوی مدیریت روش‌های پرداخت + تنظیمات کریپتو و پلن V2Ray."""
    def mark(on: bool) -> str:
        return "✅" if on else "❌"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text=f"{mark(hooshpay_on)} درگاه ریالی HooshPay", callback_data="paytgl:hooshpay"
            )],
            [
                InlineKeyboardButton(text="🔑 کلید API ریالی", callback_data="set:hooshpay_key"),
                InlineKeyboardButton(text="🔐 Secret ریالی", callback_data="set:hooshpay_secret"),
            ],
            [InlineKeyboardButton(
                text=f"{mark(crypto_on)} پرداخت مستقیم USDT (BEP20)", callback_data="paytgl:crypto"
            )],
            [InlineKeyboardButton(
                text=f"{mark(nowpayments_on)} درگاه NowPayments", callback_data="paytgl:nowpayments"
            )],
            [InlineKeyboardButton(text="👛 آدرس ولت مقصد (USDT BEP20)", callback_data="set:crypto_wallet")],
            [InlineKeyboardButton(text="🔗 آدرس RPC شبکه BSC", callback_data="set:bsc_rpc")],
            [InlineKeyboardButton(text="🔒 تعداد تأیید لازم", callback_data="set:crypto_conf")],
            [InlineKeyboardButton(text="🛡 شناسه اینباند V2Ray", callback_data="set:v2ray_inbound")],
            [InlineKeyboardButton(text="🛡 قیمت پلن V2Ray (عادی)", callback_data="set:v2ray_plan_price")],
            [InlineKeyboardButton(text="🛡 قیمت پلن V2Ray (همکار)", callback_data="set:v2ray_plan_reseller")],
            _panel_row(),
        ]
    )


def referral_discounts_menu(*, autoconfirm_on: bool) -> InlineKeyboardMarkup:
    """منوی رفرال، تخفیف کاربران و کلید تأیید خودکار."""
    mark = "✅" if autoconfirm_on else "❌"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎁 درصد پاداش رفرال", callback_data="set:referral_percent")],
            [InlineKeyboardButton(text="🏷 تعیین تخفیف برای کاربر", callback_data="disc:add")],
            [InlineKeyboardButton(text="📋 لیست تخفیف‌ها", callback_data="disc:list")],
            [InlineKeyboardButton(text=f"{mark} تأیید خودکار کریپتو", callback_data="paytgl:autoconfirm")],
            _panel_row(),
        ]
    )


def settings_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🌐 IP/دامنه سرور", callback_data="set:server_ip")],
            [InlineKeyboardButton(text="🔐 SNI", callback_data="set:sni")],
            [InlineKeyboardButton(text="📛 Host Header", callback_data="set:host")],
            [InlineKeyboardButton(text="📦 حداقل حجم خرید", callback_data="set:min_volume")],
            [InlineKeyboardButton(text="♻️ حداقل حجم تمدید", callback_data="set:renew_min_volume")],
            [InlineKeyboardButton(text="🌍 رزیدنتال ۲ — هاست", callback_data="set:iproyal_host")],
            [InlineKeyboardButton(text="🌍 رزیدنتال ۲ — پورت", callback_data="set:iproyal_port")],
            [InlineKeyboardButton(text="🌍 رزیدنتال ۲ — یوزرنیم", callback_data="set:iproyal_username")],
            [InlineKeyboardButton(text="🌍 رزیدنتال ۲ — پسورد", callback_data="set:iproyal_password")],
            _panel_row(),
        ]
    )


def prices_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🌐 رزیدنتال - عادی", callback_data="set:price")],
            [InlineKeyboardButton(text="🌐 رزیدنتال - همکار", callback_data="set:reseller_price")],
            [InlineKeyboardButton(text="🌍 رزیدنتال ۲ - عادی", callback_data="set:residential2_price")],
            [InlineKeyboardButton(text="🌍 رزیدنتال ۲ - همکار", callback_data="set:residential2_reseller_price")],
            [InlineKeyboardButton(text="🛡 V2Ray - عادی", callback_data="set:v2ray_price")],
            [InlineKeyboardButton(text="🛡 V2Ray - همکار", callback_data="set:v2ray_reseller_price")],
            [InlineKeyboardButton(text="💰 حداقل موجودی همکار v2ray", callback_data="set:reseller_min_balance")],
            [InlineKeyboardButton(text="💵 حداقل شارژ کیف پول", callback_data="set:min_topup")],
            [InlineKeyboardButton(text="💱 نرخ تتر/تومان", callback_data="set:toman_rate")],
            _panel_row(),
        ]
    )


def toggles_menu(
    *,
    partnership: bool,
    residential: bool,
    residential2: bool,
    v2ray: bool,
) -> InlineKeyboardMarkup:
    """منوی نمایش/مخفی‌سازی بخش‌ها؛ هر دکمه وضعیت فعلی را نشان می‌دهد و با زدن آن برعکس می‌شود."""
    def mark(on: bool) -> str:
        return "✅" if on else "❌"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"{mark(partnership)} همکاری", callback_data="tgl:partnership")],
            [InlineKeyboardButton(text=f"{mark(residential)} رزیدنتال", callback_data="tgl:residential")],
            [InlineKeyboardButton(text=f"{mark(residential2)} رزیدنتال ۲", callback_data="tgl:residential2")],
            [InlineKeyboardButton(text=f"{mark(v2ray)} V2Ray", callback_data="tgl:v2ray")],
            _panel_row(),
        ]
    )


def custbot_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="ℹ️ راهنمای راه‌اندازی", callback_data="custbot:help")],
            _panel_row(),
        ]
    )


def users_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📋 لیست همه‌ی کاربران", callback_data="adm:allusers:0")],
            [InlineKeyboardButton(text="🌐 لیست همکاران رزیدنتال", callback_data="usr:list_res")],
            [InlineKeyboardButton(text="🛡 لیست همکاران v2ray", callback_data="usr:list_v2")],
            [InlineKeyboardButton(text="🔎 پروفایل/مدیریت کاربر", callback_data="adm:userinfo")],
            [InlineKeyboardButton(text="✏️ تعیین نقش با آیدی", callback_data="usr:setrole")],
            [InlineKeyboardButton(text="👑 مدیریت ادمین‌ها", callback_data="adm:admins")],
            _panel_row(),
        ]
    )


def admins_menu(admin_ids: list[int], main_admin_id: int = 0) -> InlineKeyboardMarkup:
    """مدیریت ادمین‌های اضافه: افزودن با آیدی و حذف هر ادمین."""
    kb: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text="➕ افزودن ادمین با آیدی", callback_data="adm:addadmin")],
    ]
    for aid in admin_ids:
        kb.append([
            InlineKeyboardButton(text=f"⬇️ حذف {aid}", callback_data=f"adm:rmadmin:{aid}"),
        ])
    kb.append(_panel_row())
    return InlineKeyboardMarkup(inline_keyboard=kb)


def users_list_keyboard(rows: list, *, page: int, has_next: bool, currency: str = "") -> InlineKeyboardMarkup:
    """لیست کاربران با دکمه‌ی هر کاربر (باز کردن پروفایل) + ناوبری صفحه."""
    kb: list[list[InlineKeyboardButton]] = []
    for r in rows:
        role = r["role"] if "role" in r.keys() else "user"
        role_icon = {"admin": "👑", "residential_reseller": "🌐", "v2ray_reseller": "🛡"}.get(role, "👤")
        banned = ""
        try:
            banned = "🚫" if int(r["is_banned"] or 0) else ""
        except (KeyError, IndexError, TypeError, ValueError):
            banned = ""
        label = f"{banned}{role_icon} {r['tg_id']} • {float(r['balance']):g}"
        kb.append([InlineKeyboardButton(text=label, callback_data=f"uopen:{r['tg_id']}")])
    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️ قبلی", callback_data=f"adm:allusers:{page-1}"))
    if has_next:
        nav.append(InlineKeyboardButton(text="بعدی ➡️", callback_data=f"adm:allusers:{page+1}"))
    if nav:
        kb.append(nav)
    kb.append(_panel_row())
    return InlineKeyboardMarkup(inline_keyboard=kb)


def setrole_keyboard(tg_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🌐 همکار رزیدنتال", callback_data=f"role:{tg_id}:residential_reseller")],
            [InlineKeyboardButton(text="🛡 همکار v2ray", callback_data=f"role:{tg_id}:v2ray_reseller")],
            [InlineKeyboardButton(text="👤 کاربر عادی", callback_data=f"role:{tg_id}:user")],
            _panel_row(),
        ]
    )
