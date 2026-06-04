"""Pytest configuration and shared fixtures."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest

if TYPE_CHECKING:
    from custom_components.lidl_plus.api import LidlPlusApiClient


@dataclass
class CouponSpec:
    """Specification for building a test coupon dict."""

    title: str = "Test Coupon"
    is_activated: bool = True
    is_expired: bool = False
    is_special: bool = False
    is_online_shop: bool = False
    image: str = ""
    coupon_id: str = "coupon-1"
    discount: dict = field(default_factory=lambda: {"title": "", "description": ""})


@pytest.fixture
def mock_client() -> LidlPlusApiClient:
    """Return a LidlPlusApiClient with a mocked session."""
    from custom_components.lidl_plus.api import LidlPlusApiClient

    session = AsyncMock()
    return LidlPlusApiClient(
        refresh_token="test-refresh-token",
        country="DE",
        language="de",
        session=session,
    )


@pytest.fixture
def mock_hass() -> MagicMock:
    """Return a mocked HomeAssistant instance."""
    hass = MagicMock()
    hass.config_entries = MagicMock()
    hass.data = {}
    return hass


@pytest.fixture
def mock_entry() -> MagicMock:
    """Return a mocked ConfigEntry."""
    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    entry.title = "Lidl Test"
    entry.data = {"token": "test-refresh-token", "country": "DE", "language": "de"}
    return entry


def make_coupon(spec: CouponSpec | None = None, **overrides: object) -> dict:
    """Create a test coupon dict from a CouponSpec."""
    if spec is None:
        spec = CouponSpec()
    for key, value in overrides.items():
        setattr(spec, key, value)
    now = datetime.now(UTC)
    end = (
        (now + timedelta(days=30)).isoformat()
        if not spec.is_expired
        else (now - timedelta(days=1)).isoformat()
    )
    return {
        "id": spec.coupon_id,
        "title": spec.title,
        "isActivated": spec.is_activated,
        "specialPromotion": spec.is_special,
        "isSpecial": spec.is_special,
        "isOnlineShop": spec.is_online_shop,
        "endValidityDate": end,
        "image": spec.image,
        "discount": spec.discount,
    }
