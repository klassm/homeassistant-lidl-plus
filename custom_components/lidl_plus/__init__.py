"""
Custom integration to integrate integration_blueprint with Home Assistant.

For more details about this integration, please refer to
https://github.com/ludeeus/integration_blueprint
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.const import Platform, CONF_TOKEN, CONF_LANGUAGE, CONF_COUNTRY
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.loader import async_get_loaded_integration
from .activate_coupons import activate_coupons

from .api import LidlPlusApiClient
from .data import LidlPlusData
from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant, ServiceCall

    from .data import LidlPlusConfigEntry

PLATFORMS: list[Platform] = []


# https://developers.home-assistant.io/docs/config_entries_index/#setting-up-an-entry
async def async_setup_entry(
    hass: HomeAssistant,
    entry: LidlPlusConfigEntry,
) -> bool:
    entry.runtime_data = LidlPlusData(
        client=LidlPlusApiClient(
            refresh_token=entry.data[CONF_TOKEN],
            language=entry.data[CONF_LANGUAGE],
            country=entry.data[CONF_COUNTRY],
            session=async_get_clientsession(hass),
        ),
        integration=async_get_loaded_integration(hass, entry.domain),
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: LidlPlusConfigEntry,
) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(
    hass: HomeAssistant,
    entry: LidlPlusConfigEntry,
) -> None:
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)

def setup(hass, config):
    async def update_coupons(call: ServiceCall):
        """Handle the service action call."""
        entries = hass.config_entries.async_loaded_entries(DOMAIN)
        for entry in entries:
            await activate_coupons(entry.runtime_data)
    hass.services.register(DOMAIN, "update_coupons", update_coupons)
    return True