"""Tests for activate_coupons module."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from custom_components.lidl_plus.activate_coupons import activate_coupons


def _make_coupon(
    coupon_id: str = "c1",
    title: str = "Test",
    is_activated: bool = False,
    is_expired: bool = False,
    is_special: bool = False,
) -> dict:
    end = (
        (datetime.now(UTC) - timedelta(days=1)).isoformat()
        if is_expired
        else (datetime.now(UTC) + timedelta(days=30)).isoformat()
    )
    return {
        "id": coupon_id,
        "title": title,
        "isActivated": is_activated,
        "endValidityDate": end,
        "specialPromotion": is_special,
        "discount": {"title": "", "description": ""},
    }


@pytest.fixture
def mock_client() -> AsyncMock:
    client = AsyncMock()
    client.get_access_token = AsyncMock(return_value="token")
    return client


class TestActivateCoupons:
    """Tests for activate_coupons()."""

    async def test_activates_inactive_coupons(self, mock_client: AsyncMock) -> None:
        c1 = _make_coupon(coupon_id="c1", title="Apple")
        c2 = _make_coupon(coupon_id="c2", title="Banana")
        mock_client.coupons = AsyncMock(
            return_value={"sections": [{"coupons": [c1, c2]}]}
        )
        mock_client.coupon_promotions_v1 = AsyncMock(return_value={"sections": []})
        mock_client.activate_coupon = AsyncMock()

        result = await activate_coupons(mock_client)
        assert result == 2
        assert mock_client.activate_coupon.await_count == 2

    async def test_skips_already_activated(self, mock_client: AsyncMock) -> None:
        c1 = _make_coupon(coupon_id="c1", is_activated=True)
        mock_client.coupons = AsyncMock(return_value={"sections": [{"coupons": [c1]}]})
        mock_client.coupon_promotions_v1 = AsyncMock(return_value={"sections": []})

        result = await activate_coupons(mock_client)
        assert result == 0
        mock_client.activate_coupon.assert_not_awaited()

    async def test_skips_expired(self, mock_client: AsyncMock) -> None:
        c1 = _make_coupon(coupon_id="c1", is_expired=True)
        mock_client.coupons = AsyncMock(return_value={"sections": [{"coupons": [c1]}]})
        mock_client.coupon_promotions_v1 = AsyncMock(return_value={"sections": []})

        result = await activate_coupons(mock_client)
        assert result == 0
        mock_client.activate_coupon.assert_not_awaited()

    async def test_skips_special_promotions(self, mock_client: AsyncMock) -> None:
        c1 = _make_coupon(coupon_id="c1", is_special=True)
        mock_client.coupons = AsyncMock(return_value={"sections": [{"coupons": [c1]}]})
        mock_client.coupon_promotions_v1 = AsyncMock(return_value={"sections": []})

        result = await activate_coupons(mock_client)
        assert result == 0
        mock_client.activate_coupon.assert_not_awaited()

    async def test_activates_v1_promotions(self, mock_client: AsyncMock) -> None:
        p1 = _make_coupon(coupon_id="p1", title="V1 Promo")
        mock_client.coupons = AsyncMock(return_value={"sections": [{"coupons": []}]})
        mock_client.coupon_promotions_v1 = AsyncMock(
            return_value={"sections": [{"promotions": [p1]}]}
        )
        mock_client.activate_coupon_promotion_v1 = AsyncMock()

        result = await activate_coupons(mock_client)
        assert result == 1
        mock_client.activate_coupon_promotion_v1.assert_awaited_once_with("p1")

    async def test_mixed_v2_and_v1(self, mock_client: AsyncMock) -> None:
        c1 = _make_coupon(coupon_id="c1", title="V2")
        p1 = _make_coupon(coupon_id="p1", title="V1")
        mock_client.coupons = AsyncMock(return_value={"sections": [{"coupons": [c1]}]})
        mock_client.coupon_promotions_v1 = AsyncMock(
            return_value={"sections": [{"promotions": [p1]}]}
        )
        mock_client.activate_coupon = AsyncMock()
        mock_client.activate_coupon_promotion_v1 = AsyncMock()

        result = await activate_coupons(mock_client)
        assert result == 2
