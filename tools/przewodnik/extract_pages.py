"""Split docs/Przewodnik_Rodzica_ZUS.pdf into per-page text for the assistant's `read_guide` tool.

Run from the repo root after the PDF changes (requires poppler: pdftotext, pdfinfo):
    python3 tools/przewodnik/extract_pages.py
"""

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PDF = ROOT / "docs" / "Przewodnik_Rodzica_ZUS.pdf"
OUT = ROOT / "backend" / "app" / "assistant" / "przewodnik_pages.json"


def page_count(pdf: Path) -> int:
    info = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True, check=True).stdout
    match = re.search(r"^Pages:\s+(\d+)", info, re.MULTILINE)
    if not match:
        raise SystemExit("pdfinfo did not report a page count")
    return int(match.group(1))


def page_text(pdf: Path, page: int) -> str:
    cmd = ["pdftotext", "-enc", "UTF-8", "-f", str(page), "-l", str(page), str(pdf), "-"]
    text = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    text = text.replace("\f", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(rf"\n{page}\s*$", "", text.strip())  # page number in the footer
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def main() -> None:
    pages = {str(n): page_text(PDF, n) for n in range(1, page_count(PDF) + 1)}
    payload = {"source": PDF.name, "pages": pages}
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(pages)} pages -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
