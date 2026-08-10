from __future__ import annotations

import json
import sys
from datetime import date, datetime
from pathlib import Path

from PySide6.QtCore import QSettings, QStandardPaths, Qt, QThread, Signal
from PySide6.QtGui import QAction, QDragEnterEvent, QDropEvent
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
    changed = Signal(str)

    def __init__(self, settings: QSettings, parent=None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Impostazioni")
        self.setMinimumWidth(520)
        self.theme = QComboBox()
        self.theme.addItems(["Chiaro", "Scuro"])
        self.theme.setCurrentText(str(settings.value("appearance/theme", "Chiaro")))
        self.ha_url = QLineEdit(
            str(settings.value("homeassistant/url", "http://homeassistant.local:8123"))
        )
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
        form = QFormLayout()
        form.addRow("Tema:", self.theme)
        form.addRow("Indirizzo Home Assistant:", self.ha_url)
        form.addRow("Backup automatico:", self.auto_backup)
        form.addRow("Cartella backup:", folder_row)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
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
        self.settings.setValue("homeassistant/url", url)
        self.settings.setValue("backup/enabled", self.auto_backup.isChecked())
        self.settings.setValue("backup/folder", self.backup_folder.text().strip())
        self.settings.sync()
        self.changed.emit(self.theme.currentText())
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
        self.confirm =…8684 tokens truncated…left, box_right))
            elif normalized.isdigit() and 1 <= int(normalized) <= 31:
                day_parts.append((y, box_left, box_right))
            elif WEEKDAY_LABEL.match(normalized):
                weekday_parts.append((y, box_left, box_right))

    row_tolerance = height / 100
    for y, day_left, day_right in day_parts:
        weekdays = [
            (weekday_y, weekday_right)
            for weekday_y, weekday_left, weekday_right in weekday_parts
            if abs(weekday_y - y) <= row_tolerance
            and day_right <= weekday_left < left + (right - left) * 0.75
        ]
        if weekdays:
            _weekday_y, weekday_right = min(weekdays, key=lambda item: abs(item[0] - y))
            labels.append((y, day_left, weekday_right))
    if len(labels) < 4:
        return (
            np.array([left + (right - left) * 0.08, 0.0]),
            np.array([left + (right - left) * 0.32, 0.0]),
        )
    design = np.array([[1, y] for y, _left, _right in labels])

    def fit(values: np.ndarray) -> np.ndarray:
        result = np.linalg.lstsq(design, values, rcond=None)[0]
        residuals = np.abs(values - design @ result)
        inliers = residuals < max(12.0, (right - left) * 0.06)
        if inliers.sum() >= 4:
            result = np.linalg.lstsq(design[inliers], values[inliers], rcond=None)[0]
        return result

    return (
        fit(np.array([label_left for _y, label_left, _label_right in labels])),
        fit(np.array([label_right for _y, _label_left, label_right in labels])),
    )


def _build_grids(
    words: list[tuple[str, list]], hits: list[tuple[int, float, float]], shape: tuple
) -> list[MonthGrid]:
    height, width = shape[:2]
    if len(hits) < 2:
        months = [7, 8, 9, 10, 11, 12]
        column_width = width / 6
        return [
            MonthGrid(
                month,
                index * column_width,
                (index + 1) * column_width,
                np.array([height * 0.063, height * 0.024, -height * 0.00009]),
                np.array([(index + 0.08) * column_width, 0.0]),
                np.array([(index + 0.28) * column_width, 0.0]),
            )
            for index, month in enumerate(months)
        ]

    centers = [x for _, x, _ in hits]
    boundaries = [0.0]
    boundaries.extend((first + second) / 2 for first, second in pairwise(centers))
    boundaries.append(float(width))
    grids = []
    for (month, _x, header_y), left, right in zip(hits, boundaries, boundaries[1:]):
        label_start, label_edge = _fit_label_edges(words, left, right, header_y, height)
        grids.append(
            MonthGrid(
                month,
                left,
                right,
                _fit_row_curve(words, left, right, header_y, height),
                label_start,
                label_edge,
            )
        )
    return grids


class CalendarRecognizer:
    """Offline recognizer specialized for the municipality's six-column layout."""

    def __init__(self) -> None:
        try:
            from rapidocr import RapidOCR
        except ImportError:
            try:
                from rapidocr_onnxruntime import RapidOCR
            except ImportError:
                self.ocr = None
            else:
                self.ocr = RapidOCR()
        else:
            self.ocr = RapidOCR()

    def _text(self, image: np.ndarray) -> list[tuple[str, list]]:
        if self.ocr is None:
            return []
        output = self.ocr(image)
        if hasattr(output, "txts"):
            boxes = getattr(output, "boxes", None)
            texts = getattr(output, "txts", None)
            if boxes is None or texts is None:
                return []
            return [(str(text).strip(), box.tolist()) for text, box in zip(texts, boxes)]
        legacy_output, _elapsed = output
        return [(str(item[1]).strip(), item[0]) for item in (legacy_output or [])]

    def recognize(self, path: str | Path, fallback_year: int | None = None) -> RecognitionResult:
        image = cv2.imread(str(path))
        if image is None:
            raise ValueError(f"Impossibile leggere l'immagine: {path}")
        image = rectify(image)
        result = RecognitionResult(preview=image)
        words = self._text(image)
        all_text = " ".join(text for text, _ in words).lower()
        years = [year for year in re.findall(r"\b20\d{2}\b", all_text) if int(year) >= 2020]
        result.detected_year = int(years[0]) if years else fallback_year
        month_hits = _complete_semester_hits(_month_hits(words), image.shape[1])
        result.months = [month for month, _x, _y in month_hits]
        if not result.months:
            result.warnings.append("Mesi non riconosciuti: selezionarli nella revisione.")
            result.months = [7, 8, 9, 10, 11, 12]
        working_year = result.detected_year or fallback_year or datetime.now().astimezone().year
        if result.detected_year is None:
            result.warnings.append("Anno non riconosciuto: è obbligatorio confermarlo.")

        # Month headers and printed day labels define the grid directly. This
        # compensates for camera perspective instead of assuming equal rows.
        grids = _build_grids(words, month_hits, image.shape)
        for grid_index, grid in enumerate(grids):
            days = calendar.monthrange(working_year, grid.month)[1]
            for day in range(1, days + 1):
                center = grid.row_center(day)
                previous = grid.row_center(day - 1) if day > 1 else 2 * center - grid.row_center(2)
                following = (
                    grid.row_center(day + 1) if day < 31 else 2 * center - grid.row_center(30)
                )
                y0 = max(0, int((previous + center) / 2))
                y1 = min(image.shape[0], int((center + following) / 2))
                margin = max(4.0, (grid.right - grid.left) * 0.01)
                label_right = grid.label_right(center)
                x0 = max(0, int(label_right + margin))
                if grid_index + 1 < len(grids):
                    x1 = int(grids[grid_index + 1].label_left(center) - margin)
                elif grid_index:
                    previous_start = grids[grid_index - 1].label_left(center)
                    x1 = int(grid.label_left(center) + (grid.label_left(center) - previous_start))
                else:
                    x1 = int(grid.right)
                x1 = min(image.shape[1], max(x0 + 1, x1))
                cell = image[y0:y1, x0:x1]
                # RapidOCR is intentionally run once on the full page. Reusing
                # those positioned words is much faster than 181-186 separate
                # model invocations and preserves more context for tiny glyphs.
                cell_text = " ".join(
                    text
                    for text, box in words
                    if x0 <= _box_center(box)[0] < x1 and y0 <= _box_center(box)[1] < y1
                )
                visual_tokens = _visual_waste_tokens(cell)
                tokens = _combine_cell_tokens(cell_text, visual_tokens)
                for token in tokens:
                    result.collections.append(
                        Collection(date(working_year, grid.month, day), token, 0.82)
                    )
        if not result.collections:
            result.warnings.append(
                "Nessun simbolo riconosciuto: verificare manualmente tutte le date."
            )
        return result
