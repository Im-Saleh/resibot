"""میدلورها: کنترل نرخ (ضد‌فلاد) و ثبت کاربر + تزریق نقش/ادمین به هندلرها."""
from __future__ import annotations

import time
from collections import deque
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from .config import Settings
from .database import Database, ROLE_ADMIN


class ThrottleMiddleware(BaseMiddleware):
    """محدودکننده‌ی نرخ ساده و درون‌حافظه‌ای برای مقاومت در برابر فلاد/سوءاستفاده.

    برای هر کاربر، تعداد رویدادها در یک پنجره‌ی زمانی کوتاه شمرده می‌شود؛ اگر از
    سقف بگذرد، رویداد نادیده گرفته می‌شود (با یک هشدار محترمانه). ادمین معاف است.
    این جلوی حملات ساده‌ی flood و فشار روی پنل/شبکه را می‌گیرد.
    """

    def __init__(self, cfg: Settings, *, limit: int = 8, window: float = 3.0) -> None:
        self.cfg = cfg
        self.limit = limit
        self.window = window
        self._hits: dict[int, deque] = {}
        self._notified: dict[int, float] = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if user is None or user.id == self.cfg.admin_id:
            return await handler(event, data)

        now = time.monotonic()
        dq = self._hits.setdefault(user.id, deque())
        while dq and now - dq[0] > self.window:
            dq.popleft()
        dq.append(now)

        if len(dq) > self.limit:
            # جلوگیری از اسپم هشدار: حداکثر هر ۵ ثانیه یک‌بار پیام می‌دهیم.
            last = self._notified.get(user.id, 0.0)
            if now - last > 5.0:
                self._notified[user.id] = now
                try:
                    if isinstance(event, CallbackQuery):
                        await event.answer("⏳ کمی آرام‌تر! چند لحظه صبر کنید.", show_alert=False)
                    elif isinstance(event, Message):
                        await event.answer("⏳ درخواست‌ها خیلی سریع هستند؛ چند لحظه صبر کنید.")
                except Exception:  # noqa: BLE001
                    pass
            # جلوگیری از رشد بی‌نهایت حافظه
            if len(self._hits) > 10000:
                self._hits.clear()
            return None
        return await handler(event, data)


class ContextMiddleware(BaseMiddleware):
    def __init__(self, cfg: Settings, db: Database) -> None:
        self.cfg = cfg
        self.db = db

    @staticmethod
    async def _reply(event: TelegramObject, text: str) -> None:
        """پاسخ کوتاه به کاربر (چه پیام باشد چه کلیک دکمه)."""
        msg = getattr(event, "message", None)
        cb = getattr(event, "callback_query", None)
        try:
            if cb is not None:
                await cb.answer(text, show_alert=True)
            elif msg is not None:
                await msg.answer(text)
        except Exception:  # noqa: BLE001
            pass

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if user is not None:
            # نام را برای نمایش ذخیره می‌کنیم (بدون اعتماد به محتوا برای منطق)
            name = (user.full_name or user.username or "")[:64]
            self.db.ensure_user(user.id, name)
            is_admin = user.id == self.cfg.admin_id

            # کاربران مسدودشده هیچ دسترسی‌ای ندارند (ادمین مستثناست).
            if not is_admin and self.db.is_banned(user.id):
                await self._reply(event, "⛔️ دسترسی شما به ربات مسدود شده است.")
                return None

            # حالت تعمیر: فقط ادمین اجازه دارد.
            if not is_admin and self.db.get_setting("maintenance_mode", "0") == "1":
                await self._reply(
                    event,
                    "🛠 ربات موقتاً در حال تعمیر و به‌روزرسانی است. لطفاً کمی بعد دوباره امتحان کنید.",
                )
                return None

            role = ROLE_ADMIN if is_admin else self.db.get_role(user.id)
            data["role"] = role
            data["is_admin"] = is_admin
        return await handler(event, data)
