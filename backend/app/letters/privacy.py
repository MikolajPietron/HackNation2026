"""Personal data out of every text the letter explanation returns (CLAUDE.md "Dane i
poufność"). Two layers: what the model listed as personal data (each entry as written; names
also in other grammatical cases: "Anna Kowalska" removes "Anny Kowalskiej"), and patterns that
need no list: PESEL and other long numbers, account numbers, phones, e-mails, postal codes,
streets, ID cards. Removing a little too much (a city) is fine; leaving a name is not."""

import re
from collections.abc import Iterable

REMOVED = "[…]"

_PATTERNS = [
    re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"),  # e-mail
    re.compile(r"\bPL\s?\d{2}(?:\s?\d{4}){6}\b"),  # IBAN
    re.compile(r"(?<![\d.,])(?:\d[ -]?){8,}\d(?!\d)"),  # PESEL, NIP, accounts, phones
    re.compile(r"(?<![\w-])\d{2}-\d{3}(?![\w-])(?:\s+[A-ZĄĆĘŁŃÓŚŹŻ][\wąćęłńóśźż-]+)?"),  # code
    re.compile(
        r"\b(?:ul\.|ulica|al\.|aleja|aleje|os\.|osiedle|pl\.|plac)\s+[^\n,;()]{1,40}?"
        r"\d+[A-Za-z]?(?:\s?/\s?\d+[A-Za-z]?)?"
    ),  # street and number
    re.compile(r"\b[A-Z]{3}\s?\d{6}\b"),  # ID card
]

# Words the model sometimes lists with a name that are never personal on their own.
_KEEP = {
    "pan",
    "pani",
    "państwo",
    "zus",
    "zakład",
    "ubezpieczeń",
    "społecznych",
    "oddział",
    "inspektorat",
    "decyzja",
    "wezwanie",
    "dziecko",
    "dziecka",
    "matka",
    "ojciec",
}
_MIN_TOKEN = 3
_ENDING = 5
"""Letters a name may add in another case ("Kowals|kiego")."""


def _compiled(patterns: list[str], flags: int = 0) -> re.Pattern[str] | None:
    return re.compile("|".join(patterns), flags) if patterns else None


def _name_patterns(token: str) -> list[str]:
    """A word of a name, also in its other cases ("Anna": "Anny", "Annę"). The capital letter
    stays, so a name never removes an ordinary word or a month ("Maja" keeps "1 maja 2027");
    a name written in capitals ("KOWALSKA") also matches "Kowalskiej"."""
    forms = {token, token.capitalize()} if token.isupper() else {token}
    patterns = []
    for form in forms:
        stem = form if len(form) == _MIN_TOKEN else form[:-1] if len(form) <= 5 else form[:-2]
        patterns.append(rf"\b{re.escape(stem)}\w{{0,{_ENDING}}}\b")
    return patterns


class Scrubber:
    def __init__(self, personal: Iterable[str]) -> None:
        exact = sorted({p.strip() for p in personal if len(p.strip()) >= _MIN_TOKEN}, key=len)
        tokens = []
        # Names: entries without digits (an address is removed whole, also by the patterns).
        for entry in (e for e in exact if not re.search(r"\d", e)):
            for token in re.findall(r"[^\W\d_]+", entry):
                if len(token) >= _MIN_TOKEN and token[0].isupper() and token.lower() not in _KEEP:
                    tokens += _name_patterns(token)
        whole = [rf"(?<!\w){re.escape(p)}(?!\w)" for p in reversed(exact)]
        self._exact = _compiled(whole, re.IGNORECASE)
        self._tokens = _compiled(tokens)
        self.removed = False

    def __call__(self, text: str) -> str:
        clean = text
        for pattern in (self._exact, self._tokens, *_PATTERNS):
            if pattern is not None:
                clean = pattern.sub(REMOVED, clean)
        if clean != text:
            self.removed = True
        return clean

    def optional(self, text: str | None) -> str | None:
        return None if text is None else self(text)
