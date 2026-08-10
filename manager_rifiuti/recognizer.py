from __future__ import annotations

import calendar
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import cv2
import numpy as np

from .models import Collection

MONTHS = {
    "gennaio": 1,
    "febbraio": 2,
    "marzo": 3,
    "aprile": 4,
    "maggio": 5,
    "giugno": 6,
    "luglio": 7,
    "agosto": 8,
    "settembre": 9,
    "ottobre": 10,
    "novembre": 11,
    "dicembre": 12,
}
TOKENS = ("TS", "O", "I", "V", "M", "P", "C", "S")
TS_PATTERN = re.compile(r"(?<![A-Z])T[\W_]*[S5](?![A-Z])", re.IGNORECASE)


@dataclass
class RecognitionResult:
    collections: list[Collection] = field(default_factory=list)
    detected_year: int | None = None
    months: list[int] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    preview: np.ndarray | None = None


def _order(points: np.ndarray) -> np.ndarray:
    result = np.zeros((4, 2), dtype=np.float32)
    sums, differences = points.sum(1), np.diff(points, axis=1).ravel()
    result[0], result[2] = points[np.argmin(sums)], points[np.argmax(sums)]
    result[1], result[3] = points[np.argmin(differences)], points[np.argmax(differences)]
    return result


def rectify(image: np.ndarray) -> np.ndarray:
    """Rotate and flatten the largest paper-like quadrilateral."""
    if image.shape[0] > image.shape[1]:
        image = cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE)
    scale = min(1.0, 1600 / image.shape[1])
    small = cv2.resize(image, None, fx=scale, fy=scale)
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), 40, 130)
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:15]:
        polygon = cv2.approxPolyDP(contour, 0.02 * cv2.arcLength(contour, True), True)
        if len(polygon) != 4 or cv2.contourArea(polygon) < small.size * 0.03:
            continue
        points = _order(polygon.reshape(4, 2).astype(np.float32) / scale)
        width = int(
            max(np.linalg.norm(points[1] - points[0]), np.linalg.norm(points[2] - points[3]))
        )
        height = int(
            max(np.linalg.norm(points[3] - points[0]), np.linalg.norm(points[2] - points[1]))
        )
        target = np.array(
            [[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]], np.float32
        )
        return cv2.warpPerspective(
            image, cv2.getPerspectiveTransform(points, target), (width, height)
        )
    return image


def extract_waste_tokens(text: str) -> set[str]:
    """Extract every legend code, including joined text and OCR variants of ``TS``."""
    normalized = text.upper()
    found: set[str] = set()
    if TS_PATTERN.search(normalized):
        found.add("TS")
        normalized = TS_PATTERN.sub(" TS ", normalized)
    for chunk in re.findall(r"[A-Z]+", normalized):
        index = 0
        while index < len(chunk):
            if chunk.startswith("TS", index):
                found.add("TS")
                index += 2
            else:
                token = chunk[index]
                if token in TOKENS[1:]:
                    found.add(token)
                index += 1
    return found


class CalendarRecognizer:
    """Offline recognizer specialized for the municipality's six-column layout."""

    def __init__(self) -> None:
        try:
            from rapidocr_onnxruntime import RapidOCR
        except ImportError:
            self.ocr = None
        else:
            self.ocr = RapidOCR()

    def _text(self, image: np.ndarray) -> list[tuple[str, list]]:
        if self.ocr is None:
            return []
        output, _ = self.ocr(image)
        return [(str(item[1]).strip(), item[0]) for item in (output or [])]

    def recognize(self, path: str | Path, fallback_year: int | None = None) -> RecognitionResult:
        image = cv2.imread(str(path))
        if image is None:
            raise ValueError(f"Impossibile leggere l'immagine: {path}")
        image = rectify(image)
        result = RecognitionResult(preview=image)
        words = self._text(image)
        all_text = " ".join(text for text, _ in words).lower()
        years = re.findall(r"\b20\d{2}\b", all_text)
        result.detected_year = int(years[0]) if years else fallback_year
        month_hits: list[tuple[int, float]] = []
        for text, box in words:
            normalized = re.sub(r"[^a-zàèéìòù]", "", text.lower())
            for name, number in MONTHS.items():
                if name in normalized:
                    x = sum(point[0] for point in box) / len(box)
                    month_hits.append((number, x))
                    break
        month_hits = sorted(dict(month_hits).items(), key=lambda item: item[1])
        result.months = [month for month, _ in month_hits]
        if not result.months:
            result.warnings.append("Mesi non riconosciuti: selezionarli nella revisione.")
            result.months = [7, 8, 9, 10, 11, 12]
        working_year = result.detected_year or fallback_year or date.today().year
        if result.detected_year is None:
            result.warnings.append("Anno non riconosciuto: è obbligatorio confermarlo.")

        # The fixed sheet has six equal month columns. Each calendar cell is read
        # independently so text from adjacent months cannot be merged or assigned
        # to the wrong day. The left margin contains the printed day number and is
        # ignored; only the area containing the legend codes is sent to OCR.
        h, w = image.shape[:2]
        grid_top, grid_bottom = int(h * 0.075), int(h * 0.84)
        column_width = w / 6
        for column, month in enumerate(result.months[:6]):
            days = calendar.monthrange(working_year, month)[1]
            x0, x1 = int(column * column_width), int((column + 1) * column_width)
            for day in range(1, days + 1):
                y0 = int(grid_top + (day - 1) * (grid_bottom - grid_top) / 31)
                y1 = int(grid_top + day * (grid_bottom - grid_top) / 31)
                cell = image[y0:y1, x0 + int(column_width * 0.18) : x1]
                if 0 < cell.shape[0] < 48:
                    scale = 48 / cell.shape[0]
                    cell = cv2.resize(cell, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
                cell_text = " ".join(text for text, _ in self._text(cell))
                for token in extract_waste_tokens(cell_text):
                    result.collections.append(
                        Collection(date(working_year, month, day), token, 0.82)
                    )
        if not result.collections:
            result.warnings.append(
                "Nessun simbolo riconosciuto: verificare manualmente tutte le date."
            )
        return result

