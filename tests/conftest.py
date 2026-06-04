"""Pytest configuration and shared fixtures."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest

if TYPE_CHECKING:
    from custom_components.lidl_plus.api import LidlPlusApiClient


@pytest.fixture
def mock_client() -> LidlPlusApiClient:
    """Return a mocked LidlPlusApiClient."""
    from custom_components.lidl_plus.api import LidlPlusApiClient

    session = AsyncMock()
    client = LidlPlusApiClient(
        refresh_token="test-refresh-token",
        country="DE",
        language="de",
        session=session,
    )
    client._token = "test-access-token"
    client._expires = datetime.now(UTC) + timedelta(hours=1)
    return client


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


def make_coupon(
    *,
    title: str = "Test Coupon",
    is_activated: bool = True,
    is_expired: bool = False,
    is_special: bool = False,
    is_online_shop: bool = False,
    discount_title: str = "",
    discount_description: str = "",
    image: str = "",
    coupon_id: str = "coupon-1",
) -> dict:
    """Create a test coupon dict with sensible defaults."""
    now = datetime.now(UTC)
    end = (
        (now + timedelta(days=30)).isoformat()
        if not is_expired
        else (now - timedelta(days=1)).isoformat()
    )
    return {
        "id": coupon_id,
        "title": title,
        "isActivated": is_activated,
        "specialPromotion": is_special,
        "isSpecial": is_special,
        "isOnlineShop": is_online_shop,
        "endValidityDate": end,
        "image": image,
        "discount": {
            "title": discount_title,
            "description": discount_description,
        },
    }
