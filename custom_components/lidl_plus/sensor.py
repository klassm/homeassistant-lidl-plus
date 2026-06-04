from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LidlPlusCoordinator
from .data import LidlPlusData


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data: LidlPlusData = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([LidlPlusCouponSensor(data.coordinator, entry)])


def _coupon_detail(c: dict) -> dict:
    discount = c.get("discount", {})
    availability = c.get("availability", {})
    return {
        "title": c.get("title", ""),
        "discount": discount.get("title", ""),
        "discount_description": discount.get("description", ""),
        "image": c.get("image", ""),
        "end": c.get("endValidityDate") or c.get("validity", {}).get("end"),
        "available": not availability.get("apologizeStatus", False),
    }


class LidlPlusCouponSensor(CoordinatorEntity[LidlPlusCoordinator], SensorEntity):
    _attr_icon = "mdi:ticket-percent"
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: LidlPlusCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_coupons"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title,
            "manufacturer": "Lidl",
        }

    @property
    def native_value(self) -> int:
        return self.coordinator.data.get("valid", 0)

    @property
    def extra_state_attributes(self) -> dict:
        data = self.coordinator.data
        coupons = data.get("coupons", [])
        return {
            "total_coupons": data.get("total", 0),
            "in_store_coupons": data.get("in_store", 0),
            "active_coupons": data.get("active", 0),
            "valid_coupons": data.get("valid", 0),
            "activated_last_cycle": data.get("activated_this_cycle", 0),
            "coupon_names": [
                f"{c.get('discount', {}).get('title', '')} {c.get('title', '')}".strip()
                for c in coupons
            ],
            "coupons": [_coupon_detail(c) for c in coupons],
        }

    @property
    def entity_picture(self) -> str | None:
        coupons = self.coordinator.data.get("coupons", [])
        if coupons:
            return coupons[0].get("image")
        return None
