import importlib.util
import sys
import types
from datetime import date
from pathlib import Path

PACKAGE_DIR = Path(__file__).parents[1] / "custom_components" / "manager_rifiuti"
PACKAGE_NAME = "manager_rifiuti_ha_test"
package = types.ModuleType(PACKAGE_NAME)
package.__path__ = [str(PACKAGE_DIR)]
sys.modules[PACKAGE_NAME] = package


def load_module(name: str):
    spec = importlib.util.spec_from_file_location(
        f"{PACKAGE_NAME}.{name}", PACKAGE_DIR / f"{name}.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Impossibile caricare {name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


const = load_module("const")
notifications = load_module("notifications")
render_notification = notifications.render_notification
CONF_ACTION_TITLE = const.CONF_ACTION_TITLE
CONF_NOTIFY_MESSAGE = const.CONF_NOTIFY_MESSAGE
CONF_NOTIFY_TITLE = const.CONF_NOTIFY_TITLE
CONF_REMINDER_MESSAGE = const.CONF_REMINDER_MESSAGE
CONF_REMINDER_TITLE = const.CONF_REMINDER_TITLE


def test_notification_templates_expand_supported_variables():
    options = {
        CONF_NOTIFY_TITLE: "Ritiro {weekday}",
        CONF_NOTIFY_MESSAGE: "Esponi {waste} ({code}) entro il {date}",
        CONF_ACTION_TITLE: "Fatto: {waste}",
    }

    assert render_notification(options, "TS", date(2026, 8, 10)) == (
        "Ritiro lunedì",
        "Esponi Tessili sanitari (pannolini) (TS) entro il 10-08-2026",
        "Fatto: Tessili sanitari (pannolini)",
    )


def test_reminder_uses_its_own_templates():
    options = {
        CONF_REMINDER_TITLE: "Secondo avviso",
        CONF_REMINDER_MESSAGE: "Hai ricordato {waste}?",
    }

    title, message, _ = render_notification(options, "O", date(2026, 8, 11), reminder=True)

    assert title == "Secondo avviso"
    assert message == "Hai ricordato Organico?"


def test_unknown_placeholder_falls_back_to_safe_default():
    title, message, action = render_notification(
        {CONF_NOTIFY_MESSAGE: "Campo {sconosciuto}"}, "C", date(2026, 8, 13)
    )

    assert title == "Raccolta rifiuti domani"
    assert message == "Porta fuori: Carta"
    assert action == "Rifiuti già portati fuori"
