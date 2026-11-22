"""A letter from ZUS as the model reads it (`LetterReading`, structured output) and as the API
returns it (`LetterExplanation`, marked as AI). The reading is transcription and plain wording:
dates copied from the letter, never computed (CLAUDE.md), each claim with a quoted fragment and
its page."""

import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field

from app.engine.params import KnownForm

LetterKind = Literal["decision", "summons", "notice", "information", "other"]
Outcome = Literal["granted", "refused", "partial", "changed", "none"]
Benefit = Literal[
    "maternity",
    "parental",
    "paternity",
    "supplementary",
    "sickness",
    "rehabilitation",
    "job_loss",
    "rate_815",
    "other",
]


class LetterQuote(BaseModel):
    text: str = Field(
        description=(
            "Dosłowny fragment pisma, słowo w słowo. Dane osobowe w nim zastąp znakiem „[…]”."
        )
    )
    page: int = Field(description="Numer strony pisma, na której jest ten fragment.")


class LetterItem(BaseModel):
    text: str = Field(description="Prostym językiem, jednym krótkim zdaniem.")
    quote: LetterQuote


class LetterAction(BaseModel):
    what: str = Field(
        description=(
            "Co trzeba zrobić według pisma, w trybie rozkazującym, np. „Dostarcz do ZUS "
            "zaświadczenie płatnika składek Z-3.”"
        )
    )
    deadline_text: str | None = Field(
        default=None,
        description=(
            "Termin dokładnie słowami pisma, np. „w terminie 7 dni od dnia doręczenia pisma” "
            "albo „do 15 grudnia 2026 r.”; null, gdy pismo nie podaje terminu."
        ),
    )
    deadline_date: dt.date | None = Field(
        default=None,
        description=(
            "Data terminu, tylko gdy w piśmie jest napisana konkretna data. Niczego nie licz: "
            "termin „7 dni od doręczenia” to null."
        ),
    )
    quote: LetterQuote = Field(description="Fragment pisma, który mówi o tym obowiązku.")


class LetterPeriod(BaseModel):
    benefit: Benefit
    start: dt.date | None = Field(default=None, description="Pierwszy dzień, jak w piśmie.")
    end: dt.date | None = Field(default=None, description="Ostatni dzień, jak w piśmie.")
    quote: LetterQuote


class LetterReading(BaseModel):
    """What the model fills in. `personal_data` never leaves the server: it only says what to
    remove from the answer."""

    is_zus_letter: bool = Field(description="Czy to pismo z ZUS (decyzja, wezwanie, informacja).")
    kind: LetterKind = Field(
        description=(
            "decision = decyzja (rozstrzyga sprawę, zwykle z pouczeniem o odwołaniu), summons = "
            "wezwanie (ZUS prosi o dokumenty albo wyjaśnienia), notice = zawiadomienie (np. o "
            "wszczęciu postępowania, o możliwości zapoznania się z aktami), information = "
            "informacja, other = inne."
        )
    )
    heading: str = Field(description="Nagłówek pisma, np. „DECYZJA”, bez danych osobowych.")
    subject: str = Field(description="Czego dotyczy pismo, jednym zdaniem prostym językiem.")
    benefits: list[Benefit] = Field(
        description=(
            "Których świadczeń dotyczy: maternity = zasiłek/urlop macierzyński, parental = "
            "rodzicielski, paternity = ojcowski, supplementary = uzupełniający urlop macierzyński, "
            "sickness = zasiłek chorobowy, rehabilitation = świadczenie rehabilitacyjne, job_loss "
            "= zasiłek w wysokości zasiłku macierzyńskiego, rate_815 = zasiłek 81,5%, other = inne."
        )
    )
    outcome: Outcome = Field(
        description=(
            "Rozstrzygnięcie decyzji: granted = przyznano, refused = odmowa, partial = częściowo, "
            "changed = zmiana albo ponowne ustalenie, none = pismo niczego nie rozstrzyga."
        )
    )
    summary: str = Field(
        description="Co pismo mówi: 2–4 krótkie zdania prostym językiem, zwracając się do rodzica."
    )
    reason: LetterItem | None = Field(
        default=None, description="Uzasadnienie (np. powód odmowy), gdy pismo je podaje."
    )
    actions: list[LetterAction] = Field(
        description="Co rodzic musi zrobić według pisma. Pusta lista, gdy nic nie trzeba robić."
    )
    prepare: list[LetterItem] = Field(
        description="Dokumenty i informacje, które według pisma trzeba przygotować albo dostarczyć."
    )
    periods: list[LetterPeriod] = Field(
        description="Okresy zasiłku albo urlopu, które pismo podaje datami."
    )
    appeal: LetterAction | None = Field(
        default=None,
        description=(
            "Jak i do kiedy można się odwołać, gdy pismo o tym mówi (pouczenie). To prawo, "
            "nie obowiązek."
        ),
    )
    forms: list[str] = Field(
        description="Kody formularzy wymienione w piśmie, jak w piśmie, np. ZAM, Z-3, ZAS-53."
    )
    personal_data: list[str] = Field(
        description=(
            "Każda dana osobowa widoczna w piśmie, dokładnie jak w piśmie: imiona i nazwiska, "
            "PESEL, NIP, adresy, numery dokumentów, kont, telefonów, e-maile, numer sprawy. "
            "Aplikacja używa tej listy tylko do usunięcia ich z odpowiedzi i nigdzie jej nie "
            "pokazuje ani nie zapisuje."
        )
    )
    unreadable: list[str] = Field(
        default=[], description="Co jest nieczytelne, ze stroną, bez danych osobowych."
    )


KIND_LABELS: dict[LetterKind, str] = {
    "decision": "Decyzja",
    "summons": "Wezwanie",
    "notice": "Zawiadomienie",
    "information": "Informacja",
    "other": "Inne pismo",
}
OUTCOME_LABELS: dict[Outcome, str | None] = {
    "granted": "Przyznano",
    "refused": "Odmowa",
    "partial": "Przyznano częściowo",
    "changed": "Zmiana",
    "none": None,
}

AI_LABEL = (
    "Pismo odczytał i wyjaśnił model AI. Daty i terminy są przepisane z pisma: sprawdź je "
    "w oryginale. To nie jest porada prawna."
)


class LetterExplanation(BaseModel):
    """The letter in plain Polish. `ai` is always true: the UI labels it as an AI feature."""

    ai: Literal[True] = True
    ai_label: str = AI_LABEL
    model: str
    """The model that read the letter (Claude or Gemini)."""
    is_zus_letter: bool
    kind: LetterKind
    kind_label: str
    heading: str
    subject: str
    outcome: Outcome
    outcome_label: str | None
    summary: str
    reason: LetterItem | None
    action_needed: bool
    """Whether the letter asks the parent to do something (`actions` not empty)."""
    actions: list[LetterAction]
    prepare: list[LetterItem]
    periods: list[LetterPeriod]
    appeal: LetterAction | None
    forms: list[KnownForm]
    """The forms the letter names that the guide knows, with what they are and whether they were
    abolished (guide pages 3, 6, 12)."""
    other_forms: list[str]
    """Form codes the letter names that the guide does not describe."""
    timeline_elements: list[str]
    """Ids of the timeline elements the letter is about (with a session: only those on its
    timeline). The rules stay with the timeline; the letter is explained by its own quotes."""
    quotes: list[LetterQuote]
    """Every fragment of the letter the explanation relies on, by page."""
    pages: int
    pages_read: int
    personal_data_removed: bool
    warnings: list[str]
    unreadable: list[str]
