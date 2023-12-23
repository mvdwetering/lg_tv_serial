from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable, Coroutine

from homeassistant.components.switch import (
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_DEVICE_NAME, DOMAIN
from .coordinator import CoordinatorData, LgTvCoordinator
from .lgtv_api import LgTv


@dataclass
class LgTvSwitchEntityDescription(SwitchEntityDescription):
    is_on: Callable[[CoordinatorData], bool] = None  # type: ignore[assignment]
    turn_on: Callable[[LgTv, CoordinatorData], Coroutine] = None  # type: ignore[assignment]
    turn_off: Callable[[LgTv, CoordinatorData], Coroutine] = None  # type: ignore[assignment]
    is_supported: Callable[[LgTv, CoordinatorData], bool] = lambda api, data: True
    is_available: Callable[[LgTv, CoordinatorData], bool] = lambda api, data: True


async def set_remote_control_lock(api:LgTv, data:CoordinatorData, value:bool):
    await api.set_remote_control_lock(value)
    data.remote_control_lock = value


ENTITY_DESCRIPTIONS = [
    LgTvSwitchEntityDescription(  # type: ignore
        key="remote_control_lock",  # type: ignore
        icon="mdi:monitor-lock",  # type: ignore
        is_on=lambda coordinator_data: coordinator_data.remote_control_lock == True,
        turn_on=lambda api, data: set_remote_control_lock(api, data, True),
        turn_off=lambda api, data: set_remote_control_lock(api, data, False),
        is_available=lambda api, coordinator_data: coordinator_data.remote_control_lock is not None and coordinator_data.power_on,
    ),
]

async def async_setup_entry(hass, config_entry, async_add_entities):

    coordinator: LgTvCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    entities: list[SwitchEntity] = []

    for entity_description in ENTITY_DESCRIPTIONS:
        if entity_description.is_supported(coordinator.api, coordinator.data):
            entities.append(LgTvSwitch(config_entry.entry_id, coordinator, entity_description))

    async_add_entities(entities)


class LgTvSwitch(CoordinatorEntity, SwitchEntity):
    """Representation of a switch on a Yamaha Ynca device."""

    _attr_has_entity_name = True

    def __init__(
        self,
        configentry_id: str,
        coordinator: LgTvCoordinator,
        entity_description: LgTvSwitchEntityDescription,
    ):
        super().__init__(coordinator)
        self.coordinator: LgTvCoordinator

        self.entity_description: LgTvSwitchEntityDescription = entity_description
        self._attr_translation_key = self.entity_description.key

        self._attr_unique_id = f"{configentry_id}_switch_{self.entity_description.key}"

        self._attr_device_info = {
            "name": DEFAULT_DEVICE_NAME,  # API does not expose a name. Pick a decent default, user can change
            "identifiers": {(DOMAIN, configentry_id)},
        }


    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.entity_description.is_available(self.coordinator.api, self.coordinator.data)

    @property
    def is_on(self) -> bool | None:
        """Return True if entity is on."""
        return self.entity_description.is_on(self.coordinator.data)

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        await self.entity_description.turn_on(self.coordinator.api, self.coordinator.data)
        self.async_write_ha_state()        

    async def async_turn_off(self, **kwargs: Any):
        """Turn the entity off."""
        await self.entity_description.turn_off(self.coordinator.api, self.coordinator.data)
        self.async_write_ha_state()