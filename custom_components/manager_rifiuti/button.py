from datetime import timedelta

from homeassistant.components.button import ButtonEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([DoneButton(hass.data[DOMAIN][entry.entry_id])])


class DoneButton(ButtonEntity):
    _attr_name = "Rifiuti già portati fuori"
    _attr_unique_id = "manager_rifiuti_done"
    _attr_icon = "mdi:check-circle-outline"

    def __init__(self, coordinator):
        self.coordinator = coordinator

    async def async_press(self):
        await self.coordinator.complete(dt_util.now().date() + timedelta(days=1))
