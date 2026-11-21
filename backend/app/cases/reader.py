"""Reading a scanned case with Claude or Gemini: the page images go in, `CaseFacts` come out
(structured output). The model only transcribes what the documents say, with page numbers; it
never computes dates or amounts (CLAUDE.md). Tests use a fake reader (no key, no network)."""

from typing import Protocol

from pydantic_ai import Agent, BinaryContent, ToolOutput
from pydantic_ai.models import Model
from pydantic_ai.settings import ModelSettings

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
- Ubezpieczenie: przepisz okresy z poświadczeń, zrzutów i Z-3 dla każdej osoby, z rodzajem \
ubezpieczenia chorobowego (obowiązkowe przy umowie o pracę, dobrowolne przy zleceniu i JDG). \
Ustalenie ZUS ma pierwszeństwo przed deklaracją płatnika: gdy ZUS stwierdził w decyzji lub \
piśmie, że osoba nie podlega ubezpieczeniu (np. umowa zawarta dla pozoru) albo że \
ubezpieczenie ustało, zapisz ten okres z sickness „none” i dopisz to w label (np. „umowa o \
pracę — wg ZUS nie podlega od 2025-10-01”).
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
            model_settings=ModelSettings(max_tokens=12000),
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
