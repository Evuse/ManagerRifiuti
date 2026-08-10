from __future__ import annotations

import json
import sys
from datetime import date, datetime
from pathlib import Path

from PySide6.QtCore import QSettings, QStandardPaths, Qt, QThread, QUrl, Signal
from PySide6.QtGui import QAction, QDesktopServices, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .homeassistant import upload
from .models import WASTE_NAMES, Collection
from .recognizer import CalendarRecognizer, RecognitionResult
from .theme import apply_theme

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}


def default_backup_folder() -> Path:
    documents = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)
    return Path(documents) / "ManagerRifiuti" / "backup"


def write_backup(path: Path, year: int, collections: list[Collection]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"year": year, "collections": [item.to_dict() for item in collections]}
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def read_backup(path: Path) -> tuple[int, list[Collection]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        year = int(payload["year"])
        raw_collections = payload["collections"]
        if not isinstance(raw_collections, list):
            raise TypeError("collections deve essere una lista")
        collections = []
        for item in raw_collections:
            waste = str(item["waste"])
            if waste not in WASTE_NAMES:
                raise ValueError(f"tipologia sconosciuta: {waste}")
            collections.append(Collection(date.fromisoformat(str(item["day"])), waste))
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError(f"Backup non valido: {exc}") from exc
    return year, sorted(set(collections))


class RecognitionWorker(QThread):
    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, paths: list[str]) -> None:
        super().__init__()
        self.paths = paths

    def run(self) -> None:
        try:
            recognizer = CalendarRecognizer()
            self.completed.emit([recognizer.recognize(path) for path in self.paths])
        except Exception as exc:  # noqa: BLE001 - thread boundary, display error in GUI
            self.failed.emit(str(exc))


class DropZone(QFrame):
    files_selected = Signal(list)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("DropZone")
        self.setAcceptDrops(True)
        self.setMinimumHeight(116)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        title = QLabel("Trascina qui una o due foto del calendario")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 16px; font-weight: 600; border: none;")
        hint = QLabel("oppure fai clic per scegliere i file")
        hint.setObjectName("Muted")
        hint.setAlignment(Qt.AlignCenter)
        hint.setStyleSheet("border: none;")
        layout.addWidget(title)
        layout.addWidget(hint)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.files_selected.emit([])
        super().mousePressEvent(event)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        urls = event.mimeData().urls()
        if urls and all(Path(url.toLocalFile()).suffix.lower() in IMAGE_SUFFIXES for url in urls):
            self.setProperty("dragging", True)
            self.style().unpolish(self)
            self.style().polish(self)
            event.acceptProposedAction()

    def dragLeaveEvent(self, event) -> None:
        self.setProperty("dragging", False)
        self.style().unpolish(self)
        self.style().polish(self)
        super().dragLeaveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        self.setProperty("dragging", False)
        paths = [url.toLocalFile() for url in event.mimeData().urls()]
        self.files_selected.emit(paths)
        event.acceptProposedAction()


class MetricCard(QFrame):
    def __init__(self, caption: str, value: str = "—") -> None:
        super().__init__()
        self.setObjectName("Card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        self.value = QLabel(value)
        self.value.setObjectName("Metric")
        label = QLabel(caption)
        label.setObjectName("Muted")
        layout.addWidget(self.value)
        layout.addWidget(label)


class SettingsDialog(QDialog):
    changed = Signal()

    def __init__(self, settings: QSettings, current_webhook: str = "", parent=None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Impostazioni")
        self.setMinimumWidth(520)
        self.theme = QComboBox()
        self.theme.addItems(["Chiaro", "Scuro"])
        self.theme.setCurrentText(str(settings.value("appearance/theme", "Chiaro")))
        self.accent = QComboBox()
        self.accent.addItems(["Verde", "Blu", "Viola", "Arancio"])
        self.accent.setCurrentText(str(settings.value("appearance/accent", "Verde")))
        self.font_size = QSpinBox()
        self.font_size.setRange(12, 18)
        self.font_size.setSuffix(" px")
        self.font_size.setValue(settings.value("appearance/font_size", 14, type=int))
        self.ha_url = QLineEdit(
            str(settings.value("homeassistant/url", "http://homeassistant.local:8123"))
        )
        self.webhook = QLineEdit(
            str(settings.value("homeassistant/webhook_id", current_webhook))
            if settings.value("homeassistant/remember_webhook", False, type=bool)
            else current_webhook
        )
        self.webhook.setEchoMode(QLineEdit.Password)
        self.webhook.setPlaceholderText("ID importazione Manager Rifiuti")
        show_id = QCheckBox("Mostra")
        show_id.toggled.connect(
            lambda visible: self.webhook.setEchoMode(
                QLineEdit.Normal if visible else QLineEdit.Password
            )
        )
        id_row = QHBoxLayout()
        id_row.addWidget(self.webhook, 1)
        id_row.addWidget(show_id)
        self.remember_id = QCheckBox("Salva l'ID su questo PC")
        self.remember_id.setChecked(
            settings.value("homeassistant/remember_webhook", False, type=bool)
        )
        id_note = QLabel("L'ID viene salvato nelle impostazioni locali di Windows, non cifrato.")
        id_note.setObjectName("Muted")
        self.auto_backup = QCheckBox("Crea automaticamente un JSON dopo ogni revisione")
        self.auto_backup.setChecked(settings.value("backup/enabled", True, type=bool))
        self.backup_folder = QLineEdit(
            str(settings.value("backup/folder", str(default_backup_folder())))
        )
        browse = QPushButton("Sfoglia…")
        browse.clicked.connect(self.choose_folder)
        folder_row = QHBoxLayout()
        folder_row.addWidget(self.backup_folder, 1)
        folder_row.addWidget(browse)
        appearance_group = QGroupBox("Aspetto")
        appearance_form = QFormLayout(appearance_group)
        appearance_form.addRow("Tema:", self.theme)
        appearance_form.addRow("Colore principale:", self.accent)
        appearance_form.addRow("Dimensione testo:", self.font_size)
        ha_group = QGroupBox("Home Assistant")
        ha_form = QFormLayout(ha_group)
        ha_form.addRow("Indirizzo:", self.ha_url)
        ha_form.addRow("ID importazione:", id_row)
        ha_form.addRow("Memorizzazione:", self.remember_id)
        ha_form.addRow("", id_note)
        backup_group = QGroupBox("Backup")
        backup_form = QFormLayout(backup_group)
        backup_form.addRow("Backup automatico:", self.auto_backup)
        backup_form.addRow("Cartella:", folder_row)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(appearance_group)
        layout.addWidget(ha_group)
        layout.addWidget(backup_group)
        layout.addWidget(buttons)

    def choose_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, "Cartella dei backup", self.backup_folder.text()
        )
        if folder:
            self.backup_folder.setText(folder)

    def save(self) -> None:
        url = self.ha_url.text().strip().rstrip("/")
        if not url:
            QMessageBox.warning(
                self, "Indirizzo mancante", "Inserisci l'indirizzo di Home Assistant."
            )
            return
        self.settings.setValue("appearance/theme", self.theme.currentText())
        self.settings.setValue("appearance/accent", self.accent.currentText())
        self.settings.setValue("appearance/font_size", self.font_size.value())
        self.settings.setValue("homeassistant/url", url)
        self.settings.setValue("homeassistant/remember_webhook", self.remember_id.isChecked())
        if self.remember_id.isChecked():
            if not self.webhook.text().strip():
                QMessageBox.warning(
                    self, "ID mancante", "Inserisci l'ID oppure disattiva il salvataggio."
                )
                return
            self.settings.setValue("homeassistant/webhook_id", self.webhook.text().strip())
        else:
            self.settings.remove("homeassistant/webhook_id")
        self.settings.setValue("backup/enabled", self.auto_backup.isChecked())
        self.settings.setValue("backup/folder", self.backup_folder.text().strip())
        self.settings.sync()
        self.changed.emit()
        self.accept()


class ReviewDialog(QDialog):
    def __init__(self, results: list[RecognitionResult], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Controllo delle raccolte")
        self.resize(980, 720)
        years = [result.detected_year for result in results if result.detected_year]
        self.year = QSpinBox()
        self.year.setRange(2020, 2100)
        self.year.setValue(years[0] if years else datetime.now().astimezone().year)
        self.confirm = QCheckBox("Confermo che l'anno selezionato è corretto")
        self.months_need_confirmation = any(
            any("Mesi non riconosciuti" in warning for warning in result.warnings)
            for result in results
        )
        self.confirm_months = QCheckBox(
            "Confermo di avere verificato manualmente i mesi non riconosciuti"
        )
        self.confirm_months.setVisible(self.months_need_confirmation)
        waste_group = QGroupBox("Tipologie da importare")
        waste_layout = QGridLayout(waste_group)
        self.waste_checks: dict[str, QCheckBox] = {}
        for index, (code, name) in enumerate(WASTE_NAMES.items()):
            checkbox = QCheckBox(name)
            checkbox.setChecked(True)
            checkbox.toggled.connect(
                lambda checked, selected_code=code: self.set_waste_enabled(selected_code, checked)
            )
            self.waste_checks[code] = checkbox
            waste_layout.addWidget(checkbox, index // 2, index % 2)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Data (GG-MM)", "Tipologia di rifiuto", "Includi"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.itemChanged.connect(lambda _item: self.update_count())
        seen = set()
        for result in results:
            for collection in result.collections:
                key = (collection.day.month, collection.day.day, collection.waste)
                if key not in seen:
                    self.add_row(*key)
                    seen.add(key)
        self.count = QLabel()
        self.count.setObjectName("Status")
        self.update_count()
        add = QPushButton("+ Aggiungi raccolta")
        remove = QPushButton("Rimuovi selezionate")
        add.clicked.connect(lambda: self.add_row(1, 1, "O"))
        remove.clicked.connect(self.remove_rows)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Conferma e crea backup")
        buttons.button(QDialogButtonBox.Ok).setObjectName("Primary")
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        warning_text = "\n".join(warning for result in results for warning in result.warnings)
        layout = QVBoxLayout(self)
        heading = QLabel("Verifica il risultato prima dell'importazione")
        heading.setObjectName("HeroTitle")
        layout.addWidget(heading)
        layout.addWidget(
            QLabel(
                "Tutte le tipologie sono incluse. Puoi correggere, aggiungere o escludere righe."
            )
        )
        if warning_text:
            warning = QLabel(warning_text)
            warning.setStyleSheet("color: #d97928")
            layout.addWidget(warning)
        top = QHBoxLayout()
        top.addWidget(QLabel("Anno rilevato:"))
        top.addWidget(self.year)
        top.addWidget(self.confirm)
        top.addStretch()
        layout.addLayout(top)
        layout.addWidget(self.confirm_months)
        layout.addWidget(waste_group)
        layout.addWidget(self.count)
        layout.addWidget(self.table, 1)
        row = QHBoxLayout()
        row.addWidget(add)
        row.addWidget(remove)
        row.addStretch()
        layout.addLayout(row)
        layout.addWidget(buttons)

    def add_row(self, month: int, day: int, waste: str) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(f"{day:02d}-{month:02d}"))
        selector = QComboBox()
        for code, name in WASTE_NAMES.items():
            selector.addItem(name, code)
        selector.setCurrentIndex(max(selector.findData(waste), 0))
        selector.currentIndexChanged.connect(
            lambda _index, selected=selector: self.sync_selector_enabled(selected)
        )
        self.table.setCellWidget(row, 1, selector)
        checked = QTableWidgetItem("Sì")
        checked.setFlags(checked.flags() | Qt.ItemIsUserCheckable)
        enabled = self.waste_checks[str(selector.currentData())].isChecked()
        checked.setCheckState(Qt.Checked if enabled else Qt.Unchecked)
        self.table.setItem(row, 2, checked)
        self.update_count()

    def row_waste(self, row: int) -> str:
        selector = self.table.cellWidget(row, 1)
        if not isinstance(selector, QComboBox):
            raise TypeError(f"Tipologia non valida alla riga {row + 1}")
        return str(selector.currentData())

    def sync_row_enabled(self, row: int) -> None:
        include = self.table.item(row, 2)
        if include is not None:
            include.setCheckState(
                Qt.Checked if self.waste_checks[self.row_waste(row)].isChecked() else Qt.Unchecked
            )

    def sync_selector_enabled(self, selector: QComboBox) -> None:
        for row in range(self.table.rowCount()):
            if self.table.cellWidget(row, 1) is selector:
                self.sync_row_enabled(row)
                self.update_count()
                return

    def set_waste_enabled(self, waste: str, enabled: bool) -> None:
        for row in range(self.table.rowCount()):
            if self.row_waste(row) == waste:
                self.table.item(row, 2).setCheckState(Qt.Checked if enabled else Qt.Unchecked)
        self.update_count()

    def update_count(self) -> None:
        if not hasattr(self, "count"):
            return
        included = sum(
            self.table.item(row, 2) is not None
            and self.table.item(row, 2).checkState() == Qt.Checked
            for row in range(self.table.rowCount())
        )
        self.count.setText(f"{included} raccolte incluse su {self.table.rowCount()} rilevate")

    def remove_rows(self) -> None:
        for index in sorted({item.row() for item in self.table.selectedIndexes()}, reverse=True):
            self.table.removeRow(index)
        self.update_count()

    def _accept(self) -> None:
        if not self.confirm.isChecked():
            QMessageBox.warning(self, "Anno non confermato", "Conferma esplicitamente l'anno.")
            return
        if self.months_need_confirmation and not self.confirm_months.isChecked():
            QMessageBox.warning(
                self,
                "Mesi non confermati",
                "Conferma di avere verificato i mesi mancanti prima di continuare.",
            )
            return
        try:
            self.collections()
        except ValueError as exc:
            QMessageBox.warning(self, "Riga non valida", str(exc))
            return
        self.accept()

    def collections(self) -> list[Collection]:
        if not any(checkbox.isChecked() for checkbox in self.waste_checks.values()):
            raise ValueError("Seleziona almeno una tipologia di rifiuto da importare.")
        values = []
        for row in range(self.table.rowCount()):
            waste = self.row_waste(row)
            if (
                not self.waste_checks[waste].isChecked()
                or self.table.item(row, 2).checkState() != Qt.Checked
            ):
                continue
            raw_date = self.table.item(row, 0).text().strip()
            try:
                day, month = (int(value) for value in raw_date.split("-"))
                collection_day = date(self.year.value(), month, day)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Data non valida alla riga {row + 1}: {raw_date}") from exc
            values.append(Collection(collection_day, waste))
        return sorted(set(values))


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.settings = QSettings()
        self.setWindowTitle("Manager Rifiuti")
        self.setMinimumSize(820, 650)
        self.resize(1040, 760)
        self.paths: list[str] = []
        self.collections: list[Collection] = []
        self.year: int | None = None
        self.worker: RecognitionWorker | None = None

        title = QLabel("Il calendario rifiuti, senza fatica")
        title.setObjectName("HeroTitle")
        subtitle = QLabel("Analisi locale delle fotografie e invio diretto a Home Assistant.")
        subtitle.setObjectName("Subtitle")
        self.drop_zone = DropZone()
        self.drop_zone.files_selected.connect(self.select_or_open_files)
        self.files = QLabel("Nessuna immagine selezionata")
        self.files.setObjectName("Muted")
        self.analyze = QPushButton("Analizza le immagini")
        self.analyze.setObjectName("Primary")
        self.analyze.setEnabled(False)
        self.analyze.clicked.connect(self.start_analysis)
        self.clear = QPushButton("Azzera selezione")
        self.clear.clicked.connect(self.reset_session)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setVisible(False)
        self.status = QLabel("Pronto. Le immagini restano sempre su questo computer.")
        self.status.setObjectName("Status")

        self.images_metric = MetricCard("Immagini", "0")
        self.events_metric = MetricCard("Raccolte", "—")
        self.year_metric = MetricCard("Anno", "—")
        metrics = QHBoxLayout()
        metrics.addWidget(self.images_metric)
        metrics.addWidget(self.events_metric)
        metrics.addWidget(self.year_metric)

        import_backup = QPushButton("Importa backup JSON")
        import_backup.clicked.connect(self.import_json)
        open_backups = QPushButton("Apri cartella backup")
        open_backups.clicked.connect(self.open_backup_folder)
        customize = QPushButton("Personalizza")
        customize.clicked.connect(self.open_settings)
        utilities = QHBoxLayout()
        utilities.addWidget(import_backup)
        utilities.addWidget(open_backups)
        utilities.addStretch()
        utilities.addWidget(customize)

        connection = QFrame()
        connection.setObjectName("Card")
        connection_layout = QVBoxLayout(connection)
        connection_layout.setContentsMargins(20, 18, 20, 18)
        connection_title = QLabel("Connessione a Home Assistant")
        connection_title.setStyleSheet("font-size: 17px; font-weight: 700;")
        self.ha_url = QLineEdit(
            str(self.settings.value("homeassistant/url", "http://homeassistant.local:8123"))
        )
        self.webhook = QLineEdit()
        self.webhook.setEchoMode(QLineEdit.Password)
        self.webhook.setPlaceholderText("ID importazione mostrato dall'integrazione")
        if self.settings.value("homeassistant/remember_webhook", False, type=bool):
            self.webhook.setText(str(self.settings.value("homeassistant/webhook_id", "")))
        reveal = QCheckBox("Mostra ID")
        reveal.toggled.connect(
            lambda visible: self.webhook.setEchoMode(
                QLineEdit.Normal if visible else QLineEdit.Password
            )
        )
        webhook_row = QHBoxLayout()
        webhook_row.addWidget(self.webhook, 1)
        webhook_row.addWidget(reveal)
        form = QFormLayout()
        form.addRow("Indirizzo:", self.ha_url)
        form.addRow("ID importazione:", webhook_row)
        self.send = QPushButton("Invia il calendario a Home Assistant")
        self.send.setObjectName("Primary")
        self.send.setEnabled(False)
        self.send.clicked.connect(self.send_calendar)
        clear_remote = QPushButton("Azzera calendario su Home Assistant")
        clear_remote.setObjectName("Danger")
        clear_remote.clicked.connect(self.clear_home_assistant)
        connection_layout.addWidget(connection_title)
        connection_layout.addLayout(form)
        connection_layout.addWidget(self.send)
        connection_layout.addWidget(clear_remote)

        actions = QHBoxLayout()
        actions.addWidget(self.analyze, 1)
        actions.addWidget(self.clear)
        layout = QVBoxLayout()
        layout.setContentsMargins(30, 24, 30, 30)
        layout.setSpacing(14)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addLayout(metrics)
        layout.addLayout(utilities)
        layout.addWidget(self.drop_zone)
        layout.addWidget(self.files)
        layout.addLayout(actions)
        layout.addWidget(self.progress)
        layout.addWidget(self.status)
        layout.addWidget(connection)
        widget = QWidget()
        widget.setLayout(layout)
        self.setCentralWidget(widget)

        file_menu = self.menuBar().addMenu("File")
        export_action = QAction("Esporta un altro backup JSON…", self)
        export_action.triggered.connect(self.export_json)
        file_menu.addAction(export_action)
        file_menu.addAction("Azzera sessione", self.reset_session)
        preferences = QAction("Impostazioni…", self)
        preferences.triggered.connect(self.open_settings)
        self.menuBar().addMenu("Personalizza").addAction(preferences)

    def select_or_open_files(self, paths: list[str]) -> None:
        if not paths:
            paths, _ = QFileDialog.getOpenFileNames(
                self, "Calendario", "", "Immagini (*.jpg *.jpeg *.png *.webp *.tif *.tiff)"
            )
        self.set_files(paths)

    def set_files(self, paths: list[str]) -> None:
        valid = [path for path in paths if Path(path).suffix.lower() in IMAGE_SUFFIXES]
        if len(valid) > 2:
            QMessageBox.warning(self, "Troppi file", "Seleziona al massimo due immagini.")
            return
        if not valid:
            return
        self.paths = valid
        self.files.setText(" • ".join(Path(path).name for path in valid))
        self.images_metric.value.setText(str(len(valid)))
        self.events_metric.value.setText("—")
        self.year_metric.value.setText("—")
        self.analyze.setEnabled(True)
        self.send.setEnabled(False)
        self.status.setText("Immagini caricate. Puoi avviare l'analisi.")

    def reset_session(self) -> None:
        self.paths = []
        self.collections = []
        self.year = None
        self.files.setText("Nessuna immagine selezionata")
        self.images_metric.value.setText("0")
        self.events_metric.value.setText("—")
        self.year_metric.value.setText("—")
        self.analyze.setEnabled(False)
        self.send.setEnabled(False)
        self.status.setText("Sessione azzerata. Home Assistant non è stato modificato.")

    def start_analysis(self) -> None:
        self.progress.setRange(0, 0)
        self.progress.setVisible(True)
        self.analyze.setEnabled(False)
        self.status.setText("Correzione prospettiva e riconoscimento dei simboli in corso…")
        self.worker = RecognitionWorker(self.paths)
        self.worker.completed.connect(self.review)
        self.worker.failed.connect(self.failure)
        self.worker.start()

    def failure(self, message: str) -> None:
        self.progress.setVisible(False)
        self.analyze.setEnabled(True)
        self.status.setText("Analisi non riuscita. Controlla il messaggio di errore.")
        QMessageBox.critical(self, "Analisi non riuscita", message)

    def review(self, results: list[RecognitionResult]) -> None:
        self.progress.setVisible(False)
        self.analyze.setEnabled(True)
        dialog = ReviewDialog(results, self)
        if dialog.exec() != QDialog.Accepted:
            self.status.setText("Revisione annullata: nessun dato è stato modificato.")
            return
        self.collections = dialog.collections()
        self.year = dialog.year.value()
        self.send.setText(f"Invia {len(self.collections)} raccolte a Home Assistant")
        self.send.setEnabled(True)
        self.events_metric.value.setText(str(len(self.collections)))
        self.year_metric.value.setText(str(self.year))
        backup = self.create_automatic_backup()
        message = f"Revisione completata: {len(self.collections)} raccolte per il {self.year}."
        if backup:
            message += f" Backup salvato in {backup}."
        self.status.setText(message)

    def create_automatic_backup(self) -> Path | None:
        if not self.settings.value("backup/enabled", True, type=bool):
            return None
        folder = Path(str(self.settings.value("backup/folder", str(default_backup_folder()))))
        timestamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
        path = folder / f"raccolte-{self.year}-{timestamp}.json"
        try:
            write_backup(path, self.year or 0, self.collections)
        except OSError as exc:
            QMessageBox.warning(
                self,
                "Backup non creato",
                f"Il calendario è pronto, ma il backup automatico non è stato salvato:\n{exc}",
            )
            return None
        return path

    def import_json(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Importa backup", "", "JSON (*.json)")
        if not path:
            return
        try:
            year, collections = read_backup(Path(path))
        except ValueError as exc:
            QMessageBox.warning(self, "Backup non valido", str(exc))
            return
        self.year = year
        self.collections = collections
        self.events_metric.value.setText(str(len(collections)))
        self.year_metric.value.setText(str(year))
        self.send.setText(f"Invia {len(collections)} raccolte a Home Assistant")
        self.send.setEnabled(bool(collections))
        self.status.setText(f"Backup caricato: {len(collections)} raccolte per il {year}.")

    def open_backup_folder(self) -> None:
        folder = Path(str(self.settings.value("backup/folder", str(default_backup_folder()))))
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            QMessageBox.warning(self, "Cartella non disponibile", str(exc))
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def clear_home_assistant(self) -> None:
        webhook = self.webhook.text().strip()
        if not webhook:
            QMessageBox.warning(
                self, "ID mancante", "Inserisci prima l'ID importazione di Home Assistant."
            )
            return
        answer = QMessageBox.question(
            self,
            "Conferma azzeramento",
            "Vuoi eliminare tutte le raccolte importate da Manager Rifiuti?\n"
            "Le altre integrazioni di Home Assistant non verranno modificate.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        try:
            upload(
                self.ha_url.text().strip(),
                webhook,
                self.year or datetime.now().astimezone().year,
                [],
            )
        except Exception as exc:  # noqa: BLE001 - convert transport errors into GUI feedback
            QMessageBox.critical(self, "Azzeramento non riuscito", str(exc))
            return
        self.status.setText("Calendario di Manager Rifiuti azzerato su Home Assistant.")
        QMessageBox.information(self, "Calendario azzerato", "Home Assistant ora contiene 0 raccolte.")

    def send_calendar(self) -> None:
        webhook = self.webhook.text().strip()
        if not webhook:
            QMessageBox.warning(
                self, "ID mancante", "Inserisci l'ID importazione di Home Assistant."
            )
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            upload(self.ha_url.text().strip(), webhook, self.year or 0, self.collections)
        except Exception as exc:  # noqa: BLE001 - convert transport errors into GUI feedback
            QMessageBox.critical(self, "Invio non riuscito", str(exc))
        else:
            self.status.setText(
                f"Importazione completata: Home Assistant ha ricevuto {len(self.collections)} raccolte."
            )
            QMessageBox.information(
                self, "Importazione completata", "Home Assistant ha ricevuto il calendario."
            )
        finally:
            QApplication.restoreOverrideCursor()

    def export_json(self) -> None:
        if not self.collections:
            QMessageBox.information(self, "Nessun dato", "Completa prima l'analisi e la revisione.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Backup", f"raccolte-{self.year}.json", "JSON (*.json)"
        )
        if path:
            write_backup(Path(path), self.year or 0, self.collections)
            self.status.setText(f"Backup esportato in {path}.")

    def open_settings(self) -> None:
        dialog = SettingsDialog(self.settings, self.webhook.text(), self)
        dialog.changed.connect(self.apply_preferences)
        dialog.exec()

    def apply_preferences(self) -> None:
        app = QApplication.instance()
        if isinstance(app, QApplication):
            apply_theme(
                app,
                str(self.settings.value("appearance/theme", "Chiaro")),
                str(self.settings.value("appearance/accent", "Verde")),
                self.settings.value("appearance/font_size", 14, type=int),
            )
        self.ha_url.setText(str(self.settings.value("homeassistant/url")))
        if self.settings.value("homeassistant/remember_webhook", False, type=bool):
            self.webhook.setText(str(self.settings.value("homeassistant/webhook_id", "")))


def main() -> int:
    app = QApplication(sys.argv)
    app.setOrganizationName("ManagerRifiuti")
    app.setApplicationName("Manager Rifiuti")
    settings = QSettings()
    apply_theme(
        app,
        str(settings.value("appearance/theme", "Chiaro")),
        str(settings.value("appearance/accent", "Verde")),
        settings.value("appearance/font_size", 14, type=int),
    )
    window = MainWindow()
    window.show()
    return app.exec()
