from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Coroutine

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.helpers.entity import EntityCategory, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import DEFAULT_DEVICE_NAME, DOMAIN
from .coordinator import CoordinatorData, LgTvCoordinator
from .lgtv_api import EnergySaving, LgTv


@dataclass(frozen=True, kw_only=True)
class LgTvSelectEntityDescription(SelectEntityDescription):
    is_supported: Callable[[LgTv, CoordinatorData], bool] = lambda api, data: True
    is_available: Callable[[LgTv, CoordinatorData], bool] = lambda api, data: True
    select_option_fn: Callable[[LgTv, str], Coroutine] = None  # type: ignore[assignment]

async def select_energy_saving(api: LgTv, option:str) -> None:
    value = [
        e.value
        for e in EnergySaving
        if slugify(e.name) == option
    ]

    if len(value) == 1:
        await api.set_energy_saving(value[0])


ENTITY_DESCRIPTIONS = [
    LgTvSelectEntityDescription(  # type: ignore
        key="energy_saving",  # type: ignore
        icon="mdi:leaf",  # type: ignore
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default = False,
        options = [slugify(e.name) for e in EnergySaving],
        is_available=lambda api, coordinator_data: coordinator_data.energy_saving is not None and coordinator_data.power_on is True,
        select_option_fn = select_energy_saving
    ),
]

async def async_setup_entry(hass, config_entry, async_add_entities):

    coordinator: LgTvCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    entities: list[SelectEntity] = []

    for entity_description in ENTITY_DESCRIPTIONS:
        if entity_description.is_supported(coordinator.api, coordinator.data):
            entities.append(LgTvSelect(config_entry.entry_id, coordinator, entity_description))

    async_add_entities(entities)


class LgTvSelect(CoordinatorEntity, SelectEntity):
    """Representation of a select on a LG TV."""

    _attr_has_entity_name = True

    def __init__(
        self,
        configentry_id: str,
        coordinator: LgTvCoordinator,
        entity_description: LgTvSelectEntityDescription,
    ):
        super().__init__(coordinator)
        self.coordinator: LgTvCoordinator

        self.entity_description: LgTvSelectEntityDescription = entity_description
        self._attr_translation_key = self.entity_description.key

        self._attr_unique_id = f"{configentry_id}_select_{self.entity_description.key}"

        self._attr_device_info = DeviceInfo(
            name=DEFAULT_DEVICE_NAME,  # API does not expose a name. Pick a decent default, user can change
            identifiers={(DOMAIN, configentry_id)},
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.entity_description.is_available(self.coordinator.api, self.coordinator.data)

    @property
    def current_option(self) -> str | None:
        """Return the selected entity option to represent the entity state."""
        return slugify(getattr(self.coordinator.data, self.entity_description.key).name)

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self.entity_description.select_option_fn(self.coordinator.api, option)
        await self.coordinator.async_request_refresh()
