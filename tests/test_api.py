"""Tests for the LidlPlusApiClient."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.lidl_plus.api import LidlPlusApiClient
from custom_components.lidl_plus.exceptions import LoginError


def _mock_auth_response(session: AsyncMock, json_return: dict) -> None:
    """Configure the session mock to return an auth POST response."""
    resp = AsyncMock()
    resp.json = AsyncMock(return_value=json_return)
    resp.__aenter__ = AsyncMock(return_value=resp)
    resp.__aexit__ = AsyncMock(return_value=False)
    session.post = MagicMock(return_value=resp)


def _mock_get_response(session: AsyncMock, json_return: dict) -> None:
    """Configure the session mock to return a GET response."""
    resp = AsyncMock()
    resp.json = AsyncMock(return_value=json_return)
    resp.__aenter__ = AsyncMock(return_value=resp)
    resp.__aexit__ = AsyncMock(return_value=False)
    session.get = MagicMock(return_value=resp)


def _mock_activate_response(session: AsyncMock, status: int) -> None:
    """Configure the session mock to return an activation POST response."""
    resp = AsyncMock()
    resp.status = status
    resp.raise_for_status = MagicMock()
    resp.__aenter__ = AsyncMock(return_value=resp)
    resp.__aexit__ = AsyncMock(return_value=False)
    session.post = MagicMock(return_value=resp)


@pytest.fixture
def session() -> AsyncMock:
    """Return a mocked aiohttp session."""
    return AsyncMock()


@pytest.fixture
def client(session: AsyncMock) -> LidlPlusApiClient:
    """Return a LidlPlusApiClient with a mocked session."""
    return LidlPlusApiClient(
        refresh_token="test-refresh",
        country="DE",
        language="de",
        session=session,
    )


class TestGetAccessToken:
    """Tests for get_access_token()."""

    async def test_authenticates_on_first_call(
        self, client: LidlPlusApiClient, session: AsyncMock
    ) -> None:
        """Test that first call authenticates and returns a token."""
        _mock_auth_response(
            session,
            {
                "access_token": "new-access",
                "refresh_token": "new-refresh",
                "expires_in": 3600,
            },
        )
        result = await client.get_access_token()
        assert result == "new-access"
        assert client.refresh_token == "new-refresh"

    async def test_raises_login_error_on_auth_failure(
        self, client: LidlPlusApiClient, session: AsyncMock
    ) -> None:
        """Test that auth failure raises LoginError."""
        _mock_auth_response(session, {"error": "invalid_grant"})
        with pytest.raises(LoginError, match="invalid_grant"):
            await client.get_access_token()

    async def test_reuses_cached_token(
        self, client: LidlPlusApiClient, session: AsyncMock
    ) -> None:
        """Test that subsequent calls reuse the cached token."""
        _mock_auth_response(
            session,
            {
                "access_token": "cached-token",
                "refresh_token": "cached-refresh",
                "expires_in": 3600,
            },
        )
        await client.get_access_token()
        second = await client.get_access_token()
        assert second == "cached-token"
        session.post.assert_called_once()

    async def test_refreshes_expired_token(
        self, client: LidlPlusApiClient, session: AsyncMock
    ) -> None:
        """Test that an expired token is refreshed automatically."""
        base_time = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)

        _mock_auth_response(
            session,
            {
                "access_token": "first-token",
                "refresh_token": "first-refresh",
                "expires_in": 3600,
            },
        )
        with patch("custom_components.lidl_plus.api.datetime") as mock_dt:
            mock_dt.now.return_value = base_time
            mock_dt.side_effect = datetime
            await client.get_access_token()

        session.post.reset_mock()

        _mock_auth_response(
            session,
            {
                "access_token": "renewed-token",
                "refresh_token": "renewed-refresh",
                "expires_in": 3600,
            },
        )
        with patch("custom_components.lidl_plus.api.datetime") as mock_dt:
            mock_dt.now.return_value = base_time + timedelta(hours=2)
            mock_dt.side_effect = datetime
            result = await client.get_access_token()

        assert result == "renewed-token"
        assert client.refresh_token == "renewed-refresh"


class TestRefreshTokenProperty:
    """Tests for refresh_token property."""

    async def test_returns_updated_token_after_auth(
        self, client: LidlPlusApiClient, session: AsyncMock
    ) -> None:
        """Test that refresh_token reflects the latest auth response."""
        _mock_auth_response(
            session,
            {
                "access_token": "access",
                "refresh_token": "updated-refresh",
                "expires_in": 3600,
            },
        )
        await client.get_access_token()
        assert client.refresh_token == "updated-refresh"


class TestCoupons:
    """Tests for coupons() and coupon_promotions_v1()."""

    async def test_coupons_returns_data(
        self, client: LidlPlusApiClient, session: AsyncMock
    ) -> None:
        """Test that coupons() returns API data."""
        _mock_auth_response(
            session,
            {
                "access_token": "token",
                "refresh_token": "refresh",
                "expires_in": 3600,
            },
        )
        _mock_get_response(session, {"sections": [{"coupons": []}]})

        result = await client.coupons()
        assert result == {"sections": [{"coupons": []}]}

    async def test_coupon_promotions_v1_returns_data(
        self, client: LidlPlusApiClient, session: AsyncMock
    ) -> None:
        """Test that coupon_promotions_v1() returns API data."""
        _mock_auth_response(
            session,
            {
                "access_token": "token",
                "refresh_token": "refresh",
                "expires_in": 3600,
            },
        )
        _mock_get_response(session, {"sections": [{"promotions": []}]})

        result = await client.coupon_promotions_v1()
        assert result == {"sections": [{"promotions": []}]}


class TestActivateCoupon:
    """Tests for activate_coupon() and activate_coupon_promotion_v1()."""

    async def test_activate_coupon_success(
        self, client: LidlPlusApiClient, session: AsyncMock
    ) -> None:
        """Test successful coupon activation returns the response."""
        _mock_auth_response(
            session,
            {
                "access_token": "token",
                "refresh_token": "refresh",
                "expires_in": 3600,
            },
        )
        await client.get_access_token()

        _mock_activate_response(session, 200)
        result = await client.activate_coupon("coupon-1")
        assert result.status == 200

    async def test_activate_coupon_conflict_is_ok(
        self, client: LidlPlusApiClient, session: AsyncMock
    ) -> None:
        """Test that a 409 conflict on activation does not raise."""
        _mock_auth_response(
            session,
            {
                "access_token": "token",
                "refresh_token": "refresh",
                "expires_in": 3600,
            },
        )
        await client.get_access_token()

        _mock_activate_response(session, 409)
        result = await client.activate_coupon("coupon-1")
        assert result.status == 409
        result.raise_for_status.assert_not_called()

    async def test_activate_coupon_promotion_v1_success(
        self, client: LidlPlusApiClient, session: AsyncMock
    ) -> None:
        """Test successful V1 promotion activation returns the response."""
        _mock_auth_response(
            session,
            {
                "access_token": "token",
                "refresh_token": "refresh",
                "expires_in": 3600,
            },
        )
        await client.get_access_token()

        _mock_activate_response(session, 200)
        result = await client.activate_coupon_promotion_v1("promo-1")
        assert result.status == 200
