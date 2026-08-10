from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
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
        except Exception as exc:  # thread boundary: errors must be shown in the GUI
            self.failed.emit(str(exc))


class ReviewDialog(QDialog):
    def __init__(self, results: list[RecognitionResult], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Revisione obbligatoria")
        self.resize(920, 700)
        years = [r.detected_year for r in results if r.detected_year]
        self.year = QSpinBox()
        self.year.setRange(2020, 2100)
        self.year.setValue(years[0] if years else date.today().year)
        self.confirm = QCheckBox("Confermo che l'anno selezionato Ã¨ corretto")
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
        seen = set()
        for result in results:
            for collection in result.collections:
                key = (collection.day.month, collection.day.day, collection.waste)
                if key not in seen:
                    self.add_row(*key)
                    seen.add(key)
        add = QPushButton("Aggiungi raccolta")
        remove = QPushButton("Rimuovi selezionate")
        add.clicked.connect(lambda: self.add_row(1, 1, "O"))
        remove.clicked.connect(self.remove_rows)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        warning_text = "\n".join(w for r in results for w in r.warnings)
        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                "Scegli le tipologie che ti interessano e controlla ogni raccolta. "
                "Per impostazione predefinita sono incluse tutte."
            )
        )
        if warning_text:
            warning = QLabel(warning_text)
            warning.setStyleSheet("color: #9c4a00")
            layout.addWidget(warning)
        form = QFormLayout()
        form.addRow("Anno rilevato:", self.year)
        layout.addLayout(form)
        layout.addWidget(self.confirm)
        layout.addWidget(self.confirm_months)
        layout.addWidget(waste_group)
        layout.addWidget(self.table)
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
        waste_selector = QComboBox()
        for code, name in WASTE_NAMES.items():
            waste_selector.addItem(name, code)
        selected_index = waste_selector.findData(waste)
        waste_selector.setCurrentIndex(max(selected_index, 0))
        waste_selector.currentIndexChanged.connect(
            lambda _index, current_row=row: self.sync_row_enabled(current_row)
        )
        self.table.setCellWidget(row, 1, waste_selector)
        checked = QTableWidgetItem("SÃ¬")
        checked.setFlags(checked.flags() | Qt.ItemIsUserCheckable)
        waste_is_enabled = self.waste_checks[waste_selector.currentData()].isChecked()
        checked.setCheckState(Qt.Checked if waste_is_enabled else Qt.Unchecked)
        self.table.setItem(row, 2, checked)

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

    def set_waste_enabled(self, waste: str, enabled: bool) -> None:
        for row in range(self.table.rowCount()):
            if self.row_waste(row) == waste:
                self.table.item(row, 2).setCheckState(Qt.Checked if enabled else Qt.Unchecked)

    def remove_rows(self) -> None:
        for index in sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True):
            self.table.removeRow(index)

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
        self.setWindowTitle("Manager Rifiuti")
        self.resize(760, 460)
        self.paths: list[str] = []
        self.collections: list[Collection] = []
        self.year: int | None = None
        title = QLabel("Importa il calendario rifiuti")
        title.setStyleSheet("font-size: 24px; font-weight: 600")
        self.files = QLabel("Nessuna immagine selezionata")
        choose = QPushButton("Scegli una o due immaginiâ€¦")
        choose.clicked.connect(self.choose_files)
        self.analyze = QPushButton("Analizza localmente")
        self.analyze.setEnabled(False)
        self.analyze.clicked.connect(self.start_analysis)
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.status = QLabel("Le immagini non vengono mai inviate in rete.")
        self.ha_url = QLineEdit("http://homeassistant.local:8123")
        self.webhook = QLineEdit()
        self.webhook.setPlaceholderText("ID mostrato dall'integrazione")
        self.send = QPushButton("Invia il calendario a Home Assistant")
        self.send.setEnabled(False)
        self.send.clicked.connect(self.send_calendar)
        form = QFormLayout()
        form.addRow("Indirizzo Home Assistant:", self.ha_url)
        form.addRow("ID webhook:", self.webhook)
        layout = QVBoxLayout()
        layout.setContentsMargins(32, 28, 32, 28)
        layout.addWidget(title)
        layout.addSpacing(12)
        layout.addWidget(self.files)
        layout.addWidget(choose)
        layout.addWidget(self.analyze)
        layout.addWidget(self.progress)
        layout.addWidget(self.status)
        layout.addStretch()
        layout.addLayout(form)
        layout.addWidget(self.send)
        widget = QWidget()
        widget.setLayout(layout)
        self.setCentralWidget(widget)
        export_action = QAction("Esporta backup JSONâ€¦", self)
        export_action.triggered.connect(self.export_json)
        self.menuBar().addMenu("File").addAction(export_action)

    def choose_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Calendario", "", "Immagini (*.jpg *.jpeg *.png *.webp *.tif *.tiff)"
        )
        if len(paths) > 2:
            QMessageBox.warning(self, "Troppi file", "Seleziona al massimo due immagini.")
            return
        if paths:
            self.paths = paths
            self.files.setText("\n".join(Path(p).name for p in paths))
            self.analyze.setEnabled(True)

    def start_analysis(self) -> None:
        self.progress.setRange(0, 0)
        self.progress.setVisible(True)
        self.analyze.setEnabled(False)
        self.status.setText("Correzione prospettiva e riconoscimento OCR in corsoâ€¦")
        self.worker = RecognitionWorker(self.paths)
        self.worker.completed.connect(self.review)
        self.worker.failed.connect(self.failure)
        self.worker.start()

    def failure(self, message: str) -> None:
        self.progress.setVisible(False)
        self.analyze.setEnabled(True)
        QMessageBox.critical(self, "Analisi non riuscita", message)

    def review(self, results: list[RecognitionResult]) -> None:
        self.progress.setVisible(False)
        self.analyze.setEnabled(True)
        dialog = ReviewDialog(results, self)
        if dialog.exec() == QDialog.Accepted:
            self.collections = dialog.collections()
            self.year = dialog.year.value()
            self.send.setEnabled(True)
            self.status.setText(
                f"Revisione completata: {len(self.collections)} raccolte per il {self.year}."
            )

    def send_calendar(self) -> None:
        if not self.webhook.text().strip():
            QMessageBox.warning(
                self, "Webhook mancante", "Inserisci l'ID webhook di Home Assistant."
            )
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            upload(self.ha_url.text(), self.webhook.text(), self.year or 0, self.collections)
        except Exception as exc:
            QMessageBox.critical(self, "Invio non riuscito", str(exc))
        else:
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
            Path(path).write_text(
                json.dumps(
                    {"year": self.year, "collections": [c.to_dict() for c in self.collections]},
                    indent=2,
                ),
                encoding="utf-8",
            )


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Manager Rifiuti")
    window = MainWindow()
    window.show()
    return app.exec()

