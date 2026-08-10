from __future__ import annotations

from datetime import date, datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN, WASTE_NAMES


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([WasteCalendar(hass.data[DOMAIN][entry.entry_id])])


class WasteCalendar(CalendarEntity):
    _attr_name = "Raccolta rifiuti"
    _attr_unique_id = "manager_rifiuti_calendar"

    def __init__(self, coordinator):
        self.coordinator = coordinator

    async def async_added_to_hass(self):
        self.async_on_remove(
            async_dispatcher_connect(self.hass, f"{DOMAIN}_updated", self.async_write_ha_state)
        )

    @property
    def event(self):
        item = self.coordinator.next_item()
        return self._event(item) if item else None

    def _event(self, item):
        day = date.fromisoformat(item["day"])
        return CalendarEvent(
            start=day, end=day + timedelta(days=1), summary=WASTE_NAMES[item["waste"]]
        )

    async def async_get_events(self, hass, start_date: datetime, end_date: datetime):
        return [
            self._event(item)
            for item in self.coordinator.collections
            if start_date.date() <= date.fromisoformat(item["day"]) < end_date.date()
        ]
