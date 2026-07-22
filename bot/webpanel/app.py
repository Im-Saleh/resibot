"""اپلیکیشن aiohttp پنل وب مدیریتی امن.

لایه‌های امنیتی (ضدنفوذ):
  - احراز هویت اجباری با سشن امضاشده‌ی HMAC (کوکی HttpOnly, SameSite=Strict)
  - محافظت CSRF روی همه‌ی درخواست‌های POST
  - محدودسازی نرخ لاگین + قفل موقت آی‌پی (ضد brute-force)
  - هدرهای امنیتی سخت‌گیرانه (CSP, X-Frame-Options, nosniff, ...)
  - لیست سفید آی‌پی (اختیاری)
  - ثبت رخدادهای حساس در لاگ حسابرسی
  - هش پسورد با PBKDF2 و مقایسه‌ی ثابت‌زمان
"""
from __future__ import annotations

import logging
import secrets
from typing import Any

from aiohttp import web

from ..config import Settings
from ..database import Database
from .. import digital as digital_mod
from ..service import (
    S_MIN_TOPUP,
    S_PRICE,
    S_RESELLER_PRICE,
    S_TOMAN_PER_USD,
    S_V2RAY_PLAN_PRICE,
    S_V2RAY_PLAN_RESELLER_PRICE,
    Service,
)
from . import templates as T
from .security import (
    LoginRateLimiter,
    SessionManager,
    csrf_ok,
    new_csrf_token,
    verify_password,
)

logger = logging.getLogger("resibot.webpanel")

SESSION_COOKIE = "rb_session"
PRE_COOKIE = "rb_pre"


def _client_ip(request: web.Request) -> str:
    xff = request.headers.get("X-Forwarded-For", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.remote or "?"


def make_web_app(cfg: Settings, db: Database, service: Service) -> web.Application:
    is_https = bool(cfg.web_panel_cert_file and cfg.web_panel_key_file)
    # کلید امضا و رمز و لیست IP همگی «پویا» از سرویس/دیتابیس خوانده می‌شوند تا
    # تغییرشان از داخل ربات بدون ری‌استارت اعمال شود.
    secret = service.web_panel_secret or cfg.web_panel_secret or secrets.token_hex(32)
    sessions = SessionManager(secret)
    limiter = LoginRateLimiter()

    def _allowed_ips() -> set[str]:
        return {ip.strip() for ip in (service.web_panel_allowed_ips or "").split(",") if ip.strip()}

    app = web.Application()

    # ---------------- کوکی امن ---------------- #
    def _set_cookie(resp: web.StreamResponse, name: str, value: str, *, max_age: int) -> None:
        resp.set_cookie(
            name, value, max_age=max_age, httponly=True, secure=is_https,
            samesite="Strict", path="/panel",
        )

    def _del_cookie(resp: web.StreamResponse, name: str) -> None:
        resp.del_cookie(name, path="/panel")

    def _session(request: web.Request) -> dict | None:
        return sessions.verify(request.cookies.get(SESSION_COOKIE, ""))

    # ---------------- میدلورها ---------------- #
    @web.middleware
    async def security_headers_mw(request: web.Request, handler: Any) -> web.StreamResponse:
        resp = await handler(request)
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Referrer-Policy"] = "no-referrer"
        resp.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        resp.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        # CSP سخت‌گیرانه: فقط منابع خودی، style درون‌خطی مجاز (چون CSS درون‌خطی داریم)
        resp.headers["Content-Security-Policy"] = (
            "default-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; script-src 'none'; base-uri 'none'; "
            "form-action 'self'; frame-ancestors 'none'"
        )
        if is_https:
            resp.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return resp

    @web.middleware
    async def ip_allowlist_mw(request: web.Request, handler: Any) -> web.StreamResponse:
        allowed_ips = _allowed_ips()
        if allowed_ips and _client_ip(request) not in allowed_ips:
            logger.warning("دسترسی پنل وب از IP غیرمجاز رد شد: %s", _client_ip(request))
            db.audit("web_ip_blocked", ip=_client_ip(request), detail=request.path)
            raise web.HTTPForbidden(text="Forbidden")
        return await handler(request)

    @web.middleware
    async def auth_mw(request: web.Request, handler: Any) -> web.StreamResponse:
        path = request.path
        # مسیرهای باز (بدون نیاز به لاگین)
        if path in ("/panel/login", "/panel/health", "/health", "/"):
            return await handler(request)
        if not _session(request):
            raise web.HTTPFound("/panel/login")
        return await handler(request)

    app.middlewares.append(security_headers_mw)
    app.middlewares.append(ip_allowlist_mw)
    app.middlewares.append(auth_mw)

    # ---------------- کمکی‌ها ---------------- #
    def _html(text: str, status: int = 200) -> web.Response:
        return web.Response(text=text, content_type="text/html", charset="utf-8", status=status)

    async def _check_csrf(request: web.Request, session: dict | None) -> bool:
        data = await request.post()
        submitted = str(data.get("csrf", ""))
        expected = str((session or {}).get("csrf", ""))
        return csrf_ok(expected, submitted)

    # ---------------- مسیرها ---------------- #
    async def health(_request: web.Request) -> web.Response:
        return web.Response(text="ok")

    async def login_get(request: web.Request) -> web.Response:
        if _session(request):
            raise web.HTTPFound("/panel")
        csrf = new_csrf_token()
        pre = sessions.create({"csrf": csrf, "pre": 1})
        locked = limiter.locked_seconds(_client_ip(request))
        resp = _html(T.login_page(csrf=csrf, locked=locked))
        _set_cookie(resp, PRE_COOKIE, pre, max_age=1800)
        return resp

    async def login_post(request: web.Request) -> web.StreamResponse:
        ip = _client_ip(request)
        locked = limiter.locked_seconds(ip)
        if locked > 0:
            db.audit("web_login_locked", ip=ip)
            return _html(T.login_page(csrf=new_csrf_token(), locked=locked), status=429)
        # CSRF پیش از لاگین از کوکی موقت
        pre = sessions.verify(request.cookies.get(PRE_COOKIE, ""))
        data = await request.post()
        submitted_csrf = str(data.get("csrf", ""))
        if not pre or not pre.get("pre") or not csrf_ok(str(pre.get("csrf", "")), submitted_csrf):
            return _html(T.login_page(csrf=new_csrf_token(), error="نشست منقضی شد. دوباره تلاش کنید."), status=400)
        password = str(data.get("password", ""))
        if not verify_password(password, service.web_panel_password):
            limiter.record_failure(ip)
            db.audit("web_login_fail", ip=ip)
            return _html(T.login_page(csrf=new_csrf_token(), error="رمز عبور اشتباه است."), status=401)
        # موفق
        limiter.record_success(ip)
        db.audit("web_login_ok", actor="admin", ip=ip)
        token = sessions.create({"sub": "admin", "csrf": new_csrf_token()})
        resp = web.HTTPFound("/panel")
        _set_cookie(resp, SESSION_COOKIE, token, max_age=8 * 3600)
        _del_cookie(resp, PRE_COOKIE)
        return resp

    async def logout(request: web.Request) -> web.StreamResponse:
        db.audit("web_logout", actor="admin", ip=_client_ip(request))
        resp = web.HTTPFound("/panel/login")
        _del_cookie(resp, SESSION_COOKIE)
        return resp

    async def dashboard(request: web.Request) -> web.Response:
        try:
            pt = db.payment_totals()
        except Exception:  # noqa: BLE001
            pt = {"paid": 0, "by_currency": []}
        stock = db.stock_counts()
        stats = {
            "brand": cfg.brand_name,
            "users": db.count_users(),
            "configs": len(db.list_all_configs()),
            "digital_products": len(db.list_digital_products()),
            "stock": sum(stock.values()),
            "paid": pt.get("paid", 0),
            "banned": db.count_banned(),
            "revenue": pt.get("by_currency", []),
        }
        return _html(T.dashboard_page(stats))

    async def products_list(request: web.Request) -> web.Response:
        flash = request.query.get("m", "")
        return _html(T.products_page(
            db.list_digital_products(), db.stock_counts(),
            service.currency, service.toman_per_usd, flash=flash,
        ))

    async def product_new_get(request: web.Request) -> web.Response:
        session = _session(request)
        return _html(T.product_form_page(csrf=str(session.get("csrf", "")), is_new=True, currency=service.currency))

    async def product_new_post(request: web.Request) -> web.StreamResponse:
        session = _session(request)
        if not await _check_csrf(request, session):
            raise web.HTTPForbidden(text="CSRF")
        data = await request.post()
        slug = str(data.get("slug", "")).strip().lower()
        title = str(data.get("title", "")).strip()
        if not digital_mod.valid_slug(slug) or not title:
            return _html(T.product_form_page(
                csrf=str(session.get("csrf", "")), is_new=True, currency=service.currency,
                flash="شناسه یا عنوان نامعتبر است.",
            ), status=400)
        if db.get_digital_product_by_slug(slug) is not None:
            return _html(T.product_form_page(
                csrf=str(session.get("csrf", "")), is_new=True, currency=service.currency,
                flash="محصولی با این شناسه وجود دارد.",
            ), status=400)
        price = _to_float(data.get("price"), 0.0)
        pid = db.create_digital_product(
            slug, title,
            subtitle=str(data.get("subtitle", "")).strip(),
            description=str(data.get("description", "")),
            price=price,
            duration_days=_to_int(data.get("duration_days"), 0),
            active=bool(data.get("active")),
        )
        db.audit("web_product_create", actor="admin", ip=_client_ip(request), detail=f"{slug} ({price}$)")
        raise web.HTTPFound(f"/panel/products/{pid}")

    async def product_edit_get(request: web.Request) -> web.Response:
        pid = int(request.match_info["pid"])
        product = db.get_digital_product(pid)
        if not product:
            raise web.HTTPFound("/panel/products")
        session = _session(request)
        return _html(T.product_form_page(
            csrf=str(session.get("csrf", "")), product=product,
            stock_items=db.list_stock(pid, limit=40), currency=service.currency,
        ))

    async def product_edit_post(request: web.Request) -> web.StreamResponse:
        pid = int(request.match_info["pid"])
        session = _session(request)
        if not await _check_csrf(request, session):
            raise web.HTTPForbidden(text="CSRF")
        product = db.get_digital_product(pid)
        if not product:
            raise web.HTTPFound("/panel/products")
        data = await request.post()
        title = str(data.get("title", "")).strip()
        if not title:
            raise web.HTTPFound(f"/panel/products/{pid}")
        db.update_digital_product(
            pid,
            title=title,
            subtitle=str(data.get("subtitle", "")).strip(),
            description=str(data.get("description", "")),
            price=_to_float(data.get("price"), float(product["price"])),
            duration_days=_to_int(data.get("duration_days"), int(product["duration_days"])),
            active=1 if data.get("active") else 0,
        )
        db.audit("web_product_edit", actor="admin", ip=_client_ip(request), detail=f"#{pid}")
        product = db.get_digital_product(pid)
        return _html(T.product_form_page(
            csrf=str(session.get("csrf", "")), product=product,
            stock_items=db.list_stock(pid, limit=40), currency=service.currency,
            flash="تغییرات ذخیره شد.",
        ))

    async def product_stock_post(request: web.Request) -> web.StreamResponse:
        pid = int(request.match_info["pid"])
        session = _session(request)
        if not await _check_csrf(request, session):
            raise web.HTTPForbidden(text="CSRF")
        if not db.get_digital_product(pid):
            raise web.HTTPFound("/panel/products")
        data = await request.post()
        lines = [ln.strip() for ln in str(data.get("items", "")).splitlines() if ln.strip()]
        added = db.add_stock_items(pid, lines) if lines else 0
        db.audit("web_stock_add", actor="admin", ip=_client_ip(request), detail=f"#{pid} +{added}")
        product = db.get_digital_product(pid)
        return _html(T.product_form_page(
            csrf=str(session.get("csrf", "")), product=product,
            stock_items=db.list_stock(pid, limit=40), currency=service.currency,
            flash=f"{added} قلم به انبار اضافه شد.",
        ))

    async def product_delete_post(request: web.Request) -> web.StreamResponse:
        pid = int(request.match_info["pid"])
        session = _session(request)
        if not await _check_csrf(request, session):
            raise web.HTTPForbidden(text="CSRF")
        db.delete_digital_product(pid)
        db.audit("web_product_delete", actor="admin", ip=_client_ip(request), detail=f"#{pid}")
        raise web.HTTPFound("/panel/products?m=" + "محصول+حذف+شد")

    async def prices_get(request: web.Request) -> web.Response:
        session = _session(request)
        return _html(_render_prices(session, service))

    async def prices_post(request: web.Request) -> web.StreamResponse:
        session = _session(request)
        if not await _check_csrf(request, session):
            raise web.HTTPForbidden(text="CSRF")
        data = await request.post()
        mapping = {
            S_PRICE: "price_per_gb",
            S_RESELLER_PRICE: "reseller_price_per_gb",
            S_V2RAY_PLAN_PRICE: "v2ray_plan_price",
            S_V2RAY_PLAN_RESELLER_PRICE: "v2ray_plan_reseller_price",
            S_TOMAN_PER_USD: "toman_per_usd",
            S_MIN_TOPUP: "min_topup",
        }
        for skey, form_name in mapping.items():
            raw = data.get(form_name)
            if raw is None or str(raw).strip() == "":
                continue
            val = _to_float(raw, None)
            if val is None or val < 0:
                continue
            service.set_setting(skey, str(val))
        db.audit("web_prices_edit", actor="admin", ip=_client_ip(request))
        return _html(_render_prices(session, service, flash="قیمت‌ها ذخیره شد."))

    async def audit_view(request: web.Request) -> web.Response:
        return _html(T.audit_page(db.list_audit(limit=100)))

    # ---------------- درگاه‌های پرداخت ---------------- #
    def _gateway_values(session: dict | None) -> dict:
        from ..service import (
            S_HOOSHPAY_ENABLED, S_PAY_CRYPTO_ENABLED, S_PAY_NOWPAYMENTS_ENABLED,
        )
        hp_key = service.hooshpay_api_key
        return {
            "hp_on": service.feature_enabled(S_HOOSHPAY_ENABLED, default=False),
            "hp_key": hp_key,
            "hp_secret": "",  # هرگز Secret را در فرم نشان نمی‌دهیم
            "crypto_on": service.feature_enabled(S_PAY_CRYPTO_ENABLED),
            "now_on": service.feature_enabled(S_PAY_NOWPAYMENTS_ENABLED),
        }

    async def gateways_get(request: web.Request) -> web.Response:
        session = _session(request)
        return _html(T.gateways_page(csrf=str(session.get("csrf", "")), values=_gateway_values(session)))

    async def gateways_post(request: web.Request) -> web.StreamResponse:
        session = _session(request)
        if not await _check_csrf(request, session):
            raise web.HTTPForbidden(text="CSRF")
        from ..service import (
            S_HOOSHPAY_API_KEY, S_HOOSHPAY_API_SECRET, S_HOOSHPAY_ENABLED,
            S_PAY_CRYPTO_ENABLED, S_PAY_NOWPAYMENTS_ENABLED,
        )
        data = await request.post()
        if data.get("section") == "crypto":
            service.set_setting(S_PAY_CRYPTO_ENABLED, "1" if data.get("crypto_enabled") else "0")
            service.set_setting(S_PAY_NOWPAYMENTS_ENABLED, "1" if data.get("now_enabled") else "0")
            flash = "درگاه‌های ارزی ذخیره شد."
        else:
            service.set_setting(S_HOOSHPAY_ENABLED, "1" if data.get("hp_enabled") else "0")
            key = str(data.get("hp_key", "")).strip()
            if key:
                service.set_setting(S_HOOSHPAY_API_KEY, key[:200])
            secret = str(data.get("hp_secret", "")).strip()
            if secret:
                service.set_setting(S_HOOSHPAY_API_SECRET, secret[:200])
            flash = "درگاه ریالی ذخیره شد."
        db.audit("web_gateways_edit", actor="admin", ip=_client_ip(request), detail=str(data.get("section", "hooshpay")))
        return _html(T.gateways_page(csrf=str(session.get("csrf", "")), values=_gateway_values(session), flash=flash))

    # ---------------- DevOps / سیستم ---------------- #
    def _system_stats() -> dict:
        import os as _os
        import sys as _sys
        import glob as _glob
        try:
            db_size = _os.path.getsize(str(db.path))
            db_size_h = f"{db_size/1024/1024:.2f} MB"
        except OSError:
            db_size_h = "—"
        backups = sorted(_glob.glob(str(db.path) + "*.bak")) if False else []
        # پوشه‌ی backups کنار فایل دیتابیس
        bdir = _os.path.join(_os.path.dirname(str(db.path)), "..", "backups")
        last_backup = "—"
        try:
            files = sorted(_glob.glob(_os.path.join(bdir, "resibot-*.db")))
            if files:
                last_backup = _os.path.basename(files[-1])
        except OSError:
            pass
        try:
            audit_rows = len(db.list_audit(limit=100000))
        except Exception:  # noqa: BLE001
            audit_rows = 0
        return {
            "db_size": db_size_h,
            "users": db.count_users(),
            "configs": len(db.list_all_configs()),
            "manual_pending": db.count_manual_pending(),
            "audit_rows": audit_rows,
            "python": _sys.version.split()[0],
            "maintenance": db.get_setting("maintenance_mode", "0") == "1",
            "last_backup": last_backup,
        }

    async def system_get(request: web.Request) -> web.Response:
        session = _session(request)
        return _html(T.system_page(csrf=str(session.get("csrf", "")), stats=_system_stats()))

    async def system_post(request: web.Request) -> web.StreamResponse:
        session = _session(request)
        if not await _check_csrf(request, session):
            raise web.HTTPForbidden(text="CSRF")
        data = await request.post()
        action = str(data.get("action", ""))
        flash = ""
        if action == "backup":
            flash = _do_backup(db)
        elif action == "maint_on":
            db.set_setting("maintenance_mode", "1")
            flash = "حالت تعمیر روشن شد."
        elif action == "maint_off":
            db.set_setting("maintenance_mode", "0")
            flash = "حالت تعمیر خاموش شد."
        elif action == "prune_audit":
            db.prune_audit(keep=2000)
            flash = "لاگ‌های قدیمی هرس شدند."
        db.audit("web_system_action", actor="admin", ip=_client_ip(request), detail=action)
        return _html(T.system_page(csrf=str(session.get("csrf", "")), stats=_system_stats(), flash=flash))

    # ثبت مسیرها
    app.router.add_get("/", health)
    app.router.add_get("/health", health)
    app.router.add_get("/panel/health", health)
    app.router.add_get("/panel/login", login_get)
    app.router.add_post("/panel/login", login_post)
    app.router.add_get("/panel/logout", logout)
    app.router.add_get("/panel", dashboard)
    app.router.add_get("/panel/products", products_list)
    app.router.add_get("/panel/products/new", product_new_get)
    app.router.add_post("/panel/products/new", product_new_post)
    app.router.add_get("/panel/products/{pid:\\d+}", product_edit_get)
    app.router.add_post("/panel/products/{pid:\\d+}", product_edit_post)
    app.router.add_post("/panel/products/{pid:\\d+}/stock", product_stock_post)
    app.router.add_post("/panel/products/{pid:\\d+}/delete", product_delete_post)
    app.router.add_get("/panel/prices", prices_get)
    app.router.add_post("/panel/prices", prices_post)
    app.router.add_get("/panel/gateways", gateways_get)
    app.router.add_post("/panel/gateways", gateways_post)
    app.router.add_get("/panel/system", system_get)
    app.router.add_post("/panel/system", system_post)
    app.router.add_get("/panel/audit", audit_view)
    return app


def _render_prices(session: dict | None, service: Service, flash: str = "") -> str:
    values = {
        "price": f"{service.price_per_gb:g}",
        "reseller": f"{service.reseller_price_per_gb:g}",
        "v2ray_plan": f"{service.v2ray_plan_price:g}",
        "v2ray_plan_res": f"{service.v2ray_plan_reseller_price:g}",
        "toman": f"{service.toman_per_usd:g}",
        "min_topup": f"{service.min_topup:g}",
    }
    return T.prices_page(
        csrf=str((session or {}).get("csrf", "")), values=values,
        currency=service.currency, flash=flash,
    )


def _do_backup(db: Database) -> str:
    """یک نسخه‌ی پشتیبان سازگار با WAL از دیتابیس در پوشه‌ی backups می‌سازد."""
    import os
    import sqlite3
    import time as _time
    try:
        base_dir = os.path.dirname(os.path.dirname(str(db.path)))
        bdir = os.path.join(base_dir, "backups")
        os.makedirs(bdir, exist_ok=True)
        ts = _time.strftime("%Y%m%d-%H%M%S")
        out = os.path.join(bdir, f"resibot-{ts}.db")
        src = sqlite3.connect(str(db.path))
        dst = sqlite3.connect(out)
        with dst:
            src.backup(dst)
        src.close()
        dst.close()
        # چرخش: فقط ۲۰ نسخه‌ی اخیر
        import glob
        files = sorted(glob.glob(os.path.join(bdir, "resibot-*.db")))
        for old in files[:-20]:
            try:
                os.remove(old)
            except OSError:
                pass
        return f"پشتیبان ساخته شد: {os.path.basename(out)}"
    except Exception as exc:  # noqa: BLE001
        logger.exception("backup failed")
        return f"خطا در تهیه‌ی پشتیبان: {exc}"


def _to_float(raw: Any, default):
    try:
        return round(float(str(raw).replace(",", ".")), 4)
    except (TypeError, ValueError):
        return default


def _to_int(raw: Any, default: int) -> int:
    try:
        return int(float(str(raw)))
    except (TypeError, ValueError):
        return default


class WebPanelManager:
    """مدیریت چرخه‌ی حیات پنل وب با امکان استارت پویا از داخل ربات.

    وقتی ادمین از داخل ربات رمز پنل وب را تنظیم می‌کند، بدون نیاز به ری‌استارتِ
    کل سرویس، پنل وب با ensure_started() بالا می‌آید.
    """

    def __init__(self, cfg: Settings, db: Database, service: Service) -> None:
        self.cfg = cfg
        self.db = db
        self.service = service
        self._runner: web.AppRunner | None = None

    @property
    def is_running(self) -> bool:
        return self._runner is not None

    async def ensure_started(self) -> bool:
        """اگر پنل فعال و دارای رمز باشد و هنوز اجرا نشده، آن را بالا می‌آورد.

        True یعنی الان در حال اجراست (چه از قبل، چه همین حالا استارت شد).
        """
        if self._runner is not None:
            return True
        if not self.service.web_panel_active:
            return False
        try:
            await self._start()
            return True
        except Exception:  # noqa: BLE001
            logger.exception("استارت پویای پنل وب ناموفق بود")
            return False

    async def _start(self) -> None:
        cfg = self.cfg
        app = make_web_app(cfg, self.db, self.service)
        runner = web.AppRunner(app)
        await runner.setup()
        ssl_context = None
        if cfg.web_panel_cert_file and cfg.web_panel_key_file:
            import ssl
            ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            ssl_context.load_cert_chain(cfg.web_panel_cert_file, cfg.web_panel_key_file)
        site = web.TCPSite(runner, cfg.web_panel_host, cfg.web_panel_port, ssl_context=ssl_context)
        await site.start()
        self._runner = runner
        scheme = "https" if ssl_context else "http"
        logger.info("پنل وب روی %s://%s:%s بالا آمد", scheme, cfg.web_panel_host, cfg.web_panel_port)

    async def cleanup(self) -> None:
        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None


async def start_web_panel(cfg: Settings, db: Database, service: Service) -> WebPanelManager:
    """پنل وب را (در صورت فعال بودن) بالا می‌آورد و مدیر آن را برمی‌گرداند."""
    manager = WebPanelManager(cfg, db, service)
    await manager.ensure_started()
    return manager
