import json
from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox

from manager_rifiuti.app import ReviewDialog, write_backup
from manager_rifiuti.models import WASTE_NAMES, Collection
from manager_rifiuti.recognizer import RecognitionResult


def make_dialog(qtbot):
    result = RecognitionResult(
        collections=[
            Collection(date(2026, 7, 2), "O"),
            Collection(date(2026, 7, 3), "P"),
        ],
        detected_year=2026,
        months=[7, 8, 9, 10, 11, 12],
    )
    dialog = ReviewDialog([result])
    qtbot.addWidget(dialog)
    return dialog


def test_review_selects_all_waste_types_by_default(qtbot):
    dialog = make_dialog(qtbot)

    assert [checkbox.text() for checkbox in dialog.waste_checks.values()] == list(
        WASTE_NAMES.values()
    )
    assert all(checkbox.isChecked() for checkbox in dialog.waste_checks.values())


def test_review_shows_names_instead_of_codes(qtbot):
    dialog = make_dialog(qtbot)

    selector = dialog.table.cellWidget(0, 1)
    assert isinstance(selector, QComboBox)
    assert selector.currentText() == "Organico"
    assert selector.currentData() == "O"


def test_disabling_a_type_excludes_only_its_rows(qtbot):
    dialog = make_dialog(qtbot)

    dialog.waste_checks["O"].setChecked(False)
    dialog.table.item(0, 2).setCheckState(Qt.Checked)

    assert dialog.table.item(1, 2).checkState() == Qt.Checked
    assert [(item.day, item.waste) for item in dialog.collections()] == [(date(2026, 7, 3), "P")]


def test_type_change_targets_current_row_after_an_earlier_row_is_removed(qtbot):
    dialog = make_dialog(qtbot)
    dialog.waste_checks["O"].setChecked(False)
    dialog.table.removeRow(0)

    selector = dialog.table.cellWidget(0, 1)
    assert isinstance(selector, QComboBox)
    selector.setCurrentIndex(selector.findData("O"))

    assert dialog.table.item(0, 2).checkState() == Qt.Unchecked


def test_backup_contains_all_reviewed_collections(tmp_path):
    path = tmp_path / "backup" / "raccolte-2026.json"
    collections = [
        Collection(date(2026, 8, 10), "O"),
        Collection(date(2026, 8, 10), "I"),
        Collection(date(2026, 8, 10), "TS"),
    ]

    write_backup(path, 2026, collections)

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["year"] == 2026
    assert [(item["day"], item["waste"]) for item in payload["collections"]] == [
        ("2026-08-10", "O"),
        ("2026-08-10", "I"),
        ("2026-08-10", "TS"),
    ]
