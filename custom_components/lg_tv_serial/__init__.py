"""The LG TV Serial integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry, OperationNotAllowed
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from custom_components.lg_tv_serial.lib import LgTv

from .const import DOMAIN, LOGGER
from .coordinator import LgTvCoordinator

# TODO List the platforms that you want to support.
# For your initial PR, limit it to 1 platform.
PLATFORMS: list[Platform] = [Platform.MEDIA_PLAYER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up LG TV Serial from a config entry."""

    hass.data.setdefault(DOMAIN, {})
    # TODO 1. Create API instance
    api = LgTv(entry.data["serial_url"])

    # TODO 2. Validate the API connection (and authentication)
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
        await api.connect(on_disconnect)
    except ConnectionError as e:
        raise ConfigEntryNotReady("Could not connect to LG TV: %s" % entry.title)

    coordinator = LgTvCoordinator(hass, api)
    await coordinator.async_config_entry_first_refresh()


    # TODO 3. Store an API object for your platforms to access
    # hass.data[DOMAIN][entry.entry_id] = MyApi(...)
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator:LgTvCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.api.close()

    return unload_ok
