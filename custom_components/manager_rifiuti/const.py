DOMAIN = "manager_rifiuti"
PLATFORMS = ["calendar", "sensor", "button"]
STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}.calendar"
WASTE_NAMES = {
    "O": "Organico",
    "I": "Indifferenziata",
    "TS": "Tessili sanitari (pannolini)",
    "V": "Vetro",
    "M": "Metalli",
    "P": "Plastica",
    "C": "Carta",
    "S": "Sfalci verdi",
}
CONF_NOTIFY_SERVICES = "notify_services"
CONF_NOTIFY_TIME = "notify_time"
CONF_REMINDER_TIME = "reminder_time"
CONF_ENABLED_WASTE = "enabled_waste"
CONF_NOTIFY_TITLE = "notify_title"
CONF_NOTIFY_MESSAGE = "notify_message"
CONF_REMINDER_TITLE = "reminder_title"
CONF_REMINDER_MESSAGE = "reminder_message"
CONF_ACTION_TITLE = "action_title"
DEFAULT_NOTIFY_TIME = "20:00:00"
DEFAULT_NOTIFY_TITLE = "Raccolta rifiuti domani"
DEFAULT_NOTIFY_MESSAGE = "Porta fuori: {waste}"
DEFAULT_REMINDER_TITLE = "Promemoria raccolta"
DEFAULT_REMINDER_MESSAGE = "Non dimenticare: {waste}"
DEFAULT_ACTION_TITLE = "Rifiuti già portati fuori"
