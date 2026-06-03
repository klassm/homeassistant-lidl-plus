from __future__ import annotations

from dataclasses import dataclass

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import LidlPlusApiClient


@dataclass
class LidlPlusData:
    client: LidlPlusApiClient
    coordinator: DataUpdateCoordinator
