"""Shared coupon constants and helpers used by both HA integration and CLI."""

from __future__ import annotations

from datetime import UTC, datetime

_SKIP_TITLES = {"Aktionsrabatt", "Wiedereröffnung"}


def is_expired(coupon: dict) -> bool:
    now = datetime.now(UTC)
    end = coupon.get("endValidityDate")
    if end and datetime.fromisoformat(end) < now:
        return True
    start = coupon.get("startValidityDate")
    if start and datetime.fromisoformat(start) > now:
        return True
    validity = coupon.get("validity", {})
    end = validity.get("end")
    if end and datetime.fromisoformat(end) < now:
        return True
    start = validity.get("start")
    if start and datetime.fromisoformat(start) > now:
        return True
    return False


def is_special_promotion(coupon: dict) -> bool:
    return bool(coupon.get("specialPromotion")) or coupon.get("isSpecial", False)


def should_show(coupon: dict) -> bool:
    return not coupon.get("isOnlineShop") and coupon.get("title") not in _SKIP_TITLES


def coupon_label(coupon: dict) -> str:
    discount = coupon.get("discount", {}).get("title", "")
    desc = coupon.get("discount", {}).get("description", "")
    title = coupon["title"]
    label = f"{discount} {title}".strip() if discount else title
    return f"{label} ({desc})" if desc else label
