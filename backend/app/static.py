"""The built frontend served by the API process (the online demo: one container, one address).

`npm run build` writes `frontend/dist`. When that folder is there, every path that is not
`/api/*` gets its file, or `index.html` for the routes of the single-page app (`/admin`,
`/raport`, `/plan/<token>`). In development the folder is not used: Vite serves the frontend."""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


def mount_frontend(app: FastAPI, dist: Path = DIST) -> bool:
    """Add the routes when the build is there; call it after the API routers."""
    index = dist / "index.html"
    if not index.is_file():
        return False
    root = dist.resolve()

    @app.get("/{path:path}", include_in_schema=False)
    async def frontend(path: str) -> FileResponse:
        if path == "api" or path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")
        file = (root / path).resolve()
        if path and file.is_file() and file.is_relative_to(root):
            # Vite names the files in assets/ by their content: they never change.
            cache = "public, max-age=31536000, immutable" if path.startswith("assets/") else None
            return FileResponse(file, headers={"Cache-Control": cache} if cache else None)
        return FileResponse(index, headers={"Cache-Control": "no-cache"})

    return True
