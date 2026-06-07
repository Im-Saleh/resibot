"""ساخت رشته‌ی username برای SmartProxy و مدیریت پارامترهای لوکیشن.

فرمت نمونه:
    smart-myrRsidFntpraGNS_area-GB_life-120_session-PzZyPXwOY

پارامترها (طبق مستندات SmartProxy):
    area    : کد کشور (مثل US, GB) — اختیاری
    state   : کد استان (مثل state-California) — اختیاری
    city    : کد شهر (مثل city-NewYork) — اختیاری
    life    : مدت ماندگاری IP به دقیقه (1..1440) — اختیاری
    session : رشته 4..12 کاراکتری حرف/عدد؛ با تغییرش IP عوض می‌شود — اختیاری

با تغییر session مقدار IP عوض می‌شود (همان IP تا وقتی session ثابت بماند).
"""
from __future__ import annotations

import random
import re
import string
from dataclasses import dataclass

SESSION_RE = re.compile(r"^[A-Za-z0-9]{4,12}$")
# کد area/state/city فقط حروف، عدد و خط‌تیره مجاز است (بدون فاصله)
CODE_RE = re.compile(r"^[A-Za-z0-9\-]+$")


def generate_session(length: int = 9) -> str:
    """یک session تصادفی معتبر (حرف/عدد) تولید می‌کند."""
    length = max(4, min(12, length))
    alphabet = string.ascii_letters + string.digits
    return "".join(random.choices(alphabet, k=length))


def validate_session(session: str) -> bool:
    return bool(SESSION_RE.match(session))


def validate_code(code: str) -> bool:
    """اعتبارسنجی کد area/state/city. رشته‌ی خالی هم مجاز است (یعنی تنظیم‌نشده)."""
    if code == "":
        return True
    return bool(CODE_RE.match(code))


def normalize_code(code: str) -> str:
    """فاصله‌ها را حذف و کد را تمیز می‌کند (SmartProxy فاصله نمی‌پذیرد)."""
    return code.strip().replace(" ", "")


@dataclass
class ProxyLocation:
    """پارامترهای لوکیشن یک اوتباند."""
    area: str = ""      # کد کشور، مثلا "GB" یا "US"
    state: str = ""     # مثلا "California"
    city: str = ""      # مثلا "NewYork"
    life: int = 0       # دقیقه؛ 0 یعنی استفاده نشود
    session: str = ""   # رشته session؛ خالی یعنی استفاده نشود

    def cleaned(self) -> "ProxyLocation":
        return ProxyLocation(
            area=normalize_code(self.area),
            state=normalize_code(self.state),
            city=normalize_code(self.city),
            life=int(self.life or 0),
            session=self.session.strip(),
        )


def build_username(user_base: str, loc: ProxyLocation) -> str:
    """رشته‌ی کامل username را با ترتیب area, state, city, life, session می‌سازد."""
    loc = loc.cleaned()
    parts = [user_base]
    if loc.area:
        parts.append(f"area-{loc.area}")
    if loc.state:
        parts.append(f"state-{loc.state}")
    if loc.city:
        parts.append(f"city-{loc.city}")
    if loc.life and loc.life > 0:
        # محدوده مجاز 1..1440
        life = max(1, min(1440, int(loc.life)))
        parts.append(f"life-{life}")
    if loc.session:
        parts.append(f"session-{loc.session}")
    return "_".join(parts)


# لیست کشورهای پرکاربرد برای انتخاب سریع در ربات (کد ISO).
# کاربر می‌تواند کد دلخواه دیگری هم دستی وارد کند.
COMMON_COUNTRIES: list[tuple[str, str]] = [
    ("GB", "🇬🇧 انگلستان"),
    ("US", "🇺🇸 آمریکا"),
    ("DE", "🇩🇪 آلمان"),
    ("FR", "🇫🇷 فرانسه"),
    ("NL", "🇳🇱 هلند"),
    ("CA", "🇨🇦 کانادا"),
    ("TR", "🇹🇷 ترکیه"),
    ("AE", "🇦🇪 امارات"),
    ("IT", "🇮🇹 ایتالیا"),
    ("ES", "🇪🇸 اسپانیا"),
    ("SE", "🇸🇪 سوئد"),
    ("PL", "🇵🇱 لهستان"),
    ("JP", "🇯🇵 ژاپن"),
    ("SG", "🇸🇬 سنگاپور"),
    ("AU", "🇦🇺 استرالیا"),
]
