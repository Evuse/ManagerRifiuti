from datetime import date

import cv2
import numpy as np

from manager_rifiuti.recognizer import CalendarRecognizer, extract_waste_tokens, rectify


def test_rectify_rotates_portrait_image():
    image = np.full((300, 180, 3), 255, dtype=np.uint8)
    corrected = rectify(image)
    assert corrected.shape[1] > corrected.shape[0]


def test_rectify_keeps_landscape_image():
    image = np.full((180, 300, 3), 255, dtype=np.uint8)
    corrected = rectify(image)
    assert corrected.shape == image.shape


def test_extract_waste_tokens_recognizes_ts_variants():
    assert extract_waste_tokens("TS") == {"TS"}
    assert extract_waste_tokens("T S") == {"TS"}
    assert extract_waste_tokens("T-5") == {"TS"}
    assert extract_waste_tokens("TS O") == {"TS", "O"}
    assert extract_waste_tokens("OITSVMPCS") == {
        "O",
        "I",
        "TS",
        "V",
        "M",
        "P",
        "C",
        "S",
    }


def test_recognizer_reads_each_calendar_cell_and_keeps_all_codes(tmp_path, monkeypatch):
    image_path = tmp_path / "calendar.png"
    cv2.imwrite(str(image_path), np.full((620, 1200, 3), 255, dtype=np.uint8))
    recognizer = CalendarRecognizer.__new__(CalendarRecognizer)
    calls = []

    def fake_text(image):
        calls.append(image.shape)
        if len(calls) == 1:
            names = ["luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]
            return [
                (name, [[column * 200, 0], [column * 200 + 100, 0]])
                for column, name in enumerate(names)
            ]
        if len(calls) == 2:
            return [("O I T S V M P C S", [[80, 0], [120, 0]])]
        return []

    monkeypatch.setattr(recognizer, "_text", fake_text)

    result = recognizer.recognize(image_path, fallback_year=2026)

    assert len(calls) == 185
    assert {(item.day, item.waste) for item in result.collections} == {
        (date(2026, 7, 1), code) for code in ("O", "I", "TS", "V", "M", "P", "C", "S")
    }

