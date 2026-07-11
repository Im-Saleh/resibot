"""پیکربندی ربات کمکی مشتری.

تنها مقدار لازم: CUSTOMER_BOT_TOKEN — توکن ربات تلگرام کمکی (از .env خوانده
می‌شود). این ربات به یک «مشتری ثابت» محدود نیست؛ تعیین این‌که کدام مشتری به
کدام سرویس دسترسی دارد، به‌صورت per-config و از داخل ربات اصلی (دکمه‌ی
«🤖 تعیین مشتری») انجام می‌شود — نگاه کنید به bot/database.py::set_config_customer.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

_BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(_BASE_DIR / ".env")


def _get(name: str, default: str = "") -> str:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip()


@dataclass
class CustomerBotConfig:
    """تنظیمات ربات کمکی مشتری."""

    customer_bot_token: str = field(default_factory=lambda: _get("CUSTOMER_BOT_TOKEN"))


def load_customer_config() -> CustomerBotConfig:
    return CustomerBotConfig()
