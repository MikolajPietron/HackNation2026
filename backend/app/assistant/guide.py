"""The challenge guide (Przewodnik) split into pages. Regenerate with tools/przewodnik/."""

import json
from functools import lru_cache
from pathlib import Path

PAGES_FILE = Path(__file__).with_name("przewodnik_pages.json")


@lru_cache
def guide_pages() -> dict[int, str]:
    data = json.loads(PAGES_FILE.read_text(encoding="utf-8"))
    return {int(number): text for number, text in data["pages"].items()}
