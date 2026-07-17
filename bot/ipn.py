"""سرور دریافت IPN از NowPayments (aiohttp) برای شارژ خودکار کیف پول.

امنیت:
  - امضای هر callback با HMAC تأیید می‌شود؛ درخواست بدون امضای معتبر رد می‌شود.
  - شارژ کیف پول idempotent است (هر پرداخت فقط یک‌بار credit می‌شود).
"""
from __future__ import annotations

import logging
from typing import Any

from aiohttp import web

from .config import Settings
from .database import Database
from .fulfillment import deliver_paid_order
from .nowpayments import PAID_STATUSES, verify_ipn_signature

logger = logging.getLogger("resibot.ipn")


def make_ipn_app(cfg: Settings, db: Database, bot: Any, service: Any = None) -> web.Application:
    app = web.Application()

    async def health(_request: web.Request) -> web.Response:
        return web.Response(text="ok")

    async def ipn_handler(request: web.Request) -> web.Response:
        raw = await request.read()
        signature = request.headers.get("x-nowpayments-sig", "")
        try:
            import json
            payload = json.loads(raw.decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("payload must be object")
        except Exception:
            logger.warning("IPN با بدنه‌ی نامعتبر رد شد")
            return web.json_response({"error": "bad request"}, status=400)

        if not verify_ipn_signature(payload, signature, cfg.nowpayments_ipn_secret):
            logger.warning("IPN با امضای نامعتبر رد شد")
            return web.json_response({"error": "invalid signature"}, status=403)

        order_id = str(payload.get("order_id") or "")
        status = str(payload.get("payment_status") or "")
        payment = db.get_payment_by_order(order_id)
        if not payment:
            # سفارش ناشناس — نادیده می‌گیریم ولی 200 می‌دهیم تا تکرار نشود
            return web.json_response({"ok": True})

        db.set_payment_status(order_id, status, invoice_id=str(payload.get("invoice_id") or ""))

        if status in PAID_STATUSES:
            credited = db.credit_payment_once(order_id)
            if credited is not None:
                # تحویل یکپارچه (رزیدنتال/V2Ray/شارژ کیف پول) — دقیقاً مثل مسیر کریپتو.
                await deliver_paid_order(bot, cfg, db, service, credited)

        return web.json_response({"ok": True})

    app.router.add_get("/", health)
    app.router.add_get("/health", health)
    app.router.add_post("/nowpayments/ipn", ipn_handler)
    return app


async def start_ipn_server(cfg: Settings, db: Database, bot: Any, service: Any = None) -> web.AppRunner:
    app = make_ipn_app(cfg, db, bot, service)
    runner = web.AppRunner(app)
    await runner.setup()
    ssl_context = None
    if cfg.ipn_cert_file and cfg.ipn_key_file:
        import ssl
        ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        ssl_context.load_cert_chain(cfg.ipn_cert_file, cfg.ipn_key_file)
        logger.info("IPN روی HTTPS سرو می‌شود")
    site = web.TCPSite(runner, cfg.ipn_host, cfg.ipn_port, ssl_context=ssl_context)
    await site.start()
    scheme = "https" if ssl_context else "http"
    logger.info("IPN server روی %s://%s:%s بالا آمد", scheme, cfg.ipn_host, cfg.ipn_port)
    return runner
