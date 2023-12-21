from __future__ import annotations
from typing import List

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity


from .const import DOMAIN
from .coordinator import LgTvCoordinator
from .lgtv_api import Input

SUPPORTED_MEDIAPLAYER_COMMANDS = (
    MediaPlayerEntityFeature.TURN_ON | MediaPlayerEntityFeature.TURN_OFF
)

SOURCE_INPUT_MAPPING = {
    Input.DTV: "Digital TV",
    Input.CADTV: "Cable Digital TV",
    Input.SATELLITE_DTV__ISDB_BS_JAPAN: "Satellite TV / ISDB BS (Japan)",
    Input.ISDB_CS1_JAPAN: "ISDB CS1",
    Input.ISDB_CS2_JAPAN: "ISDB CS2",
    Input.CATV: "Cable TV",
    Input.AV1: "AV 1",
    Input.AV2: "AV 2",
    Input.COMPONENT1: "Component 1",
    Input.COMPONENT2: "Component 2",
    Input.RGB: "RGB",
    Input.HDMI1: "HDMI1",
    Input.HDMI2: "HDMI2",
    Input.HDMI3: "HDMI3",
    Input.HDMI4: "HDMI4",
}

# Also add the reverse mapping to SOURCE_INPUT_MAPPING
# This works because the values do not overlap
reverse_mapping = {}
for k, v in SOURCE_INPUT_MAPPING.items():
    reverse_mapping[v] = k
SOURCE_INPUT_MAPPING = SOURCE_INPUT_MAPPING | reverse_mapping


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities
):
    coordinator: LgTvCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([LgTvMediaPlayer(coordinator, config_entry.entry_id)], True)


class LgTvMediaPlayer(CoordinatorEntity, MediaPlayerEntity):
    """LG TV mediaplayer."""

    _attr_name = None
    _attr_has_entity_name = True
    _attr_device_class = MediaPlayerDeviceClass.TV

    def __init__(self, coordinator: LgTvCoordinator, configentry_id: str) -> None:
        super().__init__(coordinator)
        self.coordinator: LgTvCoordinator
        self._configentry_id = configentry_id

        self._attr_unique_id = configentry_id
        self._attr_device_info = {
            "name": "LG TV",  # API does not expose a name. Pick a decent default, user can change
            "identifiers": {(DOMAIN, configentry_id)},
        }

    def schedule_ha_update(func):
        async def _decorator(self: LgTvMediaPlayer, *args, **kwargs):
            await func(self, *args, **kwargs)
            # Use request_async_refresh so the debouncer is used to delay the request a bit
            # await self.coordinator.async_request_refresh()
            self.async_write_ha_state()

        return _decorator

    @property
    def supported_features(self):
        """Flag of media commands that are supported."""
        features = SUPPORTED_MEDIAPLAYER_COMMANDS
        if self.coordinator.data.volume is not None:
            features |= (
                MediaPlayerEntityFeature.VOLUME_SET
                | MediaPlayerEntityFeature.VOLUME_STEP
            )
        if self.coordinator.data.mute is not None:
            features |= MediaPlayerEntityFeature.VOLUME_MUTE
        if self.coordinator.data.input is not None:
            features |= MediaPlayerEntityFeature.SELECT_SOURCE
        return features

    @property
    def state(self) -> MediaPlayerState | None:
        """Return the state of the entity."""
        if self.coordinator.data.power_on:
            return MediaPlayerState.ON
        return MediaPlayerState.STANDBY

    @schedule_ha_update
    async def async_turn_on(self):
        """Turn the media player on."""
        await self.coordinator.api.set_power_on(True)
        self.coordinator.data.power_on = True
        # Use request_async_refresh so the debouncer is used to delay the request a bit
        await self.coordinator.async_request_refresh()

    @schedule_ha_update
    async def async_turn_off(self):
        """Turn off media player."""
        await self.coordinator.api.set_power_on(False)
        self.coordinator.data.power_on = False

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        return (
            self.coordinator.data.volume / 100.0
            if self.coordinator.data.volume is not None
            else None
        )

    @schedule_ha_update
    async def async_set_volume_level(self, volume) -> None:
        """Set volume level, convert range from 0..1."""
        tv_volume = int(volume * 100)
        await self.coordinator.api.set_volume(tv_volume)
        self.coordinator.data.volume = tv_volume

    @schedule_ha_update
    async def async_volume_up(self) -> None:
        """Volume up media player."""
        await self.coordinator.api.volume_up()
        self.coordinator.data.volume = min(100, self.coordinator.data.volume + 1)

    @schedule_ha_update
    async def async_volume_down(self) -> None:
        """Volume down media player."""
        await self.coordinator.api.volume_down()
        self.coordinator.data.volume = max(0, self.coordinator.data.volume - 1)

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self.coordinator.data.mute

    @schedule_ha_update
    async def async_mute_volume(self, mute):
        """Mute (true) or unmute (false) media player."""
        await self.coordinator.api.set_mute(mute)
        self.coordinator.data.mute = mute

    @property
    def source(self):
        """Return the current input source."""
        if self.coordinator.data.input is not None:
            return SOURCE_INPUT_MAPPING[self.coordinator.data.input]
        return None

    @schedule_ha_update
    async def async_select_source(self, source):
        """Select input source."""
        await self.coordinator.api.set_input(SOURCE_INPUT_MAPPING[source])
        self.coordinator.data.input = SOURCE_INPUT_MAPPING[source]

    @property
    def source_list(self) -> List[str]:
        """List of available sources."""
        sources = []
        for k in SOURCE_INPUT_MAPPING.keys():
            if isinstance(k, str):
                sources.append(k)
        return sorted(sources, key=str.lower)
