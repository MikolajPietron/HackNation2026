"""Polish wording shared by the timeline and the case explanation."""

import datetime as dt

_MONTHS = [
    "stycznia",
    "lutego",
    "marca",
    "kwietnia",
    "maja",
    "czerwca",
    "lipca",
    "sierpnia",
    "września",
    "października",
    "listopada",
    "grudnia",
]

# Wording of the Labour Code (art. 180 § 1): "przy urodzeniu jednego dziecka / dwojga dzieci".
_CHILDREN = {1: "jednego dziecka", 2: "dwojga dzieci", 3: "trojga dzieci", 4: "czworga dzieci"}
_MULTIPLES = {2: "Bliźnięta", 3: "Trojaczki", 4: "Czworaczki"}


def fmt(d: dt.date) -> str:
    """15.03.2027"""
    return d.strftime("%d.%m.%Y")


def long_date(d: dt.date) -> str:
    """15 marca 2027"""
    return f"{d.day} {_MONTHS[d.month - 1]} {d.year}"


def children_phrase(count: int) -> str:
    """After "przy urodzeniu": "jednego dziecka", "dwojga dzieci", "6 dzieci"."""
    return _CHILDREN.get(count, f"{count} dzieci")


def multiples(count: int) -> str:
    """ "Bliźnięta", "Trojaczki", "6 dzieci" — for headings."""
    return _MULTIPLES.get(count, f"{count} dzieci")
