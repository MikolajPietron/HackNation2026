# /// script
# requires-python = ">=3.12"
# dependencies = ["pillow"]
# ///
"""Generate onboarding icons in one shared style via OpenRouter (Nano Banana 2.1).

Usage (from the repo root):
    uv run tools/illustrations/generate.py tata blizniaki   # subjects/<name>.txt -> png + webp
    uv run tools/illustrations/generate.py --webp-only mama # only re-export png/<name>.png

Prompt = HEADER + subjects/<name>.txt + style.txt. The style anchor (png/mama.png) is attached
as a reference image so every icon matches the set. The full-size source lands in
png/<name>.png. The app gets frontend/src/assets/onboarding/<name>.webp: transparent background
(flood fill from the corners), cropped to a padded square around the drawing, 640 px.
The API key comes from the OPENROUTER_API_KEY env var, otherwise backend/.env or the root .env.
"""

import argparse
import base64
import json
import os
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image, ImageDraw

MODEL = "google/gemini-nano-banana-2.1"
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PNG = HERE / "png"
ASSETS = ROOT / "frontend/src/assets/onboarding"
STYLE_ANCHOR = PNG / "mama.png"
WEBP_SIZE = 640
BG_THRESHOLD = 48
"""Sum of RGBA differences from the corner colour that still counts as background."""
PADDING = 0.06
"""Empty margin around the drawing, as a share of its longer side."""
HEADER = (
    "Create a single square ICON for a premium mobile app "
    "(same icon set as the attached reference)."
)


def api_key() -> str:
    if key := os.environ.get("OPENROUTER_API_KEY"):
        return key
    for env in (ROOT / "backend/.env", ROOT / ".env"):
        if not env.exists():
            continue
        for line in env.read_text().splitlines():
            if line.startswith("OPENROUTER_API_KEY=") and line.split("=", 1)[1].strip():
                return line.split("=", 1)[1].strip().strip('"')
    raise SystemExit("Brak OPENROUTER_API_KEY (env, backend/.env albo .env)")


def generate(prompt: str, refs: list[Path], out: Path) -> float | None:
    content: list[dict] = [{"type": "text", "text": prompt}]
    for ref in refs:
        data = base64.b64encode(ref.read_bytes()).decode()
        content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{data}"}})
    body = {
        "model": MODEL,
        "messages": [{"role": "user", "content": content}],
        "modalities": ["image", "text"],
        "image_config": {"aspect_ratio": "1:1"},
    }
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {api_key()}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        data = json.load(resp)
    images = data["choices"][0]["message"].get("images") or []
    if not images:
        raise RuntimeError(f"Model nie zwrócił obrazu: {json.dumps(data)[:500]}")
    out.write_bytes(base64.b64decode(images[0]["image_url"]["url"].split(",", 1)[1]))
    return data.get("usage", {}).get("cost")


def cut_out(img: Image.Image) -> Image.Image:
    """Make the background transparent and crop to a padded square around the drawing.

    Flood fill from the corners keeps white parts inside the outlines (paper, blanket).
    """
    img = img.convert("RGBA")
    w, h = img.size
    for corner in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
        if img.getpixel(corner)[3]:
            ImageDraw.floodfill(img, corner, (255, 255, 255, 0), thresh=BG_THRESHOLD)
    box = img.getbbox()
    if box is None:
        raise RuntimeError("Pusty obraz po usunięciu tła")
    left, top, right, bottom = box
    side = round(max(right - left, bottom - top) * (1 + 2 * PADDING))
    square = Image.new("RGBA", (side, side), (255, 255, 255, 0))
    offset = ((side - (right - left)) // 2, (side - (bottom - top)) // 2)
    square.paste(img.crop(box), offset)
    return square


def export_webp(name: str) -> Path:
    out = ASSETS / f"{name}.webp"
    with Image.open(PNG / f"{name}.png") as img:
        icon = cut_out(img).resize((WEBP_SIZE, WEBP_SIZE), Image.LANCZOS)
    icon.save(out, quality=90, alpha_quality=100)
    return out


def run(name: str) -> str:
    subject = (HERE / "subjects" / f"{name}.txt").read_text().strip()
    style = (HERE / "style.txt").read_text().strip()
    cost = generate(f"{HEADER}\n\n{subject}\n\n{style}", [STYLE_ANCHOR], PNG / f"{name}.png")
    return f"{export_webp(name).relative_to(ROOT)}  (koszt: {cost} $)"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("names", nargs="+", help="nazwy plików w subjects/ (bez .txt)")
    parser.add_argument("--webp-only", action="store_true", help="tylko eksport png -> webp")
    args = parser.parse_args()

    PNG.mkdir(exist_ok=True)
    ASSETS.mkdir(parents=True, exist_ok=True)
    if args.webp_only:
        for name in args.names:
            print(export_webp(name).relative_to(ROOT))
        return
    with ThreadPoolExecutor(max_workers=6) as pool:
        for name, result in zip(args.names, pool.map(run, args.names), strict=True):
            print(f"{name}: {result}")


if __name__ == "__main__":
    main()
