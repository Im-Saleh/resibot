"""ثبت همه‌ی روترهای ربات و اعمال فیلترهای دسترسی."""
from __future__ import annotations

from aiogram import Dispatcher

from ..config import Settings
from ..database import Database
from ..filters import IsAdmin
from . import admin, common, configs, digital, order, payments, products_admin, wallet


def register_handlers(dp: Dispatcher, cfg: Settings, db: Database) -> None:
    # پنل مدیریت فقط برای ادمین
    is_admin = IsAdmin(cfg)
    admin.router.message.filter(is_admin)
    admin.router.callback_query.filter(is_admin)
    products_admin.router.message.filter(is_admin)
    products_admin.router.callback_query.filter(is_admin)

    # بقیه برای همه‌ی کاربران باز است (میدلور کاربر را ثبت می‌کند)
    dp.include_router(common.router)
    dp.include_router(admin.router)
    dp.include_router(products_admin.router)
    dp.include_router(wallet.router)
    dp.include_router(order.router)
    dp.include_router(payments.router)
    dp.include_router(digital.router)
    dp.include_router(configs.router)
