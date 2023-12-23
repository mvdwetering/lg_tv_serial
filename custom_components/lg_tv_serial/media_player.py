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


from .const import DEFAULT_DEVICE_NAME, DOMAIN
from .coordinator import LgTvCoordinator
from .lgtv_api import Input

SUPPORTED_MEDIAPLAYER_COMMANDS = (
    MediaPlayerEntityFeature.TURN_ON | MediaPlayerEntityFeature.TURN_OFF
)

INPUT_SOURCE_MAPPING = {
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
    Input.UNKNOWN: "Unknown",
}

# Also add the reverse mapping to SOURCE_INPUT_MAPPING
# This works because the values do not overlap
SOURCE_INPUT_MAPPING:dict[str, Input] = {}
for k, v in INPUT_SOURCE_MAPPING.items():
    SOURCE_INPUT_MAPPING[v] = k


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities
):
    coordinator: LgTvCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([LgTvMediaPlayer(coordinator, config_entry.entry_id)], True)


def update_ha_state(func):
    async def _decorator(self:LgTvMediaPlayer, *args, **kwargs):
        await func(self, *args, **kwargs)
        # Trigger listeners with new optimistic data
        # Also resets polling delay so won't interfere with turn on/off
        self.coordinator.async_set_updated_data(self.coordinator.data)
        # self.async_write_ha_state()

    return _decorator

class LgTvMediaPlayer(CoordinatorEntity, MediaPlayerEntity):
    """LG TV mediaplayer."""

    _attr_name = None
    _attr_has_entity_name = True
    _attr_device_class = MediaPlayerDeviceClass.TV

    def __init__(self, coordinator: LgTvCoordinator, configentry_id: str) -> None:
        super().__init__(coordinator)
        self.coordinator: LgTvCoordinator

        self._attr_unique_id = configentry_id
        self._attr_device_info = {
            "name": DEFAULT_DEVICE_NAME,  # API does not expose a name. Pick a decent default, user can change
            "identifiers": {(DOMAIN, configentry_id)},
        }

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
        if self.coordinator.data.power_on is False:
            return MediaPlayerState.STANDBY

        if not self.coordinator.data.power_synced:
            # It is busy turning on/off which takes a while
            # There seems to be no way to idicate this.
            # To avoid UI flipping use Buffering as placeholder
            return MediaPlayerState.BUFFERING

        return MediaPlayerState.ON

    @update_ha_state
    async def async_turn_on(self):
        """Turn the media player on."""
        await self.coordinator.api.set_power_on(True)
        self.coordinator.data.power_on = True
        self.coordinator.data.power_synced = False

    @update_ha_state
    async def async_turn_off(self):
        """Turn off media player."""
        await self.coordinator.api.set_power_on(False)
        self.coordinator.data.power_on = False
        self.coordinator.data.power_synced= False

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        return (
            self.coordinator.data.volume / 100.0
            if self.coordinator.data.volume is not None
            else None
        )

    @update_ha_state
    async def async_set_volume_level(self, volume) -> None:
        """Set volume level, convert range from 0..1."""
        tv_volume = int(volume * 100)
        await self.coordinator.api.set_volume(tv_volume)
        self.coordinator.data.volume = tv_volume

    @update_ha_state
    async def async_volume_up(self) -> None:
        """Volume up media player."""
        await self.coordinator.api.volume_up()
        if self.coordinator.data.volume is not None:
            self.coordinator.data.volume = min(100, self.coordinator.data.volume + 1)

    @update_ha_state
    async def async_volume_down(self) -> None:
        """Volume down media player."""
        await self.coordinator.api.volume_down()
        if self.coordinator.data.volume is not None:
            self.coordinator.data.volume = max(0, self.coordinator.data.volume - 1)

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self.coordinator.data.mute

    @update_ha_state
    async def async_mute_volume(self, mute):
        """Mute (true) or unmute (false) media player."""
        await self.coordinator.api.set_mute(mute)
        if self.coordinator.data.mute is not None:
            self.coordinator.data.mute = mute

    @property
    def source(self):
        """Return the current input source."""
        if self.coordinator.data.input is not None:
            return INPUT_SOURCE_MAPPING[self.coordinator.data.input]
        return None

    @update_ha_state
    async def async_select_source(self, source):
        """Select input source."""
        await self.coordinator.api.set_input(SOURCE_INPUT_MAPPING[source])
        if self.coordinator.data.input is not None:
            self.coordinator.data.input = SOURCE_INPUT_MAPPING[source]

    @property
    def source_list(self) -> List[str]:
        """List of available sources."""
        return sorted([v for v in INPUT_SOURCE_MAPPING.values()], key=str.lower)
