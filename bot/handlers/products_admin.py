"""مدیریت محصولات دیجیتال از پنل ادمین تلگرام — همه با دکمه‌های شیشه‌ای.

امکانات:
  - افزودن محصول جدید (شناسه، عنوان، قیمت)
  - ویرایش عنوان، زیرعنوان، متن فروش، قیمت، مدت اعتبار
  - فعال/غیرفعال‌سازی و حذف محصول
  - افزودن/مشاهده/پاک‌سازی موجودی انبار (اکانت‌ها/کدها)

این هندلر فقط برای ادمین ثبت می‌شود (فیلتر در handlers/__init__).
"""
from __future__ import annotations

import logging
from html import escape

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from ..database import Database
from ..digital import valid_slug
from ..service import Service
from ..states import DigitalAdminStates

logger = logging.getLogger("resibot.products_admin")
router = Router(name="products_admin")


# نگاشت فیلدهای قابل ویرایش → (برچسب، راهنما، نوع)
_EDIT_FIELDS = {
    "title": ("عنوان", "عنوان جدید محصول را بفرستید:", "text"),
    "subtitle": ("زیرعنوان", "زیرعنوان (یک خط کوتاه) را بفرستید:", "text"),
    "description": ("متن فروش", "متن فروش/توضیحات کامل را بفرستید (می‌تواند چند خط و شامل HTML ساده باشد):", "text"),
    "price": ("قیمت (USD)", "قیمت جدید به دلار را بفرستید (مثلاً 12.5):", "float"),
    "duration_days": ("مدت اعتبار (روز)", "مدت اعتبار به روز را بفرستید (0 یعنی نامشخص):", "int"),
}


def _panel_row() -> list[InlineKeyboardButton]:
    return [InlineKeyboardButton(text="🔙 بازگشت به پنل", callback_data="menu:admin")]


def _products_list_kb(db: Database) -> InlineKeyboardMarkup:
    products = db.list_digital_products()
    stock = db.stock_counts()
    rows: list[list[InlineKeyboardButton]] = []
    for p in products:
        avail = int(stock.get(int(p["id"]), 0))
        state_icon = "🟢" if int(p["active"]) else "🔴"
        rows.append([InlineKeyboardButton(
            text=f"{state_icon} {p['title']} • {float(p['price']):g}$ • انبار {avail}",
            callback_data=f"dp:open:{p['id']}",
        )])
    rows.append([InlineKeyboardButton(text="➕ افزودن محصول جدید", callback_data="dp:add")])
    rows.append(_panel_row())
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _product_actions_kb(product_id: int, *, active: bool) -> InlineKeyboardMarkup:
    toggle = "🔴 غیرفعال کردن" if active else "🟢 فعال کردن"
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✏️ عنوان", callback_data=f"dp:edit:{product_id}:title"),
            InlineKeyboardButton(text="✏️ زیرعنوان", callback_data=f"dp:edit:{product_id}:subtitle"),
        ],
        [
            InlineKeyboardButton(text="📝 متن فروش", callback_data=f"dp:edit:{product_id}:description"),
            InlineKeyboardButton(text="💵 قیمت", callback_data=f"dp:edit:{product_id}:price"),
        ],
        [InlineKeyboardButton(text="⏳ مدت اعتبار", callback_data=f"dp:edit:{product_id}:duration_days")],
        [
            InlineKeyboardButton(text="➕ افزودن موجودی", callback_data=f"dp:stock:{product_id}"),
            InlineKeyboardButton(text="📦 مشاهده انبار", callback_data=f"dp:stockview:{product_id}"),
        ],
        [
            InlineKeyboardButton(text=toggle, callback_data=f"dp:toggle:{product_id}"),
            InlineKeyboardButton(text="🧹 خالی‌کردن انبار", callback_data=f"dp:clear:{product_id}"),
        ],
        [InlineKeyboardButton(text="🗑 حذف محصول", callback_data=f"dp:del:{product_id}")],
        [InlineKeyboardButton(text="⬅️ بازگشت به لیست", callback_data="adm:digital")],
        _panel_row(),
    ])


def _product_detail(db: Database, service: Service, product) -> str:
    pid = int(product["id"])
    avail = db.count_available_stock(pid)
    sold = db.count_digital_sales(pid)
    price_usd = float(product["price"])
    return "\n".join([
        f"🧩 <b>{escape(product['title'])}</b>",
        f"🔖 شناسه: <code>{escape(product['slug'])}</code>",
        f"📄 زیرعنوان: {escape(product['subtitle'] or '—')}",
        f"💵 قیمت: <b>{price_usd:g} USDT</b> (≈ {service.digital_price_toman(price_usd):g} {service.currency})",
        f"⏳ مدت اعتبار: <b>{int(product['duration_days'] or 0)} روز</b>",
        f"⚙️ وضعیت: {'🟢 فعال' if int(product['active']) else '🔴 غیرفعال'}",
        f"📦 موجودی آماده: <b>{avail}</b> | فروخته‌شده: <b>{sold}</b>",
        "",
        "📝 <b>متن فروش فعلی:</b>",
        (product["description"] or "—"),
    ])


# ====================================================================== #
#  ورود به مدیریت محصولات
# ====================================================================== #
@router.callback_query(F.data == "adm:digital")
async def adm_digital(call: CallbackQuery, state: FSMContext, db: Database) -> None:
    await state.clear()
    await call.answer()
    await call.message.answer(
        "🤖 <b>مدیریت محصولات دیجیتال</b>\n"
        "محصولات (Gemini، ChatGPT و ...) را از اینجا بسازید، ویرایش کنید و انبار را شارژ کنید.\n\n"
        "🟢 فعال | 🔴 غیرفعال — روی هر محصول بزنید:",
        reply_markup=_products_list_kb(db),
    )


@router.callback_query(F.data.startswith("dp:open:"))
async def dp_open(call: CallbackQuery, state: FSMContext, db: Database, service: Service) -> None:
    await state.clear()
    await call.answer()
    try:
        pid = int(call.data.split(":")[2])
    except (ValueError, IndexError):
        await call.answer("نامعتبر", show_alert=True)
        return
    product = db.get_digital_product(pid)
    if not product:
        await call.message.answer("محصول پیدا نشد.", reply_markup=_products_list_kb(db))
        return
    await call.message.answer(
        _product_detail(db, service, product),
        reply_markup=_product_actions_kb(pid, active=bool(int(product["active"]))),
    )


# ====================================================================== #
#  افزودن محصول جدید
# ====================================================================== #
@router.callback_query(F.data == "dp:add")
async def dp_add(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(DigitalAdminStates.new_slug)
    await call.answer()
    await call.message.answer(
        "🔖 یک <b>شناسه‌ی یکتا</b> برای محصول بفرستید (فقط حروف کوچک انگلیسی، عدد، «-» و «_»).\n"
        "مثال: <code>gemini_18m</code> یا <code>chatgpt_1m</code>"
    )


@router.message(DigitalAdminStates.new_slug)
async def dp_new_slug(message: Message, state: FSMContext, db: Database) -> None:
    slug = (message.text or "").strip().lower()
    if not valid_slug(slug):
        await message.answer("⛔️ شناسه نامعتبر است. فقط حروف کوچک انگلیسی/عدد/«-»/«_» و ۲ تا ۴۱ نویسه.")
        return
    if db.get_digital_product_by_slug(slug) is not None:
        await message.answer("⛔️ محصولی با این شناسه از قبل وجود دارد. شناسه‌ی دیگری بفرستید.")
        return
    await state.update_data(new_slug=slug)
    await state.set_state(DigitalAdminStates.new_title)
    await message.answer("📝 عنوان نمایشی محصول را بفرستید (مثلاً «اشتراک ChatGPT یک‌ماهه»):")


@router.message(DigitalAdminStates.new_title)
async def dp_new_title(message: Message, state: FSMContext) -> None:
    title = (message.text or "").strip()
    if len(title) < 2:
        await message.answer("⛔️ عنوان خیلی کوتاه است. دوباره بفرستید:")
        return
    await state.update_data(new_title=title[:120])
    await state.set_state(DigitalAdminStates.new_price)
    await message.answer("💵 قیمت محصول را به دلار (USDT) بفرستید (مثلاً 8 یا 12.5):")


@router.message(DigitalAdminStates.new_price)
async def dp_new_price(message: Message, state: FSMContext, db: Database) -> None:
    raw = (message.text or "").strip().replace(",", ".")
    try:
        price = round(float(raw), 2)
        if price < 0:
            raise ValueError
    except ValueError:
        await message.answer("⛔️ یک عدد معتبر و نامنفی بفرستید:")
        return
    data = await state.get_data()
    await state.clear()
    slug = data.get("new_slug", "")
    title = data.get("new_title", slug)
    pid = db.create_digital_product(
        slug, title, price=price, currency="USD",
        description="این محصول به‌زودی توضیحات کامل خواهد داشت.", active=False,
    )
    db.audit("digital_product_create", actor=str(message.from_user.id), detail=f"{slug} ({price}$)")
    await message.answer(
        f"✅ محصول <b>{escape(title)}</b> ساخته شد (فعلاً غیرفعال).\n"
        f"🔖 شناسه: <code>{escape(slug)}</code>\n"
        "حالا متن فروش را ویرایش کنید، انبار را شارژ کنید و بعد فعالش کنید.",
        reply_markup=_product_actions_kb(pid, active=False),
    )


# ====================================================================== #
#  ویرایش فیلدها
# ====================================================================== #
@router.callback_query(F.data.startswith("dp:edit:"))
async def dp_edit_start(call: CallbackQuery, state: FSMContext) -> None:
    parts = call.data.split(":")
    if len(parts) != 4 or not parts[2].isdigit() or parts[3] not in _EDIT_FIELDS:
        await call.answer("نامعتبر", show_alert=True)
        return
    pid, field = int(parts[2]), parts[3]
    label, prompt, _kind = _EDIT_FIELDS[field]
    await state.set_state(DigitalAdminStates.edit_value)
    await state.update_data(edit_pid=pid, edit_field=field)
    await call.answer()
    await call.message.answer(f"✏️ ویرایش «{label}»\n{prompt}")


@router.message(DigitalAdminStates.edit_value)
async def dp_edit_save(message: Message, state: FSMContext, db: Database, service: Service) -> None:
    data = await state.get_data()
    pid = int(data.get("edit_pid", 0))
    field = data.get("edit_field", "")
    if field not in _EDIT_FIELDS:
        await state.clear()
        await message.answer("⛔️ فیلد نامعتبر.")
        return
    label, _prompt, kind = _EDIT_FIELDS[field]
    # برای متن فروش، HTML خام کاربر ادمین حفظ می‌شود؛ برای بقیه فقط trim.
    raw = message.html_text if (field == "description" and message.text) else (message.text or "").strip()
    if kind == "float":
        try:
            value = round(float(raw.replace(",", ".")), 2)
            if value < 0:
                raise ValueError
        except ValueError:
            await message.answer("⛔️ یک عدد معتبر و نامنفی بفرستید:")
            return
    elif kind == "int":
        if not raw.isdigit():
            await message.answer("⛔️ یک عدد صحیح بفرستید:")
            return
        value = int(raw)
    else:
        if not raw:
            await message.answer("⛔️ متن خالی است. دوباره بفرستید:")
            return
        value = raw[:4000]
    await state.clear()
    db.update_digital_product(pid, **{field: value})
    db.audit("digital_product_edit", actor=str(message.from_user.id), detail=f"#{pid} {field}")
    product = db.get_digital_product(pid)
    if not product:
        await message.answer("محصول پیدا نشد.")
        return
    await message.answer(
        f"✅ «{label}» به‌روزرسانی شد.",
    )
    await message.answer(
        _product_detail(db, service, product),
        reply_markup=_product_actions_kb(pid, active=bool(int(product["active"]))),
    )


# ====================================================================== #
#  موجودی انبار
# ====================================================================== #
@router.callback_query(F.data.startswith("dp:stock:"))
async def dp_stock_start(call: CallbackQuery, state: FSMContext, db: Database) -> None:
    try:
        pid = int(call.data.split(":")[2])
    except (ValueError, IndexError):
        await call.answer("نامعتبر", show_alert=True)
        return
    if not db.get_digital_product(pid):
        await call.answer("محصول پیدا نشد.", show_alert=True)
        return
    await state.set_state(DigitalAdminStates.add_stock)
    await state.update_data(stock_pid=pid)
    await call.answer()
    await call.message.answer(
        "📦 اقلام موجودی را بفرستید — <b>هر خط یک اکانت/کد</b>.\n"
        "همان متنی که به مشتری تحویل داده می‌شود (مثلاً ایمیل:پسورد یا کد فعال‌سازی).\n\n"
        "می‌توانید چند خط را یک‌جا بفرستید."
    )


@router.message(DigitalAdminStates.add_stock)
async def dp_stock_save(message: Message, state: FSMContext, db: Database, service: Service) -> None:
    data = await state.get_data()
    pid = int(data.get("stock_pid", 0))
    await state.clear()
    text = message.text or ""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        await message.answer("⛔️ چیزی برای افزودن پیدا نشد.")
        return
    added = db.add_stock_items(pid, lines)
    db.audit("digital_stock_add", actor=str(message.from_user.id), detail=f"#{pid} +{added}")
    product = db.get_digital_product(pid)
    await message.answer(f"✅ <b>{added}</b> قلم به انبار اضافه شد.")
    if product:
        await message.answer(
            _product_detail(db, service, product),
            reply_markup=_product_actions_kb(pid, active=bool(int(product["active"]))),
        )


@router.callback_query(F.data.startswith("dp:stockview:"))
async def dp_stock_view(call: CallbackQuery, db: Database) -> None:
    await call.answer()
    try:
        pid = int(call.data.split(":")[2])
    except (ValueError, IndexError):
        await call.answer("نامعتبر", show_alert=True)
        return
    rows = db.list_stock(pid, limit=30)
    if not rows:
        await call.message.answer("انبار این محصول خالی است.")
        return
    lines = ["📦 <b>۳۰ قلم اخیر انبار:</b>", ""]
    for r in rows:
        icon = "🟢" if r["status"] == "available" else "🔴"
        buyer = f" → <code>{r['buyer_tg_id']}</code>" if r["status"] == "sold" else ""
        lines.append(f"{icon} <code>#{r['id']}</code> {escape(r['payload'][:40])}{buyer}")
    await call.message.answer("\n".join(lines))


@router.callback_query(F.data.startswith("dp:clear:"))
async def dp_clear(call: CallbackQuery, db: Database) -> None:
    try:
        pid = int(call.data.split(":")[2])
    except (ValueError, IndexError):
        await call.answer("نامعتبر", show_alert=True)
        return
    removed = db.clear_available_stock(pid)
    db.audit("digital_stock_clear", actor=str(call.from_user.id), detail=f"#{pid} -{removed}")
    await call.answer(f"{removed} قلم آماده حذف شد.", show_alert=True)


# ====================================================================== #
#  فعال/غیرفعال و حذف
# ====================================================================== #
@router.callback_query(F.data.startswith("dp:toggle:"))
async def dp_toggle(call: CallbackQuery, db: Database, service: Service) -> None:
    try:
        pid = int(call.data.split(":")[2])
    except (ValueError, IndexError):
        await call.answer("نامعتبر", show_alert=True)
        return
    product = db.get_digital_product(pid)
    if not product:
        await call.answer("محصول پیدا نشد.", show_alert=True)
        return
    new_active = 0 if int(product["active"]) else 1
    if new_active and db.count_available_stock(pid) <= 0:
        await call.answer("⚠️ اول انبار را شارژ کنید؛ بدون موجودی فعال نمی‌شود.", show_alert=True)
        return
    db.update_digital_product(pid, active=new_active)
    db.audit("digital_product_toggle", actor=str(call.from_user.id), detail=f"#{pid} active={new_active}")
    await call.answer("✅ فعال شد." if new_active else "🔴 غیرفعال شد.")
    product = db.get_digital_product(pid)
    try:
        await call.message.edit_reply_markup(
            reply_markup=_product_actions_kb(pid, active=bool(new_active))
        )
    except Exception:  # noqa: BLE001
        pass


@router.callback_query(F.data.startswith("dp:del:"))
async def dp_del(call: CallbackQuery, db: Database) -> None:
    try:
        pid = int(call.data.split(":")[2])
    except (ValueError, IndexError):
        await call.answer("نامعتبر", show_alert=True)
        return
    await call.answer()
    await call.message.answer(
        "⚠️ آیا از حذف کامل این محصول و انبارش مطمئن هستید؟ این کار برگشت‌ناپذیر است.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ بله، حذف کن", callback_data=f"dp:delyes:{pid}"),
            InlineKeyboardButton(text="❌ انصراف", callback_data=f"dp:open:{pid}"),
        ]]),
    )


@router.callback_query(F.data.startswith("dp:delyes:"))
async def dp_del_yes(call: CallbackQuery, db: Database) -> None:
    try:
        pid = int(call.data.split(":")[2])
    except (ValueError, IndexError):
        await call.answer("نامعتبر", show_alert=True)
        return
    db.delete_digital_product(pid)
    db.audit("digital_product_delete", actor=str(call.from_user.id), detail=f"#{pid}")
    await call.answer("محصول حذف شد.", show_alert=True)
    await call.message.answer("🗑 محصول حذف شد.", reply_markup=_products_list_kb(db))
