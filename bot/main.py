"""نقطه‌ی ورود ربات resibot."""
from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from .config import ConfigError, settings
from .database import Database
from .handlers import register_handlers
from .panel import PanelClient
from .service import Service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("resibot")


async def run() -> None:
    try:
        settings.validate()
    except ConfigError as exc:
        logger.error("%s", exc)
        sys.exit(1)

    db = Database(settings.db_full_path())

    panel = PanelClient(
        base_url=settings.panel_base_url,
        api_token=settings.panel_api_token,
        username=settings.panel_username,
        password=settings.panel_password,
    )

    service = Service(settings, db, panel)
    service.seed_settings()

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    # تزریق وابستگی‌ها به هندلرها
    dp["cfg"] = settings
    dp["db"] = db
    dp["service"] = service

    register_handlers(dp, settings, db)

    logger.info("resibot در حال اجرا است...")
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
        logger.info("خاموش شد.")


if __name__ == "__main__":
    main()
