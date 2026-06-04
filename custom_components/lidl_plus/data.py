"""Data classes for the Lidl Plus integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

    from .api import LidlPlusApiClient


@dataclass
class LidlPlusData:
    """Runtime data for a Lidl Plus config entry."""

    client: LidlPlusApiClient
    coordinator: DataUpdateCoordinator
