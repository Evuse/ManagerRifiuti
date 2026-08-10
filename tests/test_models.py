from datetime import date

from manager_rifiuti.models import Collection


def test_collection_serialization():
    assert Collection(date(2026, 7, 2), "O", 0.9).to_dict() == {
        "day": "2026-07-02",
        "waste": "O",
        "confidence": 0.9,
    }
