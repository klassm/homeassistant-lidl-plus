"""Data update coordinator for the Lidl Plus integration."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

import aiohttp
from homeassistant.const import CONF_TOKEN
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .activate_coupons import activate_coupons
from .const import LOGGER
from .coupon_helpers import is_expired, should_show

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .api import LidlPlusApiClient

SCAN_INTERVAL = timedelta(hours=6)


async def fetch_and_process_coupons(client: LidlPlusApiClient) -> dict:
    """Fetch coupons from the API and return processed summary data."""
    coupons: list[dict] = []
    try:
        data = await client.coupons()
        for section in data.get("sections", []):
            coupons.extend(section.get("coupons", []))
    except (aiohttp.ClientError, TimeoutError):
        LOGGER.warning("Failed to fetch V2 coupons")

    try:
        data_v1 = await client.coupon_promotions_v1()
        for section in data_v1.get("sections", []):
            coupons.extend(section.get("promotions", []))
    except (aiohttp.ClientError, TimeoutError):
        LOGGER.warning("Failed to fetch V1 coupons")

    displayable = [c for c in coupons if should_show(c)]
    active = [c for c in displayable if c.get("isActivated")]
    valid = [c for c in active if not is_expired(c)]

    return {
        "total": len(coupons),
        "in_store": len(displayable),
        "active": len(active),
        "valid": len(valid),
        "coupons": valid,
    }


class LidlPlusCoordinator(DataUpdateCoordinator[dict]):
    """Coordinator for Lidl Plus coupon data."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: LidlPlusApiClient,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name="Lidl Plus",
            update_interval=SCAN_INTERVAL,
        )
        self._client = client
        self._entry = entry

    async def _async_update_data(self) -> dict:
        """Fetch data from the Lidl Plus API."""
        try:
            await self._client.get_access_token()
        except Exception as err:
            msg = f"Auth failed: {err}"
            raise UpdateFailed(msg) from err

        if self._client.refresh_token != self._entry.data.get(CONF_TOKEN):
            self.hass.config_entries.async_update_entry(
                self._entry,
                data={**self._entry.data, CONF_TOKEN: self._client.refresh_token},
            )

        activated = await activate_coupons(self._client)
        result = await fetch_and_process_coupons(self._client)
        result["activated_this_cycle"] = activated
        return result
