#!/usr/bin/env bash
# Przygotowanie danych ZUS: rozpakowanie zipów, OCR spraw, poprawa obróconych stron, katalog spraw.
# Wymaga: python3, poppler (pdftoppm, pdftotext), tesseract z językiem "pol", macOS (sips, textutil).
# Wejście: zipy od organizatora w docs/dokumentyZUS/. Wyjście: docs/dokumentyZUS/{materialy,sprawy,ocr,katalog_spraw.*}
# Cały docs/dokumentyZUS/ jest w .gitignore – dane są poufne.
set -euo pipefail
T="$(cd "$(dirname "$0")" && pwd)"
D="$(cd "$T/../../docs/dokumentyZUS" && pwd)"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
cd "$D"
[ -d materialy ] || python3 -I "$T/unzip_utf8.py" Materia*.zip materialy
[ -d sprawy ]    || python3 -I "$T/unzip_utf8.py" Sprawy*.zip sprawy
mkdir -p ocr
# OCR 300 dpi, 8 równolegle; pomija duplikat "(1)" i pliki już przetworzone
find sprawy -name '*.pdf' ! -name '*(1).pdf' -print0 | xargs -0 -P 8 -I{} python3 -I "$T/ocr_one.py" "{}" ocr "$TMP"
# słownik do oceny jakości OCR = tekst materiałów prawnych
{ for f in materialy/*.pdf ../Przewodnik_Rodzica_ZUS.pdf; do pdftotext "$f" -; done; textutil -convert txt -stdout materialy/*.docx; } > "$TMP/vocab.txt"
python3 -I "$T/page_scores.py" "$TMP/vocab.txt" ocr "$TMP/page_scores.json"
[ -f ocr/_rotated_pages.json ] || python3 -I "$T/fix_rotation.py" "$TMP/vocab.txt" "$TMP/page_scores.json" sprawy ocr/_rotated_pages.json "$TMP"
python3 -I "$T/build_catalog.py" ocr katalog_spraw.md katalog_spraw.json
