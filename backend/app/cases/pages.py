"""Pages of a scanned case as images for the reader, in grey JPEG. Claude reads an image at up
to about 1.15 megapixels, which for a whole A4 page is too little for the dense tables of Z-3,
so every page goes as two overlapping halves (top and bottom; left and right when the scan lies
on its side). Blank pages (about 15% of the scans) are marked so they are not sent."""

import io
import threading
from dataclasses import dataclass

import pypdfium2 as pdfium
from PIL import Image, ImageOps

LONG_SIDE = 2200
JPEG_QUALITY = 74
# Each half reaches a bit past the middle, so a table row is never cut in two.
OVERLAP = 0.06
# A page with less than this share of dark pixels is blank (a scanned empty back side).
BLANK_INK = 0.004
PDFIUM = threading.Lock()
"""pdfium is not thread-safe: two cases rendered at once in threads (`app.cases.batch --jobs 2`,
two uploads to the server) crashed the process with SIGBUS in FPDF_LoadPage (22.11.2026). Every
pdfium call holds this lock, and documents are closed inside it, not by the garbage collector."""


@dataclass(frozen=True)
class Page:
    number: int
    tiles: tuple[bytes, ...]
    """The page in halves, in reading order."""
    blank: bool


def _jpeg(image: Image.Image) -> bytes:
    out = io.BytesIO()
    image.save(out, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    return out.getvalue()


def _encode(image: Image.Image) -> tuple[tuple[bytes, ...], bool]:
    grey = ImageOps.grayscale(image)
    grey.thumbnail((LONG_SIDE, LONG_SIDE))
    histogram = grey.histogram()
    dark = sum(histogram[:128]) / max(1, grey.width * grey.height)
    width, height = grey.size
    if height >= width:
        half = int(height * (0.5 + OVERLAP / 2))
        boxes = [(0, 0, width, half), (0, height - half, width, height)]
    else:
        half = int(width * (0.5 + OVERLAP / 2))
        boxes = [(0, 0, half, height), (width - half, 0, width, height)]
    return tuple(_jpeg(grey.crop(box)) for box in boxes), dark < BLANK_INK


def page_count(data: bytes) -> int:
    if not data.startswith(b"%PDF"):
        return 1
    with PDFIUM:
        document = pdfium.PdfDocument(data)
        try:
            return len(document)
        finally:
            document.close()


def render_pages(data: bytes) -> list[Page]:
    """A PDF page by page, or a single photo or scan (JPEG, PNG)."""
    if not data.startswith(b"%PDF"):
        image = ImageOps.exif_transpose(Image.open(io.BytesIO(data)))
        tiles, blank = _encode(image.convert("RGB"))
        return [Page(1, tiles, blank)]
    pages: list[Page] = []
    with PDFIUM:
        document = pdfium.PdfDocument(data)
        try:
            for index in range(len(document)):
                page = document[index]
                width, height = page.get_size()
                scale = LONG_SIDE / max(width, height)
                bitmap = page.render(scale=scale, grayscale=True)
                image = bitmap.to_pil().copy()  # own pixels: the bitmap is closed below
                bitmap.close()
                page.close()
                tiles, blank = _encode(image)
                pages.append(Page(index + 1, tiles, blank))
        finally:
            document.close()
    return pages
