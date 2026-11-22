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
from app.engine.models import JobLossReason, MotherEventKind, Role, TakenIn

InsuranceTitle = Literal["employment", "contract", "business", "other"]
SicknessInsurance = Literal["mandatory", "voluntary", "none", "unknown"]
LeaveKind = Literal["maternity", "parental", "paternity", "supplementary", "sick", "other"]
Outcome = Literal["granted", "refused", "partial", "unknown"]
DifferenceReason = Literal["reading", "missing-rule", "other-refusal"]
"""Why the calculator and ZUS differ: reading = the facts as read lack or contradict what the
decision rests on (read the case again); missing-rule = the calculator has no rule for what the
case turns on; other-refusal = ZUS refused for a reason the calculator does not check (e.g.
documents, deadlines)."""
BonusKind = Literal["quarterly", "annual"]
ZusFinding = Literal["sham", "not-subject"]
"""What ZUS established about an insurance period: a sham contract or business (guide H.1), or
no sickness insurance for another reason."""


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
            "Ubezpieczenie chorobowe w tym okresie, według dokumentu: mandatory = obowiązkowe "
            "(umowa o pracę), voluntary = dobrowolne, gdy dokument potwierdza zgłoszenie do "
            "dobrowolnego ubezpieczenia chorobowego (zlecenie, JDG), none = dokument mówi, że "
            "go nie ma (niezgłoszona, ustało, ZUS stwierdził niepodleganie), unknown = dokument "
            "nie mówi. Przy zleceniu i JDG nie wpisuj voluntary tylko z powodu rodzaju umowy."
        )
    )
    zus_finding: ZusFinding | None = Field(
        default=None,
        description=(
            "Ustalenie ZUS w decyzji lub piśmie co do tego okresu: sham = ZUS uznał umowę albo "
            "działalność za zawartą dla pozoru i stwierdził niepodleganie ubezpieczeniom; "
            "not-subject = ZUS stwierdził z innego powodu, że osoba nie podlega ubezpieczeniu "
            "chorobowemu (np. niezgłoszona, dobrowolne ubezpieczenie ustało). Wtedy sickness = "
            "none. Puste, gdy ZUS nic takiego nie ustalił."
        ),
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
    days_required: int | None = Field(
        default=None,
        description=(
            "Miesiąc niepełny: liczba dni obowiązujących do przepracowania w tym miesiącu (przy "
            "zleceniu lub JDG: dni miesiąca), jak w Z-3. Puste, gdy miesiąc jest pełny."
        ),
    )
    days_worked: int | None = Field(
        default=None,
        description="Miesiąc niepełny: liczba dni faktycznie przepracowanych, jak w Z-3.",
    )
    fixed: float | None = Field(
        default=None,
        description=(
            "Miesiąc niepełny, tylko gdy Z-3 podaje to osobno: wynagrodzenie stałe w kwocie "
            "miesięcznej określone w umowie, w zł."
        ),
    )
    variable: float | None = Field(
        default=None,
        description=(
            "Miesiąc niepełny, tylko gdy Z-3 podaje to osobno: wynagrodzenie zmienne za dni "
            "przepracowane, w zł."
        ),
    )
    not_topped: float | None = Field(
        default=None,
        description=(
            "Tylko gdy Z-3 podaje to osobno: składniki, których się nie uzupełnia (wynagrodzenie "
            "za nadgodziny, dodatek za pracę w nocy, prowizje) w tym miesiącu, w zł."
        ),
    )
    note: str = Field(default="", description="Uwagi z dokumentu, np. dni nieobecności, premia.")
    pages: list[int]


class Bonus(BaseModel):
    """A quarterly or annual bonus from the payer's certificate (Z-3), as listed there."""

    person: Role
    kind: BonusKind = Field(
        description=(
            "quarterly = premia lub nagroda kwartalna, annual = składnik roczny (np. trzynastka, "
            "nagroda roczna)."
        )
    )
    period: str = Field(description="Za jaki okres, jak w dokumencie, np. „IV kwartał 2025”.")
    amount: float = Field(description="Kwota w zł dokładnie jak w dokumencie. Nie sumuj premii.")
    pages: list[int] = []


class PayDetails(BaseModel):
    """What else the benefit base depends on, from the payer's certificate or the contract."""

    person: Role
    full_time: bool | None = Field(
        default=None,
        description="Praca w pełnym wymiarze czasu pracy (Z-3: wymiar czasu pracy), jeśli podano.",
    )
    insured_from: dt.date | None = Field(
        default=None,
        description=(
            "Od kiedy osoba nieprzerwanie podlega ubezpieczeniu chorobowemu u tego płatnika "
            "(z tej umowy, z tej działalności), jeśli dokument to podaje."
        ),
    )
    contract_pay: float | None = Field(
        default=None,
        description=(
            "Wynagrodzenie miesięczne albo przychód określony w umowie, w zł, jeśli dokument je "
            "podaje (ważne, gdy prawo powstało w pierwszym miesiącu ubezpieczenia)."
        ),
    )
    pages: list[int] = []


class CaseJobLoss(BaseModel):
    """The mother's work ended in pregnancy (guide page 4; ustawa art. 30)."""

    ended_on: dt.date = Field(description="Ostatni dzień zatrudnienia (umowy, działalności).")
    reason: JobLossReason = Field(
        description=(
            "bankruptcy = upadłość pracodawcy, liquidation = likwidacja pracodawcy, "
            "employer-death = śmierć pracodawcy, unlawful = rozwiązanie umowy o pracę z "
            "naruszeniem przepisów prawa, other = każdy inny koniec pracy (np. koniec umowy na "
            "czas określony, wypowiedzenie, zamknięcie działalności)."
        )
    )
    court_confirmed: bool | None = Field(
        default=None,
        description="Tylko przy unlawful: czy naruszenie prawa stwierdził prawomocny wyrok sądu.",
    )
    pages: list[int] = []


class CaseMotherEvent(BaseModel):
    """A special situation in which the father takes over maternity leave (guide section B)."""

    kind: MotherEventKind = Field(
        description=(
            "incapacity = mama ma orzeczenie o niezdolności do samodzielnej egzystencji, "
            "hospital = mama w szpitalu, death = zgon mamy, abandonment = mama porzuciła dziecko."
        )
    )
    start: dt.date = Field(
        description="Dzień zdarzenia (przy szpitalu: pierwszy dzień pobytu mamy w szpitalu)."
    )
    end: dt.date | None = Field(default=None, description="Tylko szpital: ostatni dzień pobytu.")
    pages: list[int] = []


class ContributionDebt(BaseModel):
    """Contribution debt of a person running a business (ustawa art. 2a)."""

    person: Role
    amount: float = Field(
        description=(
            "Zadłużenie z tytułu składek na ubezpieczenia społeczne w zł, dokładnie jak w "
            "dokumencie ZUS (stan na dzień powstania prawa do świadczenia); 0 = brak zadłużenia."
        )
    )
    on: dt.date | None = Field(default=None, description="Na jaki dzień dokument podaje stan.")
    repaid_on: dt.date | None = Field(
        default=None, description="Dzień spłaty całości zadłużenia, jeśli dokument go podaje."
    )
    pages: list[int] = []


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
    taken_in_on: dt.date | None = Field(
        default=None,
        description=(
            "Dzień przyjęcia dziecka na wychowanie (rodzina zastępcza, przysposobienie): od niego "
            "liczy się prawo. birth_date to wtedy data urodzenia dziecka."
        ),
    )
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
    bonuses: list[Bonus] = Field(
        default=[], description="Premie kwartalne i składniki roczne z Z-3, każda osobno."
    )
    pay_details: list[PayDetails] = Field(
        default=[],
        description="Wymiar czasu pracy, początek ubezpieczenia u płatnika, kwota z umowy.",
    )
    job_loss: CaseJobLoss | None = Field(
        default=None, description="Koniec pracy mamy w czasie ciąży, przed porodem."
    )
    mother_event: CaseMotherEvent | None = Field(
        default=None,
        description="Sytuacja szczególna mamy, w której tata przejmuje urlop macierzyński.",
    )
    contribution_debt: ContributionDebt | None = Field(
        default=None,
        description="Zadłużenie składkowe osoby prowadzącej działalność, z dokumentu ZUS.",
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
    reason: DifferenceReason | None = None
    """Set when `match` is False: why the calculator and ZUS differ."""
    reason_text: str = ""
    """The difference in a sentence or two, for the agreement report."""


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


class AgreementRow(BaseModel):
    """One catalogue case in the agreement report (from the cache of readings only)."""

    id: str
    category: str
    read: bool
    title: str = ""
    zus: Outcome | None = None
    ours: Outcome | None = None
    match: bool | None = None
    reason: DifferenceReason | None = None
    reason_text: str = ""
    covered: bool | None = None
    timeline: bool = False
    payments: int = 0
    problem: str | None = None


class AgreementReport(BaseModel):
    """How often the calculator agrees with the decisions of ZUS ("zgodność z decyzjami ZUS:
    X/86"), computed from the cases already read; nothing is read here."""

    configured: bool
    """CASES_DIR is set and exists."""
    total: int
    read: int
    decided: int
    """Cases where both the calculator and ZUS have an answer."""
    agree: int
    zus: dict[Outcome, int]
    """The decisions of ZUS among the cases read."""
    reasons: dict[DifferenceReason, int]
    """The differences by reason."""
    with_timeline: int
    with_amounts: int
    rows: list[AgreementRow]


class AssessRequest(BaseModel):
    id: str | None = None
    pages: int = 0
    pages_read: int = 0
    facts: CaseFacts


class ApplyRequest(BaseModel):
    scenario: Scenario


__all__ = [
    "AgreementReport",
    "AgreementRow",
    "AssessRequest",
    "ApplyRequest",
    "Bonus",
    "CaseDocument",
    "CaseJobLoss",
    "CaseMotherEvent",
    "ContributionDebt",
    "CaseFacts",
    "CaseList",
    "CaseListItem",
    "CaseResult",
    "Comparison",
    "Decision",
    "InsuranceCheck",
    "InsurancePeriod",
    "LeavePeriod",
    "PayDetails",
    "PayMonth",
]
