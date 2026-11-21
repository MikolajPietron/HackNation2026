"""What a ZUS case says, as read from its scanned documents, and what we make of it.

`CaseFacts` is transcription only: the reader (Claude, from the page images) copies what the
documents say, with page numbers, and never computes a date or an amount (CLAUDE.md: the LLM
never counts). Everything after that is deterministic: `assess.py` turns the facts into a
`Scenario`, checks the sickness insurance on the day the right arises and compares the result
with the decision of ZUS found in the case.
"""

import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field

from app.engine import Scenario, Timeline
from app.engine.models import Role, TakenIn

InsuranceTitle = Literal["employment", "contract", "business", "other"]
SicknessInsurance = Literal["mandatory", "voluntary", "none", "unknown"]
LeaveKind = Literal["maternity", "parental", "paternity", "supplementary", "sick", "other"]
Outcome = Literal["granted", "refused", "partial", "unknown"]


class CaseDocument(BaseModel):
    kind: str = Field(
        description=(
            "Rodzaj dokumentu, np. ZAM, ZUR, ZAO, ZAS-53, ZAS-12, Z-3, Z-3a, Z-3b, decyzja ZUS, "
            "pismo ZUS, poświadczenie ubezpieczenia, zrzut z systemu ZUS, e-ZLA, odpis aktu "
            "urodzenia, karta szpitalna, zaświadczenie Za życiem, umowa, wniosek urlopowy, inne."
        )
    )
    pages: list[int] = Field(description="Numery stron, na których jest ten dokument.")


class InsurancePeriod(BaseModel):
    person: Role = Field(description="Czyje to ubezpieczenie: mother albo father.")
    title: InsuranceTitle = Field(
        description=(
            "Tytuł ubezpieczenia: employment = umowa o pracę, contract = umowa zlecenia, "
            "business = własna działalność gospodarcza (JDG) lub współpraca, other = inny."
        )
    )
    label: str = Field(description="Tytuł słowami, jak w dokumencie, np. „umowa o pracę”.")
    start: dt.date | None = Field(description="Pierwszy dzień ubezpieczenia, jeśli podany.")
    end: dt.date | None = Field(description="Ostatni dzień; null = trwa albo nie podano.")
    sickness: SicknessInsurance = Field(
        description=(
            "Ubezpieczenie chorobowe w tym okresie: mandatory = obowiązkowe (umowa o pracę), "
            "voluntary = dobrowolne (zlecenie, JDG), none = brak, unknown = dokument nie mówi."
        )
    )
    pages: list[int]


class LeavePeriod(BaseModel):
    person: Role
    kind: LeaveKind = Field(
        description=(
            "maternity = urlop/zasiłek macierzyński, parental = rodzicielski, "
            "paternity = ojcowski, supplementary = uzupełniający, "
            "sick = zwolnienie lekarskie / zasiłek chorobowy."
        )
    )
    start: dt.date
    end: dt.date | None = None
    pages: list[int]


class PayMonth(BaseModel):
    month: str = Field(description="Miesiąc w formacie RRRR-MM.")
    amount: float = Field(
        description=(
            "Kwota dokładnie jak w dokumencie, w zł: przy pracowniku przychód (wynagrodzenie) z "
            "Z-3 za ten miesiąc, przy zleceniu lub JDG podstawa wymiaru składki na ubezpieczenie "
            "chorobowe. Nie przeliczaj, nie odejmuj składek."
        )
    )
    kind: Literal["salary", "contribution_base"]
    person: Role
    full_month: bool | None = Field(
        default=None, description="Czy miesiąc przepracowany w całości (Z-3: dni nieobecności)."
    )
    note: str = Field(default="", description="Uwagi z dokumentu, np. dni nieobecności, premia.")
    pages: list[int]


class Decision(BaseModel):
    outcome: Outcome = Field(
        description=(
            "Rozstrzygnięcie ZUS w tej sprawie: granted = przyznano / wypłacono, refused = "
            "odmowa, partial = przyznano częściowo, unknown = w dokumentach nie ma rozstrzygnięcia."
        )
    )
    benefit: str = Field(description="Którego świadczenia dotyczy, słowami.")
    reason: str = Field(description="Uzasadnienie jednym-dwoma zdaniami, jak w dokumencie.")
    pages: list[int]


class HospitalPeriod(BaseModel):
    start: dt.date
    end: dt.date | None = None
    pages: list[int] = []


class CaseFacts(BaseModel):
    """Everything the calculator needs from the case, transcribed with page numbers."""

    title: str = Field(
        default="",
        description="Krótki tytuł sprawy, do 6 słów, np. „Zasiłek chorobowy w ciąży, odmowa”.",
    )
    summary: str = Field(
        description="Dwa zdania po polsku: czego dotyczy sprawa i o co wnioskowano."
    )
    applicant: Role | None = Field(description="Kto wnioskuje o świadczenie: mother albo father.")
    benefit_requested: str = Field(description="O jakie świadczenie i za jaki okres wnioskowano.")
    child_born: bool | None = Field(description="Czy dziecko już się urodziło.")
    birth_date: dt.date | None = Field(description="Data urodzenia dziecka (poród).")
    due_date: dt.date | None = Field(description="Przewidywana data porodu, jeśli podana.")
    children_count: int | None = Field(
        default=None, ge=1, le=10, description="Liczba dzieci z jednego porodu."
    )
    stillborn: bool | None = Field(default=None, description="Martwe urodzenie.")
    taken_in: TakenIn | None = Field(
        default=None, description="adoption = przysposobienie, foster = rodzina zastępcza."
    )
    taken_in_on: dt.date | None = Field(default=None, description="Dzień przyjęcia dziecka.")
    za_zyciem: bool | None = Field(default=None, description="Zaświadczenie „Za życiem”.")
    hospital_after_birth: bool | None = Field(
        default=None, description="Wcześniak albo dziecko w szpitalu po porodzie."
    )
    birth_week: int | None = Field(
        default=None, ge=20, le=45, description="Tydzień ciąży, w którym dziecko się urodziło."
    )
    birth_weight_grams: int | None = Field(
        default=None, ge=200, le=7000, description="Masa urodzeniowa (najlżejszego dziecka)."
    )
    hospital_stays: list[HospitalPeriod] = Field(
        default=[], description="Pobyty dziecka w szpitalu po porodzie (z kart, zaświadczeń)."
    )
    payer_over_20: bool | None = Field(
        default=None,
        description="Czy płatnik zgłasza do chorobowego ponad 20 osób (wypłaca sam).",
    )
    documents: list[CaseDocument]
    insurance: list[InsurancePeriod] = Field(
        description="Okresy ubezpieczenia z poświadczeń, zrzutów i Z-3, dla każdej osoby."
    )
    leaves: list[LeavePeriod] = Field(description="Okresy urlopów i zasiłków z wniosków i Z-3.")
    pay: list[PayMonth] = Field(
        description="Miesiące wynagrodzenia z Z-3 albo podstawy składek z poświadczenia."
    )
    decision: Decision | None = Field(description="Rozstrzygnięcie ZUS, jeśli jest w sprawie.")
    unreadable: list[str] = Field(
        default=[], description="Czego nie dało się odczytać albo co jest niepewne (ze stroną)."
    )


class CaseListItem(BaseModel):
    id: str
    """S01–S86, as in the case catalogue (tools/zus-data)."""
    category: str
    title: str = ""
    """The short title AI gave the case once read (no personal data)."""
    """The catalogue's category, from the file name (no personal data)."""
    pages: int
    read: bool
    """Already read: the result is cached and comes back at once."""


class CaseList(BaseModel):
    configured: bool
    """CASES_DIR is set and exists."""
    cases: list[CaseListItem]


class InsuranceCheck(BaseModel):
    person: Role
    on: dt.date | None
    """The day the right arises (the birth, or the day a child is taken in)."""
    covered: bool | None
    """Sickness insurance on that day; None = the case does not say."""
    period: InsurancePeriod | None
    text: str


class Comparison(BaseModel):
    ours: Outcome
    zus: Outcome
    match: bool | None
    """None when either side is unknown."""
    text: str


class CaseResult(BaseModel):
    id: str | None
    """The catalogue id; None for an uploaded file that is not in the catalogue."""
    pages: int
    pages_read: int
    """Pages sent to the reader (blank pages are skipped)."""
    cached: bool
    facts: CaseFacts
    scenario: Scenario
    timeline: Timeline | None
    insurance: InsuranceCheck
    comparison: Comparison
    notes: list[str]
    """How the facts were turned into the calculator's answers (assumptions, gaps)."""
    problem: str | None = None
    """Why there is no timeline, when there is none."""


class AssessRequest(BaseModel):
    id: str | None = None
    pages: int = 0
    pages_read: int = 0
    facts: CaseFacts


class ApplyRequest(BaseModel):
    scenario: Scenario


__all__ = [
    "AssessRequest",
    "ApplyRequest",
    "CaseDocument",
    "CaseFacts",
    "CaseList",
    "CaseListItem",
    "CaseResult",
    "Comparison",
    "Decision",
    "InsuranceCheck",
    "InsurancePeriod",
    "LeavePeriod",
    "PayMonth",
]
