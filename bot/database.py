"""لایه‌ی دیتابیس SQLite.

از sqlite3 استاندارد با یک قفل thread برای ایمنی استفاده می‌کنیم تا وابستگی
اضافه نداشته باشیم. مهاجرت‌ها به‌صورت additive و با PRAGMA user_version انجام
می‌شوند تا هنگام آپدیت ربات، دیتابیس و داده‌ها حفظ شوند.

جداول:
  - settings(key, value)            : تنظیمات قابل‌ویرایش در زمان اجرا
  - resellers(tg_id, name, ...)     : نماینده‌های مجاز
  - configs(...)                    : کانفیگ‌های فروخته‌شده + پارامترهای اوتباند
"""
from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Iterable, Optional

# آخرین نسخه‌ی اسکیما. هر بار که مهاجرت جدید اضافه می‌شود، این عدد زیاد می‌شود.
SCHEMA_VERSION = 8

# نقش‌های کاربری
ROLE_ADMIN = "admin"
ROLE_RESIDENTIAL_RESELLER = "residential_reseller"
ROLE_V2RAY_RESELLER = "v2ray_reseller"
ROLE_USER = "user"

# انواع محصول
PRODUCT_RESIDENTIAL = "residential"       # رزیدنتال (SmartProxy)
PRODUCT_RESIDENTIAL2 = "residential2"     # رزیدنتال ۲ (IPRoyal)
PRODUCT_V2RAY = "v2ray"
PRODUCT_DIGITAL = "digital"               # محصولات دیجیتال (اکانت/اشتراک آماده)


class Database:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        # check_same_thread=False چون با قفل خودمان همگام‌سازی می‌کنیم
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        # --- سخت‌سازی امنیتی/پایداری دیتابیس ---
        # journal_mode=WAL: هم‌زمانی خواندن/نوشتن بهتر و مقاومت در برابر خرابی.
        self._conn.execute("PRAGMA journal_mode=WAL;")
        # foreign_keys=ON: یکپارچگی ارجاعی (جلوی داده‌ی یتیم و ناسازگار را می‌گیرد).
        self._conn.execute("PRAGMA foreign_keys=ON;")
        # busy_timeout: به‌جای خطای فوری «database is locked»، تا ۵ ثانیه صبر می‌کند.
        self._conn.execute("PRAGMA busy_timeout=5000;")
        # secure_delete: هنگام حذف، بایت‌های داده صفر می‌شوند تا روی دیسک باقی نماند
        # (اهمیت برای داده‌ی حساس مثل اکانت‌های تحویل‌شده).
        self._conn.execute("PRAGMA secure_delete=ON;")
        # synchronous=NORMAL: تعادل ایمن بین سرعت و دوام داده در حالت WAL.
        self._conn.execute("PRAGMA synchronous=NORMAL;")
        # trusted_schema=OFF: جلوگیری از اجرای توابع/ویوهای مخرب از داخل اسکیما.
        try:
            self._conn.execute("PRAGMA trusted_schema=OFF;")
        except sqlite3.Error:
            pass  # نسخه‌های قدیمی SQLite این PRAGMA را ندارند
        self._migrate()

    # ------------------------------------------------------------------ #
    # مهاجرت‌ها
    # ------------------------------------------------------------------ #
    def _migrate(self) -> None:
        with self._lock:
            cur = self._conn.execute("PRAGMA user_version;")
            current = int(cur.fetchone()[0])

            if current < 1:
                self._migrate_v1()
            if current < 2:
                self._migrate_v2()
            if current < 3:
                self._migrate_v3()
            if current < 4:
                self._migrate_v4()
            if current < 5:
                self._migrate_v5()
            if current < 6:
                self._migrate_v6()
            if current < 7:
                self._migrate_v7()
            if current < 8:
                self._migrate_v8()

            # نسخه را به‌روز می‌کنیم
            self._conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION};")
            self._conn.commit()

    def _migrate_v1(self) -> None:
        c = self._conn
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS resellers (
                tg_id      INTEGER PRIMARY KEY,
                name       TEXT DEFAULT '',
                added_at   INTEGER NOT NULL,
                active     INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS configs (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_tg_id    INTEGER NOT NULL,
                inbound_id     INTEGER NOT NULL,
                port           INTEGER NOT NULL,
                client_uuid    TEXT NOT NULL,
                client_email   TEXT NOT NULL,
                sub_id         TEXT NOT NULL,
                outbound_tag   TEXT NOT NULL,
                inbound_tag    TEXT NOT NULL,
                volume_gb      INTEGER NOT NULL,
                duration_days  INTEGER NOT NULL,
                expiry_ms      INTEGER NOT NULL,
                -- پارامترهای SmartProxy برای تغییر IP/لوکیشن
                area           TEXT DEFAULT '',
                state          TEXT DEFAULT '',
                city           TEXT DEFAULT '',
                life           INTEGER DEFAULT 0,
                session        TEXT DEFAULT '',
                created_at     INTEGER NOT NULL,
                active         INTEGER NOT NULL DEFAULT 1
            );

            CREATE INDEX IF NOT EXISTS idx_configs_owner ON configs(owner_tg_id);
            CREATE INDEX IF NOT EXISTS idx_configs_email ON configs(client_email);
            """
        )
        c.commit()

    def _column_exists(self, table: str, column: str) -> bool:
        cur = self._conn.execute(f"PRAGMA table_info({table})")
        return any(r[1] == column for r in cur.fetchall())

    def _migrate_v2(self) -> None:
        c = self._conn
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                tg_id      INTEGER PRIMARY KEY,
                role       TEXT NOT NULL DEFAULT 'user',
                balance    REAL NOT NULL DEFAULT 0,
                name       TEXT DEFAULT '',
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS partnership_requests (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                tg_id       INTEGER NOT NULL,
                ptype       TEXT NOT NULL,
                description TEXT DEFAULT '',
                status      TEXT NOT NULL DEFAULT 'pending',
                created_at  INTEGER NOT NULL,
                decided_at  INTEGER DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_preq_status ON partnership_requests(status);
            CREATE INDEX IF NOT EXISTS idx_preq_tg ON partnership_requests(tg_id);

            CREATE TABLE IF NOT EXISTS payments (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id    TEXT UNIQUE NOT NULL,
                tg_id       INTEGER NOT NULL,
                amount      REAL NOT NULL,
                currency    TEXT NOT NULL,
                purpose     TEXT NOT NULL DEFAULT 'wallet_topup',
                status      TEXT NOT NULL DEFAULT 'waiting',
                invoice_id  TEXT DEFAULT '',
                credited    INTEGER NOT NULL DEFAULT 0,
                created_at  INTEGER NOT NULL,
                updated_at  INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_payments_tg ON payments(tg_id);
            """
        )
        # ستون‌های جدید configs (idempotent)
        if not self._column_exists("configs", "product_type"):
            c.execute("ALTER TABLE configs ADD COLUMN product_type TEXT DEFAULT 'residential'")
        if not self._column_exists("configs", "price"):
            c.execute("ALTER TABLE configs ADD COLUMN price REAL DEFAULT 0")
        if not self._column_exists("configs", "payer"):
            c.execute("ALTER TABLE configs ADD COLUMN payer TEXT DEFAULT ''")
        # مهاجرت نماینده‌های قبلی به جدول users با نقش همکار رزیدنتال
        now = int(time.time())
        rows = c.execute("SELECT tg_id, name FROM resellers WHERE active = 1").fetchall()
        for r in rows:
            c.execute(
                "INSERT INTO users(tg_id, role, balance, name, created_at, updated_at) "
                "VALUES(?, 'residential_reseller', 0, ?, ?, ?) "
                "ON CONFLICT(tg_id) DO UPDATE SET role='residential_reseller'",
                (r[0], r[1] or "", now, now),
            )
        c.commit()

    def _migrate_v3(self) -> None:
        # ستون meta برای ذخیره‌ی جزئیات سفارش در انتظار پرداخت (JSON)
        if not self._column_exists("payments", "meta"):
            self._conn.execute("ALTER TABLE payments ADD COLUMN meta TEXT DEFAULT ''")
        self._conn.commit()

    def _migrate_v4(self) -> None:
        """افزودن ستون customer_tg_id به configs.

        این ستون برای ربات کمکی مشتری استفاده می‌شود: همکار/مالک کانفیگ
        می‌تواند از داخل «مدیریت سرویس» تعیین کند کدام مشتری (با آیدی عددی
        تلگرام) اجازه دارد IP و تنظیمات همین کانفیگ مشخص را از طریق ربات
        کمکی مدیریت کند. 0 یعنی هنوز مشتری‌ای تعیین نشده.
        """
        if not self._column_exists("configs", "customer_tg_id"):
            self._conn.execute(
                "ALTER TABLE configs ADD COLUMN customer_tg_id INTEGER NOT NULL DEFAULT 0"
            )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_configs_customer ON configs(customer_tg_id)"
        )
        self._conn.commit()

    def _migrate_v5(self) -> None:
        """افزودن پشتیبانی پرداخت مستقیم کریپتو (USDT BEP20) به جدول payments.

        همه‌ی تغییرات additive هستند و هیچ داده‌ای پاک نمی‌شود.
          - method       : روش پرداخت ('nowpayments' یا 'crypto')
          - pay_address   : آدرس مقصد کریپتو
          - pay_amount    : مبلغ دقیق و یکتای USDT که باید واریز شود (برای تطبیق)
          - pay_currency  : ارز/شبکه‌ی پرداخت (مثل 'USDT-BEP20')
          - tx_hash       : هش تراکنش تأییدشده (هر هش فقط یک‌بار قابل‌استفاده)
          - start_block   : شماره‌ی بلاک هنگام ساخت فاکتور (فقط واریزهای بعد از آن معتبرند)
          - expires_at    : زمان انقضای فاکتور (unix seconds)
        """
        c = self._conn
        for col, ddl in (
            ("method", "ALTER TABLE payments ADD COLUMN method TEXT DEFAULT 'nowpayments'"),
            ("pay_address", "ALTER TABLE payments ADD COLUMN pay_address TEXT DEFAULT ''"),
            ("pay_amount", "ALTER TABLE payments ADD COLUMN pay_amount REAL DEFAULT 0"),
            ("pay_currency", "ALTER TABLE payments ADD COLUMN pay_currency TEXT DEFAULT ''"),
            ("tx_hash", "ALTER TABLE payments ADD COLUMN tx_hash TEXT DEFAULT ''"),
            ("start_block", "ALTER TABLE payments ADD COLUMN start_block INTEGER DEFAULT 0"),
            ("expires_at", "ALTER TABLE payments ADD COLUMN expires_at INTEGER DEFAULT 0"),
        ):
            if not self._column_exists("payments", col):
                c.execute(ddl)
        # هر هش تراکنش فقط یک‌بار می‌تواند یک پرداخت را credit کند (ضدتکرار/ری‌پلی).
        # ایندکس جزئی تا رشته‌های خالی با هم تعارض نداشته باشند.
        c.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_payments_txhash "
            "ON payments(tx_hash) WHERE tx_hash != ''"
        )
        c.execute("CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_payments_method ON payments(method)")
        c.commit()

    def _migrate_v6(self) -> None:
        """رفرال (referred_by/ref_earnings روی users) + جدول تخفیف‌های کاربر.

        همه‌ی تغییرات additive هستند و هیچ داده‌ای پاک نمی‌شود.
        """
        c = self._conn
        if not self._column_exists("users", "referred_by"):
            c.execute("ALTER TABLE users ADD COLUMN referred_by INTEGER NOT NULL DEFAULT 0")
        if not self._column_exists("users", "ref_earnings"):
            c.execute("ALTER TABLE users ADD COLUMN ref_earnings REAL NOT NULL DEFAULT 0")
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS discounts (
                tg_id   INTEGER NOT NULL,
                product TEXT NOT NULL,   -- 'all' یا نوع محصول مشخص
                percent REAL NOT NULL DEFAULT 0,
                PRIMARY KEY (tg_id, product)
            );
            """
        )
        c.execute("CREATE INDEX IF NOT EXISTS idx_users_ref ON users(referred_by)")
        c.commit()

    def _migrate_v7(self) -> None:
        """افزودن ستون is_banned برای مسدودسازی کاربر (additive، بدون حذف داده)."""
        if not self._column_exists("users", "is_banned"):
            self._conn.execute("ALTER TABLE users ADD COLUMN is_banned INTEGER NOT NULL DEFAULT 0")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_payments_created ON payments(created_at)")
        self._conn.commit()

    def _migrate_v8(self) -> None:
        """محصولات دیجیتال (اکانت/اشتراک آماده) + انبار موجودی + لاگ حسابرسی.

        همه‌ی تغییرات additive هستند و هیچ داده‌ی قبلی پاک نمی‌شود.
          - digital_products : تعریف محصول (عنوان، متن فروش، قیمت، وضعیت) — قابل
                               ویرایش از ربات و پنل وب.
          - digital_stock    : اقلام آماده‌ی تحویل (اکانت/کد)؛ پس از پرداخت یکی
                               به‌صورت اتمیک به خریدار تخصیص می‌یابد.
          - audit_log        : ثبت رخدادهای حساس (ورود پنل وب، تغییر محصول، ...)
                               برای ردیابی و امنیت.
        """
        c = self._conn
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS digital_products (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                slug          TEXT UNIQUE NOT NULL,
                title         TEXT NOT NULL,
                subtitle      TEXT NOT NULL DEFAULT '',
                description   TEXT NOT NULL DEFAULT '',
                price         REAL NOT NULL DEFAULT 0,
                currency      TEXT NOT NULL DEFAULT 'USD',
                duration_days INTEGER NOT NULL DEFAULT 0,
                delivery_type TEXT NOT NULL DEFAULT 'stock',
                active        INTEGER NOT NULL DEFAULT 1,
                sort_order    INTEGER NOT NULL DEFAULT 0,
                created_at    INTEGER NOT NULL,
                updated_at    INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS digital_stock (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id   INTEGER NOT NULL,
                payload      TEXT NOT NULL,
                status       TEXT NOT NULL DEFAULT 'available',
                buyer_tg_id  INTEGER NOT NULL DEFAULT 0,
                order_id     TEXT NOT NULL DEFAULT '',
                sold_at      INTEGER NOT NULL DEFAULT 0,
                created_at   INTEGER NOT NULL,
                FOREIGN KEY(product_id) REFERENCES digital_products(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_stock_product ON digital_stock(product_id, status);

            CREATE TABLE IF NOT EXISTS audit_log (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                ts      INTEGER NOT NULL,
                actor   TEXT NOT NULL DEFAULT '',
                ip      TEXT NOT NULL DEFAULT '',
                action  TEXT NOT NULL DEFAULT '',
                detail  TEXT NOT NULL DEFAULT ''
            );
            CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit_log(ts);
            """
        )
        c.commit()

    # ------------------------------------------------------------------ #
    # محصولات دیجیتال
    # ------------------------------------------------------------------ #
    _DIGITAL_UPDATABLE = frozenset({
        "title", "subtitle", "description", "price", "currency",
        "duration_days", "delivery_type", "active", "sort_order",
    })

    def create_digital_product(
        self,
        slug: str,
        title: str,
        *,
        subtitle: str = "",
        description: str = "",
        price: float = 0.0,
        currency: str = "USD",
        duration_days: int = 0,
        delivery_type: str = "stock",
        active: bool = True,
        sort_order: int = 0,
    ) -> int:
        now = int(time.time())
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO digital_products("
                "slug, title, subtitle, description, price, currency, duration_days, "
                "delivery_type, active, sort_order, created_at, updated_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    slug, title, subtitle, description, float(price), currency,
                    int(duration_days), delivery_type, 1 if active else 0,
                    int(sort_order), now, now,
                ),
            )
            self._conn.commit()
            return int(cur.lastrowid)

    def seed_digital_product(self, slug: str, **kwargs: Any) -> Optional[int]:
        """اگر محصولی با این slug نباشد، آن را می‌سازد (idempotent). id یا None."""
        if self.get_digital_product_by_slug(slug) is not None:
            return None
        return self.create_digital_product(slug, kwargs.pop("title", slug), **kwargs)

    def update_digital_product(self, product_id: int, **fields: Any) -> None:
        cols = [k for k in fields if k in self._DIGITAL_UPDATABLE]
        if not cols:
            return
        set_clause = ", ".join(f"{c} = ?" for c in cols) + ", updated_at = ?"
        params = [fields[c] for c in cols] + [int(time.time()), int(product_id)]
        self.execute(f"UPDATE digital_products SET {set_clause} WHERE id = ?", params)

    def get_digital_product(self, product_id: int) -> Optional[sqlite3.Row]:
        return self.query_one("SELECT * FROM digital_products WHERE id = ?", (int(product_id),))

    def get_digital_product_by_slug(self, slug: str) -> Optional[sqlite3.Row]:
        return self.query_one("SELECT * FROM digital_products WHERE slug = ?", (slug,))

    def list_digital_products(self, *, active_only: bool = False) -> list[sqlite3.Row]:
        if active_only:
            return self.query_all(
                "SELECT * FROM digital_products WHERE active = 1 "
                "ORDER BY sort_order ASC, id ASC"
            )
        return self.query_all(
            "SELECT * FROM digital_products ORDER BY sort_order ASC, id ASC"
        )

    def delete_digital_product(self, product_id: int) -> None:
        self.execute("DELETE FROM digital_products WHERE id = ?", (int(product_id),))

    # --- انبار موجودی محصولات دیجیتال ---
    def add_stock_items(self, product_id: int, payloads: Iterable[str]) -> int:
        """چند قلم موجودی برای یک محصول اضافه می‌کند. تعداد اقلام اضافه‌شده را برمی‌گرداند."""
        now = int(time.time())
        count = 0
        with self._lock:
            for p in payloads:
                p = (p or "").strip()
                if not p:
                    continue
                self._conn.execute(
                    "INSERT INTO digital_stock(product_id, payload, status, created_at) "
                    "VALUES(?, ?, 'available', ?)",
                    (int(product_id), p, now),
                )
                count += 1
            self._conn.commit()
        return count

    def count_available_stock(self, product_id: int) -> int:
        row = self.query_one(
            "SELECT COUNT(*) AS c FROM digital_stock WHERE product_id = ? AND status = 'available'",
            (int(product_id),),
        )
        return int(row["c"]) if row else 0

    def stock_counts(self) -> dict[int, int]:
        """تعداد موجودی آماده‌ی هر محصول را برمی‌گرداند: {product_id: count}."""
        rows = self.query_all(
            "SELECT product_id, COUNT(*) AS c FROM digital_stock "
            "WHERE status = 'available' GROUP BY product_id"
        )
        return {int(r["product_id"]): int(r["c"]) for r in rows}

    def claim_stock_item(self, product_id: int, buyer_tg_id: int, order_id: str) -> Optional[sqlite3.Row]:
        """به‌صورت اتمیک یک قلم موجودی را به خریدار تخصیص می‌دهد.

        اگر همین سفارش قبلاً قلمی گرفته باشد، همان را برمی‌گرداند (idempotent).
        اگر موجودی نباشد None برمی‌گرداند.
        """
        with self._lock:
            # اگر این سفارش قبلاً قلمی دریافت کرده، همان را بده (جلوگیری از تحویل دوباره).
            existing = self._conn.execute(
                "SELECT * FROM digital_stock WHERE order_id = ? AND order_id != '' LIMIT 1",
                (order_id,),
            ).fetchone()
            if existing is not None:
                return existing
            row = self._conn.execute(
                "SELECT id FROM digital_stock WHERE product_id = ? AND status = 'available' "
                "ORDER BY id ASC LIMIT 1",
                (int(product_id),),
            ).fetchone()
            if row is None:
                return None
            item_id = int(row["id"])
            cur = self._conn.execute(
                "UPDATE digital_stock SET status = 'sold', buyer_tg_id = ?, order_id = ?, "
                "sold_at = ? WHERE id = ? AND status = 'available'",
                (int(buyer_tg_id), order_id, int(time.time()), item_id),
            )
            self._conn.commit()
            if cur.rowcount <= 0:
                return None
            return self._conn.execute(
                "SELECT * FROM digital_stock WHERE id = ?", (item_id,)
            ).fetchone()

    def list_stock(self, product_id: int, *, limit: int = 50) -> list[sqlite3.Row]:
        return self.query_all(
            "SELECT * FROM digital_stock WHERE product_id = ? ORDER BY id DESC LIMIT ?",
            (int(product_id), int(limit)),
        )

    def clear_available_stock(self, product_id: int) -> int:
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM digital_stock WHERE product_id = ? AND status = 'available'",
                (int(product_id),),
            )
            self._conn.commit()
            return cur.rowcount

    def count_digital_sales(self, product_id: int) -> int:
        row = self.query_one(
            "SELECT COUNT(*) AS c FROM digital_stock WHERE product_id = ? AND status = 'sold'",
            (int(product_id),),
        )
        return int(row["c"]) if row else 0

    # ------------------------------------------------------------------ #
    # لاگ حسابرسی (رخدادهای حساس)
    # ------------------------------------------------------------------ #
    def audit(self, action: str, *, actor: str = "", ip: str = "", detail: str = "") -> None:
        try:
            self.execute(
                "INSERT INTO audit_log(ts, actor, ip, action, detail) VALUES(?,?,?,?,?)",
                (int(time.time()), str(actor)[:64], str(ip)[:64], str(action)[:64], str(detail)[:500]),
            )
        except sqlite3.Error:
            pass  # لاگ‌گیری هرگز نباید مسیر اصلی را متوقف کند

    def list_audit(self, limit: int = 50) -> list[sqlite3.Row]:
        return self.query_all(
            "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (int(limit),)
        )

    def prune_audit(self, keep: int = 5000) -> None:
        """لاگ‌های قدیمی را هرس می‌کند تا جدول بی‌نهایت رشد نکند."""
        self.execute(
            "DELETE FROM audit_log WHERE id NOT IN "
            "(SELECT id FROM audit_log ORDER BY id DESC LIMIT ?)",
            (int(keep),),
        )

    def execute(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Cursor:
        with self._lock:
            cur = self._conn.execute(sql, tuple(params))
            self._conn.commit()
            return cur

    def query_one(self, sql: str, params: Iterable[Any] = ()) -> Optional[sqlite3.Row]:
        with self._lock:
            cur = self._conn.execute(sql, tuple(params))
            return cur.fetchone()

    def query_all(self, sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
        with self._lock:
            cur = self._conn.execute(sql, tuple(params))
            return cur.fetchall()

    # ------------------------------------------------------------------ #
    # settings (key-value)
    # ------------------------------------------------------------------ #
    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        row = self.query_one("SELECT value FROM settings WHERE key = ?", (key,))
        return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        self.execute(
            "INSERT INTO settings(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, str(value)),
        )

    def seed_setting(self, key: str, value: str) -> None:
        """فقط اگر کلید وجود نداشته باشد مقدار اولیه را می‌گذارد (idempotent)."""
        if self.get_setting(key) is None:
            self.set_setting(key, value)

    # ------------------------------------------------------------------ #
    # resellers
    # ------------------------------------------------------------------ #
    def add_reseller(self, tg_id: int, name: str = "") -> None:
        self.execute(
            "INSERT INTO resellers(tg_id, name, added_at, active) VALUES(?, ?, ?, 1) "
            "ON CONFLICT(tg_id) DO UPDATE SET active = 1, name = excluded.name",
            (tg_id, name, int(time.time())),
        )

    def remove_reseller(self, tg_id: int) -> None:
        self.execute("DELETE FROM resellers WHERE tg_id = ?", (tg_id,))

    def is_reseller(self, tg_id: int) -> bool:
        row = self.query_one(
            "SELECT 1 FROM resellers WHERE tg_id = ? AND active = 1", (tg_id,)
        )
        return row is not None

    def list_resellers(self) -> list[sqlite3.Row]:
        return self.query_all("SELECT * FROM resellers ORDER BY added_at DESC")

    # ------------------------------------------------------------------ #
    # configs
    # ------------------------------------------------------------------ #
    def add_config(self, data: dict[str, Any]) -> int:
        cols = (
            "owner_tg_id", "inbound_id", "port", "client_uuid", "client_email",
            "sub_id", "outbound_tag", "inbound_tag", "volume_gb", "duration_days",
            "expiry_ms", "area", "state", "city", "life", "session",
            "created_at", "active", "product_type", "price", "payer",
            "customer_tg_id",
        )
        values = [data.get(c, 0) if c == "customer_tg_id" else data.get(c) for c in cols]
        placeholders = ", ".join("?" for _ in cols)
        with self._lock:
            cur = self._conn.execute(
                f"INSERT INTO configs ({', '.join(cols)}) VALUES ({placeholders})",
                tuple(values),
            )
            self._conn.commit()
            return int(cur.lastrowid)

    def get_config(self, config_id: int) -> Optional[sqlite3.Row]:
        return self.query_one("SELECT * FROM configs WHERE id = ?", (config_id,))

    def list_configs_by_owner(self, owner_tg_id: int) -> list[sqlite3.Row]:
        return self.query_all(
            "SELECT * FROM configs WHERE owner_tg_id = ? AND active = 1 "
            "ORDER BY created_at DESC",
            (owner_tg_id,),
        )

    def list_all_configs(self) -> list[sqlite3.Row]:
        return self.query_all("SELECT * FROM configs WHERE active = 1 ORDER BY created_at DESC")

    def set_config_customer(self, config_id: int, customer_tg_id: int) -> None:
        """تعیین یا حذف مشتریِ مجاز برای مدیریت IP این کانفیگ مشخص.

        customer_tg_id=0 یعنی هیچ مشتری‌ای تعیین نشده (دسترسی ربات کمکی
        برای این کانفیگ غیرفعال است).
        """
        self.execute(
            "UPDATE configs SET customer_tg_id = ? WHERE id = ?",
            (int(customer_tg_id), config_id),
        )

    def list_configs_by_customer(self, customer_tg_id: int) -> list[sqlite3.Row]:
        """کانفیگ‌های فعالی که توسط مالک/همکار به این مشتری سپرده شده‌اند."""
        return self.query_all(
            "SELECT * FROM configs WHERE customer_tg_id = ? AND active = 1 "
            "ORDER BY created_at DESC",
            (int(customer_tg_id),),
        )

    def get_config_for_customer(self, config_id: int, customer_tg_id: int) -> Optional[sqlite3.Row]:
        """یک کانفیگ مشخص را فقط اگر متعلق به این مشتری باشد برمی‌گرداند."""
        return self.query_one(
            "SELECT * FROM configs WHERE id = ? AND customer_tg_id = ? AND active = 1",
            (config_id, int(customer_tg_id)),
        )

    def update_config_location(
        self,
        config_id: int,
        *,
        area: str,
        state: str,
        city: str,
        session: str,
    ) -> None:
        self.execute(
            "UPDATE configs SET area = ?, state = ?, city = ?, session = ? WHERE id = ?",
            (area, state, city, session, config_id),
        )

    def update_config_life(self, config_id: int, life: int) -> None:
        self.execute(
            "UPDATE configs SET life = ? WHERE id = ?",
            (int(life), config_id),
        )

    def deactivate_config(self, config_id: int) -> None:
        self.execute("UPDATE configs SET active = 0 WHERE id = ?", (config_id,))

    def renew_config(self, config_id: int, new_volume_gb: int, new_expiry_ms: int, add_price: float) -> None:
        self.execute(
            "UPDATE configs SET volume_gb = ?, expiry_ms = ?, price = price + ? WHERE id = ?",
            (int(new_volume_gb), int(new_expiry_ms), float(add_price), config_id),
        )

    # ------------------------------------------------------------------ #
    # users / roles / wallet
    # ------------------------------------------------------------------ #
    def ensure_user(self, tg_id: int, name: str = "") -> sqlite3.Row:
        now = int(time.time())
        self.execute(
            "INSERT INTO users(tg_id, role, balance, name, created_at, updated_at) "
            "VALUES(?, 'user', 0, ?, ?, ?) "
            "ON CONFLICT(tg_id) DO UPDATE SET name = CASE WHEN excluded.name != '' THEN excluded.name ELSE users.name END",
            (tg_id, name, now, now),
        )
        return self.get_user(tg_id)

    def get_user(self, tg_id: int) -> Optional[sqlite3.Row]:
        return self.query_one("SELECT * FROM users WHERE tg_id = ?", (tg_id,))

    def get_role(self, tg_id: int) -> str:
        row = self.get_user(tg_id)
        return row["role"] if row else "user"

    def set_role(self, tg_id: int, role: str) -> None:
        self.ensure_user(tg_id)
        self.execute(
            "UPDATE users SET role = ?, updated_at = ? WHERE tg_id = ?",
            (role, int(time.time()), tg_id),
        )

    def get_balance(self, tg_id: int) -> float:
        row = self.get_user(tg_id)
        return float(row["balance"]) if row else 0.0

    def add_balance(self, tg_id: int, amount: float) -> float:
        """افزایش/کاهش اتمیک موجودی. مقدار جدید را برمی‌گرداند."""
        with self._lock:
            self.ensure_user(tg_id)
            self._conn.execute(
                "UPDATE users SET balance = balance + ?, updated_at = ? WHERE tg_id = ?",
                (float(amount), int(time.time()), tg_id),
            )
            self._conn.commit()
            row = self._conn.execute("SELECT balance FROM users WHERE tg_id = ?", (tg_id,)).fetchone()
            return float(row[0]) if row else 0.0

    def try_deduct_balance(self, tg_id: int, amount: float) -> bool:
        """کسر اتمیک موجودی فقط اگر کافی باشد. True در صورت موفقیت."""
        amount = float(amount)
        with self._lock:
            self.ensure_user(tg_id)
            cur = self._conn.execute(
                "UPDATE users SET balance = balance - ?, updated_at = ? "
                "WHERE tg_id = ? AND balance >= ?",
                (amount, int(time.time()), tg_id, amount),
            )
            self._conn.commit()
            return cur.rowcount > 0

    def list_users_by_role(self, role: str) -> list[sqlite3.Row]:
        return self.query_all(
            "SELECT * FROM users WHERE role = ? ORDER BY updated_at DESC", (role,)
        )

    # ------------------------------------------------------------------ #
    # مسدودسازی کاربر
    # ------------------------------------------------------------------ #
    def set_banned(self, tg_id: int, banned: bool) -> None:
        self.ensure_user(tg_id)
        self.execute(
            "UPDATE users SET is_banned = ?, updated_at = ? WHERE tg_id = ?",
            (1 if banned else 0, int(time.time()), int(tg_id)),
        )

    def is_banned(self, tg_id: int) -> bool:
        row = self.get_user(tg_id)
        try:
            return bool(row and int(row["is_banned"]))
        except (KeyError, IndexError, TypeError, ValueError):
            return False

    def count_banned(self) -> int:
        row = self.query_one("SELECT COUNT(*) AS c FROM users WHERE is_banned = 1")
        return int(row["c"]) if row else 0

    def count_configs(self, owner_tg_id: int) -> int:
        row = self.query_one(
            "SELECT COUNT(*) AS c FROM configs WHERE owner_tg_id = ? AND active = 1",
            (int(owner_tg_id),),
        )
        return int(row["c"]) if row else 0

    # ------------------------------------------------------------------ #
    # تراکنش‌ها (گزارش)
    # ------------------------------------------------------------------ #
    def list_recent_payments(self, limit: int = 20) -> list[sqlite3.Row]:
        return self.query_all(
            "SELECT * FROM payments ORDER BY created_at DESC LIMIT ?", (int(limit),)
        )

    def latest_waiting_crypto_payment(self, tg_id: int) -> Optional[sqlite3.Row]:
        return self.query_one(
            "SELECT * FROM payments WHERE tg_id = ? AND method = 'crypto' AND credited = 0 "
            "AND status = 'waiting' ORDER BY created_at DESC LIMIT 1",
            (int(tg_id),),
        )

    def payment_totals(self) -> dict[str, Any]:
        """آمار پرداخت‌ها: تعداد کل، تعداد پرداخت‌شده، و مجموع مبالغ credit‌شده به تفکیک ارز."""
        total = self.query_one("SELECT COUNT(*) AS c FROM payments")
        paid = self.query_one("SELECT COUNT(*) AS c FROM payments WHERE credited = 1")
        by_cur = self.query_all(
            "SELECT currency, COUNT(*) AS c, SUM(amount) AS s FROM payments "
            "WHERE credited = 1 GROUP BY currency"
        )
        return {
            "total": int(total["c"]) if total else 0,
            "paid": int(paid["c"]) if paid else 0,
            "by_currency": [
                {"currency": r["currency"], "count": int(r["c"]), "sum": float(r["s"] or 0)}
                for r in by_cur
            ],
        }

    # ------------------------------------------------------------------ #
    # رفرال
    # ------------------------------------------------------------------ #
    def set_referrer(self, tg_id: int, referrer_id: int) -> bool:
        """معرف را ثبت می‌کند فقط اگر قبلاً ثبت نشده و معرف ≠ خود کاربر باشد."""
        if referrer_id <= 0 or referrer_id == tg_id:
            return False
        self.ensure_user(tg_id)
        self.ensure_user(referrer_id)
        cur = self.execute(
            "UPDATE users SET referred_by = ? WHERE tg_id = ? AND "
            "(referred_by IS NULL OR referred_by = 0)",
            (int(referrer_id), int(tg_id)),
        )
        return cur.rowcount > 0

    def get_referrer(self, tg_id: int) -> int:
        row = self.get_user(tg_id)
        try:
            return int(row["referred_by"]) if row else 0
        except (KeyError, IndexError, TypeError, ValueError):
            return 0

    def add_ref_earning(self, tg_id: int, amount: float) -> float:
        """پاداش رفرال را هم به موجودی و هم به مجموع درآمد رفرال اضافه می‌کند."""
        amount = float(amount)
        with self._lock:
            self.ensure_user(tg_id)
            self._conn.execute(
                "UPDATE users SET balance = balance + ?, ref_earnings = ref_earnings + ?, "
                "updated_at = ? WHERE tg_id = ?",
                (amount, amount, int(time.time()), int(tg_id)),
            )
            self._conn.commit()
            row = self._conn.execute("SELECT balance FROM users WHERE tg_id = ?", (tg_id,)).fetchone()
            return float(row[0]) if row else 0.0

    def count_referrals(self, tg_id: int) -> int:
        row = self.query_one(
            "SELECT COUNT(*) AS c FROM users WHERE referred_by = ?", (int(tg_id),)
        )
        return int(row["c"]) if row else 0

    def ref_earnings(self, tg_id: int) -> float:
        row = self.get_user(tg_id)
        try:
            return float(row["ref_earnings"]) if row else 0.0
        except (KeyError, IndexError, TypeError, ValueError):
            return 0.0

    # ------------------------------------------------------------------ #
    # تخفیف‌های کاربر (درصدی؛ روی همه محصولات یا محصول مشخص)
    # ------------------------------------------------------------------ #
    def set_discount(self, tg_id: int, product: str, percent: float) -> None:
        self.execute(
            "INSERT INTO discounts(tg_id, product, percent) VALUES(?, ?, ?) "
            "ON CONFLICT(tg_id, product) DO UPDATE SET percent = excluded.percent",
            (int(tg_id), product, float(percent)),
        )

    def remove_discount(self, tg_id: int, product: str) -> None:
        self.execute(
            "DELETE FROM discounts WHERE tg_id = ? AND product = ?", (int(tg_id), product)
        )

    def get_discount_percent(self, tg_id: int, product: str) -> float:
        row = self.query_one(
            "SELECT percent FROM discounts WHERE tg_id = ? AND product = ?",
            (int(tg_id), product),
        )
        return float(row["percent"]) if row else 0.0

    def list_discounts_for(self, tg_id: int) -> list[sqlite3.Row]:
        return self.query_all(
            "SELECT * FROM discounts WHERE tg_id = ? ORDER BY product", (int(tg_id),)
        )

    def list_all_discounts(self) -> list[sqlite3.Row]:
        return self.query_all("SELECT * FROM discounts ORDER BY tg_id, product")

    def count_users(self) -> int:
        row = self.query_one("SELECT COUNT(*) AS c FROM users")
        return int(row["c"]) if row else 0

    def all_user_ids(self) -> list[int]:
        rows = self.query_all("SELECT tg_id FROM users")
        return [int(r["tg_id"]) for r in rows]

    def list_all_users(self, *, limit: int = 10, offset: int = 0) -> list[sqlite3.Row]:
        """لیست همه‌ی کاربران (جدیدترین اول) برای مرور صفحه‌به‌صفحه در پنل ادمین."""
        return self.query_all(
            "SELECT * FROM users ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (int(limit), int(offset)),
        )

    # ------------------------------------------------------------------ #
    # partnership requests
    # ------------------------------------------------------------------ #
    def add_partnership_request(self, tg_id: int, ptype: str, description: str) -> int:
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO partnership_requests(tg_id, ptype, description, status, created_at) "
                "VALUES(?, ?, ?, 'pending', ?)",
                (tg_id, ptype, description, int(time.time())),
            )
            self._conn.commit()
            return int(cur.lastrowid)

    def has_pending_request(self, tg_id: int) -> bool:
        row = self.query_one(
            "SELECT 1 FROM partnership_requests WHERE tg_id = ? AND status = 'pending'",
            (tg_id,),
        )
        return row is not None

    def get_request(self, req_id: int) -> Optional[sqlite3.Row]:
        return self.query_one("SELECT * FROM partnership_requests WHERE id = ?", (req_id,))

    def list_pending_requests(self) -> list[sqlite3.Row]:
        return self.query_all(
            "SELECT * FROM partnership_requests WHERE status = 'pending' ORDER BY created_at ASC"
        )

    def set_request_status(self, req_id: int, status: str) -> None:
        self.execute(
            "UPDATE partnership_requests SET status = ?, decided_at = ? WHERE id = ?",
            (status, int(time.time()), req_id),
        )

    # ------------------------------------------------------------------ #
    # payments
    # ------------------------------------------------------------------ #
    def create_payment(
        self, order_id: str, tg_id: int, amount: float, currency: str,
        purpose: str = "wallet_topup", meta: str = "",
        *,
        method: str = "nowpayments",
        pay_address: str = "",
        pay_amount: float = 0.0,
        pay_currency: str = "",
        start_block: int = 0,
        expires_at: int = 0,
    ) -> int:
        now = int(time.time())
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO payments("
                "order_id, tg_id, amount, currency, purpose, status, meta, "
                "method, pay_address, pay_amount, pay_currency, start_block, expires_at, "
                "created_at, updated_at) "
                "VALUES(?, ?, ?, ?, ?, 'waiting', ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    order_id, tg_id, float(amount), currency, purpose, meta,
                    method, pay_address, float(pay_amount), pay_currency,
                    int(start_block), int(expires_at), now, now,
                ),
            )
            self._conn.commit()
            return int(cur.lastrowid)

    # --- پرداخت مستقیم کریپتو (USDT BEP20) --- #
    def list_waiting_crypto_payments(self) -> list[sqlite3.Row]:
        """پرداخت‌های کریپتوی در انتظار و منقضی‌نشده و credit‌نشده."""
        return self.query_all(
            "SELECT * FROM payments "
            "WHERE method = 'crypto' AND credited = 0 AND status = 'waiting'"
        )

    def waiting_crypto_pay_amounts(self) -> set:
        """مجموعه‌ی مبالغ یکتای در حال استفاده (برای انتخاب offset بدون تداخل)."""
        rows = self.query_all(
            "SELECT pay_amount FROM payments "
            "WHERE method = 'crypto' AND credited = 0 AND status = 'waiting'"
        )
        return {round(float(r["pay_amount"]), 6) for r in rows}

    def tx_hash_used(self, tx_hash: str) -> bool:
        row = self.query_one(
            "SELECT 1 FROM payments WHERE tx_hash = ? AND tx_hash != ''",
            (tx_hash.lower(),),
        )
        return row is not None

    def credit_crypto_payment(self, order_id: str, tx_hash: str) -> Optional[sqlite3.Row]:
        """به‌صورت اتمیک هش تراکنش را ثبت و پرداخت را credit می‌کند.

        فقط اگر: پرداخت هنوز credit نشده باشد و همین هش قبلاً برای پرداخت دیگری
        استفاده نشده باشد. در صورت موفقیت ردیف پرداخت را برمی‌گرداند؛ در غیر این
        صورت None (تکراری/قبلاً پردازش‌شده/تداخل هش).
        """
        tx_hash = (tx_hash or "").lower()
        with self._lock:
            # اگر این هش قبلاً جای دیگری ثبت شده، رد کن (ضدری‌پلی).
            used = self._conn.execute(
                "SELECT 1 FROM payments WHERE tx_hash = ? AND tx_hash != '' AND order_id != ?",
                (tx_hash, order_id),
            ).fetchone()
            if used is not None:
                return None
            cur = self._conn.execute(
                "UPDATE payments SET credited = 1, status = 'finished', tx_hash = ?, "
                "updated_at = ? WHERE order_id = ? AND credited = 0",
                (tx_hash, int(time.time()), order_id),
            )
            self._conn.commit()
            if cur.rowcount <= 0:
                return None
            return self._conn.execute(
                "SELECT * FROM payments WHERE order_id = ?", (order_id,)
            ).fetchone()

    def expire_stale_crypto_payments(self) -> None:
        """فاکتورهای کریپتوی منقضی‌شده‌ی credit‌نشده را به وضعیت expired می‌برد."""
        now = int(time.time())
        self.execute(
            "UPDATE payments SET status = 'expired', updated_at = ? "
            "WHERE method = 'crypto' AND status = 'waiting' AND credited = 0 "
            "AND expires_at > 0 AND expires_at < ?",
            (now, now),
        )

    def get_payment_by_order(self, order_id: str) -> Optional[sqlite3.Row]:
        return self.query_one("SELECT * FROM payments WHERE order_id = ?", (order_id,))

    def set_payment_status(self, order_id: str, status: str, invoice_id: Optional[str] = None) -> None:
        if invoice_id is not None:
            self.execute(
                "UPDATE payments SET status = ?, invoice_id = ?, updated_at = ? WHERE order_id = ?",
                (status, invoice_id, int(time.time()), order_id),
            )
        else:
            self.execute(
                "UPDATE payments SET status = ?, updated_at = ? WHERE order_id = ?",
                (status, int(time.time()), order_id),
            )

    # ستون‌های مجاز برای به‌روزرسانی (whitelist سخت‌گیرانه؛ ضدتزریق SQL).
    _PAYMENT_UPDATABLE = frozenset({
        "method", "pay_address", "pay_amount", "pay_currency",
        "start_block", "expires_at", "status", "invoice_id", "meta",
    })

    def update_payment(self, order_id: str, **fields: Any) -> None:
        """به‌روزرسانی ایمن ستون‌های یک پرداخت. فقط ستون‌های whitelist‌شده مجازند.

        نام ستون‌ها هرگز از ورودی کاربر ساخته نمی‌شوند؛ فقط از مجموعه‌ی ثابت
        بالا انتخاب می‌شوند تا تزریق SQL غیرممکن باشد.
        """
        cols = [k for k in fields if k in self._PAYMENT_UPDATABLE]
        if not cols:
            return
        set_clause = ", ".join(f"{c} = ?" for c in cols) + ", updated_at = ?"
        params = [fields[c] for c in cols] + [int(time.time()), order_id]
        self.execute(
            f"UPDATE payments SET {set_clause} WHERE order_id = ?", params
        )

    def credit_payment_once(self, order_id: str) -> Optional[sqlite3.Row]:
        """به‌صورت اتمیک پرداخت را credited=1 می‌کند فقط اگر قبلاً نشده باشد.

        اگر برای اولین بار credit شد، ردیف پرداخت را برمی‌گرداند؛ در غیر این صورت None.
        این کار از credit دوباره (تکراری) جلوگیری می‌کند.
        """
        with self._lock:
            cur = self._conn.execute(
                "UPDATE payments SET credited = 1, updated_at = ? WHERE order_id = ? AND credited = 0",
                (int(time.time()), order_id),
            )
            self._conn.commit()
            if cur.rowcount <= 0:
                return None
            return self._conn.execute(
                "SELECT * FROM payments WHERE order_id = ?", (order_id,)
            ).fetchone()

    # ------------------------------------------------------------------ #
    def close(self) -> None:
        with self._lock:
            self._conn.close()
