"""Dates written in Polish text: 22.11.2026, 22-11-2026, 22/11/2026, 2026-11-22 and "22 listopada
2026 r.". Reads the dates of a filled request, and checks that a date the letter reader gives is
really written in the letter: the AI copies dates, it never computes them (CLAUDE.md)."""

import datetime as dt
import re

MONTHS = {
    "stycznia": 1,
    "lutego": 2,
    "marca": 3,
    "kwietnia": 4,
    "maja": 5,
    "czerwca": 6,
    "lipca": 7,
    "sierpnia": 8,
    "września": 9,
    "października": 10,
    "listopada": 11,
    "grudnia": 12,
}

_DAY_FIRST = re.compile(r"(?<!\d)(\d{1,2})[./-](\d{1,2})[./-](\d{4})(?!\d)")
_ISO = re.compile(r"(?<!\d)(\d{4})-(\d{1,2})-(\d{1,2})(?!\d)")
_WORDS = re.compile(rf"(?<!\d)(\d{{1,2}})\s+({'|'.join(MONTHS)})\s+(\d{{4}})(?!\d)", re.IGNORECASE)


def _date(year: str, month: str | int, day: str) -> dt.date | None:
    try:
        return dt.date(int(year), int(month), int(day))
    except ValueError:
        return None


def dates_in(text: str) -> list[dt.date]:
    """Every valid date in the text, in the order it is written."""
    found: list[tuple[int, dt.date | None]] = []
    found += [(m.start(), _date(m[3], m[2], m[1])) for m in _DAY_FIRST.finditer(text)]
    found += [(m.start(), _date(m[1], m[2], m[3])) for m in _ISO.finditer(text)]
    found += [(m.start(), _date(m[3], MONTHS[m[2].lower()], m[1])) for m in _WORDS.finditer(text)]
    return [day for _, day in sorted(found, key=lambda hit: hit[0]) if day is not None]


def mentions(text: str | None, day: dt.date) -> bool:
    """The text has this date written in it."""
    return bool(text) and day in dates_in(text or "")
