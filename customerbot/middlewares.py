"""میدلور: ثبت آیدی کاربر فعلی برای استفاده در هندلرها.

این ربات کمکی به یک «مشتری ثابت» محدود نیست. هر کسی می‌تواند آن را استارت کند؛
ولی فقط سرویس‌هایی را می‌بیند که همکار/مالک از داخل ربات اصلی (دکمه‌ی
«🤖 تعیین مشتری») صریحاً به آیدی او سپرده باشد (ستون customer_tg_id در جدول
configs). اگر کاربری هیچ سرویسی نداشته باشد، لیست خالی خواهد بود و در عمل کاری
نمی‌تواند بکند.
"""
from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject


class CustomerContextMiddleware(BaseMiddleware):
    """آیدی کاربر تلگرام را در data تزریق می‌کند؛ محدودیتی روی کاربر اعمال نمی‌کند.

    کنترل دسترسی واقعی در سطح هر سرویس (با customer_tg_id) در هندلرها انجام
    می‌شود، نه در این میدلور.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if user is None:
            return  # رویداد بدون کاربر — رد می‌کنیم
        data["customer_id"] = user.id
        return await handler(event, data)
