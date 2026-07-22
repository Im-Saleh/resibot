"""ابزارهای امنیتی پنل وب — فقط با کتابخانه‌ی استاندارد (بدون وابستگی اضافه).

شامل:
  - هش و راستی‌آزمایی پسورد با PBKDF2-HMAC-SHA256 (نمک تصادفی، مقایسه‌ی ثابت‌زمان)
  - سشن امضاشده با HMAC-SHA256 (ضددستکاری، دارای انقضا)
  - تولید و بررسی توکن CSRF
  - محدودکننده‌ی نرخ لاگین با قفل موقت (ضد brute-force)
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass, field

# --- پسورد ---
_PBKDF2_ROUNDS = 240_000
_PBKDF2_ALGO = "sha256"


def hash_password(password: str, *, rounds: int = _PBKDF2_ROUNDS) -> str:
    """یک هش قابل‌ذخیره از پسورد می‌سازد: pbkdf2_sha256$rounds$salt$hash."""
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac(_PBKDF2_ALGO, password.encode("utf-8"), salt, rounds)
    return f"pbkdf2_sha256${rounds}${_b64(salt)}${_b64(dk)}"


def verify_password(password: str, stored: str) -> bool:
    """پسورد را با مقدار ذخیره‌شده می‌سنجد.

    اگر stored یک هش pbkdf2 باشد، با همان راستی‌آزمایی می‌شود؛ در غیر این صورت
    stored به‌عنوان متن ساده تلقی و به‌صورت ثابت‌زمان مقایسه می‌شود (تا حداقل از
    نشت زمانی جلوگیری شود). در هر دو حالت مقایسه با hmac.compare_digest است.
    """
    if not password or not stored:
        return False
    if stored.startswith("pbkdf2_sha256$"):
        try:
            _algo, rounds_s, salt_b64, hash_b64 = stored.split("$", 3)
            rounds = int(rounds_s)
            salt = _unb64(salt_b64)
            expected = _unb64(hash_b64)
        except (ValueError, TypeError):
            return False
        dk = hashlib.pbkdf2_hmac(_PBKDF2_ALGO, password.encode("utf-8"), salt, rounds)
        return hmac.compare_digest(dk, expected)
    # متن ساده — مقایسه‌ی ثابت‌زمان روی هش هر دو طرف (نرمال‌سازی طول)
    a = hashlib.sha256(password.encode("utf-8")).digest()
    b = hashlib.sha256(stored.encode("utf-8")).digest()
    return hmac.compare_digest(a, b)


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _unb64(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


# --- سشن امضاشده ---
class SessionManager:
    """سشن‌های بدون‌حالت (stateless) با امضای HMAC و انقضا.

    محتوای سشن در کوکی نگه‌داری می‌شود اما با کلید سرور امضا می‌شود؛ بنابراین کاربر
    نمی‌تواند آن را جعل یا دستکاری کند.
    """

    def __init__(self, secret: str, *, ttl_seconds: int = 8 * 3600) -> None:
        self._secret = secret.encode("utf-8")
        self._ttl = ttl_seconds

    def _sign(self, data: bytes) -> str:
        return _b64(hmac.new(self._secret, data, hashlib.sha256).digest())

    def create(self, payload: dict) -> str:
        body = dict(payload)
        now = int(time.time())
        body["iat"] = now
        body["exp"] = now + self._ttl
        raw = json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        b = _b64(raw)
        return f"{b}.{self._sign(b.encode('ascii'))}"

    def verify(self, token: str) -> dict | None:
        if not token or "." not in token:
            return None
        b, sig = token.rsplit(".", 1)
        expected = self._sign(b.encode("ascii"))
        if not hmac.compare_digest(sig, expected):
            return None
        try:
            payload = json.loads(_unb64(b).decode("utf-8"))
        except (ValueError, TypeError):
            return None
        if not isinstance(payload, dict):
            return None
        if int(payload.get("exp", 0)) < int(time.time()):
            return None
        return payload


def new_csrf_token() -> str:
    return secrets.token_urlsafe(24)


def csrf_ok(session_token_value: str, submitted: str) -> bool:
    if not session_token_value or not submitted:
        return False
    return hmac.compare_digest(session_token_value, submitted)


# --- محدودکننده‌ی نرخ لاگین ---
@dataclass
class _Attempt:
    fails: int = 0
    locked_until: float = 0.0
    window_start: float = field(default_factory=time.monotonic)


class LoginRateLimiter:
    """ضد brute-force: پس از چند تلاش ناموفق، آی‌پی برای مدتی قفل می‌شود."""

    def __init__(self, *, max_fails: int = 5, window: float = 300.0, lock: float = 900.0) -> None:
        self.max_fails = max_fails
        self.window = window
        self.lock = lock
        self._by_ip: dict[str, _Attempt] = {}

    def _get(self, ip: str) -> _Attempt:
        a = self._by_ip.get(ip)
        if a is None:
            a = _Attempt()
            self._by_ip[ip] = a
        return a

    def locked_seconds(self, ip: str) -> int:
        a = self._by_ip.get(ip)
        if not a:
            return 0
        now = time.monotonic()
        if a.locked_until > now:
            return int(a.locked_until - now)
        return 0

    def record_failure(self, ip: str) -> None:
        now = time.monotonic()
        a = self._get(ip)
        # ریست پنجره‌ی شمارش اگر گذشته باشد
        if now - a.window_start > self.window:
            a.window_start = now
            a.fails = 0
        a.fails += 1
        if a.fails >= self.max_fails:
            a.locked_until = now + self.lock
            a.fails = 0
            a.window_start = now
        # جلوگیری از رشد نامحدود حافظه
        if len(self._by_ip) > 20000:
            self._by_ip.clear()

    def record_success(self, ip: str) -> None:
        self._by_ip.pop(ip, None)
