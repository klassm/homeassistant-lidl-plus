"""API client for the Lidl Plus integration."""

from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import aiohttp

    from .exceptions import LoginError
else:
    try:
        from .exceptions import LoginError
    except ImportError:
        from exceptions import LoginError

_HTTP_CONFLICT = 409
_HTTP_BAD_REQUEST = 400


class LidlPlusApiClient:
    """Client for the Lidl Plus API."""

    _CLIENT_ID = "LidlPlusNativeClient"
    _AUTH_API = "https://accounts.lidl.com"
    _COUPONS_API = "https://coupons.lidlplus.com/app/api"
    _COUPONS_V1_API = "https://coupons.lidlplus.com/app/api"
    _TIMEOUT = 30

    def __init__(
        self,
        refresh_token: str,
        country: str,
        language: str,
        session: aiohttp.ClientSession,
    ) -> None:
        """Initialize the API client."""
        self._refresh_token = refresh_token
        self._country = country
        self._language = language
        self._session = session
        self._token = ""
        self._expires: datetime | None = None

    @property
    def refresh_token(self) -> str:
        """Return the current refresh token."""
        return self._refresh_token

    async def coupons(self) -> dict:
        """Fetch V2 coupons."""
        url = f"{self._COUPONS_API}/v2/promotionsList"
        kwargs = {
            "headers": await self._default_headers(),
            "timeout": self._TIMEOUT,
        }
        async with self._session.get(url, **kwargs) as resp:
            return await resp.json()

    async def coupon_promotions_v1(self) -> dict:
        """Fetch V1 coupon promotions."""
        url = f"{self._COUPONS_V1_API}/v1/promotionslist"
        kwargs = {
            "headers": await self._default_headers(),
            "timeout": self._TIMEOUT,
        }
        async with self._session.get(url, **kwargs) as resp:
            return await resp.json()

    async def get_access_token(self) -> str:
        """Return a valid access token, refreshing if expired."""
        if self._expires and datetime.now(UTC) < self._expires and self._token:
            return self._token
        await self._renew_token()
        return self._token

    async def activate_coupon(self, coupon_id: str) -> aiohttp.ClientResponse:
        """Activate a V2 coupon."""
        url = f"{self._COUPONS_API}/v1/promotions/{coupon_id}/activation"
        kwargs = {
            "headers": await self._default_headers(),
            "timeout": self._TIMEOUT,
        }
        async with self._session.post(url, **kwargs) as resp:
            if resp.status != _HTTP_CONFLICT and resp.status > _HTTP_BAD_REQUEST:
                resp.raise_for_status()
        return resp

    async def activate_coupon_promotion_v1(
        self, promotion_id: str
    ) -> aiohttp.ClientResponse:
        """Activate a V1 coupon promotion."""
        url = f"{self._COUPONS_V1_API}/v1/promotions/{promotion_id}/activation"
        kwargs = {
            "headers": await self._default_headers(),
            "timeout": self._TIMEOUT,
        }
        async with self._session.post(url, **kwargs) as resp:
            if resp.status != _HTTP_CONFLICT and resp.status > _HTTP_BAD_REQUEST:
                resp.raise_for_status()
        return resp

    async def _auth(self, payload: dict) -> None:
        """Authenticate with the Lidl Plus API."""
        default_secret = base64.b64encode(f"{self._CLIENT_ID}:secret".encode()).decode()
        headers = {
            "Authorization": f"Basic {default_secret}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        kwargs = {"headers": headers, "data": payload, "timeout": self._TIMEOUT}
        async with self._session.post(
            f"{self._AUTH_API}/connect/token", **kwargs
        ) as resp:
            response = await resp.json()
            if "error" in response:
                raise LoginError(response["error"])
            self._expires = datetime.now(UTC) + timedelta(
                seconds=response["expires_in"]
            )
            self._token = response["access_token"]
            self._refresh_token = response["refresh_token"]

    async def _renew_token(self) -> None:
        """Renew the access token."""
        payload = {"refresh_token": self._refresh_token, "grant_type": "refresh_token"}
        await self._auth(payload)

    async def _default_headers(self) -> dict:
        """Return default API headers with a valid access token."""
        await self.get_access_token()
        return {
            "Authorization": f"Bearer {self._token}",
            "App-Version": "14.21.2",
            "Operating-System": "iOS",
            "App": "com.lidl.eci.lidl.plus",
            "Accept-Language": self._country,
            "Country": self._country,
            "User-Agent": (
                "Mozilla/5.0 (Linux; Android 15) AppleWebKit/537.36"
                " (KHTML, like Gecko) Chrome/133.0.6943.89 Mobile Safari/537.36"
            ),
        }
