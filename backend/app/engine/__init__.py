"""Rules engine: Scenario -> Timeline. Pure and deterministic (no I/O, no database, no LLM)."""

from app.engine.explain import changed_note_ids
from app.engine.models import Scenario, ScenarioError, Timeline
from app.engine.params import Params
from app.engine.timeline import build_timeline, changed_element_ids

__all__ = [
    "Params",
    "Scenario",
    "ScenarioError",
    "Timeline",
    "build_timeline",
    "changed_element_ids",
    "changed_note_ids",
]
