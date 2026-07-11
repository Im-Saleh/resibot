"""هندلرهای عمومی ربات کمکی مشتری: /start، راهنما."""
from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from bot.database import Database

from ..keyboards import main_menu

logger = logging.getLogger("customerbot.common")
router = Router(name="cust_common")

_HELP_TEXT = (
    "🤖 <b>ربات کمکی مدیریت سرویس</b>\n\n"
    "با این ربات می‌توانید سرویس‌هایی را که همکارتان برایتان فعال کرده مدیریت کنید:\n"
    "• <b>📋 سرویس‌های من</b> — مشاهده لیست سرویس‌هایتان\n"
    "• <b>🔄 تغییر IP</b> — تغییر فوری IP سرویس\n"
    "• <b>🗺 تغییر کشور/شهر</b> — تغییر لوکیشن سرویس\n"
    "• <b>⏱ زمان تعویض IP</b> — تنظیم بازه‌ی تعویض خودکار IP\n"
    "• <b>🌍 اطلاعات IP</b> — مشاهده لوکیشن و session فعلی\n"
    "• <b>📊 مصرف</b> — مشاهده حجم مصرف‌شده و باقیمانده\n"
    "• <b>📡 تست اتصال</b> — بررسی وضعیت اتصال سرویس\n"
    "• <b>🔗 لینک سرویس</b> — دریافت لینک ساب و لینک مستقیم\n\n"
    "از منوی زیر شروع کنید 👇"
)

_NO_SERVICE_TEXT = (
    "سلام! 👋\n\n"
    "در حال حاضر هیچ سرویسی برای آیدی شما در این ربات تعریف نشده است.\n\n"
    "برای فعال‌سازی، با همکاری که از او خرید کرده‌اید تماس بگیرید تا از طریق "
    "«مدیریت سفارش» شما را به‌عنوان مشتریِ سرویس‌تان تعیین کند. سپس می‌توانید "
    "دوباره با /start وارد شوید."
)


@router.message(CommandStart())
async def cmd_start(message: Message, db: Database) -> None:
    rows = db.list_configs_by_customer(message.from_user.id)
    if not rows:
        await message.answer(_NO_SERVICE_TEXT)
        return
    await message.answer(f"سلام! 👋\n{_HELP_TEXT}", reply_markup=main_menu())


@router.message(F.text == "ℹ️ راهنما")
async def cmd_help(message: Message) -> None:
    await message.answer(_HELP_TEXT, reply_markup=main_menu())
