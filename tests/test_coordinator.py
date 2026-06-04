"""Tests for the coordinator's fetch_and_process_coupons function."""

from __future__ import annotations

from unittest.mock import AsyncMock

from custom_components.lidl_plus.coordinator import fetch_and_process_coupons
from tests.conftest import make_coupon


class TestFetchAndProcessCoupons:
    """Tests for fetch_and_process_coupons()."""

    async def test_basic_update(self) -> None:
        """Test that a basic fetch returns expected data."""
        coupon = make_coupon(title="Apple 20%", is_activated=True)
        client = AsyncMock()
        client.coupons = AsyncMock(return_value={"sections": [{"coupons": [coupon]}]})
        client.coupon_promotions_v1 = AsyncMock(return_value={"sections": []})

        result = await fetch_and_process_coupons(client)

        assert result["total"] == 1
        assert result["valid"] == 1
        assert result["active"] == 1
        assert result["in_store"] == 1
        assert len(result["coupons"]) == 1

    async def test_expired_coupons_excluded_from_valid(self) -> None:
        """Test that expired coupons are excluded from valid count."""
        expired = make_coupon(title="Expired", is_activated=True, is_expired=True)
        valid = make_coupon(title="Valid", is_activated=True)
        client = AsyncMock()
        client.coupons = AsyncMock(
            return_value={"sections": [{"coupons": [expired, valid]}]}
        )
        client.coupon_promotions_v1 = AsyncMock(return_value={"sections": []})

        result = await fetch_and_process_coupons(client)

        assert result["total"] == 2
        assert result["active"] == 2
        assert result["valid"] == 1

    async def test_inactive_coupons_excluded_from_valid(self) -> None:
        """Test that inactive coupons are excluded from valid count."""
        inactive = make_coupon(title="Inactive", is_activated=False)
        client = AsyncMock()
        client.coupons = AsyncMock(return_value={"sections": [{"coupons": [inactive]}]})
        client.coupon_promotions_v1 = AsyncMock(return_value={"sections": []})

        result = await fetch_and_process_coupons(client)

        assert result["active"] == 0
        assert result["valid"] == 0

    async def test_online_shop_hidden(self) -> None:
        """Test that online-shop coupons are excluded from in-store count."""
        online = make_coupon(title="Online", is_activated=True, is_online_shop=True)
        client = AsyncMock()
        client.coupons = AsyncMock(return_value={"sections": [{"coupons": [online]}]})
        client.coupon_promotions_v1 = AsyncMock(return_value={"sections": []})

        result = await fetch_and_process_coupons(client)

        assert result["total"] == 1
        assert result["in_store"] == 0

    async def test_v1_coupons_merged(self) -> None:
        """Test that V1 promotions are merged with V2 coupons."""
        v2_coupon = make_coupon(title="V2", is_activated=True)
        v1_coupon = make_coupon(title="V1", is_activated=True)
        client = AsyncMock()
        client.coupons = AsyncMock(
            return_value={"sections": [{"coupons": [v2_coupon]}]}
        )
        client.coupon_promotions_v1 = AsyncMock(
            return_value={"sections": [{"promotions": [v1_coupon]}]}
        )

        result = await fetch_and_process_coupons(client)

        assert result["total"] == 2
        assert result["valid"] == 2

    async def test_v2_fetch_failure_returns_empty(self) -> None:
        """Test that a V2 fetch failure still allows V1 data."""
        import aiohttp

        v1_coupon = make_coupon(title="V1 Only", is_activated=True)
        client = AsyncMock()
        client.coupons = AsyncMock(side_effect=aiohttp.ClientError("fail"))
        client.coupon_promotions_v1 = AsyncMock(
            return_value={"sections": [{"promotions": [v1_coupon]}]}
        )

        result = await fetch_and_process_coupons(client)

        assert result["total"] == 1
        assert result["valid"] == 1

    async def test_both_fetch_failures_returns_empty(self) -> None:
        """Test that both fetch failures return zeroed counts."""
        import aiohttp

        client = AsyncMock()
        client.coupons = AsyncMock(side_effect=aiohttp.ClientError("fail"))
        client.coupon_promotions_v1 = AsyncMock(side_effect=aiohttp.ClientError("fail"))

        result = await fetch_and_process_coupons(client)

        assert result["total"] == 0
        assert result["valid"] == 0
        assert result["active"] == 0
        assert result["in_store"] == 0
