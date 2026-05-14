"""Config flow for LG TV Serial integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import selector


from .const import DOMAIN, SERIAL_URL, SET_ID, RTSCTS, DSRDTR
from .lgtv_api import LgTv

_LOGGER = logging.getLogger(__name__)

SERIALX_URL_HANDLERS_DOC = (
    "https://puddly.github.io/serialx/index.html"
)
ESPHOME_SERIAL_PROXY_DOC = (
    "https://esphome.io/components/serial_proxy/"
)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(SERIAL_URL): selector.SerialPortSelector(),
        vol.Required(SET_ID, default=0): vol.All(
            selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=99, mode=selector.NumberSelectorMode.BOX
                ),
            ),
            vol.Coerce(int),
        ),
        vol.Required(RTSCTS, default=False): bool,
        vol.Required(DSRDTR, default=False): bool,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    try:
        async with LgTv(
            data[SERIAL_URL], data[SET_ID], data[RTSCTS], data[DSRDTR]
        ) as api:
            await api.connect()
            if await api.get_power_on() is None:
                raise CannotConnect("No response from LG TV")
    except ConnectionError as e:
        raise CannotConnect("Could not connect to LG TV, check port settings") from e

    return {"title": "LG TV"}


class LgTvConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for LG TV Serial."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
            description_placeholders={"serialx_url": SERIALX_URL_HANDLERS_DOC, "esphome_url": ESPHOME_SERIAL_PROXY_DOC},
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of an existing entry."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    self._get_reconfigure_entry(),
                    data_updates=user_input,
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
            description_placeholders={
                "serialx_url": SERIALX_URL_HANDLERS_DOC,
                "esphome_url": ESPHOME_SERIAL_PROXY_DOC,
            },
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
