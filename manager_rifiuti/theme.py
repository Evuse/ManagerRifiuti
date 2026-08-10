from __future__ import annotations

from PySide6.QtWidgets import QApplication

PALETTES = {
    "Chiaro": {
        "bg": "#f3f7f5",
        "surface": "#ffffff",
        "surface_alt": "#e9f2ee",
        "text": "#17251f",
        "muted": "#63736b",
        "border": "#d6e2dc",
        "accent": "#159a68",
        "accent_hover": "#0f8257",
        "accent_soft": "#dff5ea",
        "danger": "#c74848",
    },
    "Scuro": {
        "bg": "#101714",
        "surface": "#18211d",
        "surface_alt": "#202d27",
        "text": "#f0f7f3",
        "muted": "#a1b2aa",
        "border": "#31423a",
        "accent": "#32c88a",
        "accent_hover": "#54d79f",
        "accent_soft": "#173e2e",
        "danger": "#ff7676",
    },
}

ACCENTS = {
    "Verde": ("#159a68", "#0f8257", "#dff5ea", "#32c88a", "#54d79f", "#173e2e"),
    "Blu": ("#2476d2", "#185faa", "#e1efff", "#55a4ff", "#7ab8ff", "#173453"),
    "Viola": ("#7857c7", "#6242ae", "#eee8ff", "#a88aff", "#bea7ff", "#352851"),
    "Arancio": ("#d66a1f", "#b65313", "#fff0df", "#ff984f", "#ffad74", "#4d2b19"),
}


def apply_theme(app: QApplication, theme: str, accent: str = "Verde", font_size: int = 14) -> None:
    colors = PALETTES.get(theme, PALETTES["Chiaro"])
    accent_values = ACCENTS.get(accent, ACCENTS["Verde"])
    if theme == "Scuro":
        accent_color, accent_hover, accent_soft = accent_values[3:]
    else:
        accent_color, accent_hover, accent_soft = accent_values[:3]
    colors = {
        **colors,
        "accent": accent_color,
        "accent_hover": accent_hover,
        "accent_soft": accent_soft,
    }
    font_size = max(12, min(font_size, 18))
    app.setStyle("Fusion")
    app.setStyleSheet(
        f"""
        * {{ font-family: "Segoe UI", sans-serif; font-size: {font_size}px; }}
        QMainWindow, QDialog {{ background: {colors["bg"]}; color: {colors["text"]}; }}
        QScrollArea#MainScroll, QScrollArea#MainScroll > QWidget > QWidget {{
            background: {colors["bg"]}; border: none;
        }}
        QWidget {{ color: {colors["text"]}; }}
        QMenuBar, QMenu {{ background: {colors["surface"]}; border: none; }}
        QMenuBar::item:selected, QMenu::item:selected {{ background: {colors["accent_soft"]}; }}
        QFrame#Card, QGroupBox {{
            background: {colors["surface"]}; border: 1px solid {colors["border"]};
            border-radius: 14px;
        }}
        QGroupBox {{ margin-top: 10px; padding: 16px 12px 12px; font-weight: 600; }}
        QGroupBox::title {{ subcontrol-origin: margin; left: 14px; padding: 0 6px; }}
        QLabel#HeroTitle {{ font-size: 28px; font-weight: 700; }}
        QLabel#Subtitle, QLabel#Muted {{ color: {colors["muted"]}; }}
        QLabel#Metric {{ font-size: 24px; font-weight: 700; color: {colors["accent"]}; }}
        QLabel#Status {{
            background: {colors["accent_soft"]}; color: {colors["text"]};
            border-radius: 10px; padding: 10px 12px;
        }}
        QFrame#DropZone {{
            background: {colors["surface_alt"]}; border: 2px dashed {colors["accent"]};
            border-radius: 14px;
        }}
        QFrame#DropZone[dragging="true"] {{ background: {colors["accent_soft"]}; }}
        QPushButton {{
            background: {colors["surface_alt"]}; border: 1px solid {colors["border"]};
            border-radius: 9px; padding: 9px 14px; font-weight: 600;
        }}
        QPushButton:hover {{ border-color: {colors["accent"]}; }}
        QPushButton:disabled {{ color: {colors["muted"]}; background: {colors["bg"]}; }}
        QPushButton#Primary {{
            color: white; background: {colors["accent"]}; border-color: {colors["accent"]};
        }}
        QPushButton#Primary:hover {{ background: {colors["accent_hover"]}; }}
        QPushButton#Danger {{ color: {colors["danger"]}; border-color: {colors["danger"]}; }}
        QLineEdit, QSpinBox, QComboBox {{
            background: {colors["surface"]}; border: 1px solid {colors["border"]};
            border-radius: 8px; padding: 8px;
        }}
        QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{ border-color: {colors["accent"]}; }}
        QTableWidget {{
            background: {colors["surface"]}; alternate-background-color: {colors["surface_alt"]};
            border: 1px solid {colors["border"]}; border-radius: 10px; gridline-color: {colors["border"]};
        }}
        QHeaderView::section {{
            background: {colors["surface_alt"]}; padding: 8px; border: none;
            border-bottom: 1px solid {colors["border"]}; font-weight: 600;
        }}
        QProgressBar {{
            background: {colors["surface_alt"]}; border: none; border-radius: 5px; height: 10px;
        }}
        QProgressBar::chunk {{ background: {colors["accent"]}; border-radius: 5px; }}
        """
    )
