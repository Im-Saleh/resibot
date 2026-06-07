"""ثبت همه‌ی روترهای ربات و اعمال فیلترهای دسترسی."""
from __future__ import annotations

from aiogram import Dispatcher

from ..config import Settings
from ..database import Database
from ..filters import IsAdmin, IsAuthorized
from . import admin, common, configs, order


def register_handlers(dp: Dispatcher, cfg: Settings, db: Database) -> None:
    # admin: فقط ادمین
    is_admin = IsAdmin(cfg)
    admin.router.message.filter(is_admin)
    admin.router.callback_query.filter(is_admin)

    # order و configs: ادمین یا نماینده
    is_auth = IsAuthorized(cfg, db)
    order.router.message.filter(is_auth)
    order.router.callback_query.filter(is_auth)
    configs.router.message.filter(is_auth)
    configs.router.callback_query.filter(is_auth)

    # ترتیب: common (start) -> admin -> order -> configs
    dp.include_router(common.router)
    dp.include_router(admin.router)
    dp.include_router(order.router)
    dp.include_router(configs.router)
