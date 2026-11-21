"""Copy the Labour Code provisions the app cites into backend/app/assistant/kodeks_pracy.json.

The source is the Labour Code excerpt from the ZUS materials (docs/dokumentyZUS/, outside git).
Only the provisions listed below are copied: it is public law text, which the app quotes word
for word. Two things are restored, nothing else is changed:
- pdftotext glues "nie" to the next word in this PDF ("niewięcej");
- it flattens superscripts in article numbers ("art. 1831 § 1" is art. 183¹ § 1).

Run from the repo root (requires poppler: pdftotext):
    python3 tools/przewodnik/extract_kp.py
"""

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PDF = ROOT / "docs" / "dokumentyZUS" / "materialy" / "Kodeks pracy (wyciąg z przepisów).pdf"
OUT = ROOT / "backend" / "app" / "assistant" / "kodeks_pracy.json"

# Key shown in the app -> (article heading in the PDF text, paragraph number or None for an
# article without paragraphs). Superscripts are flat in the PDF text: "Art. 1831" is art. 183¹.
PROVISIONS = {
    "art. 180 § 1": ("Art. 180 [", "1"),
    "art. 180 § 2": ("Art. 180 [", "2"),
    "art. 180 § 3": ("Art. 180 [", "3"),
    "art. 180 § 4": ("Art. 180 [", "4"),
    "art. 180 § 5": ("Art. 180 [", "5"),
    "art. 180 § 6": ("Art. 180 [", "6"),
    "art. 180 § 10": ("Art. 180 [", "10"),
    "art. 180 § 11": ("Art. 180 [", "11"),
    "art. 180 § 12": ("Art. 180 [", "12"),
    "art. 180 § 13": ("Art. 180 [", "13"),
    "art. 180 § 14": ("Art. 180 [", "14"),
    "art. 180¹ § 1": ("Art. 1801 [", "1"),
    "art. 180¹ § 2": ("Art. 1801 [", "2"),
    "art. 180² § 1": ("Art. 1802 [", "1"),
    "art. 180² § 2": ("Art. 1802 [", "2"),
    "art. 180² § 3": ("Art. 1802 [", "3"),
    "art. 180² § 7": ("Art. 1802 [", "7"),
    "art. 182¹ᵃ § 1": ("Art. 1821a [", "1"),
    "art. 182¹ᵃ § 2": ("Art. 1821a [", "2"),
    "art. 182¹ᵃ § 3": ("Art. 1821a [", "3"),
    "art. 182¹ᵃ § 4": ("Art. 1821a [", "4"),
    "art. 182¹ᵃ § 6": ("Art. 1821a [", "6"),
    "art. 182¹ᶜ": ("Art. 1821c [", None),
    "art. 182¹ᵍ": ("Art. 1821g [", None),
    "art. 182³ § 1": ("Art. 1823 [", "1"),
    "art. 182³ § 1¹": ("Art. 1823 [", "11"),
    "art. 182³ § 3": ("Art. 1823 [", "3"),
    "art. 183¹ § 1": ("Art. 1831 [", "1"),
    "art. 183¹ § 2": ("Art. 1831 [", "2"),
}

GLUED = {
    "niewięcej": "nie więcej",
    "niewiększą": "nie większą",
    "niekrótszym": "nie krótszym",
    "niekrócej": "nie krócej",
    "niewcześniej": "nie wcześniej",
    "niedłużej": "nie dłużej",
    "niepóźniej": "nie później",
}

# Article numbers inside the provisions, as the PDF text has them -> as the Code numbers them.
FLAT = {
    "art. 1801 § 2": "art. 180¹ § 2",
    "art. 1831 § 1": "art. 183¹ § 1",
    "art. 1868a": "art. 186⁸ᵃ",
}


def article(text: str, heading: str) -> str:
    start = text.index(heading)
    following = re.search(r"\nArt\. \d", text[start + 1 :])
    return text[start : start + 1 + following.start()] if following else text[start:]


def paragraph(text: str, number: str | None) -> str:
    """One paragraph of an article, or the whole article when it has no paragraphs."""
    if number is None:
        body = text[text.index("]") + 1 :]
    else:
        match = re.search(rf"(?ms)^§ {number}\. (.*?)(?=^§ \d+\. |\Z)", text)
        if not match:
            raise SystemExit(f"§ {number} not found")
        body = match.group(1)
    body = re.sub(r"\s+", " ", body).strip()
    for found, restored in (GLUED | FLAT).items():
        body = body.replace(found, restored)
    return body


def main() -> None:
    cmd = ["pdftotext", "-enc", "UTF-8", str(PDF), "-"]
    text = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    text = "\n".join(line for line in text.splitlines() if line.strip() != "Legalis")
    articles = {
        key: paragraph(article(text, heading), number)
        for key, (heading, number) in PROVISIONS.items()
    }
    payload = {
        "source": "Kodeks pracy (wyciąg z przepisów) z materiałów ZUS dla HackNation 2026",
        "articles": articles,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(articles)} provisions -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
