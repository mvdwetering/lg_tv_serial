"""The LG TV Serial integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry, OperationNotAllowed
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady


from .const import DOMAIN, LOGGER
from .coordinator import LgTvCoordinator
from .lgtv_api import LgTv

PLATFORMS: list[Platform] = [Platform.MEDIA_PLAYER, Platform.REMOTE, Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up LG TV Serial from a config entry."""

    hass.data.setdefault(DOMAIN, {})

    api = LgTv(entry.data["serial_url"])

    async def on_disconnect():
        LOGGER.debug("Disconnected, attempt to reload integration")
        # Reload the entry on disconnect.
        # HA will take care of re-init and retries
        try:
            await hass.config_entries.async_reload(entry.entry_id)
        except OperationNotAllowed:  # pragma: no cover
            # Can not reload when during setup
            # Which is fine, so just let it go
            pass

    try:
        await api.connect()
        # Do something with the connection to make sure it can transfer data
        if await api.get_power_on() is None:
            raise ConfigEntryNotReady(f"Could not get data from LG TV: {entry.title}")
    except ConnectionError as e:
        raise ConfigEntryNotReady(f"Could not connect to LG TV: {entry.title}")

    # Add on_disconnect after connection seems to work.
    # This avoids issues when it gets triggered during initial setup
    # TODO: Should not access private attributes
    api._on_disconnect = on_disconnect

    coordinator = LgTvCoordinator(hass, api)
    await coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator: LgTvCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.api.close()

    return unload_ok
