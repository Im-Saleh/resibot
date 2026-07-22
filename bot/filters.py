"""فیلترهای دسترسی."""
from __future__ import annotations

from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message, TelegramObject

from .config import Settings
from .database import Database


def _user_id(event: TelegramObject) -> int | None:
    user = getattr(event, "from_user", None)
    return user.id if user else None


class IsAdmin(BaseFilter):
    """ادمین اصلی (از env) یا ادمین‌های اضافه‌شده در دیتابیس."""

    def __init__(self, cfg: Settings, db: Database | None = None) -> None:
        self.cfg = cfg
        self.db = db

    async def __call__(self, event: Message | CallbackQuery) -> bool:
        uid = _user_id(event)
        if uid is None:
            return False
        if uid == self.cfg.admin_id:
            return True
        return self.db is not None and self.db.is_extra_admin(uid)


class IsAuthorized(BaseFilter):
    """ادمین یا نماینده‌ی فعال."""

    def __init__(self, cfg: Settings, db: Database) -> None:
        self.cfg = cfg
        self.db = db

    async def __call__(self, event: Message | CallbackQuery) -> bool:
        uid = _user_id(event)
        if uid is None:
            return False
        if uid == self.cfg.admin_id:
            return True
        return self.db.is_reseller(uid)
