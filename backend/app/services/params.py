"""Source of legal parameters: the base JSON in the repo (`backend/params/`).

Versions edited in the admin panel live in `param_versions` (see `param_versions.py`); the API
picks the one in force (`api/deps.get_params`). The engine only ever gets a `Params`.
"""

from functools import lru_cache
from pathlib import Path

from app.engine.params import Params

PARAMS_DIR = Path(__file__).resolve().parents[2] / "params"
DEFAULT_VERSION = "2026"


@lru_cache
def load_params(name: str = DEFAULT_VERSION) -> Params:
    return Params.model_validate_json((PARAMS_DIR / f"{name}.json").read_text(encoding="utf-8"))
