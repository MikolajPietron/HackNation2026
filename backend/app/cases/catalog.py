"""The example cases from ZUS, numbered S01–S86 exactly as tools/zus-data/build_catalog.py does:
the category comes from the file name, files are sorted by category and name, the duplicate
"(1)" is skipped. File names contain names of people, so they stay on the server: the API shows
only the id and the category."""

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

# Same order and patterns as tools/zus-data/build_catalog.py (CATS).
CATEGORIES: list[tuple[str, str]] = [
    ("Odmowa", r"odmow|odmown"),
    ("Martwe urodzenie", r"martw"),
    ("Adopcja / rodzina zastępcza", r"przyj[ęe]ci|przysposob|zast[ęe]pcz"),
    ("Zasiłek w wys. zas. macierzyńskiego", r"w wysoko[śs]ci zas"),
    ("Wcześniak / uzupełniający", r"uzupe[łl]n|wcze[śs]niak"),
    ("Bliźnięta / Za życiem", r"bli[źz]ni|za [żz]yciem"),
    ("Łączenie rodzicielskiego z pracą", r"[łl][ąęa]czenie"),
    ("Ojciec: 9 tyg. / przejęcie", r"9 tyg|dla ojca|rezygnacja|ojciec"),
    ("Urlop ojcowski", r"ojcowsk"),
    ("Chorobowy w ciąży", r"chorobow"),
    ("Macierzyński + rodzicielski", r"rodzicielsk|u\. rodz|cz[ęe][śs][ćc]"),
    ("Macierzyński", r"mac"),
]
OTHER = "Inne"


@dataclass(frozen=True)
class CaseFile:
    id: str
    category: str
    path: Path


def category(name: str) -> str:
    lower = unicodedata.normalize("NFC", name).lower()
    return next((label for label, pattern in CATEGORIES if re.search(pattern, lower)), OTHER)


def list_case_files(folder: Path) -> list[CaseFile]:
    if not folder.is_dir():
        return []
    files = [
        path
        for path in folder.iterdir()
        if path.suffix.lower() == ".pdf" and not path.stem.endswith("(1)")
    ]
    order = [label for label, _ in CATEGORIES] + [OTHER]
    named = [(unicodedata.normalize("NFC", path.stem), path) for path in files]
    named.sort(key=lambda item: (order.index(category(item[0])), item[0]))
    return [
        CaseFile(id=f"S{index:02d}", category=category(name), path=path)
        for index, (name, path) in enumerate(named, 1)
    ]


def find_case(folder: Path, case_id: str) -> CaseFile | None:
    return next((case for case in list_case_files(folder) if case.id == case_id), None)
