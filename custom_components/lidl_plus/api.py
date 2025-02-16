
from __future__ import annotations

import base64

import aiohttp

from .exceptions import LoginError


class LidlPlusApiClient:
    _CLIENT_ID = "LidlPlusNativeClient"
    _AUTH_API = "https://accounts.lidl.com"
    _TICKET_API = "https://tickets.lidlplus.com/api/v2"
    _COUPONS_API = "https://coupons.lidlplus.com/api"
    _COUPONS_V1_API = "https://coupons.lidlplus.com/app/api"
    _PROFILE_API = "https://profile.lidlplus.com/profile/api"
    _STORES_API = "https://stores.lidlplus.com/api"
    _APP = "com.lidlplus.app"
    _OS = "iOs"
    _TIMEOUT = 10

    def __init__(
        self,
        refresh_token: str,
        country: str,
        language: str,
        session: aiohttp.ClientSession,
    ) -> None:
        self._refresh_token = refresh_token
        self._country = country
        self._language = language
        self._session = session


    async def coupons(self, token):
        """Get list of all coupons"""
        url = f"{self._COUPONS_API}/v2/{self._country}"
        kwargs = {"headers": self._default_headers(token), "timeout": self._TIMEOUT}
        async with self._session.get(url, **kwargs) as resp:
            return await resp.json()

    async def coupon_promotions_v1(self, token):
        """Get list of all coupons API V1"""
        url = f"{self._COUPONS_V1_API}/v1/promotionslist"
        kwargs = {"headers": {**self._default_headers(token), "Country": self._country}, "timeout": self._TIMEOUT}
        async with self._session.get(url, **kwargs) as resp:
            return await resp.json()

    async def get_access_token(self) -> str:
        payload = {"refresh_token": self._refresh_token, "grant_type": "refresh_token"}
        return await self._auth(payload)

    async def activate_coupon(self, token, coupon_id):
        """Activate single coupon by id"""
        url = f"{self._COUPONS_API}/v1/{self._country}/{coupon_id}/activation"
        kwargs = {"headers": self._default_headers(token), "timeout": self._TIMEOUT}
        async with self._session.post(url, **kwargs) as resp:
            if resp.status != 409 and resp.status > 400:
                resp.raise_for_status()
        return resp

    async def activate_coupon_promotion_v1(self, token, promotion_id):
        """Activate single coupon by id API V1"""
        url = f"{self._COUPONS_V1_API}/v1/promotions/{promotion_id}/activation"
        kwargs = {"headers": {**self._default_headers(token), "Country": self._country}, "timeout": self._TIMEOUT}
        async with self._session.post(url, **kwargs) as resp:
            if resp.status != 409 and resp.status > 400:
                resp.raise_for_status()
        return resp

    async def _auth(self, payload) -> str:
        default_secret = base64.b64encode(f"{self._CLIENT_ID}:secret".encode()).decode()
        headers = {
            "Authorization": f"Basic {default_secret}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        kwargs = {"headers": headers, "data": payload, "timeout": self._TIMEOUT}
        async with self._session.post(f"{self._AUTH_API}/connect/token", **kwargs) as resp:
            response = await resp.json()
            if "error" in response:
                raise LoginError(response["error"])
            return response["access_token"]

    def _default_headers(self, access_token):
        return {
            "Authorization": f"Bearer {access_token}",
            "Accept-Language": self._language,
            "User-Agent": "Mozilla/5.0 (Linux; Android 15) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.6943.89 Mobile Safari/537.36",
        }