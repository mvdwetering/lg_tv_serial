"""Coordinator for the LG TV integration."""

from dataclasses import dataclass
import datetime

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
)

from .const import COORDINATOR_UPDATE_INTERVAL, LOGGER
from .lgtv_api import LgTv, Input

@dataclass
class CoordinatorData:
    power_on:bool|None = None
    mute:bool|None = None
    volume:int|None = None
    input:Input|None = None
    remote_control_lock:bool|None = None
    power_synced:bool|None = None


class LgTvCoordinator(DataUpdateCoordinator):
    """My custom coordinator."""

    def __init__(self, hass, entry:ConfigEntry, api: LgTv):
        """Initialize my coordinator."""
        super().__init__(
            hass,
            LOGGER,
            # Name of the data. For logging purposes.
            name="LG TV",
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=datetime.timedelta(seconds=COORDINATOR_UPDATE_INTERVAL),
            request_refresh_debouncer=Debouncer(
                hass, LOGGER, cooldown=1.0, immediate=False
            ),
        )
        self.api = api
        self.data:CoordinatorData = CoordinatorData()
        self.config_entry = entry

    async def _async_update_data(self):
        """Fetch data from API endpoint."""
        # Note: asyncio.TimeoutError and aiohttp.ClientError are already
        # handled by the data update coordinator.
        try:
            self.data.power_on = await self.api.get_power_on()
            if self.data.power_on:
                self.data.mute = await self.api.get_mute()
                self.data.volume = await self.api.get_volume()
                self.data.input = await self.api.get_input()
                self.data.remote_control_lock = await self.api.get_remote_control_lock()
            else:
                self.data.mute = None
                self.data.volume = None
                self.data.input = None
                self.data.remote_control_lock = None
            self.data.power_synced = True
        except ConnectionError:
            LOGGER.debug("ConnectionError, reload integration", exc_info=True)
            # Call reload in a task, otherwise it seems to lock up
            self.hass.async_create_task(self.hass.config_entries.async_reload(self.config_entry.entry_id))

        LOGGER.debug(self.data)

        return self.data

