"""Tests for coupon_helpers module."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from custom_components.lidl_plus.coupon_helpers import (
    coupon_label,
    is_expired,
    is_special_promotion,
    should_show,
)


class TestIsExpired:
    """Tests for is_expired()."""

    def test_not_expired(self) -> None:
        coupon = {
            "endValidityDate": (datetime.now(UTC) + timedelta(days=30)).isoformat()
        }
        assert not is_expired(coupon)

    def test_expired_via_end_validity_date(self) -> None:
        coupon = {
            "endValidityDate": (datetime.now(UTC) - timedelta(days=1)).isoformat()
        }
        assert is_expired(coupon)

    def test_not_yet_valid_via_start_validity_date(self) -> None:
        coupon = {
            "startValidityDate": (datetime.now(UTC) + timedelta(days=1)).isoformat()
        }
        assert is_expired(coupon)

    def test_expired_via_validity_end(self) -> None:
        coupon = {
            "validity": {"end": (datetime.now(UTC) - timedelta(days=1)).isoformat()}
        }
        assert is_expired(coupon)

    def test_not_yet_valid_via_validity_start(self) -> None:
        coupon = {
            "validity": {"start": (datetime.now(UTC) + timedelta(days=1)).isoformat()}
        }
        assert is_expired(coupon)

    def test_no_dates_means_not_expired(self) -> None:
        assert not is_expired({})

    def test_currently_valid(self) -> None:
        coupon = {
            "startValidityDate": (datetime.now(UTC) - timedelta(days=1)).isoformat(),
            "endValidityDate": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
        }
        assert not is_expired(coupon)

    def test_validity_dict_overrides(self) -> None:
        now = datetime.now(UTC)
        coupon = {
            "endValidityDate": (now + timedelta(days=30)).isoformat(),
            "validity": {"end": (now - timedelta(days=1)).isoformat()},
        }
        assert is_expired(coupon)


class TestIsSpecialPromotion:
    """Tests for is_special_promotion()."""

    def test_special_promotion_true(self) -> None:
        assert is_special_promotion({"specialPromotion": True})

    def test_special_promotion_false(self) -> None:
        assert not is_special_promotion({"specialPromotion": False})

    def test_is_special_true(self) -> None:
        assert is_special_promotion({"isSpecial": True})

    def test_is_special_false(self) -> None:
        assert not is_special_promotion({"isSpecial": False})

    def test_neither(self) -> None:
        assert not is_special_promotion({})

    def test_both(self) -> None:
        assert is_special_promotion({"specialPromotion": True, "isSpecial": True})


class TestShouldShow:
    """Tests for should_show()."""

    def test_normal_coupon(self) -> None:
        assert should_show({"title": "My Coupon"})

    def test_online_shop_hidden(self) -> None:
        assert not should_show({"title": "My Coupon", "isOnlineShop": True})

    def test_skip_title_aktionsrabatt(self) -> None:
        assert not should_show({"title": "Aktionsrabatt"})

    def test_skip_title_wiedereroeffnung(self) -> None:
        assert not should_show({"title": "Wiedereröffnung"})

    def test_normal_title_shown(self) -> None:
        assert should_show({"title": "20% Off Fruit"})


class TestCouponLabel:
    """Tests for coupon_label()."""

    def test_title_only(self) -> None:
        assert coupon_label({"title": "Apples"}) == "Apples"

    def test_title_and_discount(self) -> None:
        coupon = {"title": "Apples", "discount": {"title": "20%"}}
        assert coupon_label(coupon) == "20% Apples"

    def test_title_discount_and_description(self) -> None:
        coupon = {
            "title": "Apples",
            "discount": {"title": "20%", "description": "all varieties"},
        }
        assert coupon_label(coupon) == "20% Apples (all varieties)"

    def test_title_and_description_no_discount_title(self) -> None:
        coupon = {"title": "Apples", "discount": {"description": "fresh only"}}
        assert coupon_label(coupon) == "Apples (fresh only)"

    def test_no_discount_key(self) -> None:
        assert coupon_label({"title": "Apples"}) == "Apples"
