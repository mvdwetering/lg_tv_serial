"""The LG TV Serial integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry, OperationNotAllowed
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.service import async_extract_config_entry_ids
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.config_validation import make_entity_service_schema


from .const import (
    ATTR_COMMAND1,
    ATTR_COMMAND2,
    ATTR_DATA,
    DOMAIN,
    LOGGER,
    SERVICE_SEND_RAW,
)
from .coordinator import LgTvCoordinator
from .lgtv_api import LgTv
from homeassistant.helpers import config_validation as cv
import voluptuous as vol # type: ignore[import]

PLATFORMS: list[Platform] = [Platform.MEDIA_PLAYER, Platform.REMOTE, Platform.SWITCH, Platform.SELECT]


LG_TV_SERIAL_SEND_RAW_SCHEMA = make_entity_service_schema(
    {
        vol.Required(ATTR_COMMAND1): cv.string,
        vol.Required(ATTR_COMMAND2): cv.string,
        vol.Optional(ATTR_DATA): cv.string,
    }
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:

    async def async_send_raw(call):
        """
        Send raw command to the TV
        """

        config_entry_ids = await async_extract_config_entry_ids(hass, call)
        for config_entry_id in config_entry_ids:
            # Need to check if it is our config entry since async_extract_config_entry_ids
            # can return config entries from other integrations also
            # (e.g. area id or devices with entities from multiple integrations)
            if config_entry := hass.config_entries.async_get_entry(config_entry_id):
                if (
                    config_entry.domain == DOMAIN
                    and config_entry.entry_id in hass.data[DOMAIN]
                ):

                    command1 = call.data.get(ATTR_COMMAND1)
                    command2 = call.data.get(ATTR_COMMAND2)
                    data = call.data.get(ATTR_DATA)

                    if not (len(command1) == 1 and len(command2) == 1):
                        LOGGER.error("Command 1 and Command 2 must be each 1 character")
                        return

                    if len(data) < 2 or len(data) > 12 or len(data) % 2 != 0:
                        LOGGER.error(
                            "Data must be a hex string with 1 to 6 bytes (2-12 hex digits)"
                        )
                        return

                    coordinator: LgTvCoordinator = hass.data[DOMAIN][
                        config_entry.entry_id
                    ]
                    await coordinator.api.send_raw(command1, command2, data)

    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_RAW,
        async_send_raw,
        schema=LG_TV_SERIAL_SEND_RAW_SCHEMA,
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up LG TV Serial from a config entry."""
    LOGGER.info("async_setup_entry")

    hass.data.setdefault(DOMAIN, {})

    api = LgTv(entry.data["serial_url"])

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
        # Do something with the connection to make sure it can transfer data
        if await api.get_power_on() is None:
            raise ConfigEntryNotReady(f"Could not get data from LG TV: {entry.title}")

        coordinator = LgTvCoordinator(hass, entry, api)
        await coordinator.async_config_entry_first_refresh()
        hass.data[DOMAIN][entry.entry_id] = coordinator

        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

        return True
    except ConnectionError as e:
        raise ConfigEntryNotReady(f"Could not connect to LG TV: {entry.title}")



async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator: LgTvCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.api.close()

    return unload_ok
