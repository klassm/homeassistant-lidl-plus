"""Adds config flow for Blueprint."""

from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_TOKEN, CONF_COUNTRY, CONF_LANGUAGE, CONF_NAME
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from slugify import slugify
from .exceptions import LoginError

from .api import (
    LidlPlusApiClient,
)
from .const import DOMAIN, LOGGER


class LidlPlusConfigFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(
            self,
            user_input: dict | None = None,
    ) -> config_entries.ConfigFlowResult:
        _errors = {}
        if user_input is not None:
            try:
                await self._test_credentials(
                    token=user_input[CONF_TOKEN],
                    country=user_input[CONF_COUNTRY],
                    language=user_input[CONF_LANGUAGE],
                )
            except LoginError as exception:
                LOGGER.warning(exception)
                _errors["base"] = "auth"
            else:
                await self.async_set_unique_id(
                    ## Do NOT use this in production code
                    ## The unique_id should never be something that can change
                    ## https://developers.home-assistant.io/docs/config_entries_config_flow_handler#unique-ids
                    unique_id=slugify(user_input[CONF_NAME])
                )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_NAME,
                        default=(user_input or {}).get(CONF_NAME, "Lidl"),
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.TEXT,
                        ),
                    ),
                    vol.Required(
                        CONF_TOKEN,
                        default=(user_input or {}).get(CONF_TOKEN, vol.UNDEFINED),
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD,
                        ),
                    ),
                    vol.Required(CONF_COUNTRY,
                                 default=(user_input or {}).get(CONF_COUNTRY, "DE")
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.TEXT,
                        ),
                    ),
                    vol.Required(CONF_LANGUAGE,
                                 default=(user_input or {}).get(CONF_LANGUAGE, "de")
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.TEXT,
                        ),
                    ),
                },
            ),
            errors=_errors,
        )

    async def _test_credentials(self, token: str, country: str, language: str) -> None:
        client = LidlPlusApiClient(
            refresh_token=token,
            country=country,
            language=language,
            session=async_create_clientsession(self.hass),
        )
        await client.get_access_token()
