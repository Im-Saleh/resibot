"""حالت‌های FSM ربات کمکی مشتری: تغییر کشور/استان/شهر و زمان تعویض IP."""
from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class CustomerLocationStates(StatesGroup):
    """مراحل تغییر کامل لوکیشن (کشور → استان → شهر) یک سرویس مشتری."""
    choosing_country = State()
    searching_country = State()
    entering_country = State()
    choosing_state = State()
    choosing_city = State()


class CustomerLifeStates(StatesGroup):
    """ورود مقدار دلخواه برای زمان تعویض خودکار IP."""
    entering_life = State()
