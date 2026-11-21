"""Provisions of the Labour Code and of the ustawa zasiłkowa the app cites (public law text;
regenerate with tools/przewodnik/).

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
