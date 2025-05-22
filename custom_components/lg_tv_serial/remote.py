from __future__ import annotations

import asyncio
from typing import Any, Iterable

from homeassistant.components.remote import (
    ATTR_DELAY_SECS,
    ATTR_NUM_REPEATS,
    DEFAULT_DELAY_SECS,
    DEFAULT_NUM_REPEATS,
    RemoteEntity,
)
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import LgTvCoordinator

from .const import (
    ATTR_COMMANDS,
    DEFAULT_DEVICE_NAME,
    DOMAIN,
)

from .lgtv_api import RemoteKeyCode
from .helpers import update_ha_state


async def async_setup_entry(hass, config_entry, async_add_entities):
    coordinator: LgTvCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([LgTvRemote(coordinator, config_entry.entry_id)])


class LgTvRemote(CoordinatorEntity, RemoteEntity):
    """Representation of a remote of an LG TV."""

    _attr_has_entity_name = True
    _attr_translation_key = "remote_control"
    _unrecorded_attributes = frozenset({ATTR_COMMANDS})

    def __init__(self, coordinator: LgTvCoordinator, configentry_id: str):
        super().__init__(coordinator)
        self.coordinator: LgTvCoordinator

        self._attr_unique_id = configentry_id
        self._attr_device_info = DeviceInfo(
            name=DEFAULT_DEVICE_NAME,  # API does not expose a name. Pick a decent default, user can change
            identifiers={(DOMAIN, configentry_id)},
        )

        self._attr_extra_state_attributes = {
            ATTR_COMMANDS: [code.name.lower() for code in RemoteKeyCode]
        }

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return bool(
            self.coordinator.data.power_on and self.coordinator.data.power_synced
        )

    @update_ha_state
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Send the power on command."""
        await self.coordinator.api.set_power_on(True)
        self.coordinator.data.power_on = True
        self.coordinator.data.power_synced = False

    @update_ha_state
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Send the power off command."""
        await self.coordinator.api.set_power_on(False)
        self.coordinator.data.power_on = False
        self.coordinator.data.power_synced = False

    async def async_send_command(self, command: Iterable[str], **kwargs):
        """Send commands to a device."""
        num_repeats = kwargs.get(ATTR_NUM_REPEATS, DEFAULT_NUM_REPEATS)
        delay_secs = kwargs.get(ATTR_DELAY_SECS, DEFAULT_DELAY_SECS)

        first = True
        for _ in range(num_repeats):
            for cmd in command:
                if not first:
                    await asyncio.sleep(delay_secs)
                first = False

                await self.coordinator.api.remote_key(RemoteKeyCode[cmd.upper()])
