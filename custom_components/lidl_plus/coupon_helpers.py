"""Shared coupon constants and helpers used by both HA integration and CLI."""

from __future__ import annotations

from datetime import UTC, datetime

_SKIP_TITLES = {"Aktionsrabatt", "Wiedereröffnung"}


def is_expired(coupon: dict) -> bool:
    """Check if a coupon has expired or is not yet valid."""
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
    return bool(start and datetime.fromisoformat(start) > now)


_INSTORE_ONLY_TAGS = {"Meal Deal"}


def is_special_promotion(coupon: dict) -> bool:
    """Check if a coupon is an in-store-only special (e.g. Meal Deal)."""
    special = coupon.get("specialPromotion", {})
    tag = special.get("tag", "") if isinstance(special, dict) else ""
    return tag in _INSTORE_ONLY_TAGS


def should_show(coupon: dict) -> bool:
    """Check if a coupon should be shown (not online-shop, not skipped title)."""
    return not coupon.get("isOnlineShop") and coupon.get("title") not in _SKIP_TITLES


def coupon_label(coupon: dict) -> str:
    """Build a human-readable label for a coupon."""
    discount = coupon.get("discount", {}).get("title", "")
    desc = coupon.get("discount", {}).get("description", "")
    title = coupon["title"]
    label = f"{discount} {title}".strip() if discount else title
    return f"{label} ({desc})" if desc else label
