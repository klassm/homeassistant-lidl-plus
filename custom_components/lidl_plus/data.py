from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry

if TYPE_CHECKING:
    from homeassistant.loader import Integration

    from .api import LidlPlusApiClient

type LidlPlusConfigEntry = ConfigEntry[LidlPlusData]


@dataclass
class LidlPlusData:
    client: LidlPlusApiClient
    integration: Integration
