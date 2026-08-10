from __future__ import annotations

import calendar
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from itertools import pairwise
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
DAY_PREFIX = re.compile(r"^(\d{1,2})")
DAY_LABEL = re.compile(r"^\d{1,2}(?:LU|MA|ME|GI|VE|SA|D[O0])$", re.IGNORECASE)


@dataclass
class RecognitionResult:
    collections: list[Collection] = field(default_factory=list)
    detected_year: int | None = None
    months: list[int] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    preview: np.ndarray | None = None


@dataclass(frozen=True)
class MonthGrid:
    month: int
    left: float
    right: float
    row_curve: np.ndarray
    label_start: np.ndarray
    label_edge: np.ndarray

    def row_center(self, day: int) -> float:
        offset = day - 1
        return float(self.row_curve @ np.array([1, offset, offset * offset]))

    def label_right(self, y: float) -> float:
        return float(self.label_edge @ np.array([1, y]))

    def label_left(self, y: float) -> float:
        return float(self.label_start @ np.array([1, y]))


def _order(points: np.ndarray) -> np.ndarray:
    result = np.zeros((4, 2), dtype=np.float32)
    sums, differences = points.sum(1), np.diff(points, axis=1).ravel()
    result[0], result[2] = points[np.argmin(sums)], points[np.argmax(sums)]
    result[1], result[3] = points[np.argmin(differences)], points[np.argmax(differences)]
    return result


def rectify(image: np.ndarray) -> np.ndarray:
    """Rotate and flatten the largest paper-like quadrilateral."""
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
    normalized = re.sub(r"T[\W_]*5", "TS", normalized)
    found: set[str] = set()
    if TS_PATTERN.search(normalized):
        found.add("TS")
        normalized = TS_PATTERN.sub(" TS ", normalized)
    normalized = re.sub(r"(?<![A-Z])C[\W_]+C(?![A-Z])", "CC", normalized)
    normalized = re.sub(r"(?<![A-Z])M[\W_]+C(?![A-Z])", "MC", normalized)
    for chunk in re.findall(r"[A-Z]+", normalized):
        index = 0
        while index < len(chunk):
            if chunk.startswith("TS", index):
                found.add("TS")
                index += 2
            elif chunk.startswith(("CC", "MC"), index):
                index += 2
            else:
                token = chunk[index]
                if token in TOKENS[1:]:
                    found.add(token)
                index += 1
    return found


def _classify_icon(hue: float, saturation: float, value: float) -> str | None:
    """Classify the municipality's colour-coded icon (OpenCV HSV ranges)."""
    if value <= 65 and saturation <= 65:
        return "TS"
    if hue < 29 and saturation <= 52 and 76 <= value <= 115:
        return "I"
    if 10 <= hue <= 32 and 55 <= saturation <= 115 and value <= 140:
        return "O"
    if 10 <= hue <= 30 and saturation >= 110 and value >= 105:
        return "C"
    if 25 <= hue <= 65 and saturation >= 95 and value >= 90:
        return "S"
    if 78 <= hue <= 125 and 30 <= saturation <= 75 and value >= 105:
        return "P"
    if 102 <= hue <= 125 and saturation >= 70 and 75 <= value < 130:
        return "V"
    if 78 <= hue <= 108 and saturation >= 72 and value >= 112:
        return "M"
    return None


def _visual_waste_tokens(cell: np.ndarray) -> set[str] | None:
    """Read each coloured icon; return ``None`` only when no icon group exists.

    This is authoritative when symbols are present.  It deliberately maps CC,
    MC and the non-domestic pictogram to nothing, preventing partial OCR text
    such as ``M`` from turning ``MC`` into a household metals collection.
    """
    if cell.size == 0:
        return None

    hsv = cv2.cvtColor(cell, cv2.COLOR_BGR2HSV)
    _hue, saturation, value = cv2.split(hsv)
    foreground = (
        ((saturation > 28) & (value < 245)) | (value < 135)
    ).astype(np.uint8) * 255
    kernel_size = max(3, round(cell.shape[0] * 0.05) | 1)
    foreground = cv2.morphologyEx(
        foreground,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size)),
    )
    _count, _labels, stats, _centroids = cv2.connectedComponentsWithStats(foreground)
    groups = [
        (x, y, width, height, area)
        for x, y, width, height, area in stats[1:]
        if height >= cell.shape[0] * 0.42 and area >= cell.shape[0] * cell.shape[0] * 0.08
    ]
    if not groups:
        return None

    tokens: set[str] = set()
    for x, y, width, height, _area in sorted(groups):
        aspect = width / max(1.0, height)
        if aspect >= 3.0:
            icon_count = 4
        elif aspect >= 2.15:
            icon_count = 3
        elif aspect >= 1.35:
            icon_count = 2
        else:
            icon_count = 1
        pitch = width / icon_count
        medians: list[np.ndarray] = []
        for index in range(icon_count):
            center = (x + (index + 0.5) * pitch, y + height / 2)
            patch = cv2.getRectSubPix(
                cell,
                (max(15, int(pitch * 0.65)), max(15, int(height * 0.62))),
                center,
            )
            pixels = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV).reshape(-1, 3)
            pixels = pixels[
                ((pixels[:, 1] > 25) & (pixels[:, 2] < 235)) | (pixels[:, 2] < 180)
            ]
            if len(pixels) < 20:
                continue
            medians.append(np.median(pixels, axis=0))

        # Multi-icon sequences have a stable semantic order in this calendar.
        # Reading the sequence avoids relying on the tiny white I/TS letters.
        if len(medians) >= 3 and medians[0][0] < 45 and medians[0][1] > 35:
            tokens.update(("O", "TS"))
            if len(medians) >= 4:
                tokens.add("I")
            continue
        if len(medians) == 2:
            first, second = medians
            if first[0] < 45 and first[1] > 35:
                tokens.add("O")
                if second[0] < 60 and second[1] > 80:
                    tokens.add("C")
                elif second[0] > 70:
                    tokens.add("P")
                continue
            if first[0] > 70 and first[1] > 55:
                tokens.add("V")
                continue

        for median in medians:
            token = _classify_icon(*median)
            if token is not None:
                tokens.add(token)

    # The very pale plastic symbol may not touch the darker O component after
    # thresholding. Its cyan fill remains unambiguous inside an O-led cell.
    if "O" in tokens and "C" not in tokens:
        plastic = (
            (_hue >= 75)
            & (_hue <= 130)
            & (saturation >= 25)
            & (saturation <= 100)
            & (value >= 95)
            & (value <= 230)
        )
        if np.count_nonzero(plastic) >= cell.shape[0] * cell.shape[0] * 0.05:
            tokens.add("P")
    return tokens


def _box_center(box: list) -> tuple[float, float]:
    return (
        sum(point[0] for point in box) / len(box),
        sum(point[1] for point in box) / len(box),
    )


def _month_hits(words: list[tuple[str, list]]) -> list[tuple[int, float, float]]:
    hits: dict[int, tuple[float, float]] = {}
    for text, box in words:
        normalized = re.sub(r"[^a-zàèéìòù]", "", text.lower())
        for name, month in MONTHS.items():
            if name in normalized:
                hits[month] = _box_center(box)
                break
    return sorted(((month, x, y) for month, (x, y) in hits.items()), key=lambda item: item[1])


def _fit_row_curve(
    words: list[tuple[str, list]], left: float, right: float, header_y: float, height: int
) -> np.ndarray:
    candidates: list[tuple[int, float]] = []
    for text, box in words:
        x, y = _box_center(box)
        match = DAY_PREFIX.match(text.upper().replace("O", "0"))
        if not match or not (left <= x < left + (right - left) * 0.68):
            continue
        day = int(match.group(1))
        if 1 <= day <= 31 and header_y + 40 < y < height * 0.85:
            candidates.append((day, y))

    slopes = [
        (second_y - first_y) / (second_day - first_day)
        for index, (first_day, first_y) in enumerate(candidates)
        for second_day, second_y in candidates[index + 1 :]
        if abs(second_day - first_day) >= 5
        and height / 80 < (second_y - first_y) / (second_day - first_day) < height / 25
    ]
    if not slopes:
        return np.array([header_y + height * 0.03, height * 0.024, 0.0])

    slope = float(np.median(slopes))
    intercept = float(np.median([y - slope * (day - 1) for day, y in candidates]))
    inliers = [
        (day, y) for day, y in candidates if abs(y - (intercept + slope * (day - 1))) < slope * 0.5
    ]
    if len(inliers) < 6:
        return np.array([intercept, slope, 0.0])
    design = np.array([[1, day - 1, (day - 1) ** 2] for day, _ in inliers])
    values = np.array([y for _, y in inliers])
    return np.linalg.lstsq(design, values, rcond=None)[0]


def _fit_label_edges(
    words: list[tuple[str, list]], left: float, right: float, header_y: float, height: int
) -> tuple[np.ndarray, np.ndarray]:
    labels: list[tuple[float, float, float]] = []
    for text, box in words:
        x, y = _box_center(box)
        if (
            left <= x < right
            and header_y + 40 < y < height * 0.85
            and DAY_LABEL.match(text.upper())
        ):
            labels.append(
                (y, min(point[0] for point in box), max(point[0] for point in box))
            )
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
        month_hits = _month_hits(words)
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
                tokens = (
                    visual_tokens
                    if visual_tokens is not None
                    else extract_waste_tokens(cell_text)
                )
                for token in tokens:
                    result.collections.append(
                        Collection(date(working_year, grid.month, day), token, 0.82)
                    )
        if not result.collections:
            result.warnings.append(
                "Nessun simbolo riconosciuto: verificare manualmente tutte le date."
            )
        return result

