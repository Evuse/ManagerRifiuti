from datetime import timedelta

from homeassistant.components.button import ButtonEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(
        [
            DoneButton(hass.data[DOMAIN][entry.entry_id]),
            TestNotificationButton(hass, entry.entry_id),
        ]
    )


class DoneButton(ButtonEntity):
    _attr_name = "Rifiuti già portati fuori"
    _attr_unique_id = "manager_rifiuti_done"
    _attr_icon = "mdi:check-circle-outline"

    def __init__(self, coordinator):
        self.coordinator = coordinator

    async def async_press(self):
        await self.coordinator.complete(dt_util.now().date() + timedelta(days=1))


class TestNotificationButton(ButtonEntity):
    _attr_name = "Invia notifica di prova"
    _attr_unique_id = "manager_rifiuti_test_notification"
    _attr_icon = "mdi:bell-ring-outline"

    def __init__(self, hass, entry_id):
        self.hass = hass
        self.entry_id = entry_id

    async def async_press(self):
        notify = self.hass.data[DOMAIN][f"{self.entry_id}_notify"]
        await notify(dt_util.now(), test=True)
