"""Tests for activate_coupons module."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from custom_components.lidl_plus.activate_coupons import activate_coupons
from tests.conftest import make_coupon


@pytest.fixture
def mock_client() -> AsyncMock:
    """Return a mocked LidlPlusApiClient."""
    client = AsyncMock()
    client.get_access_token = AsyncMock(return_value="token")
    return client


class TestActivateCoupons:
    """Tests for activate_coupons()."""

    async def test_activates_inactive_coupons(self, mock_client: AsyncMock) -> None:
        """Test that inactive coupons are activated."""
        c1 = make_coupon(coupon_id="c1", title="Apple", is_activated=False)
        c2 = make_coupon(coupon_id="c2", title="Banana", is_activated=False)
        mock_client.coupons = AsyncMock(
            return_value={"sections": [{"coupons": [c1, c2]}]}
        )
        mock_client.coupon_promotions_v1 = AsyncMock(return_value={"sections": []})
        mock_client.activate_coupon = AsyncMock()

        result = await activate_coupons(mock_client)
        assert result == 2
        assert mock_client.activate_coupon.await_count == 2

    async def test_skips_already_activated(self, mock_client: AsyncMock) -> None:
        """Test that already activated coupons are skipped."""
        c1 = make_coupon(coupon_id="c1", is_activated=True)
        mock_client.coupons = AsyncMock(return_value={"sections": [{"coupons": [c1]}]})
        mock_client.coupon_promotions_v1 = AsyncMock(return_value={"sections": []})

        result = await activate_coupons(mock_client)
        assert result == 0
        mock_client.activate_coupon.assert_not_awaited()

    async def test_skips_expired(self, mock_client: AsyncMock) -> None:
        """Test that expired coupons are skipped."""
        c1 = make_coupon(coupon_id="c1", is_expired=True)
        mock_client.coupons = AsyncMock(return_value={"sections": [{"coupons": [c1]}]})
        mock_client.coupon_promotions_v1 = AsyncMock(return_value={"sections": []})

        result = await activate_coupons(mock_client)
        assert result == 0
        mock_client.activate_coupon.assert_not_awaited()

    async def test_skips_special_promotions(self, mock_client: AsyncMock) -> None:
        """Test that special (in-store only) promotions are skipped."""
        c1 = make_coupon(coupon_id="c1", is_special=True)
        mock_client.coupons = AsyncMock(return_value={"sections": [{"coupons": [c1]}]})
        mock_client.coupon_promotions_v1 = AsyncMock(return_value={"sections": []})

        result = await activate_coupons(mock_client)
        assert result == 0
        mock_client.activate_coupon.assert_not_awaited()

    async def test_activates_v1_promotions(self, mock_client: AsyncMock) -> None:
        """Test that V1 promotions are activated correctly."""
        p1 = make_coupon(coupon_id="p1", title="V1 Promo", is_activated=False)
        mock_client.coupons = AsyncMock(return_value={"sections": [{"coupons": []}]})
        mock_client.coupon_promotions_v1 = AsyncMock(
            return_value={"sections": [{"promotions": [p1]}]}
        )
        mock_client.activate_coupon_promotion_v1 = AsyncMock()

        result = await activate_coupons(mock_client)
        assert result == 1
        mock_client.activate_coupon_promotion_v1.assert_awaited_once_with("p1")

    async def test_mixed_v2_and_v1(self, mock_client: AsyncMock) -> None:
        """Test that both V2 coupons and V1 promotions are activated."""
        c1 = make_coupon(coupon_id="c1", title="V2", is_activated=False)
        p1 = make_coupon(coupon_id="p1", title="V1", is_activated=False)
        mock_client.coupons = AsyncMock(return_value={"sections": [{"coupons": [c1]}]})
        mock_client.coupon_promotions_v1 = AsyncMock(
            return_value={"sections": [{"promotions": [p1]}]}
        )
        mock_client.activate_coupon = AsyncMock()
        mock_client.activate_coupon_promotion_v1 = AsyncMock()

        result = await activate_coupons(mock_client)
        assert result == 2
