"""Facts already read, kept on the server so a case is read by Claude only once. One JSON file
per document, named by the SHA-256 of its bytes. The folder is outside git (.gitignore): the
facts come from confidential documents, though the reader leaves out names and PESEL."""

import hashlib
import json
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel

from .models import CaseFacts


class CachedRead(BaseModel):
    facts: CaseFacts
    pages: int
    pages_read: int


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@lru_cache(maxsize=512)
def _file_digest(path: str, mtime: float, size: int) -> str:
    return digest(Path(path).read_bytes())


def file_digest(path: Path) -> str:
    stat = path.stat()
    return _file_digest(str(path), stat.st_mtime, stat.st_size)


class CaseCache:
    def __init__(self, folder: Path) -> None:
        self.folder = folder

    def _path(self, key: str) -> Path:
        return self.folder / f"{key}.json"

    def has(self, key: str) -> bool:
        return self._path(key).exists()

    def get(self, key: str) -> CachedRead | None:
        path = self._path(key)
        if not path.exists():
            return None
        try:
            return CachedRead.model_validate_json(path.read_text(encoding="utf-8"))
        except ValueError:
            return None

    def put(self, key: str, read: CachedRead) -> None:
        self.folder.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(read.model_dump(mode="json"), ensure_ascii=False, indent=1)
        self._path(key).write_text(payload, encoding="utf-8")
