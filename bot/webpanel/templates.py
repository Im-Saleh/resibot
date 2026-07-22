"""قالب‌های HTML پنل وب با ظاهر شیشه‌ای (glassmorphism) — بدون وابستگی بیرونی.

همه‌ی CSS و JS به‌صورت درون‌خطی هستند تا پنل کاملاً خودکفا باشد و نیازی به CDN
نداشته باشد (که هم امنیت بهتر است هم بدون اینترنت بیرونی کار می‌کند).
"""
from __future__ import annotations

from html import escape

_CSS = """
:root{
  --bg1:#0f0c29; --bg2:#302b63; --bg3:#24243e;
  --glass:rgba(255,255,255,.08); --glass-strong:rgba(255,255,255,.14);
  --border:rgba(255,255,255,.18); --text:#eef1ff; --muted:#a9b0d6;
  --accent:#7b5cff; --accent2:#00d2ff; --ok:#2fe6a0; --warn:#ffbf47; --bad:#ff6b81;
}
*{box-sizing:border-box}
html,body{margin:0;padding:0}
body{
  font-family:'Vazirmatn',Tahoma,system-ui,-apple-system,'Segoe UI',sans-serif;
  color:var(--text); min-height:100vh; direction:rtl;
  background:linear-gradient(135deg,var(--bg1),var(--bg2),var(--bg3));
  background-attachment:fixed;
  overflow-x:hidden;
}
body::before{
  content:"";position:fixed;inset:0;z-index:-1;
  background:
    radial-gradient(40vw 40vw at 80% 10%, rgba(123,92,255,.35), transparent 60%),
    radial-gradient(35vw 35vw at 10% 90%, rgba(0,210,255,.30), transparent 60%);
  filter:blur(10px);
}
a{color:inherit;text-decoration:none}
.wrap{display:flex;min-height:100vh}
.side{
  width:270px;padding:22px 16px;backdrop-filter:blur(18px);
  background:var(--glass);border-left:1px solid var(--border);
  position:sticky;top:0;height:100vh;display:flex;flex-direction:column;gap:8px;
}
.brand{display:flex;align-items:center;gap:10px;margin-bottom:18px;padding:6px}
.brand .logo{width:40px;height:40px;border-radius:12px;
  background:linear-gradient(135deg,var(--accent),var(--accent2));
  display:flex;align-items:center;justify-content:center;font-weight:800;font-size:18px;
  box-shadow:0 8px 24px rgba(123,92,255,.5)}
.brand b{font-size:17px;letter-spacing:.3px}
.brand span{display:block;font-size:11px;color:var(--muted)}
.nav a{
  display:flex;align-items:center;gap:12px;padding:12px 14px;border-radius:14px;
  color:var(--muted);font-weight:600;transition:.2s;border:1px solid transparent;
}
.nav a:hover{background:var(--glass-strong);color:var(--text)}
.nav a.active{
  background:linear-gradient(135deg,rgba(123,92,255,.35),rgba(0,210,255,.18));
  color:#fff;border-color:var(--border);
  box-shadow:0 6px 18px rgba(0,0,0,.25)
}
.nav a .ic{font-size:18px}
.side .foot{margin-top:auto;font-size:11px;color:var(--muted);text-align:center}
.main{flex:1;padding:28px 32px;max-width:1200px;margin:0 auto;width:100%}
.top{display:flex;align-items:center;justify-content:space-between;margin-bottom:24px;flex-wrap:wrap;gap:12px}
.top h1{margin:0;font-size:24px}
.top .who{font-size:13px;color:var(--muted)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:18px;margin-bottom:26px}
.card{
  background:var(--glass);backdrop-filter:blur(18px);border:1px solid var(--border);
  border-radius:20px;padding:20px;box-shadow:0 8px 30px rgba(0,0,0,.22);
}
.stat .k{font-size:13px;color:var(--muted);margin-bottom:8px}
.stat .v{font-size:30px;font-weight:800;
  background:linear-gradient(135deg,#fff,var(--accent2));-webkit-background-clip:text;background-clip:text;color:transparent}
.panel{background:var(--glass);backdrop-filter:blur(18px);border:1px solid var(--border);
  border-radius:22px;padding:24px;margin-bottom:22px;box-shadow:0 10px 34px rgba(0,0,0,.22)}
.panel h2{margin:0 0 16px;font-size:19px;display:flex;gap:10px;align-items:center}
table{width:100%;border-collapse:collapse}
th,td{padding:12px 10px;text-align:right;border-bottom:1px solid rgba(255,255,255,.08);font-size:14px}
th{color:var(--muted);font-weight:700}
tr:hover td{background:rgba(255,255,255,.03)}
.badge{display:inline-block;padding:4px 10px;border-radius:999px;font-size:12px;font-weight:700}
.badge.ok{background:rgba(47,230,160,.16);color:var(--ok)}
.badge.off{background:rgba(255,107,129,.16);color:var(--bad)}
.badge.warn{background:rgba(255,191,71,.16);color:var(--warn)}
.btn{
  display:inline-flex;align-items:center;gap:8px;cursor:pointer;border:1px solid var(--border);
  background:var(--glass-strong);color:var(--text);padding:11px 18px;border-radius:14px;
  font-weight:700;font-size:14px;font-family:inherit;transition:.2s;backdrop-filter:blur(8px);
}
.btn:hover{transform:translateY(-1px);background:rgba(255,255,255,.2);box-shadow:0 8px 22px rgba(0,0,0,.28)}
.btn.primary{background:linear-gradient(135deg,var(--accent),var(--accent2));border-color:transparent;color:#fff}
.btn.danger{background:rgba(255,107,129,.2);border-color:rgba(255,107,129,.4);color:#ffd0d8}
.btn.sm{padding:7px 12px;font-size:12.5px;border-radius:11px}
.row{display:flex;gap:10px;flex-wrap:wrap;align-items:center}
label{display:block;margin:0 0 6px;font-size:13px;color:var(--muted);font-weight:600}
input,textarea,select{
  width:100%;background:rgba(0,0,0,.22);border:1px solid var(--border);color:var(--text);
  border-radius:14px;padding:12px 14px;font-size:14px;font-family:inherit;margin-bottom:16px;outline:none;transition:.2s
}
input:focus,textarea:focus,select:focus{border-color:var(--accent2);box-shadow:0 0 0 3px rgba(0,210,255,.15)}
textarea{min-height:150px;resize:vertical;line-height:1.9}
.hint{font-size:12px;color:var(--muted);margin:-8px 0 16px}
.flash{padding:12px 16px;border-radius:14px;margin-bottom:18px;font-weight:600}
.flash.err{background:rgba(255,107,129,.14);border:1px solid rgba(255,107,129,.35);color:#ffd0d8}
.flash.ok{background:rgba(47,230,160,.14);border:1px solid rgba(47,230,160,.35);color:#b6ffe0}
.plist{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:18px}
.pcard{background:var(--glass);border:1px solid var(--border);border-radius:20px;padding:18px;backdrop-filter:blur(14px);transition:.2s}
.pcard:hover{transform:translateY(-2px);box-shadow:0 12px 30px rgba(0,0,0,.3)}
.pcard h3{margin:0 0 4px;font-size:16px}
.pcard .sub{font-size:12.5px;color:var(--muted);margin-bottom:12px;min-height:32px}
.pcard .price{font-size:20px;font-weight:800;color:var(--accent2)}
.pcard .meta{display:flex;justify-content:space-between;align-items:center;margin:12px 0}
/* login */
.login-wrap{min-height:100vh;display:flex;align-items:center;justify-content:center;padding:20px}
.login{width:100%;max-width:400px}
.login .panel{padding:34px 30px;text-align:center}
.login .logo-big{width:70px;height:70px;border-radius:20px;margin:0 auto 16px;
  background:linear-gradient(135deg,var(--accent),var(--accent2));display:flex;align-items:center;justify-content:center;
  font-size:30px;font-weight:800;box-shadow:0 12px 34px rgba(123,92,255,.55)}
.login h1{font-size:22px;margin:0 0 4px}
.login p{color:var(--muted);font-size:13px;margin:0 0 22px}
.login input{text-align:center}
@media(max-width:820px){
  .wrap{flex-direction:column}
  .side{width:100%;height:auto;position:relative;flex-direction:row;flex-wrap:wrap;gap:6px}
  .side .foot{display:none}
  .nav{display:flex;flex-wrap:wrap;gap:6px}
  .nav a{padding:9px 12px}
  .main{padding:20px 16px}
}
"""

_NAV = [
    ("dashboard", "🏠", "داشبورد", "/panel"),
    ("products", "🤖", "محصولات دیجیتال", "/panel/products"),
    ("prices", "💵", "قیمت‌ها", "/panel/prices"),
    ("audit", "🛡", "لاگ امنیتی", "/panel/audit"),
]


def _head(title: str) -> str:
    return (
        "<!doctype html><html lang='fa' dir='rtl'><head>"
        "<meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<meta name='robots' content='noindex,nofollow'>"
        f"<title>{escape(title)} — ResiBot Panel</title>"
        f"<style>{_CSS}</style></head><body>"
    )


def render_page(title: str, body: str, *, active: str, brand: str = "ResiBot") -> str:
    nav = "".join(
        f"<a class='{'active' if key == active else ''}' href='{href}'>"
        f"<span class='ic'>{ic}</span><span>{escape(label)}</span></a>"
        for key, ic, label, href in _NAV
    )
    return (
        _head(title)
        + "<div class='wrap'>"
        + "<aside class='side'>"
        + f"<div class='brand'><div class='logo'>R</div><div><b>{escape(brand)}</b>"
          "<span>پنل مدیریت</span></div></div>"
        + f"<nav class='nav'>{nav}</nav>"
        + "<a class='btn danger sm' href='/panel/logout' style='justify-content:center'>🚪 خروج</a>"
        + "<div class='foot'>ResiBot Secure Panel</div>"
        + "</aside>"
        + f"<main class='main'>{body}</main>"
        + "</div></body></html>"
    )


def login_page(*, csrf: str, error: str = "", locked: int = 0) -> str:
    flash = ""
    if error:
        flash = f"<div class='flash err'>{escape(error)}</div>"
    if locked > 0:
        flash = (
            f"<div class='flash err'>به دلیل تلاش‌های ناموفق زیاد، ورود موقتاً قفل شده است. "
            f"حدود {locked} ثانیه دیگر دوباره امتحان کنید.</div>"
        )
    disabled = "disabled" if locked > 0 else ""
    return (
        _head("ورود")
        + "<div class='login-wrap'><div class='login'><div class='panel'>"
        + "<div class='logo-big'>R</div>"
        + "<h1>پنل مدیریت ResiBot</h1>"
        + "<p>برای ادامه، رمز عبور مدیریت را وارد کنید</p>"
        + flash
        + "<form method='post' action='/panel/login'>"
        + f"<input type='hidden' name='csrf' value='{escape(csrf)}'>"
        + f"<input type='password' name='password' placeholder='رمز عبور' autofocus {disabled}>"
        + f"<button class='btn primary' style='width:100%;justify-content:center' {disabled}>ورود امن 🔐</button>"
        + "</form>"
        + "</div></div></div></body></html>"
    )


def _stat(k: str, v: str) -> str:
    return f"<div class='card stat'><div class='k'>{escape(k)}</div><div class='v'>{escape(str(v))}</div></div>"


def dashboard_page(stats: dict) -> str:
    cards = "".join([
        _stat("کاربران", stats.get("users", 0)),
        _stat("سرویس‌های فعال", stats.get("configs", 0)),
        _stat("محصولات دیجیتال", stats.get("digital_products", 0)),
        _stat("موجودی آماده (کل)", stats.get("stock", 0)),
        _stat("پرداخت‌های موفق", stats.get("paid", 0)),
        _stat("کاربران مسدود", stats.get("banned", 0)),
    ])
    rev_rows = "".join(
        f"<tr><td>{escape(c['currency'])}</td><td>{c['sum']:g}</td><td>{c['count']}</td></tr>"
        for c in stats.get("revenue", [])
    ) or "<tr><td colspan='3' style='color:var(--muted)'>هنوز پرداختی ثبت نشده</td></tr>"
    body = (
        "<div class='top'><h1>🏠 داشبورد</h1>"
        f"<div class='who'>خوش آمدید — {escape(stats.get('brand',''))}</div></div>"
        f"<div class='grid'>{cards}</div>"
        "<div class='panel'><h2>💰 درآمد به تفکیک ارز</h2>"
        "<table><thead><tr><th>ارز</th><th>مجموع</th><th>تعداد</th></tr></thead>"
        f"<tbody>{rev_rows}</tbody></table></div>"
    )
    return render_page("داشبورد", body, active="dashboard", brand=stats.get("brand", "ResiBot"))


def products_page(products: list, stock: dict, currency: str, toman: float, *, flash: str = "") -> str:
    cards = []
    for p in products:
        pid = int(p["id"])
        avail = int(stock.get(pid, 0))
        state = "<span class='badge ok'>فعال</span>" if int(p["active"]) else "<span class='badge off'>غیرفعال</span>"
        stock_badge = (
            f"<span class='badge ok'>انبار: {avail}</span>" if avail > 0
            else "<span class='badge warn'>ناموجود</span>"
        )
        price_toman = round(float(p["price"]) * toman, 0)
        cards.append(
            "<div class='pcard'>"
            f"<h3>{escape(p['title'])}</h3>"
            f"<div class='sub'>{escape(p['subtitle'] or '')}</div>"
            f"<div class='meta'><span class='price'>{float(p['price']):g} $</span>"
            f"<span style='color:var(--muted);font-size:12px'>≈ {price_toman:g} {escape(currency)}</span></div>"
            f"<div class='row'>{state} {stock_badge}</div>"
            f"<div class='row' style='margin-top:14px'>"
            f"<a class='btn sm primary' href='/panel/products/{pid}'>✏️ ویرایش</a>"
            f"<a class='btn sm' href='/panel/products/{pid}#stock'>📦 انبار</a>"
            "</div></div>"
        )
    flash_html = f"<div class='flash ok'>{escape(flash)}</div>" if flash else ""
    body = (
        "<div class='top'><h1>🤖 محصولات دیجیتال</h1>"
        "<a class='btn primary' href='/panel/products/new'>➕ محصول جدید</a></div>"
        + flash_html
        + (f"<div class='plist'>{''.join(cards)}</div>" if cards
           else "<div class='panel'>هنوز محصولی ثبت نشده. یک محصول جدید بسازید.</div>")
    )
    return render_page("محصولات", body, active="products")


def product_form_page(
    *, csrf: str, product=None, stock_items=None, currency: str = "", flash: str = "", is_new: bool = False,
) -> str:
    stock_items = stock_items or []
    title = "➕ محصول جدید" if is_new else "✏️ ویرایش محصول"
    action = "/panel/products/new" if is_new else f"/panel/products/{int(product['id'])}"
    v = {
        "slug": product["slug"] if product else "",
        "title": product["title"] if product else "",
        "subtitle": product["subtitle"] if product else "",
        "description": product["description"] if product else "",
        "price": f"{float(product['price']):g}" if product else "",
        "duration_days": str(int(product["duration_days"])) if product else "0",
        "active": bool(int(product["active"])) if product else False,
    }
    flash_html = f"<div class='flash ok'>{escape(flash)}</div>" if flash else ""
    checked = "checked" if v["active"] else ""
    slug_field = (
        f"<label>شناسه یکتا (slug)</label><input name='slug' value='{escape(v['slug'])}' "
        "placeholder='مثلاً chatgpt_1m' pattern='[a-z0-9][a-z0-9_-]{1,40}' required>"
        "<div class='hint'>فقط حروف کوچک انگلیسی، عدد، «-» و «_».</div>"
        if is_new else
        f"<label>شناسه یکتا (slug)</label><input value='{escape(v['slug'])}' disabled>"
    )
    def _stock_badge(status: str) -> str:
        if status == "available":
            return "<span class='badge ok'>آماده</span>"
        return "<span class='badge off'>فروخته‌شده</span>"

    stock_rows = "".join(
        f"<tr><td>#{r['id']}</td><td>{_stock_badge(r['status'])}</td>"
        f"<td style='font-family:monospace'>{escape(r['payload'][:60])}</td></tr>"
        for r in stock_items
    ) or "<tr><td colspan='3' style='color:var(--muted)'>انبار خالی است</td></tr>"

    stock_section = "" if is_new else (
        "<div class='panel' id='stock'><h2>📦 مدیریت انبار</h2>"
        f"<form method='post' action='/panel/products/{int(product['id'])}/stock'>"
        f"<input type='hidden' name='csrf' value='{escape(csrf)}'>"
        "<label>افزودن اقلام (هر خط یک اکانت/کد)</label>"
        "<textarea name='items' placeholder='email:pass&#10;code-1234&#10;...'></textarea>"
        "<button class='btn primary'>➕ افزودن به انبار</button></form>"
        "<table style='margin-top:18px'><thead><tr><th>#</th><th>وضعیت</th><th>محتوا</th></tr></thead>"
        f"<tbody>{stock_rows}</tbody></table></div>"
    )
    delete_section = "" if is_new else (
        "<div class='panel'><h2>🗑 حذف محصول</h2>"
        "<p class='hint'>حذف محصول همه‌ی موجودی انبارش را هم پاک می‌کند و برگشت‌ناپذیر است.</p>"
        f"<form method='post' action='/panel/products/{int(product['id'])}/delete' "
        "onsubmit=\"return confirm('از حذف کامل این محصول مطمئنید؟')\">"
        f"<input type='hidden' name='csrf' value='{escape(csrf)}'>"
        "<button class='btn danger'>حذف کامل محصول</button></form></div>"
    )

    body = (
        f"<div class='top'><h1>{title}</h1>"
        "<a class='btn' href='/panel/products'>⬅️ بازگشت</a></div>"
        + flash_html
        + "<div class='panel'><h2>مشخصات محصول</h2>"
        + f"<form method='post' action='{action}'>"
        + f"<input type='hidden' name='csrf' value='{escape(csrf)}'>"
        + slug_field
        + f"<label>عنوان</label><input name='title' value='{escape(v['title'])}' required>"
        + f"<label>زیرعنوان</label><input name='subtitle' value='{escape(v['subtitle'])}'>"
        + f"<label>متن فروش (توضیحات)</label><textarea name='description'>{escape(v['description'])}</textarea>"
        + "<div class='hint'>می‌توانید از تگ‌های ساده مثل &lt;b&gt; استفاده کنید (در تلگرام نمایش داده می‌شود).</div>"
        + "<div class='row'>"
        + f"<div style='flex:1'><label>قیمت (دلار/USDT)</label><input name='price' value='{escape(v['price'])}' required></div>"
        + f"<div style='flex:1'><label>مدت اعتبار (روز)</label><input name='duration_days' value='{escape(v['duration_days'])}'></div>"
        + "</div>"
        + f"<label style='display:flex;gap:10px;align-items:center;cursor:pointer'>"
          f"<input type='checkbox' name='active' style='width:auto;margin:0' {checked}> فعال باشد (برای مشتریان نمایش داده شود)</label>"
        + "<div style='margin-top:10px'><button class='btn primary'>💾 ذخیره</button></div>"
        + "</form></div>"
        + stock_section
        + delete_section
    )
    return render_page(title, body, active="products")


def prices_page(*, csrf: str, values: dict, currency: str, flash: str = "") -> str:
    flash_html = f"<div class='flash ok'>{escape(flash)}</div>" if flash else ""

    def f(name: str, label: str, val) -> str:
        return (f"<div style='flex:1;min-width:200px'><label>{escape(label)}</label>"
                f"<input name='{name}' value='{escape(str(val))}'></div>")

    body = (
        "<div class='top'><h1>💵 قیمت‌ها و نرخ‌ها</h1></div>"
        + flash_html
        + "<div class='panel'><h2>قیمت‌های پایه</h2>"
        + f"<form method='post' action='/panel/prices'>"
        + f"<input type='hidden' name='csrf' value='{escape(csrf)}'>"
        + "<div class='row'>"
        + f(values.get("_k_price", "price_per_gb"), "رزیدنتال عادی (هر گیگ، $)", values.get("price", ""))
        + f(values.get("_k_res", "reseller_price_per_gb"), "رزیدنتال همکار (هر گیگ، $)", values.get("reseller", ""))
        + "</div><div class='row'>"
        + f("v2ray_plan_price", "پلن V2Ray عادی ($)", values.get("v2ray_plan", ""))
        + f("v2ray_plan_reseller_price", "پلن V2Ray همکار ($)", values.get("v2ray_plan_res", ""))
        + "</div><div class='row'>"
        + f("toman_per_usd", f"نرخ هر دلار به {currency}", values.get("toman", ""))
        + f("min_topup", f"حداقل شارژ کیف پول ({currency})", values.get("min_topup", ""))
        + "</div>"
        + "<div style='margin-top:8px'><button class='btn primary'>💾 ذخیره تغییرات</button></div>"
        + "</form></div>"
        + "<p class='hint'>این مقادیر بلافاصله در ربات هم اعمال می‌شوند (همان جدول تنظیمات).</p>"
    )
    return render_page("قیمت‌ها", body, active="prices")


def audit_page(rows: list) -> str:
    import datetime as _dt
    trs = []
    for r in rows:
        try:
            ts = _dt.datetime.fromtimestamp(int(r["ts"])).strftime("%Y-%m-%d %H:%M:%S")
        except (ValueError, OverflowError, OSError):
            ts = "—"
        trs.append(
            f"<tr><td style='white-space:nowrap'>{escape(ts)}</td>"
            f"<td>{escape(r['action'])}</td>"
            f"<td>{escape(r['actor'] or '—')}</td>"
            f"<td style='font-family:monospace'>{escape(r['ip'] or '—')}</td>"
            f"<td>{escape((r['detail'] or '')[:80])}</td></tr>"
        )
    empty = "<tr><td colspan=5 style='color:var(--muted)'>لاگی ثبت نشده</td></tr>"
    tbody = "".join(trs) or empty
    body = (
        "<div class='top'><h1>🛡 لاگ امنیتی و رخدادها</h1></div>"
        "<div class='panel'>"
        "<table><thead><tr><th>زمان</th><th>رخداد</th><th>کاربر</th><th>IP</th><th>جزئیات</th></tr></thead>"
        f"<tbody>{tbody}</tbody>"
        "</table></div>"
    )
    return render_page("لاگ امنیتی", body, active="audit")
