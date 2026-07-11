"""ثبت همه‌ی روترهای ربات کمکی مشتری."""
from __future__ import annotations

from aiogram import Dispatcher

from .common import router as common_router
from .services import router as services_router


def register_handlers(dp: Dispatcher) -> None:
    dp.include_router(common_router)
    dp.include_router(services_router)
