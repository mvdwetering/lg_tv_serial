"""The LG TV Serial integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry, OperationNotAllowed
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady, ServiceValidationError
from homeassistant.helpers.typing import ConfigType


from .const import (
    ATTR_COMMAND_1,
    ATTR_COMMAND_2,
    ATTR_CONFIG_ENTRY,
    ATTR_DATA_0,
    ATTR_DATA_1,
    ATTR_DATA_2,
    ATTR_DATA_3,
    ATTR_DATA_4,
    ATTR_DATA_5,
    DOMAIN,
    LOGGER,
    SERVICE_SEND_RAW,
)
from .coordinator import LgTvCoordinator
from .lgtv_api import LgTv
from homeassistant.helpers import config_validation as cv
import voluptuous as vol  # type: ignore[import]

PLATFORMS: list[Platform] = [
    Platform.MEDIA_PLAYER,
    Platform.REMOTE,
    Platform.SWITCH,
    Platform.SELECT,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:

    async def async_send_raw(call: ServiceCall):
        """
        Send raw command to the TV
        """

        config_entry = hass.config_entries.async_get_entry(call.data.get(ATTR_CONFIG_ENTRY))

        if config_entry is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="config_entry_not_found",
                translation_placeholders={"config_entry": call.data.get(ATTR_CONFIG_ENTRY)},
            )

        command1 = call.data.get(ATTR_COMMAND_1)
        if len(command1) != 1:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_command_value",
                translation_placeholders={"command": ATTR_COMMAND_1, "wrong_value": command1},
            )

        command2 = call.data.get(ATTR_COMMAND_2)
        if len(command2) != 1:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_command_value",
                translation_placeholders={"command": ATTR_COMMAND_2, "wrong_value": command2},
            )

        data: list[int | None] = []
        for attr in [
            ATTR_DATA_0,
            ATTR_DATA_1,
            ATTR_DATA_2,
            ATTR_DATA_3,
            ATTR_DATA_4,
            ATTR_DATA_5,
        ]:
            value = call.data.get(attr)
            if value is None:
                data.append(None)
            else:
                try:
                    parsed_value = int(str(value).strip(), 0)  # 0 = auto base
                    if 0 <= parsed_value <= 255:
                        data.append(parsed_value)
                    else:
                        raise ValueError
                except (TypeError, ValueError) as e:
                    raise ServiceValidationError(
                        translation_domain=DOMAIN,
                        translation_key="invalid_data_value",
                        translation_placeholders={"data_byte": attr, "wrong_value": value},
                    ) from e

        coordinator: LgTvCoordinator = hass.data[DOMAIN][
            config_entry.entry_id
        ]
        await coordinator.api.send_raw(command1, command2, data)

    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_RAW,
        async_send_raw,
        schema=vol.Schema(
            {
                vol.Required(ATTR_CONFIG_ENTRY): cv.string,
                vol.Required(ATTR_COMMAND_1): cv.string,
                vol.Required(ATTR_COMMAND_2): cv.string,
                vol.Required(ATTR_DATA_0): cv.string,
                vol.Optional(ATTR_DATA_1): cv.string,
                vol.Optional(ATTR_DATA_2): cv.string,
                vol.Optional(ATTR_DATA_3): cv.string,
                vol.Optional(ATTR_DATA_4): cv.string,
                vol.Optional(ATTR_DATA_5): cv.string,
            }
        )
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up LG TV Serial from a config entry."""
    LOGGER.info("async_setup_entry")

    hass.data.setdefault(DOMAIN, {})

    api = LgTv(
        entry.data["serial_url"],
        entry.data.get("set_id", 0),
        entry.data.get("rtscts", False),
        entry.data.get("dsrdtr", False),
        entry.data.get("xonxoff", False)
    )

    @callback
    async def on_disconnect():
        LOGGER.info("Disconnected, attempt to reload integration")
        # Reload the entry on disconnect.
        # HA will take care of re-init and retries
        try:
            # Call reload in a task, otherwise it seems to lock up
            hass.async_create_task(hass.config_entries.async_reload(entry.entry_id))
        except OperationNotAllowed:  # pragma: no cover
            # Can not reload when during setup
            # Which is fine, so just let it go
            LOGGER.debug("Operation not allowed", exc_info=True)

    try:
        await api.connect(on_disconnect)

        coordinator = LgTvCoordinator(hass, entry, api)
        await coordinator.async_config_entry_first_refresh()
        hass.data[DOMAIN][entry.entry_id] = coordinator

        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

        return True
    except ConnectionError as e:
        raise ConfigEntryNotReady(f"Could not connect to LG TV: {entry.title}") from e


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator: LgTvCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.api.close()

    return unload_ok
