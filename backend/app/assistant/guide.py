"""The guide (Przewodnik ZUS) as sections the app covers so far.

`przewodnik_pages.json` is the text of the PDF, page by page (regenerate with tools/przewodnik/).
A section is cut out of its page between two anchors, so its text is the document's own wording:
the model reads it, and every quote shown in the UI is checked against it.
"""

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

PAGES_FILE = Path(__file__).with_name("przewodnik_pages.json")


@dataclass(frozen=True)
class GuideSection:
    id: str
    title: str
    page: int
    text: str

    def contains(self, quote: str) -> bool:
        """True if `quote` is a literal fragment of this section (whitespace aside)."""
        return normalize(quote) in normalize(self.text)


# (id, title, page, first words, last words): the part of each section the phases cover so far.
_SECTIONS = [
    # Phase 1.
    ("A.1", "Przygotowanie do porodu", 5, "Kobieta może rozpocząć", "po urodzeniu dziecka."),
    # Phase 2a: length of maternity leave and the 14 weeks after the birth.
    ("A.2", "Urodzenie dziecka", 5, "Wymiar zasiłku macierzyńskiego", "wykorzystać osobiście."),
]


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


@lru_cache
def guide_sections() -> dict[str, GuideSection]:
    pages = json.loads(PAGES_FILE.read_text(encoding="utf-8"))["pages"]
    sections = {}
    for section_id, title, page, first, last in _SECTIONS:
        text = pages[str(page)]
        start = text.index(first)
        end = text.index(last, start) + len(last)
        sections[section_id] = GuideSection(section_id, title, page, normalize(text[start:end]))
    return sections
