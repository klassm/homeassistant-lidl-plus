"""Tests for the LidlPlusCouponSensor."""

from __future__ import annotations

from unittest.mock import MagicMock

from custom_components.lidl_plus.coordinator import LidlPlusCoordinator
from custom_components.lidl_plus.sensor import LidlPlusCouponSensor
from tests.conftest import make_coupon


def _mock_coordinator(data: dict) -> MagicMock:
    """Return a mocked coordinator with the given data."""
    coord = MagicMock(spec=LidlPlusCoordinator)
    coord.data = data
    return coord


class TestSensorProperties:
    """Tests for sensor properties."""

    def _sensor(self, data: dict) -> LidlPlusCouponSensor:
        """Create a sensor with the given coordinator data."""
        coord = _mock_coordinator(data)
        entry = MagicMock()
        entry.entry_id = "test"
        entry.title = "Lidl"
        return LidlPlusCouponSensor(coord, entry)

    def test_native_value(self) -> None:
        """Test that native_value returns the valid coupon count."""
        sensor = self._sensor({"valid": 5})
        assert sensor.native_value == 5

    def test_native_value_default(self) -> None:
        """Test that native_value defaults to 0 when no data."""
        sensor = self._sensor({})
        assert sensor.native_value == 0

    def test_extra_state_attributes(self) -> None:
        """Test that extra_state_attributes contains all expected fields."""
        coupon = make_coupon(title="Apples")
        sensor = self._sensor(
            {
                "total": 3,
                "in_store": 2,
                "active": 2,
                "valid": 1,
                "activated_this_cycle": 1,
                "coupons": [coupon],
            }
        )
        attrs = sensor.extra_state_attributes
        assert attrs["total_coupons"] == 3
        assert attrs["in_store_coupons"] == 2
        assert attrs["active_coupons"] == 2
        assert attrs["valid_coupons"] == 1
        assert attrs["activated_last_cycle"] == 1
        assert attrs["coupon_names"] == ["Apples"]
        assert len(attrs["coupons"]) == 1

    def test_coupon_detail_available(self) -> None:
        """Test that coupon detail reflects availability via extra_state_attributes."""
        coupon = make_coupon(title="Fresh Fruit")
        sensor = self._sensor(
            {
                "total": 1,
                "in_store": 1,
                "active": 1,
                "valid": 1,
                "activated_this_cycle": 0,
                "coupons": [coupon],
            }
        )
        attrs = sensor.extra_state_attributes
        assert attrs["coupons"][0]["available"] is True

    def test_coupon_detail_unavailable(self) -> None:
        """Test that coupon detail reflects unavailability via attributes."""
        coupon = make_coupon(title="Gone")
        coupon["availability"] = {"apologizeStatus": True}
        sensor = self._sensor(
            {
                "total": 1,
                "in_store": 1,
                "active": 1,
                "valid": 1,
                "activated_this_cycle": 0,
                "coupons": [coupon],
            }
        )
        attrs = sensor.extra_state_attributes
        assert attrs["coupons"][0]["available"] is False

    def test_entity_picture_with_coupons(self) -> None:
        """Test that entity_picture returns the first coupon image."""
        coupon = make_coupon(image="https://img.example.com/c.png")
        sensor = self._sensor({"coupons": [coupon]})
        assert sensor.entity_picture == "https://img.example.com/c.png"

    def test_entity_picture_no_coupons(self) -> None:
        """Test that entity_picture is None when there are no coupons."""
        sensor = self._sensor({"coupons": []})
        assert sensor.entity_picture is None
