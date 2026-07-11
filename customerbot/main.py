"""ربات کمکی مشتری (Customer Bot) — تغییر IP و مشاهده تنظیمات سرویس.

این یک ربات تلگرام جداگانه و سبک است که هر کسی می‌تواند آن را استارت کند؛ اما
هر کاربر فقط سرویس‌هایی را می‌بیند که همکار/مالک از داخل «مدیریت سفارش» در ربات
اصلی، آیدی عددی او را برای همان سرویس مشخص تعیین کرده باشد (دکمه‌ی «🤖 تعیین
مشتری (ربات کمکی)» روی هر کانفیگ).

مشتری می‌تواند برای سرویس‌هایی که به او سپرده شده:
  - لیست آن‌ها را ببیند
  - IP را تغییر دهد
  - کشور/شهر و زمان تعویض خودکار را تنظیم کند (شامل رزیدنتال و رزیدنتال ۲)
  - مصرف را ببیند و اتصال را تست کند و لینک سرویس را بگیرد
"""
from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

# پروژه resibot در یک سطح بالاتر قرار دارد؛ مسیر را اضافه می‌کنیم
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from bot.config import settings as main_settings
from bot.database import Database
from bot.panel import PanelClient
from bot.service import Service
from .config import load_customer_config
from .handlers import register_handlers
from .middlewares import CustomerContextMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("customerbot")


async def run() -> None:
    cb_cfg = load_customer_config()

    if not cb_cfg.customer_bot_token:
        logger.error("CUSTOMER_BOT_TOKEN تنظیم نشده است. لطفاً آن را در .env تنظیم کنید.")
        sys.exit(1)

    # از همان دیتابیس اصلی استفاده می‌کنیم
    db = Database(main_settings.db_full_path())

    panel = PanelClient(
        base_url=main_settings.panel_base_url,
        api_token=main_settings.panel_api_token,
        username=main_settings.panel_username,
        password=main_settings.panel_password,
    )

    service = Service(main_settings, db, panel)
    service.seed_settings()

    bot = Bot(
        token=cb_cfg.customer_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    dp["cfg"] = main_settings
    dp["db"] = db
    dp["service"] = service

    dp.update.outer_middleware(CustomerContextMiddleware())

    register_handlers(dp)

    logger.info(
        "Customer Bot در حال اجرا است. هر مشتری فقط سرویس‌هایی را می‌بیند که "
        "همکارش در «مدیریت سفارش» به او سپرده باشد."
    )
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await panel.close()
        db.close()
        await bot.session.close()


def main() -> None:
    try:
        asyncio.run(run())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Customer Bot خاموش شد.")


if __name__ == "__main__":
    main()
