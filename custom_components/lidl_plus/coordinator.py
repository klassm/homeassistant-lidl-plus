from __future__ import annotations

from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .activate_coupons import activate_coupons
from .api import LidlPlusApiClient
from .const import LOGGER
from .coupon_helpers import is_expired, should_show

SCAN_INTERVAL = timedelta(hours=6)


class LidlPlusCoordinator(DataUpdateCoordinator[dict]):
    def __init__(
        self,
        hass: HomeAssistant,
        client: LidlPlusApiClient,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(
            hass,
            LOGGER,
            name="Lidl Plus",
            update_interval=SCAN_INTERVAL,
        )
        self._client = client
        self._entry = entry

    async def _async_update_data(self) -> dict:
        try:
            await self._client.get_access_token()
        except Exception as err:
            raise UpdateFailed(f"Auth failed: {err}") from err

        if self._client.refresh_token != self._entry.data.get(CONF_TOKEN):
            self.hass.config_entries.async_update_entry(
                self._entry,
                data={**self._entry.data, CONF_TOKEN: self._client.refresh_token},
            )

        activated = await activate_coupons(self._client)

        coupons: list[dict] = []
        try:
            data = await self._client.coupons()
            for section in data.get("sections", []):
                for coupon in section.get("coupons", []):
                    coupons.append(coupon)
        except Exception:
            LOGGER.warning("Failed to fetch V2 coupons")

        try:
            data_v1 = await self._client.coupon_promotions_v1()
            for section in data_v1.get("sections", []):
                for coupon in section.get("promotions", []):
                    coupons.append(coupon)
        except Exception:
            LOGGER.warning("Failed to fetch V1 coupons")

        displayable = [c for c in coupons if should_show(c)]
        active = [c for c in displayable if c.get("isActivated")]
        valid = [c for c in active if not is_expired(c)]

        return {
            "total": len(coupons),
            "in_store": len(displayable),
            "active": len(active),
            "valid": len(valid),
            "activated_this_cycle": activated,
            "coupons": valid,
        }
