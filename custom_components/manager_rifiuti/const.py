DOMAIN = "manager_rifiuti"
PLATFORMS = ["calendar", "sensor", "button"]
STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}.calendar"
WASTE_NAMES = {
    "O": "Organico",
    "I": "Indifferenziata",
    "TS": "Tessili sanitari (pannolini)",
    "V": "Vetro",
    "M": "Metallo",
    "P": "Plastica",
    "C": "Carta",
    "S": "Sfalci verdi",
}
CONF_NOTIFY_SERVICES = "notify_services"
CONF_NOTIFY_TIME = "notify_time"
CONF_REMINDER_TIME = "reminder_time"
CONF_ENABLED_WASTE = "enabled_waste"
DEFAULT_NOTIFY_TIME = "20:00:00"

