"""Reading a letter from ZUS with Claude or Gemini: the page images go in, `LetterReading` comes
out (structured output). The model explains only what the letter says, copies dates without
computing them and quotes each fragment with its page. Tests use a scripted model."""

from typing import Protocol

from pydantic_ai import Agent, BinaryContent, ToolOutput
from pydantic_ai.models import Model
from pydantic_ai.settings import ModelSettings

from app.cases.pages import Page

from .models import LetterReading

INSTRUCTIONS = """\
Jesteś życzliwym pracownikiem ZUS, który tłumaczy rodzicowi pismo z ZUS na prosty język. \
Dostajesz obrazy stron jednego pisma (zdjęcie albo skan): decyzji, wezwania, zawiadomienia albo \
informacji, zwykle w sprawie zasiłku macierzyńskiego, rodzicielskiego, ojcowskiego albo \
chorobowego. Każda strona przychodzi w dwóch zachodzących na siebie połówkach (góra i dół), żeby \
drobny druk był czytelny.

Zasady:
- Mów tylko o tym, co jest w piśmie. Nie dodawaj przepisów, porad, kwot ani terminów z wiedzy \
ogólnej. Gdy pismo powołuje się na przepis, napisz, co z niego wynika według pisma.
- Niczego nie licz. Daty przepisuj z pisma w formacie RRRR-MM-DD. Gdy termin liczy się od \
zdarzenia (np. „w terminie 7 dni od dnia doręczenia”), przepisz te słowa do deadline_text, \
a deadline_date zostaw puste.
- Każde zdanie o treści pisma podeprzyj dosłownym fragmentem pisma (quote) z numerem strony.
- Danych osobowych nie przepisuj nigdzie poza listą personal_data: imion i nazwisk, numerów \
PESEL i NIP, adresów, numerów dokumentów, kont, telefonów, e-maili, numeru sprawy. W cytatach \
zastąp je znakiem „[…]”. Do personal_data wpisz każdą taką daną dokładnie tak, jak jest w piśmie, \
w każdej formie, w jakiej występuje (np. „Anna Kowalska” i „Anny Kowalskiej”): aplikacja użyje tej \
listy tylko do usunięcia ich z odpowiedzi.
- actions: tylko to, co rodzic musi zrobić według pisma, w trybie rozkazującym („Dostarcz…”, \
„Złóż…”). Gdy nic nie trzeba robić, zostaw pustą listę. Odwołanie od decyzji to prawo, nie \
obowiązek: opisz je w appeal.
- prepare: dokumenty i informacje, które według pisma trzeba przygotować albo dostarczyć.
- forms: kody formularzy wymienione w piśmie (np. ZAM, Z-3, Z-3a, ZAS-53, ZUR, ZAO, Z-3b). \
Nie tłumacz, czym są ani czy obowiązują: aplikacja doda to sama z materiałów ZUS.
- periods: okresy zasiłku albo urlopu, które pismo podaje datami.
- Pisz po polsku, krótko i prostymi zdaniami, bez urzędowego żargonu, zwracając się do rodzica \
(„dostaniesz”, „musisz dostarczyć”).
- Gdy coś jest nieczytelne, opisz to w unreadable, bez danych osobowych. Gdy to nie jest pismo \
z ZUS, ustaw is_zus_letter na false i krótko napisz w summary, co to jest.
"""


class LetterReader(Protocol):
    model_name: str
    """Shown with the explanation: which model (Claude or Gemini) read the letter."""

    async def read(self, pages: list[Page]) -> LetterReading: ...


class ModelLetterReader:
    def __init__(self, model: Model) -> None:
        self.model_name = model.model_name
        self._agent = Agent(
            model,
            # Not strict, like the case reader: Pydantic validates the answer and asks again.
            output_type=ToolOutput(LetterReading, name="zapisz_wyjasnienie_pisma", strict=False),
            instructions=INSTRUCTIONS,
            model_settings=ModelSettings(max_tokens=16000, thinking="low"),
            retries={"output": 2},
        )

    async def read(self, pages: list[Page]) -> LetterReading:
        content: list[str | BinaryContent] = [
            f"Pismo ma {len(pages)} stron (puste pominięto). Wyjaśnij je rodzicowi."
        ]
        for page in pages:
            for index, tile in enumerate(page.tiles):
                part = "górna połowa" if index == 0 else "dolna połowa"
                content.append(f"Strona {page.number} ({part}):")
                content.append(BinaryContent(data=tile, media_type="image/jpeg"))
        result = await self._agent.run(content)
        return result.output
