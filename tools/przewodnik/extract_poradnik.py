"""Copy the text of the ZUS Poradnik into backend/app/assistant/poradnik.json, page by page.

The source is "Poradnik dla rodziców i opiekunów dzieci" (ZUS 2026, stan prawny na 1 kwietnia
2026 r.), a PDF in the ZUS materials (docs/dokumentyZUS/, outside git). It is no. 4 in the
hierarchy of sources (CLAUDE.md): the app quotes it word for word only where the guide, the
Załącznik and the law say nothing. Being a ZUS document "wyłącznie na użytek HackNation", the
output is not in git either (.gitignore): each checkout builds it from the materials. Without it
the app works the same and tests/test_sources.py skips checking the Poradnik's quotes.

Page numbers are the PRINTED ones ("numer druku"): the number printed on the page and used by the
Poradnik's own table of contents. In this PDF the printed number is the file's page number minus
one (the cover has none), so printed page 34 is page 35 of the file. `SourceRef.page` (and
`page_to`) for doc "poradnik" is always the printed number. The script checks that every page
that prints its number prints the expected one.

Removed from each page: the running header on its first line ("PORADNIK DLA RODZICÓW
I OPIEKUNÓW DZIECI" or the chapter's name), the line with the page number and the C1 control
characters pdftotext gives for the pictograms of the "WAŻNE!" boxes. Nothing else is changed: the footnotes stay at the foot of their page, and pdftotext flattens the footnote marks
into the text ("kodu B11" is "kodu B" with footnote 11), so quotes avoid them. Whitespace is
collapsed as for the guide (extract_pages.py).

Run from the repo root (requires poppler: pdftotext, pdfinfo):
    python3 tools/przewodnik/extract_poradnik.py
"""

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PDF = ROOT / "docs" / "dokumentyZUS" / "materialy" / "Poradnik dla rodziców, ZUS 2026.pdf"
OUT = ROOT / "backend" / "app" / "assistant" / "poradnik.json"

OFFSET = 1
"""File page = printed page + OFFSET."""
NUMBERED = range(3, 41)
"""Printed pages that print their own number (the table of contents to the last page of text)."""
HEADERS = (
    "PORADNIK DLA RODZICÓW I OPIEKUNÓW DZIECI",
    "Objaśnienie używanych pojęć i skrótów",
    "Zasady podlegania ubezpieczeniom społecznym i ubezpieczeniu zdrowotnemu z wybranych tytułów",
    "Świadczenia z ubezpieczenia chorobowego",
)
"""The running headers: the first line of a page of text."""


def page_count(pdf: Path) -> int:
    info = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True, check=True).stdout
    match = re.search(r"^Pages:\s+(\d+)", info, re.MULTILINE)
    if not match:
        raise SystemExit("pdfinfo did not report a page count")
    return int(match.group(1))


def page_text(pdf: Path, printed: int) -> str:
    file_page = printed + OFFSET
    cmd = ["pdftotext", "-enc", "UTF-8", "-f", str(file_page), "-l", str(file_page), str(pdf), "-"]
    raw = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    raw = re.sub(r"[\x80-\x9f]", "", raw.replace("\f", ""))  # pictograms, not text
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in raw.split("\n")]
    lines = [line for line in lines if line]
    if lines and lines[0] in HEADERS:
        lines = lines[1:]
    number = [i for i, line in enumerate(lines) if line == str(printed)]
    if printed in NUMBERED:
        if not number:
            raise SystemExit(f"printed page {printed} (file page {file_page}) has no page number")
        del lines[number[-1]]
    return "\n".join(lines)


def main() -> None:
    last = page_count(PDF) - OFFSET
    pages = {str(n): page_text(PDF, n) for n in range(1, last + 1)}
    payload = {
        "source": (
            "Poradnik dla rodziców i opiekunów dzieci, ZUS 2026 (stan prawny na 1 kwietnia "
            f"2026 r.), {PDF.name}"
        ),
        "page_numbers": "printed (file page - 1)",
        "pages": pages,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(pages)} pages -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
