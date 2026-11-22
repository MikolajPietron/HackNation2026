"""Copy the provisions of the two regulations the request forms cite into
backend/app/assistant/rozporzadzenia.json.

The sources are the two regulations in the ZUS materials (docs/dokumentyZUS/, outside git):
- "wnioski": the regulation of 11 March 2025 on the requests concerning employees' parental
  rights and the documents attached to them (Dz.U. z 2025 r. poz. 322): what each leave request
  contains and what goes with it;
- "zasilki": the regulation of 27 September 2026 on the information affecting the right to the
  benefits and the documents needed to grant and pay them (Dz.U. z 2026 r. poz. 1316): the
  documents for the maternity and sickness benefit and, in its annexes, the data a request to ZUS
  holds (annex 6: the maternity benefit, the ZAM form; annex 1: the sickness benefit).

Only the provisions listed below are copied: it is public law text, which the app quotes word for
word. Removed: page headers ("Legalis") and the footnotes printed at the bottom of a page.
Restored, nothing else changed:
- pdftotext glues "nie" to the next word in these PDFs ("niewcześniej");
- it flattens superscripts in article numbers ("art. 1802 § 5" is art. 180² § 5).

Run from the repo root (requires poppler: pdftotext):
    python3 tools/przewodnik/extract_rozporzadzenia.py
"""

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MATERIALS = ROOT / "docs" / "dokumentyZUS" / "materialy"
OUT = ROOT / "backend" / "app" / "assistant" / "rozporzadzenia.json"

ACTS = {
    "wnioski": {
        "pdf": "rozporządzenie w sprawie wniosków dot. uprawnień pracowników związanych z "
        "rodzicielstwem .pdf",
        "source": (
            "Rozporządzenie Ministra Rodziny, Pracy i Polityki Społecznej z dnia 11 marca 2025 r. "
            "w sprawie wniosków dotyczących uprawnień pracowników związanych z rodzicielstwem oraz "
            "dokumentów dołączanych do takich wniosków (Dz.U. z 2025 r. poz. 322), z materiałów "
            "ZUS dla HackNation 2026"
        ),
        # The leave requests on the timeline (engine/forms.py): the part of maternity leave
        # before the birth, the mother's resignation, the father's part of maternity leave
        # (taking over, the mother's incapacity, hospital, death, abandonment), supplementary,
        # parental leave, combining parental leave with work, paternity leave; attachments kept
        # in the personal files.
        "provisions": [
            "§ 2 ust. 1",
            "§ 2 ust. 2",
            "§ 3 ust. 1",
            "§ 3 ust. 2",
            "§ 5 ust. 1",
            "§ 5 ust. 2",
            "§ 6 ust. 1",
            "§ 6 ust. 2",
            "§ 7 ust. 1",
            "§ 7 ust. 2",
            "§ 8 ust. 1",
            "§ 8 ust. 2",
            "§ 9 ust. 1",
            "§ 9 ust. 2",
            "§ 14 ust. 1",
            "§ 14 ust. 2",
            "§ 15 ust. 1",
            "§ 15 ust. 2",
            "§ 16",
            "§ 17 ust. 1",
            "§ 17 ust. 2",
            "§ 22",
        ],
    },
    "zasilki": {
        "pdf": "rozporządzenie w spr. zakresu informacji o okolicznościach mających wpływ na "
        "prawo do zasiłków ...pdf",
        "source": (
            "Rozporządzenie Ministra Rodziny, Pracy i Polityki Społecznej z dnia 27 września "
            "2026 r. w sprawie zakresu informacji o okolicznościach mających wpływ na prawo do "
            "zasiłków z ubezpieczenia społecznego w razie choroby i macierzyństwa lub ich "
            "wysokość oraz dokumentów niezbędnych do przyznania i wypłaty zasiłków (Dz.U. "
            "z 2026 r. poz. 1316), z materiałów ZUS dla HackNation 2026"
        ),
        # The sickness benefit (§ 2, annex 1) and the maternity benefit: the data of the request
        # (§ 12, annex 6), the documents from the birth (§ 13), for the father taking over
        # (§ 20, § 22, § 23), supplementary leave (§ 26), an uninsured mother (§ 32) and
        # paternity leave (§ 33).
        "provisions": [
            "§ 2",
            "§ 12",
            "§ 13 ust. 1",
            "§ 13 ust. 2",
            "§ 13 ust. 3",
            # The mother stops her maternity benefit: the father takes over (§ 18), she has
            # a ruling of incapacity (§ 21) or is in hospital (§ 24).
            "§ 18 ust. 1",
            "§ 20 ust. 1",
            "§ 20 ust. 3",
            "§ 21",
            "§ 22 ust. 1",
            "§ 23 ust. 1",
            "§ 24 ust. 1",
            "§ 26",
            # ZAM of a non-employee for parental leave: filed before the benefit starts.
            "§ 29",
            "§ 30 ust. 1",
            "§ 32 ust. 1",
            "§ 33 ust. 1",
            "zał. 1",
            "zał. 6",
        ],
    },
}

GLUED = {
    "niewcześniej": "nie wcześniej",
    "niekrótszym": "nie krótszym",
    "niepóźniej": "nie później",
    "nieniższym": "nie niższym",
}

# Article numbers inside the provisions, as the PDF text has them -> as the Code numbers them.
FLAT = {
    "art. 1802 § 4": "art. 180² § 4",
    "art. 1802 § 5": "art. 180² § 5",
    "art. 1821a § 2": "art. 182¹ᵃ § 2",
    "art. 1821d § 1": "art. 182¹ᵈ § 1",
    "art. 1821e § 2": "art. 182¹ᵉ § 2",
    "art. 1821f § 3–7": "art. 182¹ᶠ § 3–7",
    "art. 1823 § 2": "art. 182³ § 2",
    "art. 183 § 31": "art. 183 § 3¹",
    "art. 183 § 4–42": "art. 183 § 4–4²",
}

FOOTNOTE_LINES = 8
"""A footnote is short: its number, a sentence or two, the end of the page."""
HEADING = re.compile(r"^(?:§ ?\d+|Załącznik \d+\.)")


def without_page_furniture(text: str) -> str:
    """Drop the "Legalis" page headers and the footnotes: a footnote starts with a line holding
    only its number and runs, in a few lines without a heading, to the end of the page."""
    lines = text.splitlines()
    kept: list[str] = []
    skip_to = -1
    for index, line in enumerate(lines):
        if index <= skip_to or line.strip() == "Legalis":
            continue
        if re.fullmatch(r"\d+", line.strip()):
            rest = lines[index + 1 : index + 1 + FOOTNOTE_LINES]
            end = next((i for i, x in enumerate(rest) if x.strip() == "Legalis"), None)
            if end is not None and not any(HEADING.match(x) for x in rest[:end]):
                skip_to = index + end
                continue
        kept.append(line)
    return "\n".join(kept)


def paragraph(text: str, number: str) -> str:
    """The text of "§ N" after its heading, to the next paragraph or annex."""
    match = re.search(rf"(?m)^§ ?{number}\b ?", text)
    if not match:
        raise SystemExit(f"§ {number} not found")
    following = re.search(r"(?m)^(?:§ ?\d+\b|Załącznik \d+\.)", text[match.end() :])
    end = match.end() + following.start() if following else len(text)
    return text[match.end() : end]


def annex(text: str, number: str) -> str:
    """The text of "Załącznik N." after its title line, to the next annex."""
    match = re.search(rf"(?m)^Załącznik {number}\. .*$", text)
    if not match:
        raise SystemExit(f"Załącznik {number} not found")
    following = re.search(r"(?m)^Załącznik \d+\.", text[match.end() :])
    end = match.end() + following.start() if following else len(text)
    return text[match.end() : end]


def unit(body: str, number: str) -> str:
    """One "ust." of a paragraph: "2. " starts it, the next "N. " at a line start ends it."""
    match = re.search(rf"(?ms)^{number}\. (.*?)(?=^\d+\. |\Z)", body)
    if not match:
        raise SystemExit(f"ust. {number} not found")
    return match.group(1)


def provision(text: str, key: str) -> str:
    if key.startswith("zał. "):
        body = annex(text, key.removeprefix("zał. "))
    else:
        parts = re.fullmatch(r"§ (\d+)(?: ust\. (\d+))?", key)
        if parts is None:
            raise SystemExit(f"bad key {key}")
        body = paragraph(text, parts.group(1))
        if parts.group(2):
            body = unit(body, parts.group(2))
    body = re.sub(r"\s+", " ", body).strip()
    for found, restored in (GLUED | FLAT).items():
        body = body.replace(found, restored)
    return body


def main() -> None:
    payload = {}
    for name, act in ACTS.items():
        pdf = MATERIALS / str(act["pdf"])
        cmd = ["pdftotext", "-enc", "UTF-8", str(pdf), "-"]
        text = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
        text = without_page_furniture(text)
        provisions = {key: provision(text, key) for key in act["provisions"]}
        payload[name] = {"source": act["source"], "provisions": provisions}
        print(f"{name}: {len(provisions)} provisions")
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"-> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
