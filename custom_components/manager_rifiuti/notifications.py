from __future__ import annotations

from datetime import date

from .const import (
    CONF_ACTION_TITLE,
    CONF_NOTIFY_MESSAGE,
    CONF_NOTIFY_TITLE,
    CONF_REMINDER_MESSAGE,
    CONF_REMINDER_TITLE,
    DEFAULT_ACTION_TITLE,
    DEFAULT_NOTIFY_MESSAGE,
    DEFAULT_NOTIFY_TITLE,
    DEFAULT_REMINDER_MESSAGE,
    DEFAULT_REMINDER_TITLE,
    WASTE_NAMES,
)

WEEKDAYS = (
    "lunedì",
    "martedì",
    "mercoledì",
    "giovedì",
    "venerdì",
    "sabato",
    "domenica",
)


def _format(template: str, fallback: str, values: dict[str, str]) -> str:
    try:
        return template.format_map(values)
    except (KeyError, ValueError):
        return fallback.format_map(values)


def render_notification(
    options: dict, waste: str, collection_day: date, reminder: bool = False
) -> tuple[str, str, str]:
    values = {
        "waste": WASTE_NAMES[waste],
        "code": waste,
        "date": collection_day.strftime("%d-%m-%Y"),
        "weekday": WEEKDAYS[collection_day.weekday()],
    }
    if reminder:
        default_title = DEFAULT_REMINDER_TITLE
        default_message = DEFAULT_REMINDER_MESSAGE
        title_template = str(options.get(CONF_REMINDER_TITLE, default_title))
        message_template = str(options.get(CONF_REMINDER_MESSAGE, default_message))
    else:
        default_title = DEFAULT_NOTIFY_TITLE
        default_message = DEFAULT_NOTIFY_MESSAGE
        title_template = str(options.get(CONF_NOTIFY_TITLE, default_title))
        message_template = str(options.get(CONF_NOTIFY_MESSAGE, default_message))
    action_template = str(options.get(CONF_ACTION_TITLE, DEFAULT_ACTION_TITLE))
    return (
        _format(title_template, default_title, values),
        _format(message_template, default_message, values),
        _format(action_template, DEFAULT_ACTION_TITLE, values),
    )
