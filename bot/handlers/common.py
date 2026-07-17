"""هندلرهای عمومی: /start، /id، منوی اصلی (شیشه‌ای) و منوی محصولات."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

from ..config import Settings
from ..database import (
    PRODUCT_RESIDENTIAL,
    PRODUCT_RESIDENTIAL2,
    PRODUCT_V2RAY,
    ROLE_RESIDENTIAL_RESELLER,
    ROLE_V2RAY_RESELLER,
)
from ..keyboards import main_menu, products_menu
from ..service import S_SHOW_PARTNERSHIP, Service

router = Router(name="common")


def _is_reseller(role: str) -> bool:
    return role in (ROLE_RESIDENTIAL_RESELLER, ROLE_V2RAY_RESELLER)


def _intro_text(cfg: Settings, role: str, is_admin: bool) -> str:
    title = f"<b>{cfg.brand_name}</b> — {cfg.brand_full}"
    if is_admin:
        return f"👋 سلام ادمین گرامی!\nبه پنل مدیریت {title} خوش آمدید."
    if _is_reseller(role):
        return f"👋 سلام همکار گرامی!\nبه {title} خوش آمدید."
    return (
        f"👋 به {title} خوش آمدید!\n\n"
        "از منوی زیر می‌توانید سرویس بخرید، سرویس‌هایتان را مدیریت کنید، "
        "کیف پولتان را شارژ کنید یا درخواست همکاری بدهید."
    )


def _menu_kb(service: Service, role: str, is_admin: bool):
    return main_menu(
        is_admin=is_admin,
        is_reseller=_is_reseller(role),
        show_partnership=service.feature_enabled(S_SHOW_PARTNERSHIP),
    )


@router.message(CommandStart())
async def cmd_start(
    message: Message, state: FSMContext, cfg: Settings, service: Service, role: str, is_admin: bool
) -> None:
    await state.clear()
    # کیبورد قدیمی پایین صفحه (reply) را حذف می‌کنیم تا فقط دکمه‌های شیشه‌ای بماند.
    try:
        await message.answer("⌛️", reply_markup=ReplyKeyboardRemove())
    except Exception:  # noqa: BLE001
        pass
    await message.answer(
        _intro_text(cfg, role, is_admin),
        reply_markup=_menu_kb(service, role, is_admin),
    )


@router.callback_query(F.data == "menu:home")
async def menu_home(
    call: CallbackQuery, state: FSMContext, cfg: Settings, service: Service, role: str, is_admin: bool
) -> None:
    await state.clear()
    await call.answer()
    await call.message.answer(
        _intro_text(cfg, role, is_admin),
        reply_markup=_menu_kb(service, role, is_admin),
    )


@router.message(Command("id"))
async def cmd_id(message: Message) -> None:
    await message.answer(f"🆔 آیدی عددی شما: <code>{message.from_user.id}</code>")


# ---------------------------------------------------------------------- #
#  منوی محصولات
# ---------------------------------------------------------------------- #
async def _send_products(target: Message, state: FSMContext, service: Service) -> None:
    await state.clear()
    res = service.product_enabled(PRODUCT_RESIDENTIAL)
    res2 = service.product_enabled(PRODUCT_RESIDENTIAL2)
    v2 = service.product_enabled(PRODUCT_V2RAY)
    if not (res or res2 or v2):
        await target.answer("در حال حاضر هیچ محصولی برای فروش فعال نیست.")
        return
    await target.answer(
        "🛍 <b>محصولات</b>\nیکی از سرویس‌های زیر را انتخاب کنید:",
        reply_markup=products_menu(residential=res, residential2=res2, v2ray=v2),
    )


@router.callback_query(F.data == "menu:buy")
async def menu_buy(call: CallbackQuery, state: FSMContext, service: Service) -> None:
    await call.answer()
    await _send_products(call.message, state, service)


@router.message(F.text == "🛒 خرید سرویس")
async def show_products(message: Message, state: FSMContext, service: Service) -> None:
    await _send_products(message, state, service)


@router.callback_query(F.data == "noop")
async def noop(call: CallbackQuery) -> None:
    await call.answer()
