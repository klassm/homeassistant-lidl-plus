from __future__ import annotations

from datetime import UTC, datetime, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .activate_coupons import activate_coupons
from .api import LidlPlusApiClient
from .const import LOGGER

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

        _SKIP_TITLES = {"Aktionsrabatt", "Wiedereröffnung"}
        in_store = [
            c
            for c in coupons
            if not c.get("isOnlineShop")
            and c.get("title") not in _SKIP_TITLES
        ]
        active = [c for c in in_store if c.get("isActivated")]
        now = datetime.now(UTC)

        valid = []
        for c in active:
            end = c.get("endValidityDate") or c.get("validity", {}).get("end")
            if end:
                try:
                    if datetime.fromisoformat(end) < now:
                        continue
                except (ValueError, TypeError):
                    pass
            valid.append(c)

        return {
            "total": len(coupons),
            "in_store": len(in_store),
            "active": len(active),
            "valid": len(valid),
            "activated_this_cycle": activated,
            "coupons": valid,
        }
