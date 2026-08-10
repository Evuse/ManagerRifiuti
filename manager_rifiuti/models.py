from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date

WASTE_NAMES = {
    "O": "Organico",
    "I": "Indifferenziata",
    "TS": "Pannolini",
    "V": "Vetro",
    "M": "Metallo",
    "P": "Plastica",
    "C": "Carta",
    "S": "Sfalci verdi",
}


@dataclass(frozen=True, order=True)
class Collection:
    day: date
    waste: str
    confidence: float = 1.0

    def to_dict(self) -> dict:
        data = asdict(self)
        data["day"] = self.day.isoformat()
        return data
