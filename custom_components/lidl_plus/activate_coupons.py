from datetime import UTC, datetime

from .api import LidlPlusApiClient
from .const import LOGGER


async def activate_coupons(client: LidlPlusApiClient) -> int:
    LOGGER.info("Activating all available coupons")
    await client.get_access_token()

    activated = 0

    try:
        coupons = await client.coupons()
        for section in coupons.get("sections", []):
            for coupon in section.get("coupons", []):
                if coupon["isActivated"]:
                    continue
                end = coupon.get("endValidityDate")
                if end and datetime.fromisoformat(end) < datetime.now(UTC):
                    continue
                start = coupon.get("startValidityDate")
                if start and datetime.fromisoformat(start) > datetime.now(UTC):
                    continue
                LOGGER.info("Activating coupon: %s", coupon["title"])
                await client.activate_coupon(coupon["id"])
                activated += 1
    except Exception:
        LOGGER.warning("Failed to fetch/activate V2 coupons")

    try:
        coupons_v1 = await client.coupon_promotions_v1()
        for section in coupons_v1.get("sections", []):
            for coupon in section.get("promotions", []):
                if coupon["isActivated"]:
                    continue
                validity = coupon.get("validity", {})
                if datetime.fromisoformat(validity["end"]) < datetime.now(UTC):
                    continue
                if datetime.fromisoformat(validity["start"]) > datetime.now(UTC):
                    continue
                LOGGER.info("Activating coupon v1: %s", coupon["title"])
                await client.activate_coupon_promotion_v1(coupon["id"])
                activated += 1
    except Exception:
        LOGGER.warning("Failed to fetch/activate V1 coupons")

    LOGGER.info("Activated %d coupons", activated)
    return activated
