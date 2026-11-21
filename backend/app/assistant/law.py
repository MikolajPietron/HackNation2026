"""Labour Code provisions the app cites (public law text; regenerate with tools/przewodnik/).

The model reads them in its instructions, and every Labour Code quote shown in the UI is
checked against them.
"""

import json
from functools import lru_cache
from pathlib import Path

from app.assistant.guide import normalize

LAW_FILE = Path(__file__).with_name("kodeks_pracy.json")


@lru_cache
def kp_articles() -> dict[str, str]:
    """Provision ("art. 180 § 1") -> its text."""
    articles = json.loads(LAW_FILE.read_text(encoding="utf-8"))["articles"]
    return {key: normalize(text) for key, text in articles.items()}


def kp_contains(article: str, quote: str) -> bool:
    """True if `quote` is a literal fragment of that provision (whitespace aside)."""
    text = kp_articles().get(article)
    return text is not None and normalize(quote) in text
