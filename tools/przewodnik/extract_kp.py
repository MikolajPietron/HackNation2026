"""Copy the Labour Code provisions the app cites into backend/app/assistant/kodeks_pracy.json.

The source is the Labour Code excerpt from the ZUS materials (docs/dokumentyZUS/, outside git).
Only the provisions listed below are copied: it is public law text, which the app quotes word
for word. Two things are restored, nothing else is changed:
- pdftotext glues "nie" to the next word in this PDF ("niewięcej");
- it flattens superscripts in article and paragraph numbers ("art. 1831 § 1" is art. 183¹ § 1,
  "§ 11" in art. 182¹ᶠ § 3 is § 1¹).

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
    "art. 177 § 1": ("Art. 177 [", "1"),
    "art. 177 § 1¹": ("Art. 177 [", "11"),
    "art. 177 § 3": ("Art. 177 [", "3"),
    "art. 92 § 1": ("Art. 92 [", "1"),
    "art. 92 § 3": ("Art. 92 [", "3"),
    "art. 92 § 4": ("Art. 92 [", "4"),
    "art. 92 § 5": ("Art. 92 [", "5"),
    "art. 180 § 1": ("Art. 180 [", "1"),
    "art. 180 § 2": ("Art. 180 [", "2"),
    "art. 180 § 3": ("Art. 180 [", "3"),
    "art. 180 § 4": ("Art. 180 [", "4"),
    "art. 180 § 5": ("Art. 180 [", "5"),
    "art. 180 § 6": ("Art. 180 [", "6"),
    "art. 180 § 8": ("Art. 180 [", "8"),
    "art. 180 § 9": ("Art. 180 [", "9"),
    "art. 180 § 10": ("Art. 180 [", "10"),
    "art. 180 § 11": ("Art. 180 [", "11"),
    "art. 180 § 12": ("Art. 180 [", "12"),
    "art. 180 § 13": ("Art. 180 [", "13"),
    "art. 180 § 14": ("Art. 180 [", "14"),
    "art. 180 § 16": ("Art. 180 [", "16"),
    "art. 180¹ § 1": ("Art. 1801 [", "1"),
    "art. 180¹ § 2": ("Art. 1801 [", "2"),
    "art. 180² § 1": ("Art. 1802 [", "1"),
    "art. 180² § 2": ("Art. 1802 [", "2"),
    "art. 180² § 3": ("Art. 1802 [", "3"),
    "art. 180² § 4": ("Art. 1802 [", "4"),
    "art. 180² § 5": ("Art. 1802 [", "5"),
    "art. 180² § 7": ("Art. 1802 [", "7"),
    "art. 182¹ᵃ § 1": ("Art. 1821a [", "1"),
    "art. 182¹ᵃ § 2": ("Art. 1821a [", "2"),
    "art. 182¹ᵃ § 3": ("Art. 1821a [", "3"),
    "art. 182¹ᵃ § 4": ("Art. 1821a [", "4"),
    "art. 182¹ᵃ § 6": ("Art. 1821a [", "6"),
    "art. 182¹ᵃ § 7": ("Art. 1821a [", "7"),
    "art. 182¹ᶜ": ("Art. 1821c [", None),
    "art. 182¹ᵈ § 1": ("Art. 1821d [", "1"),
    "art. 182¹ᵈ § 2": ("Art. 1821d [", "2"),
    "art. 182¹ᵉ § 1": ("Art. 1821e [", "1"),
    "art. 182¹ᵉ § 2": ("Art. 1821e [", "2"),
    "art. 182¹ᶠ § 1": ("Art. 1821f [", "1"),
    "art. 182¹ᶠ § 1¹": ("Art. 1821f [", "11"),
    "art. 182¹ᶠ § 2": ("Art. 1821f [", "2"),
    "art. 182¹ᶠ § 3": ("Art. 1821f [", "3"),
    "art. 182¹ᶠ § 4": ("Art. 1821f [", "4"),
    "art. 182¹ᶠ § 5": ("Art. 1821f [", "5"),
    "art. 182¹ᵍ": ("Art. 1821g [", None),
    "art. 182³ § 1": ("Art. 1823 [", "1"),
    "art. 182³ § 1¹": ("Art. 1823 [", "11"),
    "art. 182³ § 2": ("Art. 1823 [", "2"),
    "art. 182³ § 3": ("Art. 1823 [", "3"),
    "art. 183 § 1": ("Art. 183 [", "1"),
    "art. 183 § 1¹": ("Art. 183 [", "11"),
    "art. 183 § 2": ("Art. 183 [", "2"),
    "art. 183 § 3": ("Art. 183 [", "3"),
    "art. 183 § 3¹": ("Art. 183 [", "31"),
    "art. 183 § 4": ("Art. 183 [", "4"),
    "art. 183 § 4¹": ("Art. 183 [", "41"),
    "art. 183 § 4²": ("Art. 183 [", "42"),
    "art. 183 § 4³": ("Art. 183 [", "43"),
    "art. 183 § 4⁴": ("Art. 183 [", "44"),
    "art. 183 § 4⁵": ("Art. 183 [", "45"),
    "art. 183 § 4⁶": ("Art. 183 [", "46"),
    "art. 183 § 5": ("Art. 183 [", "5"),
    "art. 183 § 6": ("Art. 183 [", "6"),
    "art. 183 § 7": ("Art. 183 [", "7"),
    "art. 183 § 8": ("Art. 183 [", "8"),
    "art. 183¹ § 1": ("Art. 1831 [", "1"),
    "art. 183¹ § 2": ("Art. 1831 [", "2"),
}

GLUED = {
    "niewięcej": "nie więcej",
    "niewiększą": "nie większą",
    "niewyższym": "nie wyższym",
    "niekrótszym": "nie krótszym",
    "niekrócej": "nie krócej",
    "niewcześniej": "nie wcześniej",
    "niedłużej": "nie dłużej",
    "niepóźniej": "nie później",
}

# Article and paragraph numbers inside the provisions, as the PDF text has them -> as the Code
# numbers them.
FLAT = {
    "art. 1801 § 2": "art. 180¹ § 2",
    "§ 1 albo § 11,": "§ 1 albo § 1¹,",
    "art. 1831 § 1": "art. 183¹ § 1",
    "art. 1868a": "art. 186⁸ᵃ",
    "art. 186 8a": "art. 186⁸ᵃ",
    "art. 1802 § 4": "art. 180² § 4",
    "art. 1821d § 1": "art. 182¹ᵈ § 1",
    "art. 1823 § 2": "art. 182³ § 2",
    "art. 182 1a § 3-7": "art. 182¹ᵃ § 3-7",
    "art. 1821c -1821g": "art. 182¹ᶜ -182¹ᵍ",
    # Paragraphs of art. 183 referred to inside it.
    "§ 11 pkt": "§ 1¹ pkt",
    "mowa w § 11,": "mowa w § 1¹,",
    "mowa w § 41,": "mowa w § 4¹,",
    "art. 1802, jeżeli": "art. 180², jeżeli",
    "§ 11 obniżonym": "§ 1¹ obniżonym",
    "§ 41 albo 42 albo § 44 albo 45,": "§ 4¹ albo 4² albo § 4⁴ albo 4⁵,",
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
    # The excerpt marks omitted provisions with "(…)"; what follows is not this paragraph.
    body = body.split("(…)")[0]
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
