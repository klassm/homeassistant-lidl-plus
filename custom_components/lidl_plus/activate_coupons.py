from datetime import datetime, timezone

from .data import LidlPlusData
from logging import WARNING, Logger, getLogger, INFO, DEBUG, ERROR


async def activate_coupons(entry: LidlPlusData):
    """Activate all available coupons"""
    logger = getLogger(__package__)
    logger.info(f"Activating all available coupons")
    client = entry.client
    access_token = await client.get_access_token()

    i = 0

    coupons = await client.coupons(access_token)
    for section in coupons.get("sections", {}):
        for coupon in section.get("coupons", {}):
            if coupon["isActivated"]:
                continue
            if datetime.fromisoformat(coupon["startValidityDate"]) > datetime.now(
                timezone.utc
            ):
                continue
            if datetime.fromisoformat(coupon["endValidityDate"]) < datetime.now(
                timezone.utc
            ):
                continue
            logger.debug("activating coupon: ", coupon["title"])
            await client.activate_coupon(access_token, coupon["id"])
            i += 1

    # Some coupons are only available through V1 API
    coupons = await client.coupon_promotions_v1(access_token)
    for section in coupons.get("sections", {}):
        for coupon in section.get("promotions", {}):
            if coupon["isActivated"]:
                continue
            validity = coupon.get("validity", {})
            if datetime.fromisoformat(validity["start"]) > datetime.now(timezone.utc):
                continue
            if datetime.fromisoformat(validity["end"]) < datetime.now(timezone.utc):
                continue
            print("activating coupon v1: ", coupon["title"])
            await client.activate_coupon_promotion_v1(access_token, coupon["id"])
            i += 1

    logger.info(f"Activated {i} coupons")
