"""The optional AI pass of the request check: Claude or Gemini rewords the problems the checks
found, in plain and kind Polish. It gets only the app's own messages (labels and dates, no field
values) and may not add rules: a rewording that drops or adds a number or a form code is thrown
away and the app's message stays."""

import re
from typing import Protocol

from pydantic import BaseModel
from pydantic_ai import Agent, ToolOutput
from pydantic_ai.models import Model
from pydantic_ai.settings import ModelSettings

from app.documents.forms import find_forms
from app.engine import Params

from .models import RequestProblem

INSTRUCTIONS = """\
Przeredaguj komunikaty o problemach we wniosku urlopowym albo zasiłkowym na prosty, życzliwy \
język dla rodzica. Każdy komunikat to jeden problem, który znalazła aplikacja.

Zasady:
- Nie dodawaj nowych problemów, przepisów, terminów ani porad. Nie pomijaj żadnego problemu.
- Zachowaj wszystkie daty, liczby i nazwy formularzy dokładnie tak, jak w oryginale. Nie dodawaj \
innych liczb.
- Jeden komunikat to jedno albo dwa krótkie zdania, zwracając się do rodzica.
- Zwróć każdy komunikat z jego identyfikatorem (id).
"""


class Phrased(BaseModel):
    id: str
    text: str


class Phrasing(BaseModel):
    problems: list[Phrased]


class Phraser(Protocol):
    model_name: str

    async def phrase(self, problems: list[RequestProblem]) -> dict[str, str]: ...


class ModelPhraser:
    def __init__(self, model: Model) -> None:
        self.model_name = model.model_name
        self._agent = Agent(
            model,
            output_type=ToolOutput(Phrasing, name="zapisz_komunikaty", strict=False),
            instructions=INSTRUCTIONS,
            model_settings=ModelSettings(max_tokens=3000),
            retries={"output": 1},
        )

    async def phrase(self, problems: list[RequestProblem]) -> dict[str, str]:
        listed = "\n".join(f"[{p.id}] {p.message}" for p in problems)
        result = await self._agent.run(f"Komunikaty:\n{listed}")
        return {p.id: p.text.strip() for p in result.output.problems}


def keeps_facts(original: str, phrased: str, params: Params) -> bool:
    """The same numbers (dates are numbers too) and the same form codes, nothing added."""
    numbers = set(re.findall(r"\d+", original))
    forms = {f.code for f in find_forms(original, params)}
    return (
        bool(phrased.strip())
        and set(re.findall(r"\d+", phrased)) == numbers
        and forms <= {f.code for f in find_forms(phrased, params)}
    )


def apply_phrasing(
    problems: list[RequestProblem], phrased: dict[str, str], params: Params
) -> list[RequestProblem]:
    """Each problem with its rewording when it keeps the facts; otherwise as it was."""
    return [
        p.model_copy(update={"phrased": phrased[p.id]})
        if p.id in phrased and keeps_facts(p.message, phrased[p.id], params)
        else p
        for p in problems
    ]
