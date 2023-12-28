"""Coordinator for the LG TV integration."""

from dataclasses import dataclass
import datetime
import async_timeout

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.util.dt import utcnow

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

    def __init__(self, hass, api: LgTv):
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

    async def _async_update_data(self):
        """Fetch data from API endpoint."""
        try:
            # Note: asyncio.TimeoutError and aiohttp.ClientError are already
            # handled by the data update coordinator.
            async with async_timeout.timeout(COORDINATOR_UPDATE_INTERVAL-1):
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
                LOGGER.debug(self.data)
        except Exception as e:
            LOGGER.exception("Uh, oh. Something went wrong")
            raise e

        return self.data

