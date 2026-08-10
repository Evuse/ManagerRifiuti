from __future__ import annotations

from datetime import date

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import DOMAIN, STORAGE_KEY, STORAGE_VERSION, WASTE_NAMES


class WasteCoordinator:
    def __init__(self, hass: HomeAssistant, entry) -> None:
        self.hass, self.entry = hass, entry
        self.store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self.collections: list[dict] = []
        self.completed: set[str] = set()

    async def load(self) -> None:
        data = await self.store.async_load() or {}
        self.collections = data.get("collections", [])
        self.completed = set(data.get("completed", []))

    async def save(self) -> None:
        await self.store.async_save(
            {"collections": self.collections, "completed": sorted(self.completed)}
        )
        async_dispatcher_send(self.hass, f"{DOMAIN}_updated")

    async def import_payload(self, payload: dict) -> None:
        valid = []
        year = int(payload["year"])
        for item in payload.get("collections", []):
            parsed = date.fromisoformat(item["day"])
            code = str(item["waste"]).upper()
            if parsed.year != year or code not in WASTE_NAMES:
                raise ValueError("Calendario non valido")
            valid.append({"day": parsed.isoformat(), "waste": code})
        self.collections = sorted({(x["day"], x["waste"]) for x in valid})
        self.collections = [{"day": day, "waste": waste} for day, waste in self.collections]
        self.completed.clear()
        await self.save()

    def for_day(self, day: date) -> list[dict]:
        return [item for item in self.collections if item["day"] == day.isoformat()]

    async def complete(self, day: date, waste: str | None = None) -> None:
        for item in self.for_day(day):
            if waste is None or item["waste"] == waste:
                self.completed.add(f"{item['day']}:{item['waste']}")
        await self.save()

    def is_complete(self, item: dict) -> bool:
        return f"{item['day']}:{item['waste']}" in self.completed

    @callback
    def next_item(self) -> dict | None:
        today = dt_util.now().date().isoformat()
        return next((item for item in self.collections if item["day"] >= today), None)
