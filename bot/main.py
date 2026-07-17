"""نقطه‌ی ورود ربات w2f (Way To Freedom)."""
from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from .config import ConfigError, settings
from .crypto import BscRpc, CryptoWatcher
from .database import Database
from .fulfillment import deliver_paid_order
from .handlers import register_handlers
from .ipn import start_ipn_server
from .middlewares import ContextMiddleware
from .nowpayments import NowPaymentsClient
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

    nowpayments = (
        NowPaymentsClient(settings.nowpayments_api_key)
        if settings.nowpayments_api_key
        else None
    )

    service = Service(settings, db, panel, nowpayments=nowpayments)
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

    # میدلور ثبت کاربر و تزریق نقش
    dp.update.outer_middleware(ContextMiddleware(settings, db))

    register_handlers(dp, settings, db)

    ipn_runner = None
    if settings.nowpayments_enabled:
        try:
            ipn_runner = await start_ipn_server(settings, db, bot, service)
        except Exception:  # noqa: BLE001
            logger.exception("راه‌اندازی سرور IPN ناموفق بود؛ شارژ خودکار غیرفعال می‌ماند")
    else:
        logger.info("NowPayments پیکربندی نشده؛ شارژ کیف پول از طریق درگاه غیرفعال است")

    # رصدگر پرداخت مستقیم کریپتو (USDT BEP20) — فقط رصد، بدون کلید خصوصی.
    async def _settle_crypto(order_id: str, tx_hash: str) -> None:
        row = service.settle_crypto_payment(order_id, tx_hash)
        if row is not None:
            await deliver_paid_order(bot, settings, db, service, row)

    crypto_watcher = CryptoWatcher(
        rpc=BscRpc(service.bsc_rpc_url),
        db=db,
        get_confirmations=lambda: service.crypto_confirmations,
        settle=_settle_crypto,
    )
    watcher_task = asyncio.create_task(crypto_watcher.run())

    logger.info("%s در حال اجرا است...", settings.brand_name)
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        crypto_watcher.stop()
        watcher_task.cancel()
        try:
            await watcher_task
        except (asyncio.CancelledError, Exception):  # noqa: BLE001
            pass
        if ipn_runner is not None:
            await ipn_runner.cleanup()
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
