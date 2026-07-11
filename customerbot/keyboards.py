"""کیبوردهای inline و reply برای ربات کمکی مشتری."""
from __future__ import annotations

import sqlite3
from typing import Sequence

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📋 سرویس‌های من")],
            [KeyboardButton(text="ℹ️ راهنما")],
        ],
        resize_keyboard=True,
    )


def services_keyboard(rows: Sequence[sqlite3.Row]) -> InlineKeyboardMarkup:
    """لیست سرویس‌ها برای انتخاب."""
    buttons = []
    for row in rows:
        area = row["area"] or "تصادفی"
        label = f"#{row['id']} — {area} | {row['volume_gb']} GB"
        buttons.append(
            [InlineKeyboardButton(text=label, callback_data=f"cs_open:{row['id']}")]
        )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def service_actions(config_id: int) -> InlineKeyboardMarkup:
    """دکمه‌های اقدام برای یک سرویس."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔄 تغییر IP", callback_data=f"cs_ip:{config_id}"),
                InlineKeyboardButton(text="📊 مصرف", callback_data=f"cs_usage:{config_id}"),
            ],
            [
                InlineKeyboardButton(text="🌍 اطلاعات IP", callback_data=f"cs_info:{config_id}"),
                InlineKeyboardButton(text="📡 تست اتصال", callback_data=f"cs_ping:{config_id}"),
            ],
            [
                InlineKeyboardButton(text="🗺 تغییر کشور/شهر", callback_data=f"cs_loc:{config_id}"),
                InlineKeyboardButton(text="⏱ زمان تعویض IP", callback_data=f"cs_life:{config_id}"),
            ],
            [
                InlineKeyboardButton(text="🔗 لینک سرویس", callback_data=f"cs_links:{config_id}"),
            ],
            [
                InlineKeyboardButton(text="« برگشت", callback_data="cs_back"),
            ],
        ]
    )
