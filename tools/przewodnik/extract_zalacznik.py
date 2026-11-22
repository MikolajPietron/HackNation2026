"""Copy the parts of the ZUS Załącznik the app cites into backend/app/assistant/zalacznik.json.

The source is the attachment to the HackNation 2026 challenge ("Załącznik: maksymalny czas
trwania zasiłków, wysokość, podstawa wymiaru", a .docx in the ZUS materials, docs/dokumentyZUS/,
outside git). Only the sections listed below are copied: the chapter on the benefit base, which
the app quotes word for word (engine/base.py). Nothing in the text is changed. A table is written
row by row, its cells separated by " | "; the paragraphs and line breaks inside a cell become
single spaces.

Standard library only (the .docx is a zip with word/document.xml). Run from the repo root:
    python3 tools/przewodnik/extract_zalacznik.py
"""

import json
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCX = (
    ROOT
    / "docs"
    / "dokumentyZUS"
    / "materialy"
    / "Załącznik_ maksymalny czas trwania zasiłków, wysokość, podstawa wymiaru.docx"
)
OUT = ROOT / "backend" / "app" / "assistant" / "zalacznik.json"

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

CHAPTER = "Podstawa wymiaru zasiłków"
"""The chapter copied: from this heading to the end of the document."""

# Heading in the document -> the section's name in the app (shown as "Załącznik ZUS, <name>").
SECTIONS = {
    "Dla pracowników": "Podstawa wymiaru zasiłków dla pracowników",
    "1. Okres uwzględniany w podstawie wymiaru zasiłku": (
        "Okres uwzględniany w podstawie wymiaru zasiłku"
    ),
    "2. Minimalna podstawa wymiaru zasiłku w 2026 roku": (
        "Minimalna podstawa wymiaru zasiłku w 2026 roku"
    ),
    "3. Składniki wynagrodzenia w podstawie wymiaru zasiłku": (
        "Składniki wynagrodzenia w podstawie wymiaru zasiłku"
    ),
    "4. Uzupełnianie wynagrodzenia za niepełny miesiąc": (
        "Uzupełnianie wynagrodzenia za niepełny miesiąc"
    ),
    "Dla nie pracowników": "Podstawa wymiaru zasiłków dla nie pracowników",
}


def text_of(element: ET.Element) -> str:
    """The text of a paragraph (or of all paragraphs in a cell), whitespace collapsed."""
    parts = []
    for node in element.iter():
        if node.tag == W + "t":
            parts.append(node.text or "")
        elif node.tag in (W + "tab", W + "br", W + "p"):
            # A tab, a line break or the start of another paragraph in a cell: one space.
            parts.append(" ")
    return re.sub(r"\s+", " ", "".join(parts)).strip()


def blocks(body: ET.Element) -> list[str]:
    """Paragraphs and table rows in reading order; empty paragraphs left out."""
    found = []
    for child in body:
        if child.tag == W + "p":
            if text := text_of(child):
                found.append(text)
        elif child.tag == W + "tbl":
            for row in child.findall(W + "tr"):
                found.append(" | ".join(text_of(cell) for cell in row.findall(W + "tc")))
    return found


def main() -> None:
    with zipfile.ZipFile(DOCX) as docx:
        root = ET.fromstring(docx.read("word/document.xml"))
    body = root.find(W + "body")
    if body is None:
        raise SystemExit("word/document.xml has no body")
    lines = blocks(body)
    chapter = lines[lines.index(CHAPTER) + 1 :]
    sections: dict[str, list[str]] = {}
    current = None
    for line in chapter:
        if line in SECTIONS:
            current = SECTIONS[line]
            sections[current] = []
        elif current is None:
            raise SystemExit(f"text before the first section: {line!r}")
        else:
            sections[current].append(line)
    missing = set(SECTIONS.values()) - set(sections)
    if missing:
        raise SystemExit(f"sections not found: {sorted(missing)}")
    payload = {
        "source": (
            "Załącznik do Template Wyzwania HackNation 2026: maksymalny czas trwania zasiłków, "
            "wysokość, podstawa wymiaru (materiały ZUS dla HackNation 2026), rozdział "
            f"„{CHAPTER}”"
        ),
        "sections": {name: "\n".join(text) for name, text in sections.items()},
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(sections)} sections -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
