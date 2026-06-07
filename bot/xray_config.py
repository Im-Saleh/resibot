"""دستکاری امن کانفیگ Xray برای ساخت اوتباند اختصاصی + روتینگ‌رول هر کاربر.

هر کانفیگ فروخته‌شده یک اوتباند SmartProxy مخصوص خودش دارد (با تگ یکتا) و یک
routing rule که ترافیک اینباند مربوطه را به آن اوتباند می‌فرستد. با این کار هر
نماینده/مشتری IP و لوکیشن مستقل دارد.
"""
from __future__ import annotations

from typing import Any


def build_smartproxy_outbound(
    tag: str,
    host: str,
    port: int,
    username: str,
    password: str,
) -> dict[str, Any]:
    """یک اوتباند از نوع http (SmartProxy) می‌سازد.

    SmartProxy روی پورت 3120 یک HTTP proxy است؛ تمام پارامترهای لوکیشن/سشن
    داخل رشته‌ی username کدگذاری می‌شوند.
    """
    return {
        "tag": tag,
        "protocol": "http",
        "settings": {
            "servers": [
                {
                    "address": host,
                    "port": int(port),
                    "users": [{"user": username, "pass": password}],
                }
            ]
        },
    }


def upsert_outbound(config: dict[str, Any], outbound: dict[str, Any]) -> None:
    """اوتباند را اضافه می‌کند یا اگر تگ تکراری بود جایگزین می‌کند."""
    outbounds = config.setdefault("outbounds", [])
    tag = outbound.get("tag")
    for i, ob in enumerate(outbounds):
        if ob.get("tag") == tag:
            outbounds[i] = outbound
            return
    outbounds.append(outbound)


def remove_outbound(config: dict[str, Any], tag: str) -> bool:
    """اوتباند با تگ مشخص را حذف می‌کند. True اگر چیزی حذف شد."""
    outbounds = config.get("outbounds", [])
    new = [ob for ob in outbounds if ob.get("tag") != tag]
    changed = len(new) != len(outbounds)
    config["outbounds"] = new
    return changed


def get_outbound(config: dict[str, Any], tag: str) -> dict[str, Any] | None:
    for ob in config.get("outbounds", []):
        if ob.get("tag") == tag:
            return ob
    return None


def _routing_rules(config: dict[str, Any]) -> list[dict[str, Any]]:
    routing = config.setdefault("routing", {})
    return routing.setdefault("rules", [])


def upsert_routing_rule(
    config: dict[str, Any],
    inbound_tag: str,
    outbound_tag: str,
) -> None:
    """قانون مسیریابی inbound_tag -> outbound_tag را اضافه/به‌روز می‌کند.

    قانون در ابتدای لیست قرار می‌گیرد تا بر قوانین پیش‌فرض اولویت داشته باشد.
    """
    rules = _routing_rules(config)
    # حذف قانون قبلی همین اینباند (برای جلوگیری از تکرار)
    rules[:] = [
        r for r in rules
        if not (
            r.get("type") == "field"
            and inbound_tag in (r.get("inboundTag") or [])
        )
    ]
    rule = {
        "type": "field",
        "inboundTag": [inbound_tag],
        "outboundTag": outbound_tag,
    }
    rules.insert(0, rule)


def remove_routing_rule_by_inbound(config: dict[str, Any], inbound_tag: str) -> bool:
    rules = _routing_rules(config)
    new = [
        r for r in rules
        if not (
            r.get("type") == "field"
            and inbound_tag in (r.get("inboundTag") or [])
        )
    ]
    changed = len(new) != len(rules)
    config["routing"]["rules"] = new
    return changed


def cleanup_config_for(config: dict[str, Any], inbound_tag: str, outbound_tag: str) -> None:
    """هنگام حذف یک کانفیگ، اوتباند و روتینگ‌رول مربوطه را پاک می‌کند."""
    remove_routing_rule_by_inbound(config, inbound_tag)
    remove_outbound(config, outbound_tag)
