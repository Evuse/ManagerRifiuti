from __future__ import annotations

import secrets

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_WEBHOOK_ID
from homeassistant.core import callback

from .const import (
    CONF_ENABLED_WASTE,
    CONF_NOTIFY_SERVICES,
    CONF_NOTIFY_TIME,
    CONF_REMINDER_TIME,
    DEFAULT_NOTIFY_TIME,
    DOMAIN,
    WASTE_NAMES,
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title="Raccolta rifiuti", data={CONF_WEBHOOK_ID: secrets.token_urlsafe(24)}
            )
        return self.async_show_form(
            step_id="user",
            description_placeholders={"info": "Il webhook locale verrà generato automaticamente."},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return OptionsFlow(config_entry)


class OptionsFlow(config_entries.OptionsFlow):
    def __init__(self, entry) -> None:
        self.entry = entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        current = self.entry.options
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_NOTIFY_SERVICES, default=current.get(CONF_NOTIFY_SERVICES, "")
                ): str,
                vol.Optional(
                    CONF_NOTIFY_TIME, default=current.get(CONF_NOTIFY_TIME, DEFAULT_NOTIFY_TIME)
                ): str,
                vol.Optional(CONF_REMINDER_TIME, default=current.get(CONF_REMINDER_TIME, "")): str,
                vol.Optional(
                    CONF_ENABLED_WASTE,
                    default=current.get(CONF_ENABLED_WASTE, ",".join(WASTE_NAMES)),
                ): str,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
