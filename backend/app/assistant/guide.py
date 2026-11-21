"""The guide (Przewodnik ZUS) as sections the app covers so far.

`przewodnik_pages.json` is the text of the PDF, page by page (regenerate with tools/przewodnik/).
A section is cut out of its pages between anchors, so its text is the document's own wording:
the model reads it, and every quote shown in the UI is checked against it. A sentence that runs
over a page break is joined from two parts, skipping the footnote printed between them.
"""

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

PAGES_FILE = Path(__file__).with_name("przewodnik_pages.json")


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


@dataclass(frozen=True)
class GuideSection:
    id: str
    title: str
    parts: tuple[tuple[int, str], ...]
    """(page, text) in reading order; consecutive parts continue the same running text."""

    @property
    def page(self) -> int:
        return self.parts[0][0]

    @property
    def last_page(self) -> int:
        return self.parts[-1][0]

    @property
    def text(self) -> str:
        return " ".join(text for _, text in self.parts)

    @property
    def pages_label(self) -> str:
        """ "s. 5" or "s. 5–6"."""
        return page_label(self.page, self.last_page)

    def pages_of(self, quote: str) -> tuple[int, int] | None:
        """The first and last page of `quote`, or None if it is not a literal fragment of this
        section (whitespace aside)."""
        wanted = normalize(quote)
        start = self.text.find(wanted)
        if start < 0 or not wanted:
            return None
        end = start + len(wanted) - 1
        pages = []
        offset = 0
        for page, text in self.parts:
            if start < offset + len(text) and end >= offset:
                pages.append(page)
            offset += len(text) + 1
        return pages[0], pages[-1]

    def contains(self, quote: str) -> bool:
        return self.pages_of(quote) is not None


def page_label(first: int | None, last: int | None = None) -> str:
    return f"s. {first}–{last}" if last and last != first else f"s. {first}"


# id, title, parts as (page, first words, last words): what the phases done so far rest on.
_SECTIONS: list[tuple[str, str, list[tuple[int, str, str]]]] = [
    # Who is insured (the sick-benefit chapter names both kinds of sickness insurance).
    (
        "ZC.o",
        "Ubezpieczenie chorobowe obowiązkowe",
        [(3, "obowiązkowego ubezpieczenia chorobowego", "(np. umowa o pracę)")],
    ),
    (
        "ZC.d",
        "Ubezpieczenie chorobowe dobrowolne",
        [(3, "dobrowolnego ubezpieczenia chorobowego", "działalność gospodarcza)")],
    ),
    # The maternity benefit chapter, before section A: who gets the benefit and for what periods.
    (
        "ZM",
        "Zasiłek macierzyński",
        [
            (4, "Zasiłek macierzyński jest świadczeniem wypłacanym", "następujące okresy urlopu:"),
            (5, "(w razie porodu)", "co do wymiaru i wysokości."),
        ],
    ),
    # Phase 1.
    ("A.1", "Przygotowanie do porodu", [(5, "Kobieta może rozpocząć", "po urodzeniu dziecka.")]),
    # Phase 2: the whole point; its last sentences continue on page 6, after footnote 2.
    (
        "A.2",
        "Urodzenie dziecka",
        [
            (5, "Po porodzie kobieta ubezpieczona", "nie więcej niż w"),
            (6, "5 częściach, nie później", "przysługuje zasiłek macierzyński."),
        ],
    ),
    (
        "A.2-przypis",
        "Zaświadczenie „Za życiem” (przypis 2 do punktu „Urodzenie dziecka”)",
        [
            (5, "Zaświadczenie „Za życiem” wydawane jest", "posiadający specjalizację"),
            (6, "II stopnia lub tytuł specjalisty", "lub chirurgii dziecięcej."),
        ],
    ),
    # Phase 3: stillbirth or death of the child; two bullets of one point.
    (
        "A.3",
        "Szczególna sytuacja: urodzenie martwego dziecka lub zgon dziecka",
        [
            (6, "W razie urodzenia martwego dziecka", "liczby dzieci pozostałych przy życiu."),
            (6, "W przypadku zgonu dziecka po upływie 8 tygodni", "pozostałych przy życiu."),
        ],
    ),
    # Section B "Zasiłek macierzyński dla mężczyzny (ojca dziecka)", pages 7-8.
    (
        "B",
        "Zasiłek macierzyński dla ojca dziecka",
        [(7, "Ojciec dziecka może korzystać", "nie korzysta z urlopu macierzyńskiego.")],
    ),
    (
        "B.1",
        "Przejęcie przez ojca części urlopu macierzyńskiego od matki dziecka",
        [(7, "Podstawowa zasada – matka musi", "po zakończeniu urlopu matki.")],
    ),
    (
        "B.2",
        "Sytuacje szczególne – przejęcie urlopu macierzyńskiego wcześniej niż po 14 tygodniach",
        [(7, "W sytuacjach określonych w Kodeksie pracy", "lub pozostałej części urlopu).")],
    ),
    (
        "B.3",
        "Zasiłek macierzyński za okres urlopu rodzicielskiego dla ojca",
        [(7, "Rodzice z urlopu rodzicielskiego mogą", "dziecko skończy 6 lat.")],
    ),
    (
        "B.4",
        "Zasiłek macierzyński za okres urlopu ojcowskiego",
        [(8, "Do urlopu ojcowskiego uprawniony jest", "prawo do tego urlopu wygasa.")],
    ),
    # Section C (phase 2d).
    (
        "C",
        "Zasiłek macierzyński za okres uzupełniającego urlopu macierzyńskiego",
        [(8, "Uzupełniający urlop macierzyński – urlop", "po urlopie macierzyńskim.")],
    ),
    # Section H, only what "ubezpieczona" in point A.2 depends on (phase 2c).
    (
        "H.1",
        "Zagrożenia: umowa albo działalność dla pozoru",
        [
            (9, "zawarcie umowy albo podjęcie działalności", "decyzję o niepodleganiu"),
            (10, "ubezpieczeniom społecznym; w konsekwencji", "nie ma uprawnień do zasiłków"),
        ],
    ),
    (
        "H.2",
        "Zagrożenia: podwyższenie podstawy wymiaru składek w ciąży",
        [(10, "podwyższenie podstawy wymiaru składek", "wpływ na wysokość zasiłków;")],
    ),
    (
        "H.3",
        "Zagrożenia: brak ubezpieczenia chorobowego w dniu porodu",
        [
            (
                10,
                "niepodleganie ubezpieczeniu chorobowemu na dzień porodu",
                "ubezpieczenia chorobowego.",
            )
        ],
    ),
    # Applications and protection (guide A.4, I): who pays, what to file and where.
    (
        "W",
        "Kto wypłaca zasiłki (wprowadzenie i przypis 1)",
        [
            (1, "zasiłki są wypłacane przez płatników", "albo ZUS)"),
            (1, "Zgodnie z art 61", "takiego zgłoszenia)."),
        ],
    ),
    (
        "A.4",
        "Dokumenty stanowiące podstawę do ustalenia zasiłku",
        [(6, "Kobieta będąca pracownikiem występuje", "uzupełniającego urlopu macierzyńskiego).")],
    ),
    (
        "I",
        "Szczególna ochrona kobiet – pracownic w ciąży oraz pracowników w okresie urlopów "
        "związanych z rodzicielstwem",
        [(10, "W okresie ciąży oraz w okresie urlopu", "prowadzących pozarolniczą działalność.")],
    ),
    (
        "F",
        "Formularze: ZAM, zaświadczenia płatnika składek i formularze zlikwidowane",
        [
            (12, "ZAM – wniosek o zasiłek macierzyński", "i wysokość zasiłku)"),
            (12, "Formularz ZUR od 24", "Z-3b od 24 października 2026 r. zlikwidowany"),
        ],
    ),
    # The sick-benefit chapter before section A (pages 2-4): sick leave in pregnancy.
    (
        "ZC",
        "Zasiłek chorobowy dla kobiety w ciąży",
        [
            (2, "Zasiłek chorobowy jest świadczeniem wypłacanym", "spowodowanej chorobą."),
            (3, "Kobieta w ciąży zgłasza się", "pracodawca wypłaca"),
            (4, "wynagrodzenie za czas niezdolności", "okres pobierania zasiłku macierzyńskiego."),
        ],
    ),
    (
        "ZC.s",
        "Szczególna sytuacja – zasiłek w wysokości zasiłku macierzyńskiego",
        [(4, "Zasiłek w wysokości zasiłku macierzyńskiego to", "za okres urlopu macierzyńskiego.")],
    ),
]


@lru_cache
def guide_sections() -> dict[str, GuideSection]:
    raw = json.loads(PAGES_FILE.read_text(encoding="utf-8"))["pages"]
    pages = {number: normalize(text) for number, text in raw.items()}
    sections = {}
    for section_id, title, anchors in _SECTIONS:
        parts = []
        for page, first, last in anchors:
            text = pages[str(page)]
            start = text.index(first)
            end = text.index(last, start) + len(last)
            parts.append((page, text[start:end]))
        sections[section_id] = GuideSection(section_id, title, tuple(parts))
    return sections
