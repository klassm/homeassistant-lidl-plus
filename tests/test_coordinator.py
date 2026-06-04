"""Tests for the LidlPlusCoordinator."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.lidl_plus.coordinator import LidlPlusCoordinator


def _make_coupon(
    title: str = "Test",
    is_activated: bool = True,
    end: str | None = None,
    is_online_shop: bool = False,
    is_special: bool = False,
) -> dict:
    if end is None:
        end = (datetime.now(UTC) + timedelta(days=30)).isoformat()
    return {
        "title": title,
        "isActivated": is_activated,
        "endValidityDate": end,
        "isOnlineShop": is_online_shop,
        "specialPromotion": is_special,
        "image": "https://example.com/img.png",
    }


@pytest.fixture
def mock_hass() -> MagicMock:
    hass = MagicMock()
    hass.config_entries = MagicMock()
    return hass


@pytest.fixture
def mock_entry() -> MagicMock:
    entry = MagicMock()
    entry.entry_id = "test"
    entry.data = {"token": "test-refresh-token", "country": "DE", "language": "de"}
    return entry


@pytest.fixture
def mock_client() -> AsyncMock:
    client = AsyncMock()
    client.refresh_token = "test-refresh-token"
    client.get_access_token = AsyncMock(return_value="access-token")
    return client


@pytest.fixture
def coordinator(
    mock_hass: MagicMock, mock_client: AsyncMock, mock_entry: MagicMock
) -> LidlPlusCoordinator:
    return LidlPlusCoordinator(mock_hass, mock_client, mock_entry)


class TestAsyncUpdateData:
    """Tests for _async_update_data()."""

    async def test_basic_update(
        self, coordinator: LidlPlusCoordinator, mock_client: AsyncMock
    ) -> None:
        coupon = _make_coupon(title="Apple 20%", is_activated=True)
        mock_client.coupons = AsyncMock(
            return_value={"sections": [{"coupons": [coupon]}]}
        )
        mock_client.coupon_promotions_v1 = AsyncMock(return_value={"sections": []})

        with patch(
            "custom_components.lidl_plus.coordinator.activate_coupons",
            new_callable=AsyncMock,
            return_value=0,
        ):
            result = await coordinator._async_update_data()

        assert result["total"] == 1
        assert result["valid"] == 1
        assert result["active"] == 1
        assert result["activated_this_cycle"] == 0
        assert len(result["coupons"]) == 1

    async def test_expired_coupons_excluded(
        self, coordinator: LidlPlusCoordinator, mock_client: AsyncMock
    ) -> None:
        expired = _make_coupon(
            title="Expired",
            is_activated=True,
            end=(datetime.now(UTC) - timedelta(days=1)).isoformat(),
        )
        valid = _make_coupon(title="Valid", is_activated=True)
        mock_client.coupons = AsyncMock(
            return_value={"sections": [{"coupons": [expired, valid]}]}
        )
        mock_client.coupon_promotions_v1 = AsyncMock(return_value={"sections": []})

        with patch(
            "custom_components.lidl_plus.coordinator.activate_coupons",
            new_callable=AsyncMock,
            return_value=0,
        ):
            result = await coordinator._async_update_data()

        assert result["total"] == 2
        assert result["active"] == 2
        assert result["valid"] == 1

    async def test_inactive_coupons_excluded_from_valid(
        self, coordinator: LidlPlusCoordinator, mock_client: AsyncMock
    ) -> None:
        inactive = _make_coupon(title="Inactive", is_activated=False)
        mock_client.coupons = AsyncMock(
            return_value={"sections": [{"coupons": [inactive]}]}
        )
        mock_client.coupon_promotions_v1 = AsyncMock(return_value={"sections": []})

        with patch(
            "custom_components.lidl_plus.coordinator.activate_coupons",
            new_callable=AsyncMock,
            return_value=0,
        ):
            result = await coordinator._async_update_data()

        assert result["active"] == 0
        assert result["valid"] == 0

    async def test_online_shop_hidden(
        self, coordinator: LidlPlusCoordinator, mock_client: AsyncMock
    ) -> None:
        online = _make_coupon(title="Online", is_activated=True, is_online_shop=True)
        mock_client.coupons = AsyncMock(
            return_value={"sections": [{"coupons": [online]}]}
        )
        mock_client.coupon_promotions_v1 = AsyncMock(return_value={"sections": []})

        with patch(
            "custom_components.lidl_plus.coordinator.activate_coupons",
            new_callable=AsyncMock,
            return_value=0,
        ):
            result = await coordinator._async_update_data()

        assert result["total"] == 1
        assert result["in_store"] == 0

    async def test_v1_coupons_merged(
        self, coordinator: LidlPlusCoordinator, mock_client: AsyncMock
    ) -> None:
        v2_coupon = _make_coupon(title="V2", is_activated=True)
        v1_coupon = _make_coupon(title="V1", is_activated=True)
        mock_client.coupons = AsyncMock(
            return_value={"sections": [{"coupons": [v2_coupon]}]}
        )
        mock_client.coupon_promotions_v1 = AsyncMock(
            return_value={"sections": [{"promotions": [v1_coupon]}]}
        )

        with patch(
            "custom_components.lidl_plus.coordinator.activate_coupons",
            new_callable=AsyncMock,
            return_value=0,
        ):
            result = await coordinator._async_update_data()

        assert result["total"] == 2
        assert result["valid"] == 2

    async def test_auth_failure_raises_update_failed(
        self, coordinator: LidlPlusCoordinator, mock_client: AsyncMock
    ) -> None:
        from homeassistant.helpers.update_coordinator import UpdateFailed

        mock_client.get_access_token = AsyncMock(side_effect=Exception("auth error"))

        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()

    async def test_updates_refresh_token(
        self,
        coordinator: LidlPlusCoordinator,
        mock_client: AsyncMock,
        mock_hass: MagicMock,
    ) -> None:
        mock_client.refresh_token = "new-token"
        mock_client.coupons = AsyncMock(return_value={"sections": []})
        mock_client.coupon_promotions_v1 = AsyncMock(return_value={"sections": []})

        with patch(
            "custom_components.lidl_plus.coordinator.activate_coupons",
            new_callable=AsyncMock,
            return_value=0,
        ):
            await coordinator._async_update_data()

        mock_hass.config_entries.async_update_entry.assert_called_once()
