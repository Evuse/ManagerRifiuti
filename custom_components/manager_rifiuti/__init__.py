from __future__ import annotations

from datetime import datetime, timedelta

from homeassistant.const import CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_track_time_change
from homeassistant.components import webhook

from .const import (
    CONF_ENABLED_WASTE,
    CONF_NOTIFY_SERVICES,
    CONF_NOTIFY_TIME,
    CONF_REMINDER_TIME,
    DEFAULT_NOTIFY_TIME,
    DOMAIN,
    PLATFORMS,
    WASTE_NAMES,
)
from .coordinator import WasteCoordinator

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup_entry(hass: HomeAssistant, entry) -> bool:
    coordinator = WasteCoordinator(hass, entry)
    await coordinator.load()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    async def handle_webhook(hass, webhook_id, request):
        try:
            await coordinator.import_payload(await request.json())
        except (KeyError, TypeError, ValueError) as exc:
            return webhook.json_response({"ok": False, "error": str(exc)}, status_code=400)
        return webhook.json_response({"ok": True, "count": len(coordinator.collections)})

    webhook.async_register(
        hass, DOMAIN, "Importazione calendario", entry.data[CONF_WEBHOOK_ID], handle_webhook
    )

    async def notify(now, reminder=False):
        options = entry.options
        enabled = {
            x.strip() for x in options.get(CONF_ENABLED_WASTE, ",".join(WASTE_NAMES)).split(",")
        }
        tomorrow = now.date() + timedelta(days=1)
        for item in coordinator.for_day(tomorrow):
            if item["waste"] not in enabled or coordinator.is_complete(item):
                continue
            for service in filter(
                None, (x.strip() for x in options.get(CONF_NOTIFY_SERVICES, "").splitlines())
            ):
                domain, _, name = service.partition(".")
                if domain != "notify" or not name:
                    continue
                await hass.services.async_call(
                    domain,
                    name,
                    {
                        "title": "Promemoria raccolta" if reminder else "Raccolta rifiuti domani",
                        "message": f"Porta fuori: {WASTE_NAMES[item['waste']]}",
                        "data": {
                            "actions": [
                                {
                                    "action": f"MR_DONE_{tomorrow.isoformat()}_{item['waste']}",
                                    "title": "Rifiuti già portati fuori",
                                }
                            ]
                        },
                    },
                )

    def schedule(value, reminder=False):
        try:
            hour, minute, second = (int(x) for x in value.split(":"))
        except (AttributeError, ValueError):
            return None
        return async_track_time_change(
            hass, lambda now: notify(now, reminder), hour=hour, minute=minute, second=second
        )

    unsubscribers = [schedule(entry.options.get(CONF_NOTIFY_TIME, DEFAULT_NOTIFY_TIME))]
    if entry.options.get(CONF_REMINDER_TIME):
        unsubscribers.append(schedule(entry.options[CONF_REMINDER_TIME], True))

    async def action_handler(event):
        action = event.data.get("action", "")
        if action.startswith("MR_DONE_"):
            raw = action.removeprefix("MR_DONE_")
            day_text, waste = raw.rsplit("_", 1)
            await coordinator.complete(datetime.fromisoformat(day_text).date(), waste)

    unsubscribers.append(hass.bus.async_listen("mobile_app_notification_action", action_handler))
    hass.data[DOMAIN][f"{entry.entry_id}_unsub"] = [item for item in unsubscribers if item]
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_reload))
    return True


async def _reload(hass, entry):
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass, entry) -> bool:
    webhook.async_unregister(hass, entry.data[CONF_WEBHOOK_ID])
    for unsub in hass.data[DOMAIN].pop(f"{entry.entry_id}_unsub", []):
        unsub()
    result = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if result:
        hass.data[DOMAIN].pop(entry.entry_id)
    return result
