"""تست واحد منطق خالص (بدون نیاز به پنل یا تلگرام)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bot import xray_config as xc
from bot.inbound import (
    InboundSpec,
    build_client,
    build_inbound_payload,
    build_stream_settings,
    build_sub_link,
)
from bot.proxy import (
    ProxyLocation,
    build_username,
    generate_session,
    normalize_code,
    validate_code,
    validate_session,
)


# ----------------------------- proxy ------------------------------------ #
def test_build_username_full():
    loc = ProxyLocation(area="GB", life=120, session="PzZyPXwOY")
    u = build_username("smart-myrRsidFntpraGNS", loc)
    assert u == "smart-myrRsidFntpraGNS_area-GB_life-120_session-PzZyPXwOY"


def test_build_username_with_state_city():
    loc = ProxyLocation(area="US", state="California", city="NewYork", life=60, session="abcd1234")
    u = build_username("base", loc)
    assert u == "base_area-US_state-California_city-NewYork_life-60_session-abcd1234"


def test_build_username_minimal():
    loc = ProxyLocation(session="zzzz")
    assert build_username("base", loc) == "base_session-zzzz"


def test_life_clamped():
    loc = ProxyLocation(life=99999, session="abcd")
    assert "life-1440" in build_username("b", loc)


def test_generate_session_valid():
    for _ in range(50):
        s = generate_session()
        assert validate_session(s), s


def test_validate_code():
    assert validate_code("US")
    assert validate_code("")
    assert validate_code("New-York")
    assert not validate_code("New York")
    assert not validate_code("a/b")


def test_normalize_code():
    assert normalize_code("  New York ") == "NewYork"


# --------------------------- xray config -------------------------------- #
def test_outbound_and_routing_roundtrip():
    cfg = {"outbounds": [{"tag": "direct", "protocol": "freedom"}], "routing": {"rules": []}}
    ob = xc.build_smartproxy_outbound("out-5", "proxy.smartproxy.net", 3120, "user", "pass")
    xc.upsert_outbound(cfg, ob)
    xc.upsert_routing_rule(cfg, "inbound-8081", "out-5")

    assert xc.get_outbound(cfg, "out-5")["protocol"] == "http"
    assert cfg["outbounds"][-1]["settings"]["servers"][0]["users"][0]["user"] == "user"
    assert cfg["routing"]["rules"][0]["outboundTag"] == "out-5"
    assert cfg["routing"]["rules"][0]["inboundTag"] == ["inbound-8081"]


def test_upsert_replaces_same_tag():
    cfg = {"outbounds": [], "routing": {"rules": []}}
    xc.upsert_outbound(cfg, {"tag": "out-1", "v": 1})
    xc.upsert_outbound(cfg, {"tag": "out-1", "v": 2})
    assert len(cfg["outbounds"]) == 1
    assert cfg["outbounds"][0]["v"] == 2


def test_routing_rule_no_duplicate():
    cfg = {"outbounds": [], "routing": {"rules": []}}
    xc.upsert_routing_rule(cfg, "inbound-1", "out-1")
    xc.upsert_routing_rule(cfg, "inbound-1", "out-2")
    rules = [r for r in cfg["routing"]["rules"] if "inbound-1" in r.get("inboundTag", [])]
    assert len(rules) == 1
    assert rules[0]["outboundTag"] == "out-2"


def test_cleanup_removes_both():
    cfg = {"outbounds": [], "routing": {"rules": []}}
    xc.upsert_outbound(cfg, xc.build_smartproxy_outbound("out-9", "h", 1, "u", "p"))
    xc.upsert_routing_rule(cfg, "inbound-9", "out-9")
    xc.cleanup_config_for(cfg, "inbound-9", "out-9")
    assert xc.get_outbound(cfg, "out-9") is None
    assert all("inbound-9" not in r.get("inboundTag", []) for r in cfg["routing"]["rules"])


# ----------------------------- inbound ---------------------------------- #
def test_stream_settings_xhttp_tls():
    spec = InboundSpec(
        sni="irsp.mahandevs.com", host="irsp.mahandevs.com", path="/get",
        alpn="h2", fingerprint="chrome", sc_max_each_post_bytes=5000000,
        cert_file="/c.pem", key_file="/k.pem",
    )
    ss = build_stream_settings(spec)
    assert ss["network"] == "xhttp"
    assert ss["security"] == "tls"
    assert ss["tlsSettings"]["serverName"] == "irsp.mahandevs.com"
    assert ss["tlsSettings"]["alpn"] == ["h2"]
    assert ss["tlsSettings"]["settings"]["fingerprint"] == "chrome"
    assert ss["tlsSettings"]["certificates"][0]["certificateFile"] == "/c.pem"
    assert ss["xhttpSettings"]["path"] == "/get"
    assert ss["xhttpSettings"]["host"] == "irsp.mahandevs.com"
    assert ss["xhttpSettings"]["scMaxEachPostBytes"] == "5000000"


def test_inbound_payload_serializable():
    spec = InboundSpec("s", "h", "/get", "h2", "chrome", 5000000)
    client = build_client("uuid-1", "user1", "sub1", 5 * 1024**3, 1735689600000)
    payload = build_inbound_payload(remark="r", port=12345, spec=spec, client=client)
    assert payload["protocol"] == "vless"
    assert payload["port"] == 12345
    # settings/streamSettings باید JSON معتبر باشند
    s = json.loads(payload["settings"])
    assert s["clients"][0]["id"] == "uuid-1"
    assert s["clients"][0]["totalGB"] == 5 * 1024**3
    assert s["decryption"] == "none"
    json.loads(payload["streamSettings"])
    json.loads(payload["sniffing"])


def test_sub_link():
    assert build_sub_link("https://h.com:2096", "/sub/", "abc") == "https://h.com:2096/sub/abc"
    assert build_sub_link("https://h.com:2096/", "sub", "abc") == "https://h.com:2096/sub/abc"



# --------------------------- NowPayments IPN --------------------------- #
import hashlib as _hashlib
import hmac as _hmac

from bot.nowpayments import verify_ipn_signature, _sorted_json


def _sign(payload, secret):
    msg = _sorted_json(payload).encode()
    return _hmac.new(secret.encode(), msg, _hashlib.sha512).hexdigest()


def test_ipn_signature_valid():
    payload = {"payment_status": "finished", "order_id": "w2f-1-abc", "price_amount": 10, "pay_currency": "btc"}
    sig = _sign(payload, "secret-key")
    assert verify_ipn_signature(payload, sig, "secret-key") is True


def test_ipn_signature_invalid():
    payload = {"payment_status": "finished", "order_id": "x"}
    sig = _sign(payload, "secret-key")
    # کلید اشتباه
    assert verify_ipn_signature(payload, sig, "wrong-key") is False
    # امضای دستکاری‌شده
    assert verify_ipn_signature(payload, "deadbeef", "secret-key") is False
    # ورودی خالی
    assert verify_ipn_signature(payload, "", "secret-key") is False


def test_ipn_sorted_json_is_compact_and_sorted():
    assert _sorted_json({"b": 1, "a": 2}) == '{"a":2,"b":1}'


# --------------------------- pricing / payer --------------------------- #
import os as _os
import tempfile as _tempfile

from bot.config import Settings
from bot.database import (
    Database as _DB,
    PRODUCT_RESIDENTIAL,
    PRODUCT_V2RAY,
    ROLE_ADMIN,
    ROLE_RESIDENTIAL_RESELLER,
    ROLE_USER,
    ROLE_V2RAY_RESELLER,
)
from bot.service import Service


def _make_service():
    cfg = Settings()
    cfg.price_per_gb = 3.0
    cfg.reseller_price_per_gb = 2.0
    cfg.v2ray_price_per_gb = 1.5
    cfg.v2ray_reseller_price_per_gb = 1.0
    db = _DB(_os.path.join(_tempfile.mkdtemp(), "t.db"))
    svc = Service(cfg, db, None)
    svc.seed_settings()
    return svc, db


def test_price_tiers():
    svc, _ = _make_service()
    assert svc.price_per_gb_for(ROLE_USER, PRODUCT_RESIDENTIAL) == 3.0
    assert svc.price_per_gb_for(ROLE_RESIDENTIAL_RESELLER, PRODUCT_RESIDENTIAL) == 2.0
    assert svc.price_per_gb_for(ROLE_V2RAY_RESELLER, PRODUCT_V2RAY) == 1.0
    assert svc.price_per_gb_for(ROLE_USER, PRODUCT_V2RAY) == 1.5
    assert svc.quote(ROLE_RESIDENTIAL_RESELLER, PRODUCT_RESIDENTIAL, 10) == 20.0


def test_payer_for():
    assert Service._payer_for(ROLE_ADMIN, PRODUCT_RESIDENTIAL) == "admin"
    assert Service._payer_for(ROLE_RESIDENTIAL_RESELLER, PRODUCT_RESIDENTIAL) == "postpaid"
    # رزیدنتال برای کاربر عادی → پرداخت آنلاین
    assert Service._payer_for(ROLE_USER, PRODUCT_RESIDENTIAL) == "nowpayments"
    assert Service._payer_for(ROLE_V2RAY_RESELLER, PRODUCT_RESIDENTIAL) == "nowpayments"
    # V2Ray از کیف پول
    assert Service._payer_for(ROLE_USER, PRODUCT_V2RAY) == "wallet"
    assert Service._payer_for(ROLE_V2RAY_RESELLER, PRODUCT_V2RAY) == "wallet"
    assert Service._payer_for(ROLE_ADMIN, PRODUCT_V2RAY) == "admin"


def test_wallet_atomic_deduct():
    svc, db = _make_service()
    db.add_balance(123, 50.0)
    assert db.try_deduct_balance(123, 30.0) is True
    assert db.get_balance(123) == 20.0
    assert db.try_deduct_balance(123, 30.0) is False  # insufficient
    assert db.get_balance(123) == 20.0


def test_payment_credit_once():
    svc, db = _make_service()
    db.create_payment("ord-1", 7, 25.0, "USD")
    first = db.credit_payment_once("ord-1")
    assert first is not None
    second = db.credit_payment_once("ord-1")
    assert second is None  # idempotent


def test_migration_preserves_and_adds():
    # ساخت دیتابیس و افزودن نقش
    svc, db = _make_service()
    db.set_role(999, ROLE_RESIDENTIAL_RESELLER)
    assert db.get_role(999) == ROLE_RESIDENTIAL_RESELLER



# --------------------------- IPRoyal (رزیدنتال ۲) ---------------------- #
from bot.proxy import IPROYAL_MAX_LIFE_MIN, build_iproyal_password, _iproyal_lifetime


def test_iproyal_password_matches_example():
    # نمونه‌ی رسمی: x1NFN2nK3r2w2umj_country-gb_session-YkaWtTRI_lifetime-168h
    loc = ProxyLocation(area="GB", session="YkaWtTRI", life=168 * 60)
    pw = build_iproyal_password("x1NFN2nK3r2w2umj", loc)
    assert pw == "x1NFN2nK3r2w2umj_country-gb_session-YkaWtTRI_lifetime-168h"


def test_iproyal_password_lowercases_country_and_city():
    loc = ProxyLocation(area="US", city="NewYork", session="abcd1234")
    pw = build_iproyal_password("base", loc)
    assert pw == "base_country-us_city-newyork_session-abcd1234"


def test_iproyal_password_minimal():
    assert build_iproyal_password("base", ProxyLocation(session="zzzz")) == "base_session-zzzz"


def test_iproyal_lifetime_units():
    assert _iproyal_lifetime(60) == "lifetime-1h"
    assert _iproyal_lifetime(90) == "lifetime-90m"
    assert _iproyal_lifetime(1440) == "lifetime-24h"
    # سقف ۷ روز
    assert _iproyal_lifetime(999999) == f"lifetime-{IPROYAL_MAX_LIFE_MIN // 60}h"


def test_iproyal_lifetime_max_is_7_days():
    assert IPROYAL_MAX_LIFE_MIN == 7 * 24 * 60


# --------------------------- residential2 pricing / life --------------- #
from bot.database import PRODUCT_RESIDENTIAL2


def test_residential2_price_tiers():
    svc, _ = _make_service()
    svc.set_setting("residential2_price_per_gb", "12")
    svc.set_setting("residential2_reseller_price_per_gb", "9")
    assert svc.price_per_gb_for(ROLE_USER, PRODUCT_RESIDENTIAL2) == 12.0
    assert svc.price_per_gb_for(ROLE_RESIDENTIAL_RESELLER, PRODUCT_RESIDENTIAL2) == 9.0
    # رزیدنتال ۲ واحدش دلار است (مثل رزیدنتال)
    assert svc.product_currency(PRODUCT_RESIDENTIAL2) == svc.residential_currency


def test_residential2_payer_like_residential():
    assert Service._payer_for(ROLE_ADMIN, PRODUCT_RESIDENTIAL2) == "admin"
    assert Service._payer_for(ROLE_RESIDENTIAL_RESELLER, PRODUCT_RESIDENTIAL2) == "postpaid"
    assert Service._payer_for(ROLE_USER, PRODUCT_RESIDENTIAL2) == "nowpayments"


def test_max_life_and_clamp_per_product():
    assert Service.max_life_for(PRODUCT_RESIDENTIAL) == 1440
    assert Service.max_life_for(PRODUCT_RESIDENTIAL2) == IPROYAL_MAX_LIFE_MIN
    # کلمپ محصول‌محور
    assert Service._clamp_life(99999, PRODUCT_RESIDENTIAL) == 1440
    assert Service._clamp_life(99999, PRODUCT_RESIDENTIAL2) == IPROYAL_MAX_LIFE_MIN
    assert Service._clamp_life(0, PRODUCT_RESIDENTIAL2) == 0


# --------------------------- feature toggles --------------------------- #
from bot.service import (
    S_SHOW_PARTNERSHIP,
    S_SHOW_RESIDENTIAL2,
    S_SHOW_V2RAY,
)


def test_feature_toggle_roundtrip():
    svc, _ = _make_service()
    # مقدار پیش‌فرض فعال است
    assert svc.feature_enabled(S_SHOW_PARTNERSHIP) is True
    # خاموش کردن
    assert svc.toggle_feature(S_SHOW_PARTNERSHIP) is False
    assert svc.feature_enabled(S_SHOW_PARTNERSHIP) is False
    # روشن کردن دوباره
    assert svc.toggle_feature(S_SHOW_PARTNERSHIP) is True
    assert svc.feature_enabled(S_SHOW_PARTNERSHIP) is True


def test_product_enabled_reflects_toggle():
    svc, _ = _make_service()
    assert svc.product_enabled(PRODUCT_RESIDENTIAL2) is True
    svc.toggle_feature(S_SHOW_RESIDENTIAL2)
    assert svc.product_enabled(PRODUCT_RESIDENTIAL2) is False
    svc.toggle_feature(S_SHOW_V2RAY)
    assert svc.product_enabled("v2ray") is False


def test_products_menu_hides_disabled():
    from bot.keyboards import products_menu
    kb = products_menu(residential=True, residential2=False, v2ray=False)
    cbs = [b.callback_data for row in kb.inline_keyboard for b in row]
    assert "buy:residential" in cbs
    assert "buy:residential2" not in cbs
    assert "buy:v2ray" not in cbs


def test_main_menu_hides_partnership():
    # منوی اصلی حالا شیشه‌ای (inline) است؛ مخفی‌سازی باید بلافاصله اعمال شود.
    from bot.keyboards import main_menu
    kb = main_menu(show_partnership=False)
    texts = [b.text for row in kb.inline_keyboard for b in row]
    assert "🤝 همکاری" not in texts
    kb2 = main_menu(show_partnership=True)
    texts2 = [b.text for row in kb2.inline_keyboard for b in row]
    assert "🤝 همکاری" in texts2
    # برای ادمین همیشه نمایش داده می‌شود حتی اگر خاموش باشد
    kb3 = main_menu(is_admin=True, show_partnership=False)
    texts3 = [b.text for row in kb3.inline_keyboard for b in row]
    assert "🤝 همکاری" in texts3
    # همه‌ی دکمه‌ها callback_data دارند (شیشه‌ای)
    assert all(b.callback_data for row in kb2.inline_keyboard for b in row)


# --------------------------- customer bot ------------------------------ #
from customerbot.middlewares import CustomerContextMiddleware
from customerbot.handlers.services import _get_customer_config


class _FakeUser:
    def __init__(self, uid: int) -> None:
        self.id = uid


def _make_config_row(db, owner_tg_id: int = 1001, customer_tg_id: int = 0, product: str = "residential"):
    return db.add_config({
        "owner_tg_id": owner_tg_id, "inbound_id": 1, "port": 10001,
        "client_uuid": "u1", "client_email": "e1", "sub_id": "s1",
        "outbound_tag": "out1", "inbound_tag": "in1", "volume_gb": 10,
        "duration_days": 30, "expiry_ms": 0, "area": "US", "state": "",
        "city": "", "life": 0, "session": "abc123", "created_at": 0,
        "active": 1, "product_type": product, "price": 0, "payer": "self",
        "customer_tg_id": customer_tg_id,
    })


def test_set_config_customer_roundtrip():
    svc, db = _make_service()
    cfg_id = _make_config_row(db, owner_tg_id=1001)
    row = db.get_config(cfg_id)
    assert int(row["customer_tg_id"] or 0) == 0
    db.set_config_customer(cfg_id, 555)
    assert int(db.get_config(cfg_id)["customer_tg_id"]) == 555
    db.set_config_customer(cfg_id, 0)
    assert int(db.get_config(cfg_id)["customer_tg_id"]) == 0


def test_list_configs_by_customer_is_per_order():
    svc, db = _make_service()
    cfg1 = _make_config_row(db, owner_tg_id=1001)
    cfg2 = _make_config_row(db, owner_tg_id=2002)
    cfg3 = _make_config_row(db, owner_tg_id=1001)
    db.set_config_customer(cfg1, 555)
    db.set_config_customer(cfg2, 555)
    db.set_config_customer(cfg3, 999)
    assert {r["id"] for r in db.list_configs_by_customer(555)} == {cfg1, cfg2}
    assert {r["id"] for r in db.list_configs_by_customer(999)} == {cfg3}
    assert db.list_configs_by_customer(123456) == []


def test_get_config_for_customer_enforces_ownership():
    svc, db = _make_service()
    cfg_id = _make_config_row(db, owner_tg_id=1001)
    db.set_config_customer(cfg_id, 555)
    assert db.get_config_for_customer(cfg_id, 555)["id"] == cfg_id
    assert db.get_config_for_customer(cfg_id, 999) is None
    assert db.get_config_for_customer(999999, 555) is None
    # حتی owner هم بدون تعیین‌شدن به‌عنوان مشتری دسترسی ندارد
    assert _get_customer_config(cfg_id, 1001, db) is None


def test_customer_bot_middleware_allows_any_user():
    import asyncio as _asyncio

    mw = CustomerContextMiddleware()
    calls = []

    async def handler(event, data):
        calls.append(data.get("customer_id"))
        return "ok"

    async def _run():
        assert await mw(handler, object(), {"event_from_user": _FakeUser(555)}) == "ok"
        assert await mw(handler, object(), {}) is None

    _asyncio.run(_run())
    assert calls == [555]


def test_config_summary_shows_product_and_customer():
    from bot.utils import config_summary
    svc, db = _make_service()
    cfg_id = _make_config_row(db, owner_tg_id=1001, customer_tg_id=555, product="residential2")
    text = config_summary(db.get_config(cfg_id), show_owner=True)
    assert "رزیدنتال ۲" in text
    assert "555" in text


def test_customer_service_actions_has_loc_and_life_buttons():
    from customerbot.keyboards import service_actions
    kb = service_actions(config_id=42)
    cbs = [b.callback_data for row in kb.inline_keyboard for b in row]
    assert "cs_loc:42" in cbs
    assert "cs_life:42" in cbs
    assert "cs_ip:42" in cbs
