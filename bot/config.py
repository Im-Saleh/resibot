"""بارگذاری و اعتبارسنجی پیکربندی از فایل .env

مقادیری که در زمان اجرا قابل ویرایش‌اند (مثل IP سرور، SNI، host و حداقل حجم)
از env فقط به‌عنوان «مقدار پیش‌فرض اولیه» خوانده می‌شوند و سپس در دیتابیس
(جدول settings) نگهداری می‌شوند تا تغییرات از طریق ربات ماندگار بمانند.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# ریشه‌ی پروژه (یک پوشه بالاتر از bot/)
BASE_DIR = Path(__file__).resolve().parent.parent

# بارگذاری فایل .env اگر وجود داشته باشد
load_dotenv(BASE_DIR / ".env")


def _get(name: str, default: str = "") -> str:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip()


def _get_int(name: str, default: int) -> int:
    raw = _get(name, "")
    if raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _get_float(name: str, default: float) -> float:
    raw = _get(name, "")
    if raw == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _get_bool(name: str, default: bool) -> bool:
    raw = _get(name, "").lower()
    if raw == "":
        return default
    return raw in ("1", "true", "yes", "on", "y")


class ConfigError(Exception):
    """خطای پیکربندی نامعتبر."""


@dataclass
class Settings:
    # Telegram
    bot_token: str = field(default_factory=lambda: _get("BOT_TOKEN"))
    admin_id: int = field(default_factory=lambda: _get_int("ADMIN_ID", 0))

    # Panel
    panel_base_url: str = field(default_factory=lambda: _get("PANEL_BASE_URL").rstrip("/"))
    panel_api_token: str = field(default_factory=lambda: _get("PANEL_API_TOKEN"))
    panel_username: str = field(default_factory=lambda: _get("PANEL_USERNAME"))
    panel_password: str = field(default_factory=lambda: _get("PANEL_PASSWORD"))

    # مقادیر اولیه‌ی قابل ویرایش (در DB ماندگار می‌شوند)
    server_ip: str = field(default_factory=lambda: _get("SERVER_IP"))
    inbound_sni: str = field(default_factory=lambda: _get("INBOUND_SNI", "irsp.mahandevs.com"))
    inbound_host: str = field(default_factory=lambda: _get("INBOUND_HOST", "irsp.mahandevs.com"))
    inbound_path: str = field(default_factory=lambda: _get("INBOUND_PATH", "/get"))
    inbound_alpn: str = field(default_factory=lambda: _get("INBOUND_ALPN", "h2"))
    inbound_fingerprint: str = field(default_factory=lambda: _get("INBOUND_FINGERPRINT", "chrome"))
    inbound_sc_max_each_post_bytes: int = field(
        default_factory=lambda: _get_int("INBOUND_SC_MAX_EACH_POST_BYTES", 5000000)
    )
    port_range_min: int = field(default_factory=lambda: _get_int("PORT_RANGE_MIN", 10000))
    port_range_max: int = field(default_factory=lambda: _get_int("PORT_RANGE_MAX", 60000))

    # SmartProxy (رزیدنتال ۱)
    smartproxy_host: str = field(default_factory=lambda: _get("SMARTPROXY_HOST", "proxy.smartproxy.net"))
    smartproxy_port: int = field(default_factory=lambda: _get_int("SMARTPROXY_PORT", 3120))
    smartproxy_user_base: str = field(default_factory=lambda: _get("SMARTPROXY_USER_BASE"))
    smartproxy_password: str = field(default_factory=lambda: _get("SMARTPROXY_PASSWORD"))
    smartproxy_life: int = field(default_factory=lambda: _get_int("SMARTPROXY_LIFE", 120))

    # اوتباند رزیدنتال ۲ — پارامترهای لوکیشن/سشن داخل رشته‌ی password کدگذاری می‌شوند
    # مقادیر پیش‌فرض از قبل ست شده‌اند تا رزیدنتال ۲ بدون تنظیم اضافه کار کند.
    iproyal_host: str = field(default_factory=lambda: _get("IPROYAL_HOST", "geo.iproyal.com"))
    iproyal_port: int = field(default_factory=lambda: _get_int("IPROYAL_PORT", 12321))
    iproyal_username: str = field(default_factory=lambda: _get("IPROYAL_USERNAME", "zUulUCSUneWHTauW"))
    iproyal_password: str = field(default_factory=lambda: _get("IPROYAL_PASSWORD", "x1NFN2nK3r2w2umj"))
    # مدت ماندگاری IP به دقیقه (1 تا 10080 = ۷ روز)
    iproyal_life: int = field(default_factory=lambda: _get_int("IPROYAL_LIFE", 1440))

    # فالبک‌های اختیاری وقتی /panel/setting/all در دسترس نیست
    panel_cert_file: str = field(default_factory=lambda: _get("PANEL_CERT_FILE"))
    panel_key_file: str = field(default_factory=lambda: _get("PANEL_KEY_FILE"))
    sub_port: int = field(default_factory=lambda: _get_int("SUB_PORT", 2096))
    sub_path: str = field(default_factory=lambda: _get("SUB_PATH", "/sub/"))
    sub_secure: bool = field(default_factory=lambda: _get_bool("SUB_SECURE", True))

    # برند
    brand_name: str = field(default_factory=lambda: _get("BRAND_NAME", "w2f"))
    brand_full: str = field(default_factory=lambda: _get("BRAND_FULL", "Way To Freedom"))

    # قوانین فروش
    min_volume_gb: int = field(default_factory=lambda: _get_int("MIN_VOLUME_GB", 5))
    renew_min_volume_gb: int = field(default_factory=lambda: _get_int("RENEW_MIN_VOLUME_GB", 5))
    config_duration_days: int = field(default_factory=lambda: _get_int("CONFIG_DURATION_DAYS", 30))

    # قیمت‌ها (به ازای هر گیگابایت)
    # رزیدنتال: واحد دلار | V2Ray عادی: واحد تومان
    price_per_gb: float = field(default_factory=lambda: _get_float("PRICE_PER_GB", 2.9))
    reseller_price_per_gb: float = field(default_factory=lambda: _get_float("RESELLER_PRICE_PER_GB", 2.0))
    # رزیدنتال ۲ (IPRoyal) — واحد دلار
    residential2_price_per_gb: float = field(default_factory=lambda: _get_float("RESIDENTIAL2_PRICE_PER_GB", 12.0))
    residential2_reseller_price_per_gb: float = field(default_factory=lambda: _get_float("RESIDENTIAL2_RESELLER_PRICE_PER_GB", 10.0))
    v2ray_price_per_gb: float = field(default_factory=lambda: _get_float("V2RAY_PRICE_PER_GB", 50000.0))
    v2ray_reseller_price_per_gb: float = field(default_factory=lambda: _get_float("V2RAY_RESELLER_PRICE_PER_GB", 35000.0))

    # نمایش/مخفی‌سازی بخش‌ها (مقدار اولیه؛ در دیتابیس ماندگار می‌شود)
    show_partnership: bool = field(default_factory=lambda: _get_bool("SHOW_PARTNERSHIP", True))
    show_residential: bool = field(default_factory=lambda: _get_bool("SHOW_RESIDENTIAL", True))
    show_residential2: bool = field(default_factory=lambda: _get_bool("SHOW_RESIDENTIAL2", True))
    show_v2ray: bool = field(default_factory=lambda: _get_bool("SHOW_V2RAY", True))

    # حداقل موجودی لازم برای همکار v2ray (پیش‌پرداخت)
    reseller_min_balance: float = field(default_factory=lambda: _get_float("RESELLER_MIN_BALANCE", 5000000.0))

    # کیف پول و پرداخت
    wallet_currency: str = field(default_factory=lambda: _get("WALLET_CURRENCY", "تومان"))
    residential_currency: str = field(default_factory=lambda: _get("RESIDENTIAL_CURRENCY", "USD"))
    toman_per_usd: float = field(default_factory=lambda: _get_float("TOMAN_PER_USD", 175000.0))
    nowpayments_api_key: str = field(default_factory=lambda: _get("NOWPAYMENTS_API_KEY"))
    nowpayments_ipn_secret: str = field(default_factory=lambda: _get("NOWPAYMENTS_IPN_SECRET"))
    nowpayments_public_key: str = field(default_factory=lambda: _get("NOWPAYMENTS_PUBLIC_KEY"))
    nowpayments_price_currency: str = field(default_factory=lambda: _get("NOWPAYMENTS_PRICE_CURRENCY", "usd"))
    # ارز پرداخت پیش‌فرض درگاه؛ حالا USDT روی شبکه‌ی BEP20 (BSC)
    nowpayments_pay_currency: str = field(default_factory=lambda: _get("NOWPAYMENTS_PAY_CURRENCY", "usdtbsc"))

    # --- پرداخت مستقیم کریپتو (USDT BEP20 / BSC) ---
    # آدرس مقصد که پول مستقیم به آن واریز می‌شود (بدون واسطه، بدون فی انتقال).
    crypto_wallet_address: str = field(
        default_factory=lambda: _get(
            "CRYPTO_WALLET_ADDRESS", "0x0E2D801A5A769d7C508C0602E70cec3D1386943D"
        )
    )
    # نقطه‌ی اتصال JSON-RPC شبکه‌ی BSC (رصد فقط-خواندنی؛ هیچ کلید خصوصی لازم نیست).
    # پیش‌فرض: bsc-dataseed که برای «تأیید دستی با هش» (receipt) کاملاً پایدار
    # است و همه‌جا کار می‌کند. برای «تأیید خودکار» به RPCی نیاز است که
    # eth_getLogs را پشتیبانی کند (مثل QuickNode/Alchemy/Ankr یا نود اختصاصی).
    bsc_rpc_url: str = field(
        default_factory=lambda: _get("BSC_RPC_URL", "https://bsc-dataseed.binance.org")
    )
    # تعداد تأییدهای لازم قبل از تحویل (ضدتقلب/ری‌ارگ).
    crypto_confirmations: int = field(default_factory=lambda: _get_int("CRYPTO_CONFIRMATIONS", 12))
    # مدت اعتبار هر فاکتور کریپتو به دقیقه (پس از آن منقضی می‌شود).
    crypto_payment_ttl_min: int = field(default_factory=lambda: _get_int("CRYPTO_PAYMENT_TTL_MIN", 60))
    # فعال/غیرفعال بودن هر روش پرداخت (مقدار اولیه؛ در دیتابیس ماندگار می‌شود).
    pay_crypto_enabled: bool = field(default_factory=lambda: _get_bool("PAY_CRYPTO_ENABLED", True))
    pay_nowpayments_enabled: bool = field(default_factory=lambda: _get_bool("PAY_NOWPAYMENTS_ENABLED", True))

    # --- پلن V2Ray (یک‌ماهه نامحدود روی اینباند موجود) ---
    # شناسه‌ی اینباند از پیش‌ساخته‌شده در پنل که کلاینت V2Ray در آن ساخته می‌شود.
    v2ray_inbound_id: int = field(default_factory=lambda: _get_int("V2RAY_INBOUND_ID", 6))
    # مدت اعتبار پلن V2Ray به روز (با هر تمدید از همان لحظه ریست می‌شود).
    v2ray_plan_days: int = field(default_factory=lambda: _get_int("V2RAY_PLAN_DAYS", 30))
    # قیمت ثابت پلن V2Ray یک‌ماهه‌ی نامحدود (دلار/تتر) — عادی و همکار.
    v2ray_plan_price: float = field(default_factory=lambda: _get_float("V2RAY_PLAN_PRICE", 5.0))
    v2ray_plan_reseller_price: float = field(default_factory=lambda: _get_float("V2RAY_PLAN_RESELLER_PRICE", 3.5))
    # آدرس عمومی برای IPN؛ اگر خالی باشد خودکار از IP سرور ساخته می‌شود.
    public_base_url: str = field(default_factory=lambda: _get("PUBLIC_BASE_URL").rstrip("/"))
    ipn_host: str = field(default_factory=lambda: _get("IPN_HOST", "0.0.0.0"))
    ipn_port: int = field(default_factory=lambda: _get_int("IPN_PORT", 8090))
    # اختیاری: برای سرو IPN روی HTTPS (در غیر این صورت HTTP استفاده می‌شود).
    ipn_cert_file: str = field(default_factory=lambda: _get("IPN_CERT_FILE"))
    ipn_key_file: str = field(default_factory=lambda: _get("IPN_KEY_FILE"))

    # دیتابیس
    db_path: str = field(default_factory=lambda: _get("DB_PATH", "data/resibot.db"))

    @property
    def nowpayments_enabled(self) -> bool:
        # فقط دو کلید لازم است؛ آدرس IPN خودکار ساخته می‌شود.
        return bool(self.nowpayments_api_key and self.nowpayments_ipn_secret)

    def ipn_callback_url(self, server_ip: str = "") -> str:
        """آدرس callback برای NowPayments.

        اگر PUBLIC_BASE_URL ست شده باشد از همان استفاده می‌شود؛ در غیر این صورت
        خودکار از IP/دامنه‌ی سرور روی پورت IPN ساخته می‌شود (http یا https بسته
        به وجود گواهی).
        """
        base = self.public_base_url
        if not base:
            scheme = "https" if (self.ipn_cert_file and self.ipn_key_file) else "http"
            host = server_ip or self.server_ip
            base = f"{scheme}://{host}:{self.ipn_port}"
        return base.rstrip("/") + "/nowpayments/ipn"

    def db_full_path(self) -> Path:
        p = Path(self.db_path)
        if not p.is_absolute():
            p = BASE_DIR / p
        return p

    def validate(self) -> None:
        """بررسی وجود حداقل مقادیر لازم برای راه‌اندازی."""
        errors: list[str] = []
        if not self.bot_token:
            errors.append("BOT_TOKEN تنظیم نشده است.")
        if not self.admin_id:
            errors.append("ADMIN_ID تنظیم نشده یا نامعتبر است.")
        if not self.panel_base_url:
            errors.append("PANEL_BASE_URL تنظیم نشده است.")
        if not self.panel_api_token and not (self.panel_username and self.panel_password):
            errors.append("یا PANEL_API_TOKEN یا PANEL_USERNAME/PANEL_PASSWORD لازم است.")
        if not self.smartproxy_user_base:
            errors.append("SMARTPROXY_USER_BASE تنظیم نشده است.")
        if not self.smartproxy_password:
            errors.append("SMARTPROXY_PASSWORD تنظیم نشده است.")
        if self.port_range_min >= self.port_range_max:
            errors.append("PORT_RANGE_MIN باید کوچکتر از PORT_RANGE_MAX باشد.")
        if errors:
            raise ConfigError("پیکربندی نامعتبر:\n- " + "\n- ".join(errors))


# نمونه‌ی سراسری
settings = Settings()
