"""درگاه پرداخت ریالی HooshPay (کارت‌به‌کارت با تأیید آنی).

مستندات: https://hooshpay.xyz/developers

جریان کار:
  1. با POST /api/v1/invoices یک فاکتور می‌سازیم و مشتری را به payment_url هدایت
     می‌کنیم (مبلغ به تومان و عدد صحیح، حداقل ۱۰۰۰ تومان).
  2. پس از پرداخت موفق، HooshPay یک وب‌هوک POST به callback_url ما می‌زند که با
     امضای HMAC-SHA256 (هدر X-HooshPay-Signature) امن شده است.
  3. امضا را با api_secret بازتولید و مقایسه می‌کنیم؛ در صورت صحت، سفارش را تحویل
     می‌دهیم (اعتباردهی idempotent در لایه‌ی دیتابیس انجام می‌شود).

این ماژول فقط ساخت فاکتور و اعتبارسنجی امضا را انجام می‌دهد؛ اعتباردهی و تحویل
در لایه‌های service/fulfillment انجام می‌شود تا رفتار با بقیه‌ی درگاه‌ها یکسان بماند.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import Any

import httpx

logger = logging.getLogger("resibot.hooshpay")

DEFAULT_BASE_URL = "https://hooshpay.xyz"
# وضعیت‌هایی که یعنی پرداخت قطعی انجام شده است
PAID_STATUSES = {"paid"}


class HooshPayError(Exception):
    """خطای ارتباط یا پاسخ نامعتبر از HooshPay."""


def _sorted_json(payload: dict) -> str:
    """بدنه‌ی امضا: JSON مرتب‌شده بر اساس کلیدها، فشرده و بدون escape یونیکد."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def verify_signature(payload: dict, signature: str, secret: str) -> bool:
    """امضای وب‌هوک را با کلید Secret تأیید می‌کند (مقایسه‌ی ثابت‌زمان)."""
    if not payload or not signature or not secret:
        return False
    try:
        body = _sorted_json(payload)
        expected = hmac.new(secret.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, str(signature))
    except Exception:  # noqa: BLE001
        return False


class HooshPayClient:
    """کلاینت سبک HooshPay بر پایه‌ی httpx (سازگار با REST رسمی)."""

    def __init__(self, api_key: str, api_secret: str = "", *, base_url: str = DEFAULT_BASE_URL,
                 fee_mode: str = "buyer", timeout: float = 20.0) -> None:
        self.api_key = (api_key or "").strip()
        self.api_secret = (api_secret or "").strip()
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        self.fee_mode = fee_mode or "buyer"
        self.timeout = timeout

    @property
    def api_root(self) -> str:
        return f"{self.base_url}/api/v1"

    async def create_invoice(
        self,
        *,
        amount_toman: int,
        order_id: str,
        callback_url: str = "",
        return_url: str = "",
        description: str = "",
    ) -> dict[str, Any]:
        """یک فاکتور می‌سازد و dict دادهٔ پاسخ را برمی‌گرداند (شامل payment_url و uid)."""
        if not self.api_key:
            raise HooshPayError("کلید API درگاه ریالی تنظیم نشده است.")
        amount = int(round(amount_toman))
        if amount < 1000:
            raise HooshPayError("مبلغ فاکتور باید حداقل ۱۰۰۰ تومان باشد.")
        body: dict[str, Any] = {
            "amount": amount,
            "order_id": order_id,
            "fee_mode": self.fee_mode,
        }
        if callback_url:
            body["callback_url"] = callback_url
        if return_url:
            body["return_url"] = return_url
        if description:
            body["description"] = description[:200]
        headers = {"X-API-KEY": self.api_key, "Content-Type": "application/json"}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(f"{self.api_root}/invoices", json=body, headers=headers)
        except httpx.HTTPError as exc:
            raise HooshPayError(f"ارتباط با درگاه ناموفق بود: {exc}") from exc
        if resp.status_code == 401:
            raise HooshPayError("کلید API درگاه ریالی نامعتبر است.")
        if resp.status_code == 503:
            raise HooshPayError("درگاه ریالی فعلاً غیرفعال است یا کارتی برای دریافت موجود نیست.")
        try:
            data = resp.json()
        except ValueError as exc:
            raise HooshPayError("پاسخ نامعتبر از درگاه.") from exc
        if not data.get("success") or "data" not in data:
            raise HooshPayError(str(data.get("message") or "خطای نامشخص از درگاه."))
        return data["data"]

    async def verify_invoice(self, uid: str) -> dict[str, Any]:
        """وضعیت نهایی یک فاکتور را استعلام می‌کند (paid?)."""
        if not self.api_key:
            raise HooshPayError("کلید API درگاه ریالی تنظیم نشده است.")
        headers = {"X-API-KEY": self.api_key}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(f"{self.api_root}/invoices/{uid}/verify", headers=headers)
                return resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise HooshPayError(f"استعلام فاکتور ناموفق بود: {exc}") from exc
