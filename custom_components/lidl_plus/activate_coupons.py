from .api import LidlPlusApiClient
from .const import LOGGER
from .coupon_helpers import coupon_label, is_expired


async def activate_coupons(client: LidlPlusApiClient) -> int:
    LOGGER.info("Activating all available coupons")
    await client.get_access_token()

    activated = 0

    try:
        coupons = await client.coupons()
        for section in coupons.get("sections", []):
            for coupon in section.get("coupons", []):
                if coupon["isActivated"] or is_expired(coupon):
                    continue
                LOGGER.info("Activating coupon: %s", coupon_label(coupon))
                await client.activate_coupon(coupon["id"])
                activated += 1
    except Exception as err:
        LOGGER.warning("Failed to fetch/activate V2 coupons: %s", err)

    try:
        coupons_v1 = await client.coupon_promotions_v1()
        for section in coupons_v1.get("sections", []):
            for coupon in section.get("promotions", []):
                if coupon["isActivated"] or is_expired(coupon):
                    continue
                LOGGER.info("Activating coupon v1: %s", coupon_label(coupon))
                await client.activate_coupon_promotion_v1(coupon["id"])
                activated += 1
    except Exception as err:
        LOGGER.warning("Failed to fetch/activate V1 coupons: %s", err)

    LOGGER.info("Activated %d coupons", activated)
    return activated
