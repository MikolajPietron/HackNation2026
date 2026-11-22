"""Provisions of the Labour Code, of the ustawa zasiłkowa and of the two regulations on the
requests the app cites (public law text; regenerate with tools/przewodnik/), the chapter of the
ZUS Załącznik on the benefit base and the pages of the ZUS Poradnik for parents.

The model reads them in its instructions, and every quote from them shown in the UI is checked
against them.
"""

import json
from functools import lru_cache
from pathlib import Path

from app.assistant.guide import normalize

LAW_FILE = Path(__file__).with_name("kodeks_pracy.json")
USTAWA_FILE = Path(__file__).with_name("ustawa_zasilkowa.json")


@lru_cache
def kp_articles() -> dict[str, str]:
    """Provision ("art. 180 § 1") -> its text."""
    articles = json.loads(LAW_FILE.read_text(encoding="utf-8"))["articles"]
    return {key: normalize(text) for key, text in articles.items()}


def kp_contains(article: str, quote: str) -> bool:
    """True if `quote` is a literal fragment of that provision (whitespace aside)."""
    text = kp_articles().get(article)
    return text is not None and normalize(quote) in text


@lru_cache
def ustawa_articles() -> dict[str, str]:
    """Provision of the ustawa zasiłkowa ("art. 31 ust. 1") -> its text."""
    articles = json.loads(USTAWA_FILE.read_text(encoding="utf-8"))["articles"]
    return {key: normalize(text) for key, text in articles.items()}


def ustawa_contains(article: str, quote: str) -> bool:
    """True if `quote` is a literal fragment of that provision (whitespace aside)."""
    text = ustawa_articles().get(article)
    return text is not None and normalize(quote) in text


# The ZUS Załącznik to the challenge (source no. 2 for numbers): its chapter on the benefit base,
# quoted the same way as the law. It is a ZUS document "wyłącznie na użytek HackNation", so the
# file is not in git: each checkout builds it from the materials with
# tools/przewodnik/extract_zalacznik.py. Without it the model simply doesn't get its text and the
# literal-quote test skips its quotes.
ZALACZNIK_FILE = Path(__file__).with_name("zalacznik.json")


def zalacznik_available() -> bool:
    return ZALACZNIK_FILE.exists()


@lru_cache
def zalacznik_sections() -> dict[str, str]:
    """Section of the Załącznik ("Okres uwzględniany w podstawie wymiaru zasiłku") -> its text;
    table rows keep their cells separated by " | ". Empty when the file was not built."""
    if not zalacznik_available():
        return {}
    sections = json.loads(ZALACZNIK_FILE.read_text(encoding="utf-8"))["sections"]
    return {name: normalize(text) for name, text in sections.items()}


def zalacznik_contains(section: str, quote: str) -> bool:
    """True if `quote` is a literal fragment of that section (whitespace aside)."""
    text = zalacznik_sections().get(section)
    return text is not None and normalize(quote) in text


# The ZUS Poradnik for parents (2026; source no. 4, quoted only where the guide, the Załącznik
# and the law are silent), page by page, the PRINTED page numbers (the PDF's page minus one). A
# ZUS document like the Załącznik, so not in git: each checkout builds it from the materials with
# tools/przewodnik/extract_poradnik.py. Without it the literal-quote test skips its quotes. The
# model is not given the whole Poradnik (too long): only the quotes the timeline carries.
PORADNIK_FILE = Path(__file__).with_name("poradnik.json")


def poradnik_available() -> bool:
    return PORADNIK_FILE.exists()


@lru_cache
def poradnik_pages() -> dict[int, str]:
    """Printed page of the Poradnik -> its text. Empty when the file was not built."""
    if not poradnik_available():
        return {}
    pages = json.loads(PORADNIK_FILE.read_text(encoding="utf-8"))["pages"]
    return {int(page): normalize(text) for page, text in pages.items()}


def poradnik_contains(page: int, page_to: int | None, quote: str) -> bool:
    """True if `quote` is a literal fragment of the printed page `page` (whitespace aside), or of
    the pages from `page` to `page_to` read one after the other (a sentence over a page break)."""
    pages = poradnik_pages()
    numbers = range(page, (page_to or page) + 1)
    if not all(n in pages for n in numbers):
        return False
    return normalize(quote) in " ".join(pages[n] for n in numbers)


# Two regulations the request forms quote (public law text; regenerate with
# tools/przewodnik/extract_rozporzadzenia.py): "wnioski", on the leave requests and their
# attachments, and "zasilki", on the documents for the benefits. SourceRef.doc names them
# "rozp_wnioski" and "rozp_zasilki"; the provision ("§ 15 ust. 1", "zał. 6") is its article.
ROZPORZADZENIA_FILE = Path(__file__).with_name("rozporzadzenia.json")
ROZPORZADZENIA = {"rozp_wnioski": "wnioski", "rozp_zasilki": "zasilki"}
"""SourceRef.doc -> the regulation in rozporzadzenia.json."""
ROZPORZADZENIE_NAME = {
    "rozp_wnioski": "Rozporządzenie w sprawie wniosków urlopowych",
    "rozp_zasilki": "Rozporządzenie w sprawie dokumentów do zasiłków",
}
"""How a source label starts: "Rozporządzenie w sprawie wniosków urlopowych, § 15 ust. 1"."""


@lru_cache
def rozporzadzenie_provisions(doc: str) -> dict[str, str]:
    """Provision of that regulation ("§ 15 ust. 1", "zał. 6") -> its text."""
    acts = json.loads(ROZPORZADZENIA_FILE.read_text(encoding="utf-8"))
    provisions = acts[ROZPORZADZENIA[doc]]["provisions"]
    return {key: normalize(text) for key, text in provisions.items()}


def rozporzadzenie_contains(doc: str, provision: str, quote: str) -> bool:
    """True if `quote` is a literal fragment of that provision (whitespace aside)."""
    text = rozporzadzenie_provisions(doc).get(provision)
    return text is not None and normalize(quote) in text
