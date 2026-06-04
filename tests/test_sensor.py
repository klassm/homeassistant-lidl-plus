"""Tests for the LidlPlusCouponSensor."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

from custom_components.lidl_plus.coordinator import LidlPlusCoordinator
from custom_components.lidl_plus.sensor import LidlPlusCouponSensor, _coupon_detail


def _make_coupon(
    title: str = "Test",
    is_activated: bool = True,
    discount_title: str = "",
    discount_description: str = "",
    image: str = "https://img.example.com/coupon.png",
    end: str | None = None,
) -> dict:
    if end is None:
        end = (datetime.now(UTC) + timedelta(days=30)).isoformat()
    return {
        "title": title,
        "isActivated": is_activated,
        "endValidityDate": end,
        "image": image,
        "discount": {"title": discount_title, "description": discount_description},
        "availability": {"apologizeStatus": False},
    }


def _mock_coordinator(data: dict) -> MagicMock:
    coord = MagicMock(spec=LidlPlusCoordinator)
    coord.data = data
    return coord


class TestCouponDetail:
    """Tests for _coupon_detail()."""

    def test_basic(self) -> None:
        coupon = _make_coupon(
            title="Apples", discount_title="20%", discount_description="all"
        )
        result = _coupon_detail(coupon)
        assert result["title"] == "Apples"
        assert result["discount"] == "20%"
        assert result["discount_description"] == "all"
        assert result["available"] is True

    def test_apologize_status_unavailable(self) -> None:
        coupon = _make_coupon(title="Gone")
        coupon["availability"] = {"apologizeStatus": True}
        result = _coupon_detail(coupon)
        assert result["available"] is False

    def test_validity_end_fallback(self) -> None:
        coupon = _make_coupon(title="V1")
        del coupon["endValidityDate"]
        coupon["validity"] = {"end": "2026-12-31T00:00:00+00:00"}
        result = _coupon_detail(coupon)
        assert result["end"] == "2026-12-31T00:00:00+00:00"


class TestSensorProperties:
    """Tests for sensor properties."""

    def _sensor(self, data: dict) -> LidlPlusCouponSensor:
        coord = _mock_coordinator(data)
        entry = MagicMock()
        entry.entry_id = "test"
        entry.title = "Lidl"
        return LidlPlusCouponSensor(coord, entry)

    def test_native_value(self) -> None:
        sensor = self._sensor({"valid": 5})
        assert sensor.native_value == 5

    def test_native_value_default(self) -> None:
        sensor = self._sensor({})
        assert sensor.native_value == 0

    def test_extra_state_attributes(self) -> None:
        coupon = _make_coupon(title="Apples")
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

    def test_entity_picture_with_coupons(self) -> None:
        coupon = _make_coupon(image="https://img.example.com/c.png")
        sensor = self._sensor({"coupons": [coupon]})
        assert sensor.entity_picture == "https://img.example.com/c.png"

    def test_entity_picture_no_coupons(self) -> None:
        sensor = self._sensor({"coupons": []})
        assert sensor.entity_picture is None
