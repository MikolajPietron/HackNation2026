"""Reading a scanned case with Claude or Gemini: the page images go in, `CaseFacts` come out
(structured output). The model only transcribes what the documents say, with page numbers; it
never computes dates or amounts (CLAUDE.md). Tests use a fake reader (no key, no network)."""

import base64
import json
import sys
from typing import Any, Protocol

from pydantic import ValidationError
from pydantic_ai import Agent, BinaryContent, ToolOutput
from pydantic_ai.models import Model
from pydantic_ai.settings import ModelSettings

from app.assistant.claude_code import run_claude

from .models import CaseFacts
from .pages import Page

INSTRUCTIONS = """\
Jesteś starannym pracownikiem ZUS, który przepisuje dane ze skanów sprawy o zasiłek \
macierzyński, rodzicielski, ojcowski albo chorobowy. Dostajesz obrazy kolejnych stron jednej \
sprawy (wnioski ZAM, ZUR, ZAO, ZAS-53, zaświadczenia płatnika Z-3, Z-3a, Z-3b, ZAS-12, \
poświadczenia ubezpieczenia, zrzuty z systemu ZUS, pisma i decyzje ZUS, akty urodzenia, karty \
szpitalne). Każda strona przychodzi w dwóch zachodzących na siebie połówkach (góra i dół), \
żeby drobny druk był czytelny. Strony bywają obrócone, część jest odręczna. Dane osobowe są \
celowo zasłonięte (sprawy są zanonimizowane): tego nie zgłaszaj jako problemu.

Zasady:
- Przepisuj tylko to, co jest w dokumentach. Niczego nie licz, nie zgaduj i nie uzupełniaj \
wiedzą ogólną. Daty w formacie RRRR-MM-DD, kwoty w złotych dokładnie jak w dokumencie.
- Przy każdej informacji podaj numery stron (z podpisów „Strona N”), z których ją wziąłeś.
- Wynagrodzenia: z Z-3 przepisz przychód za każdy miesiąc z tabeli (zwykle 12 miesięcy przed \
miesiącem powstania prawa); przy zleceniu lub własnej działalności przepisz podstawę wymiaru \
składki na ubezpieczenie chorobowe z poświadczenia lub zrzutu. Zaznacz miesiące niepełne.
- Z-3 w szczegółach (z tego kalkulator sam liczy podstawę wymiaru): przy miesiącu niepełnym \
przepisz liczbę dni obowiązujących do przepracowania i dni przepracowanych (days_required, \
days_worked); wynagrodzenie stałe z umowy i zmienne (fixed, variable) oraz składniki \
nieuzupełniane, np. nadgodziny (not_topped), tylko gdy Z-3 podaje je osobno. Premie kwartalne \
i składniki roczne (np. trzynastkę) przepisz do bonuses, każdą osobno z okresem i kwotą, bez \
sumowania. Do pay_details przepisz wymiar czasu pracy (full_time), datę, od której osoba \
podlega ubezpieczeniu u tego płatnika (insured_from), i wynagrodzenie albo przychód określony \
w umowie (contract_pay), jeśli dokument je podaje.
- Ubezpieczenie: przepisz okresy z poświadczeń, zrzutów i Z-3 dla każdej osoby, z rodzajem \
ubezpieczenia chorobowego. Umowa o pracę daje obowiązkowe. Przy zleceniu i JDG wpisz \
„voluntary” tylko wtedy, gdy dokument potwierdza zgłoszenie do dobrowolnego ubezpieczenia \
chorobowego; „none”, gdy dokument mówi, że go nie było albo ustało; inaczej „unknown”. \
Ustalenie ZUS ma pierwszeństwo przed deklaracją płatnika: gdy ZUS stwierdził w decyzji lub \
piśmie, że osoba nie podlega ubezpieczeniu (np. umowa zawarta dla pozoru) albo że \
ubezpieczenie ustało, zapisz ten okres z sickness „none”, z zus_finding („sham” przy umowie \
lub działalności dla pozoru, „not-subject” przy innym powodzie) i dopisz to w label (np. \
„umowa o pracę — wg ZUS nie podlega od 2025-10-01”).
- Koniec pracy mamy w ciąży (job_loss): dzień ustania zatrudnienia i przyczyna z dokumentu \
(upadłość, likwidacja albo śmierć pracodawcy, rozwiązanie umowy z naruszeniem prawa — z \
informacją, czy stwierdził to prawomocny wyrok sądu — albo inna przyczyna).
- Rodzina zastępcza albo przysposobienie: taken_in, dzień przyjęcia dziecka na wychowanie \
(taken_in_on) i data urodzenia dziecka (birth_date).
- Zadłużenie składkowe osoby prowadzącej działalność (contribution_debt): kwota z pisma, \
zaświadczenia albo decyzji ZUS, dzień, na który podano stan, i dzień spłaty, jeśli jest.
- Urlopy: każdą część urlopu rodzicielskiego zapisz osobno, z datami i osobą. Gdy tata przejmuje \
urlop macierzyński, zapisz jego urlop jako leave „maternity” taty; gdy powodem jest sytuacja \
mamy (szpital, orzeczenie o niezdolności do samodzielnej egzystencji, zgon, porzucenie \
dziecka), zapisz ją w mother_event z datami.
- Zwolnienie lekarskie w ciąży (e-ZLA, ZAS-53, Z-3 przy chorobowym) zapisz jako leave „sick”.
- Decyzja: szukaj rozstrzygnięcia ZUS (decyzja, pismo, zrzut wypłat). „Przyznano” tylko gdy \
dokument mówi o przyznaniu albo wypłacie, „odmowa” gdy ZUS odmawia. Wezwanie do uzupełnienia \
dokumentów to nie rozstrzygnięcie.
- Gdy data albo kwota jest niepewna (np. odręczna cyfra), wpisz najbardziej prawdopodobną \
wartość, porównując z innymi dokumentami sprawy (np. data porodu = pierwszy dzień urlopu \
macierzyńskiego we wniosku, gdy nie było urlopu przed porodem), a niepewność opisz w \
„unreadable” ze stroną. Pole zostaw puste tylko wtedy, gdy w sprawie w ogóle tego nie ma.
- Zasłoniętych danych osobowych nie wpisuj do „unreadable”: są zanonimizowane celowo.
- Nie przepisuj imion, nazwisk, numerów PESEL ani adresów: nie są potrzebne do wyliczeń.
"""


class CaseReader(Protocol):
    async def read(self, pages: list[Page]) -> CaseFacts: ...


class ModelCaseReader:
    def __init__(self, model: Model) -> None:
        self._agent = Agent(
            model,
            # Not strict: the schema is too big for a strict grammar (Anthropic refuses it);
            # Pydantic still validates the answer and asks again when it does not fit.
            output_type=ToolOutput(CaseFacts, name="zapisz_dane_sprawy", strict=False),
            instructions=INSTRUCTIONS,
            # The cap counts the model's thinking too: a 74-page case spent 12 000 tokens thinking
            # and wrote nothing (Gemini Pro, 22.11.2026). Copying fields needs little thinking.
            model_settings=ModelSettings(max_tokens=32000, thinking="low"),
            retries={"output": 2},
        )

    async def read(self, pages: list[Page]) -> CaseFacts:
        content: list[str | BinaryContent] = [
            f"Sprawa ma {len(pages)} stron (puste pominięto). Przepisz dane do formularza."
        ]
        for page in pages:
            for index, tile in enumerate(page.tiles):
                part = "górna połowa" if index == 0 else "dolna połowa"
                content.append(f"Strona {page.number} ({part}):")
                content.append(BinaryContent(data=tile, media_type="image/jpeg"))
        result = await self._agent.run(content)
        return result.output


READ_TIMEOUT_S = 600
"""A whole case: usually 100–200 s, a 12-page case once took over 300 s (S63, 22.11.2026)."""

CLAUDE_CODE_PREFIX = "claude-code:"
"""`CASES_MODEL=claude-code:opus`: the scans go to the local `claude -p` (ClaudeCodeCaseReader)."""


class ClaudeCodeCaseReader:
    """Dev only: the same reading through the local Claude Code CLI on the developer's claude.ai
    subscription instead of an API key (`app/assistant/claude_code.py`), for `app.cases.batch`.
    The pages go in as images in one message, as in `ModelCaseReader`; the answer is structured
    output against the `CaseFacts` schema, validated here. Claude only: the scans still go to
    Anthropic and nowhere else (CLAUDE.md). Never on a server."""

    def __init__(self, model: str) -> None:
        self._model = model

    async def read(self, pages: list[Page]) -> CaseFacts:
        content: list[dict[str, Any]] = [_text(f"Sprawa ma {len(pages)} stron (puste pominięto).")]
        for page in pages:
            for index, tile in enumerate(page.tiles):
                part = "górna połowa" if index == 0 else "dolna połowa"
                content.append(_text(f"Strona {page.number} ({part}):"))
                data = base64.b64encode(tile).decode()
                source = {"type": "base64", "media_type": "image/jpeg", "data": data}
                content.append({"type": "image", "source": source})
        content.append(_text("Przepisz dane do formularza (JSON wg schematu, daty RRRR-MM-DD)."))
        schema = _loose(CaseFacts.model_json_schema())
        for attempt in (1, 2):
            result = await run_claude(
                self._model,
                system=INSTRUCTIONS,
                prompt=content,
                schema=schema,
                timeout=READ_TIMEOUT_S,
            )
            _report(self._model, result)
            try:
                return CaseFacts.model_validate(result.get("structured_output"))
            except ValidationError as error:
                if attempt == 2:
                    raise
                # One more try with the errors: the whole case goes again, so only once.
                content.append(_text(f"Poprzednia odpowiedź nie pasowała do schematu: {error}"))
        raise AssertionError("unreachable")


def _loose(node: Any) -> Any:
    """The schema Claude Code enforces, without what made it give up on a real case
    (`error_max_structured_output_retries`, sending every page again each time): no `format`,
    `minimum` or `maximum`, and the allowed values in the description instead of `enum`.
    `CaseFacts` validates the answer afterwards and its errors go back once (`read`)."""
    if isinstance(node, list):
        return [_loose(item) for item in node]
    if not isinstance(node, dict):
        return node
    out = {k: _loose(v) for k, v in node.items() if k not in ("format", "minimum", "maximum")}
    if "enum" in out:
        values = ", ".join(json.dumps(v, ensure_ascii=False) for v in out.pop("enum"))
        out["description"] = f"{out.get('description', '')} Jedna z wartości: {values}.".strip()
    return out


def _text(text: str) -> dict[str, Any]:
    return {"type": "text", "text": text}


def _report(model: str, result: dict[str, Any]) -> None:
    """Tokens of one read on stderr, to watch the subscription's limits (no case content)."""
    usage = result.get("usage") or {}
    sent = sum(usage.get(k) or 0 for k in ("input_tokens", "cache_creation_input_tokens"))
    print(
        f"  claude -p {model}: {sent + (usage.get('cache_read_input_tokens') or 0)} in, "
        f"{usage.get('output_tokens') or 0} out, {result.get('duration_ms', 0) / 1000:.0f} s",
        file=sys.stderr,
        flush=True,
    )
