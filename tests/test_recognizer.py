from datetime import date

import cv2
import numpy as np

from manager_rifiuti.recognizer import (
    CalendarRecognizer,
    _classify_icon,
    _complete_semester_hits,
    _fit_label_edges,
    extract_waste_tokens,
    rectify,
)


def test_rectify_does_not_rotate_an_upright_portrait_photo():
    image = np.full((300, 180, 3), 255, dtype=np.uint8)
    corrected = rectify(image)
    assert corrected.shape == image.shape


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
    assert extract_waste_tokens("CC VMC") == {"V"}


def test_recognizer_reads_each_calendar_cell_and_keeps_all_codes(tmp_path, monkeypatch):
    image_path = tmp_path / "calendar.png"
    cv2.imwrite(str(image_path), np.full((620, 1200, 3), 255, dtype=np.uint8))
    recognizer = CalendarRecognizer.__new__(CalendarRecognizer)
    calls = []

    def box(center_x, center_y, width=80, height=12):
        return [
            [center_x - width / 2, center_y - height / 2],
            [center_x + width / 2, center_y - height / 2],
            [center_x + width / 2, center_y + height / 2],
            [center_x - width / 2, center_y + height / 2],
        ]

    def fake_text(image):
        calls.append(image.shape)
        names = ["luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]
        words = [(name, box(column * 200 + 100, 0)) for column, name in enumerate(names)]
        words.append(("O I T S V M P C S", box(100, 19)))
        return words

    monkeypatch.setattr(recognizer, "_text", fake_text)

    result = recognizer.recognize(image_path, fallback_year=2026)

    assert len(calls) == 1
    assert {(item.day, item.waste) for item in result.collections} == {
        (date(2026, 7, 1), code) for code in ("O", "I", "TS", "V", "M", "P", "C", "S")
    }


def test_visual_icon_colours_distinguish_requested_and_commercial_types():
    assert _classify_icon(19, 82, 92) == "O"
    assert _classify_icon(18, 148, 155) == "C"
    assert _classify_icon(37, 137, 128) == "S"
    assert _classify_icon(100, 49, 136) == "P"
    assert _classify_icon(105, 97, 112) == "V"
    assert _classify_icon(100, 101, 138) == "M"
    assert _classify_icon(20, 70, 163) is None  # CC
    assert _classify_icon(97, 89, 96) is None  # MC


def test_missing_first_semester_header_is_reconstructed_from_neighbours():
    hits = [(8, 610.0, 138.0), (9, 1150.0, 142.0), (10, 1600.0, 148.0), (11, 2100.0, 152.0)]

    completed = _complete_semester_hits(hits, 3024)

    assert [month for month, _x, _y in completed] == [7, 8, 9, 10, 11, 12]
    assert completed[0][1] == 70.0


def test_split_day_and_weekday_boxes_define_the_icon_margin():
    def box(left, top, right, bottom):
        return [[left, top], [right, top], [right, bottom], [left, bottom]]

    words = []
    for day in range(1, 7):
        y = 100 + day * 50
        words.extend(
            [
                (str(day), box(410, y - 10, 440, y + 10)),
                ("LU", box(455, y - 10, 495, y + 10)),
            ]
        )

    label_start, label_edge = _fit_label_edges(words, 380, 880, 50, 1000)

    assert abs(label_start[0] - 410) < 1
    assert abs(label_edge[0] - 495) < 1

