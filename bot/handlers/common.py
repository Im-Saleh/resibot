"""هندلرهای عمومی: /start، /id و کمک."""
from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from ..config import Settings
from ..database import Database
from ..keyboards import admin_menu, reseller_menu

router = Router(name="common")


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, cfg: Settings, db: Database) -> None:
    await state.clear()
    uid = message.from_user.id
    if uid == cfg.admin_id:
        await message.answer(
            "👋 سلام ادمین گرامی!\nبه پنل مدیریت <b>resibot</b> خوش آمدید.",
            reply_markup=admin_menu(),
        )
    elif db.is_reseller(uid):
        await message.answer(
            "👋 سلام نماینده‌ی گرامی!\nبرای ثبت سفارش از منوی زیر استفاده کنید.",
            reply_markup=reseller_menu(),
        )
    else:
        await message.answer(
            "⛔️ شما دسترسی به این ربات ندارید.\n"
            f"آیدی عددی شما: <code>{uid}</code>\n"
            "برای دریافت دسترسی این آیدی را به ادمین بدهید."
        )


@router.message(Command("id"))
async def cmd_id(message: Message) -> None:
    await message.answer(f"🆔 آیدی عددی شما: <code>{message.from_user.id}</code>")
