"""The LG TV Serial integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from custom_components.lg_tv_serial.lib import LgTv

from .const import DOMAIN
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
    await api.connect()

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
