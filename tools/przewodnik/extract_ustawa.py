"""Copy the provisions of the ustawa zasiłkowa the app cites into
backend/app/assistant/ustawa_zasilkowa.json.

The source is the excerpt of the Act of 25 June 1999 on cash benefits from social insurance in
case of sickness and maternity, from the ZUS materials (docs/dokumentyZUS/, outside git). Only
the provisions listed below are copied: it is public law text, which the app quotes word for
word. Removed: page headers ("Legalis") and the footnotes printed at the bottom of a page.
Restored, nothing else changed:
- pdftotext glues "nie" to the next word in this PDF ("niepóźniej");
- it flattens superscripts in article numbers ("art. 1821a § 4" is art. 182¹ᵃ § 4).

Run from the repo root (requires poppler: pdftotext):
    python3 tools/przewodnik/extract_ustawa.py
"""

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PDF = (
    ROOT
    / "docs"
    / "dokumentyZUS"
    / "materialy"
    / (
        "wyciąg z ustawy o świadczeniach pieniężnych z ubezpieczeń społecznych w razie choroby "
        "i macierzyństwa (ustawa zasiłkowa).pdf"
    )
)
OUT = ROOT / "backend" / "app" / "assistant" / "ustawa_zasilkowa.json"

# Key shown in the app -> (article heading in the PDF text, "ust." or "pkt" number, or None for
# an article without either).
PROVISIONS = {
    "art. 3 pkt 3": ("Art. 3 [", "pkt", "3"),
    "art. 3 pkt 4": ("Art. 3 [", "pkt", "4"),
    # The sickness benefit in pregnancy: the insurance it needs (art. 4, 6), the days the
    # employer pays count in the benefit period (art. 12).
    "art. 4 ust. 1": ("Art. 4 [", "ust", "1"),
    "art. 4 ust. 2": ("Art. 4 [", "ust", "2"),
    "art. 4 ust. 3": ("Art. 4 [", "ust", "3"),
    "art. 6 ust. 1": ("Art. 6 [", "ust", "1"),
    "art. 12 ust. 1": ("Art. 12 [", "ust", "1"),
    "art. 7": ("Art. 7 [", None, None),
    "art. 8 ust. 2": ("Art. 8 [", "ust", "2"),
    "art. 11 ust. 2": ("Art. 11 [", "ust", "2"),
    "art. 11 ust. 4": ("Art. 11 [", "ust", "4"),
    "art. 11 ust. 5": ("Art. 11 [", "ust", "5"),
    # Świadczenie rehabilitacyjne after the sickness benefit in pregnancy (art. 18-19).
    "art. 18 ust. 1": ("Art. 18 [", "ust", "1"),
    "art. 18 ust. 2": ("Art. 18 [", "ust", "2"),
    "art. 18 ust. 3": ("Art. 18 [", "ust", "3"),
    "art. 18 ust. 4": ("Art. 18 [", "ust", "4"),
    "art. 18 ust. 6": ("Art. 18 [", "ust", "6"),
    "art. 19 ust. 1": ("Art. 19 [", "ust", "1"),
    "art. 22": ("Art. 22 [", None, None),
    "art. 13 ust. 1": ("Art. 13 [", "ust", "1"),
    # The father's maternity benefit in the special situations of section B (father.py).
    "art. 29 ust. 3": ("Art. 29 [", "ust", "3"),
    "art. 29 ust. 5": ("Art. 29 [", "ust", "5"),
    "art. 29 ust. 6": ("Art. 29 [", "ust", "6"),
    "art. 29 ust. 7": ("Art. 29 [", "ust", "7"),
    "art. 29 ust. 9": ("Art. 29 [", "ust", "9"),
    "art. 29a ust. 1": ("Art. 29a [", "ust", "1"),
    "art. 30 ust. 1": ("Art. 30 [", "ust", "1"),
    "art. 30 ust. 3": ("Art. 30 [", "ust", "3"),
    "art. 30 ust. 4": ("Art. 30 [", "ust", "4"),
    "art. 30a ust. 1": ("Art. 30a [", "ust", "1"),
    "art. 30a ust. 2": ("Art. 30a [", "ust", "2"),
    "art. 30a ust. 3": ("Art. 30a [", "ust", "3"),
    "art. 31 ust. 1": ("Art. 31 [", "ust", "1"),
    "art. 31 ust. 2": ("Art. 31 [", "ust", "2"),
    "art. 31 ust. 3": ("Art. 31 [", "ust", "3"),
    "art. 31 ust. 3a": ("Art. 31 [", "ust", "3a"),
    "art. 31 ust. 3f": ("Art. 31 [", "ust", "3f"),
    "art. 31 ust. 3g": ("Art. 31 [", "ust", "3g"),
    "art. 31 ust. 4": ("Art. 31 [", "ust", "4"),
    "art. 31 ust. 4a": ("Art. 31 [", "ust", "4a"),
    "art. 31 ust. 5": ("Art. 31 [", "ust", "5"),
    "art. 36 ust. 1": ("Art. 36 [", "ust", "1"),
    "art. 36 ust. 3": ("Art. 36 [", "ust", "3"),
    "art. 47": ("Art. 47 [", None, None),
    "art. 48 ust. 1": ("Art. 48 [", "ust", "1"),
    "art. 52": ("Art. 52 [", None, None),
    "art. 61 ust. 1": ("Art. 61 [", "ust", "1"),
    # A payer that pays the sickness benefit itself does so on the basis of e-ZLA.
    "art. 61b ust. 2": ("Art. 61b [", "ust", "2"),
    # The benefit base in detail (engine/base.py).
    "art. 36 ust. 2": ("Art. 36 [", "ust", "2"),
    "art. 36 ust. 4": ("Art. 36 [", "ust", "4"),
    "art. 37 ust. 1": ("Art. 37 [", "ust", "1"),
    "art. 37 ust. 2": ("Art. 37 [", "ust", "2"),
    "art. 38 ust. 1": ("Art. 38 [", "ust", "1"),
    "art. 38 ust. 2": ("Art. 38 [", "ust", "2"),
    "art. 38 ust. 3": ("Art. 38 [", "ust", "3"),
    "art. 42 ust. 1": ("Art. 42 [", "ust", "1"),
    "art. 42 ust. 2": ("Art. 42 [", "ust", "2"),
    "art. 42 ust. 3": ("Art. 42 [", "ust", "3"),
    "art. 43": ("Art. 43 [", None, None),
    "art. 45 ust. 1": ("Art. 45 [", "ust", "1"),
    "art. 45 ust. 2": ("Art. 45 [", "ust", "2"),
    "art. 48 ust. 2": ("Art. 48 [", "ust", "2"),
    "art. 48a ust. 1": ("Art. 48a [", "ust", "1"),
    "art. 49 ust. 1": ("Art. 49 [", "ust", "1"),
    "art. 50 ust. 1": ("Art. 50 [", "ust", "1"),
    "art. 50 ust. 2": ("Art. 50 [", "ust", "2"),
    # Contribution debt of a business on the day the right arises (engine/debt.py).
    "art. 2": ("Art. 2 [", None, None),
    "art. 2a ust. 1": ("Art. 2a [", "ust", "1"),
    "art. 2a ust. 2": ("Art. 2a [", "ust", "2"),
    "art. 64 ust. 3": ("Art. 64 [", "ust", "3"),
}

GLUED = {
    "niepóźniej": "nie później",
    "niewcześniej": "nie wcześniej",
    "niedłużej": "nie dłużej",
    "nieniższym": "nie niższym",
    "nieniższej": "nie niższej",
}

# Article numbers inside the provisions, as the PDF text has them -> as the Code numbers them.
FLAT = {"art. 1821a § 4": "art. 182¹ᵃ § 4"}


FOOTNOTE_LINES = 8
"""A footnote is short: its number, a sentence or two, the end of the page."""


def without_page_furniture(text: str) -> str:
    """Drop the "Legalis" page headers and the footnotes: a footnote starts with a line holding
    only its number and runs, in a few lines without an article heading, to the end of the
    page."""
    lines = text.splitlines()
    kept: list[str] = []
    skip_to = -1
    for index, line in enumerate(lines):
        if index <= skip_to or line.strip() == "Legalis":
            continue
        if re.fullmatch(r"\d+", line.strip()):
            rest = lines[index + 1 : index + 1 + FOOTNOTE_LINES]
            end = next((i for i, x in enumerate(rest) if x.strip() == "Legalis"), None)
            if end is not None and not any(re.match(r"Art\. \d+\w* \[", x) for x in rest[:end]):
                skip_to = index + end
                continue
        kept.append(line)
    return "\n".join(kept)


def article(text: str, heading: str) -> str:
    start = text.index(heading)
    # The next article or chapter ends it.
    following = re.search(r"\n(?:Art\. \d|ROZDZIAŁ )", text[start + 1 :])
    return text[start : start + 1 + following.start()] if following else text[start:]


def provision(text: str, kind: str | None, number: str | None) -> str:
    """One "ust." or "pkt" of an article, or the article's text after its heading."""
    if kind is None:
        body = text[text.index("]") + 1 :]
    else:
        # "3a. " starts a paragraph (ust.), "3) " a point (pkt). A footnote's number may follow
        # the paragraph's own ("2.7 " in art. 61b is ust. 2 with footnote 7).
        mark = r"\.\d* " if kind == "ust" else r"\) "
        any_start = rf"\d+[a-z]?{mark}"
        this = rf"{re.escape(number or '')}{mark}"
        match = re.search(rf"(?ms)^{this}(.*?)(?=^{any_start}|\Z)", text)
        if not match:
            raise SystemExit(f"{kind} {number} not found")
        body = match.group(1)
    # The excerpt marks omitted provisions with "(…)"; what follows is not this provision.
    body = body.split("(…)")[0]
    body = re.sub(r"\s+", " ", body).strip()
    for found, restored in (GLUED | FLAT).items():
        body = body.replace(found, restored)
    return body


def main() -> None:
    cmd = ["pdftotext", "-enc", "UTF-8", str(PDF), "-"]
    text = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    text = without_page_furniture(text)
    provisions = {
        key: provision(article(text, heading), kind, number)
        for key, (heading, kind, number) in PROVISIONS.items()
    }
    payload = {
        "source": (
            "Wyciąg z ustawy o świadczeniach pieniężnych z ubezpieczenia społecznego w razie "
            "choroby i macierzyństwa (Dz.U. z 2026 r. poz. 854) z materiałów ZUS dla HackNation "
            "2026"
        ),
        "articles": provisions,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(provisions)} provisions -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
