"""Provisions of the Labour Code and of the ustawa zasiłkowa the app cites (public law text;
regenerate with tools/przewodnik/), and the chapter of the ZUS Załącznik on the benefit base.

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
