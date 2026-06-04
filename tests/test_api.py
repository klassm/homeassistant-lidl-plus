"""Tests for the LidlPlusApiClient."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.lidl_plus.api import LidlPlusApiClient
from custom_components.lidl_plus.exceptions import LoginError


@pytest.fixture
def session() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def client(session: AsyncMock) -> LidlPlusApiClient:
    return LidlPlusApiClient(
        refresh_token="test-refresh",
        country="DE",
        language="de",
        session=session,
    )


class TestGetAccessToken:
    """Tests for get_access_token()."""

    async def test_returns_cached_token(self, client: LidlPlusApiClient) -> None:
        client._token = "cached-token"
        client._expires = datetime.now(UTC) + timedelta(hours=1)
        result = await client.get_access_token()
        assert result == "cached-token"

    async def test_renews_when_expired(self, client: LidlPlusApiClient) -> None:
        client._token = "old-token"
        client._expires = datetime.now(UTC) - timedelta(hours=1)

        with patch.object(client, "_renew_token", new_callable=AsyncMock) as mock_renew:
            mock_renew.side_effect = (
                lambda: setattr(client, "_token", "new-token") or None
            )
            result = await client.get_access_token()
            mock_renew.assert_awaited_once()
            assert result == "new-token"

    async def test_renews_when_no_token(self, client: LidlPlusApiClient) -> None:
        client._token = ""
        client._expires = None

        with patch.object(client, "_renew_token", new_callable=AsyncMock) as mock_renew:
            mock_renew.side_effect = (
                lambda: setattr(client, "_token", "fresh-token") or None
            )
            result = await client.get_access_token()
            mock_renew.assert_awaited_once()
            assert result == "fresh-token"


class TestAuth:
    """Tests for _auth()."""

    async def test_successful_auth(
        self, client: LidlPlusApiClient, session: AsyncMock
    ) -> None:
        resp_mock = AsyncMock()
        resp_mock.json = AsyncMock(
            return_value={
                "access_token": "new-access",
                "refresh_token": "new-refresh",
                "expires_in": 3600,
            }
        )
        session.post = MagicMock(return_value=resp_mock)
        resp_mock.__aenter__ = AsyncMock(return_value=resp_mock)
        resp_mock.__aexit__ = AsyncMock(return_value=False)

        await client._auth(
            {"grant_type": "refresh_token", "refresh_token": "test-refresh"}
        )
        assert client._token == "new-access"
        assert client._refresh_token == "new-refresh"
        assert client._expires is not None

    async def test_auth_raises_login_error(
        self, client: LidlPlusApiClient, session: AsyncMock
    ) -> None:
        resp_mock = AsyncMock()
        resp_mock.json = AsyncMock(return_value={"error": "invalid_grant"})
        session.post = MagicMock(return_value=resp_mock)
        resp_mock.__aenter__ = AsyncMock(return_value=resp_mock)
        resp_mock.__aexit__ = AsyncMock(return_value=False)

        with pytest.raises(LoginError, match="invalid_grant"):
            await client._auth({"grant_type": "refresh_token"})


class TestRefreshToken:
    """Tests for refresh_token property."""

    def test_returns_current_token(self, client: LidlPlusApiClient) -> None:
        client._refresh_token = "my-token"
        assert client.refresh_token == "my-token"
