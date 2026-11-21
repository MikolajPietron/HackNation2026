"""Copy the Labour Code provisions the app cites into backend/app/assistant/kodeks_pracy.json.

The source is the Labour Code excerpt from the ZUS materials (docs/dokumentyZUS/, outside git).
Only the provisions listed below are copied: it is public law text, which the app quotes word
for word. pdftotext glues "nie" to the next word in this PDF ("niewięcej"); those spaces are
restored, nothing else is changed.

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

# Key shown in the app -> (article heading in the PDF text, paragraph number).
# Superscripts are flat in the PDF text: "Art. 1831" is art. 183¹.
PROVISIONS = {
    "art. 180 § 1": ("Art. 180 [", "1"),
    "art. 180 § 2": ("Art. 180 [", "2"),
    "art. 180 § 3": ("Art. 180 [", "3"),
    "art. 183¹ § 1": ("Art. 1831 [", "1"),
    "art. 183¹ § 2": ("Art. 1831 [", "2"),
}

GLUED = {
    "niewięcej": "nie więcej",
    "niekrótszym": "nie krótszym",
    "niedłużej": "nie dłużej",
    "niepóźniej": "nie później",
}


def article(text: str, heading: str) -> str:
    start = text.index(heading)
    following = re.search(r"\nArt\. \d", text[start + 1 :])
    return text[start : start + 1 + following.start()] if following else text[start:]


def paragraph(text: str, number: str) -> str:
    match = re.search(rf"(?ms)^§ {number}\. (.*?)(?=^§ \d+\. |\Z)", text)
    if not match:
        raise SystemExit(f"§ {number} not found")
    body = re.sub(r"\s+", " ", match.group(1)).strip()
    for glued, spaced in GLUED.items():
        body = body.replace(glued, spaced)
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
