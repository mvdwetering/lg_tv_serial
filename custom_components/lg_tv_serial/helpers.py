

def update_ha_state(func):
    async def _decorator(self, *args, **kwargs):
        await func(self, *args, **kwargs)
        # Trigger listeners with new optimistic data
        # Also resets polling delay so won't interfere with turn on/off
        self.coordinator.async_set_updated_data(self.coordinator.data)
        # self.async_write_ha_state()

    return _decorator
