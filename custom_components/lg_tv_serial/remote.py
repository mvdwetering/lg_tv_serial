from __future__ import annotations

from typing import Any, Iterable

from homeassistant.components.remote import RemoteEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import LgTvCoordinator

from .const import (
    ATTR_COMMANDS,
    DEFAULT_DEVICE_NAME,
    DOMAIN,
)

from .lgtv_api import RemoteKeyCode

async def async_setup_entry(hass, config_entry, async_add_entities):
    coordinator: LgTvCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([LgTvRemote(coordinator, config_entry.entry_id)])

class LgTvRemote(CoordinatorEntity, RemoteEntity):
    """Representation of a remote of an LG TV."""

    _attr_name = "Remote"
    _attr_has_entity_name = True
    _unrecorded_attributes = frozenset({ATTR_COMMANDS})

    def __init__(
        self,
        coordinator: LgTvCoordinator,
        configentry_id: str
    ):
        super().__init__(coordinator)
        self.coordinator: LgTvCoordinator

        self._attr_unique_id = configentry_id
        self._attr_device_info = {
            "name": DEFAULT_DEVICE_NAME,  # API does not expose a name. Pick a decent default, user can change
            "identifiers": {(DOMAIN, configentry_id)},
        }

        self._attr_extra_state_attributes = {ATTR_COMMANDS: [code.name.lower() for code in RemoteKeyCode]}

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Send the power on command."""
        await self.coordinator.api.set_power_on(True)


    async def async_turn_off(self, **kwargs: Any) -> None:
        """Send the power off command."""
        self.send_command(["standby"])

    async def async_send_command(self, command: Iterable[str], **kwargs):
        """Send commands to a device."""
        for cmd in command:
            self.coordinator.api.remote_key(RemoteKeyCode[cmd])
