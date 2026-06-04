"""The Lidl Plus integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.const import CONF_COUNTRY, CONF_LANGUAGE, CONF_TOKEN
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import LidlPlusApiClient
from .const import DOMAIN
from .coordinator import LidlPlusCoordinator
from .data import LidlPlusData

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

PLATFORMS = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a Lidl Plus config entry."""
    session = async_get_clientsession(hass)
    client = LidlPlusApiClient(
        refresh_token=entry.data[CONF_TOKEN],
        country=entry.data[CONF_COUNTRY],
        language=entry.data[CONF_LANGUAGE],
        session=session,
    )

    coordinator = LidlPlusCoordinator(hass, client, entry)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = LidlPlusData(
        client=client,
        coordinator=coordinator,
    )

    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Lidl Plus config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
