from __future__ import annotations

from datetime import timedelta

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.util import dt as dt_util

from .const import DOMAIN, WASTE_NAMES


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            WasteSensor(coordinator, 0, "Raccolta oggi"),
            WasteSensor(coordinator, 1, "Raccolta domani"),
            WebhookSensor(entry.data["webhook_id"]),
        ]
    )


class WasteSensor(SensorEntity):
    def __init__(self, coordinator, offset, name):
        self.coordinator, self.offset = coordinator, offset
        self._attr_name = name
        self._attr_unique_id = f"manager_rifiuti_{offset}"
        self._attr_icon = "mdi:trash-can-outline"

    async def async_added_to_hass(self):
        self.async_on_remove(
            async_dispatcher_connect(self.hass, f"{DOMAIN}_updated", self.async_write_ha_state)
        )

    @property
    def native_value(self):
        items = self.coordinator.for_day(dt_util.now().date() + timedelta(days=self.offset))
        return ", ".join(WASTE_NAMES[x["waste"]] for x in items) or "Nessuna raccolta"


class WebhookSensor(SensorEntity):
    _attr_name = "ID importazione Manager Rifiuti"
    _attr_unique_id = "manager_rifiuti_webhook"
    _attr_icon = "mdi:key-variant"
    _attr_entity_registry_enabled_default = True

    def __init__(self, webhook_id):
        self._attr_native_value = webhook_id
