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
        """Test that a future end date is not expired."""
        coupon = {
            "endValidityDate": (datetime.now(UTC) + timedelta(days=30)).isoformat()
        }
        assert not is_expired(coupon)

    def test_expired_via_end_validity_date(self) -> None:
        """Test that a past end date is expired."""
        coupon = {
            "endValidityDate": (datetime.now(UTC) - timedelta(days=1)).isoformat()
        }
        assert is_expired(coupon)

    def test_not_yet_valid_via_start_validity_date(self) -> None:
        """Test that a future start date is not yet valid."""
        coupon = {
            "startValidityDate": (datetime.now(UTC) + timedelta(days=1)).isoformat()
        }
        assert is_expired(coupon)

    def test_expired_via_validity_end(self) -> None:
        """Test that a past validity.end is expired."""
        coupon = {
            "validity": {"end": (datetime.now(UTC) - timedelta(days=1)).isoformat()}
        }
        assert is_expired(coupon)

    def test_not_yet_valid_via_validity_start(self) -> None:
        """Test that a future validity.start is not yet valid."""
        coupon = {
            "validity": {"start": (datetime.now(UTC) + timedelta(days=1)).isoformat()}
        }
        assert is_expired(coupon)

    def test_no_dates_means_not_expired(self) -> None:
        """Test that a coupon with no dates is not expired."""
        assert not is_expired({})

    def test_currently_valid(self) -> None:
        """Test that a currently active date range is not expired."""
        coupon = {
            "startValidityDate": (datetime.now(UTC) - timedelta(days=1)).isoformat(),
            "endValidityDate": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
        }
        assert not is_expired(coupon)

    def test_validity_dict_overrides(self) -> None:
        """Test that the validity dict takes precedence over top-level dates."""
        now = datetime.now(UTC)
        coupon = {
            "endValidityDate": (now + timedelta(days=30)).isoformat(),
            "validity": {"end": (now - timedelta(days=1)).isoformat()},
        }
        assert is_expired(coupon)


class TestIsSpecialPromotion:
    """Tests for is_special_promotion()."""

    def test_meal_deal_is_special(self) -> None:
        """Test that Meal Deal tagged coupons are in-store-only specials."""
        assert is_special_promotion({"specialPromotion": {"tag": "Meal Deal"}})

    def test_fur_dich_is_not_special(self) -> None:
        """Test that 'Für Dich' personal coupons are NOT in-store-only."""
        assert not is_special_promotion({"specialPromotion": {"tag": "Für Dich"}})

    def test_empty_special_promotion(self) -> None:
        """Test that empty specialPromotion dict is not special."""
        assert not is_special_promotion({"specialPromotion": {}})

    def test_no_special_promotion_key(self) -> None:
        """Test that missing specialPromotion is not special."""
        assert not is_special_promotion({})

    def test_special_promotion_without_tag(self) -> None:
        """Test that specialPromotion without tag is not special."""
        assert not is_special_promotion({"specialPromotion": {"other": "value"}})

    def test_is_special_flag_ignored(self) -> None:
        """Test that isSpecial=true alone is not treated as in-store-only."""
        assert not is_special_promotion({"isSpecial": True})

    def test_is_special_true_with_meal_deal_tag(self) -> None:
        """Test that isSpecial=true with Meal Deal tag is in-store-only."""
        assert is_special_promotion(
            {"specialPromotion": {"tag": "Meal Deal"}, "isSpecial": True}
        )


class TestShouldShow:
    """Tests for should_show()."""

    def test_normal_coupon(self) -> None:
        """Test that a normal coupon is shown."""
        assert should_show({"title": "My Coupon"})

    def test_online_shop_hidden(self) -> None:
        """Test that online-shop coupons are hidden."""
        assert not should_show({"title": "My Coupon", "isOnlineShop": True})

    def test_skip_title_aktionsrabatt(self) -> None:
        """Test that 'Aktionsrabatt' is hidden."""
        assert not should_show({"title": "Aktionsrabatt"})

    def test_skip_title_wiedereroeffnung(self) -> None:
        """Test that 'Wiedereröffnung' is hidden."""
        assert not should_show({"title": "Wiedereröffnung"})

    def test_normal_title_shown(self) -> None:
        """Test that a regular title is shown."""
        assert should_show({"title": "20% Off Fruit"})


class TestCouponLabel:
    """Tests for coupon_label()."""

    def test_title_only(self) -> None:
        """Test label with only a title."""
        assert coupon_label({"title": "Apples"}) == "Apples"

    def test_title_and_discount(self) -> None:
        """Test label with discount title prepended."""
        coupon = {"title": "Apples", "discount": {"title": "20%"}}
        assert coupon_label(coupon) == "20% Apples"

    def test_title_discount_and_description(self) -> None:
        """Test label with discount title and description."""
        coupon = {
            "title": "Apples",
            "discount": {"title": "20%", "description": "all varieties"},
        }
        assert coupon_label(coupon) == "20% Apples (all varieties)"

    def test_title_and_description_no_discount_title(self) -> None:
        """Test label with description but no discount title."""
        coupon = {"title": "Apples", "discount": {"description": "fresh only"}}
        assert coupon_label(coupon) == "Apples (fresh only)"

    def test_no_discount_key(self) -> None:
        """Test label with no discount dict at all."""
        assert coupon_label({"title": "Apples"}) == "Apples"
