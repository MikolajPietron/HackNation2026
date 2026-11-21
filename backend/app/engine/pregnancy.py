"""Pregnancy: sick leave, losing the job, and the risks to the right to benefits.

The guide's chapter "Zasiłek chorobowy dla kobiety w ciąży" (pages 2-4) with its "Szczególna
sytuacja – zasiłek w wysokości zasiłku macierzyńskiego" (page 4), section H (pages 9-10), and the
Labour Code art. 92. Applied after the mother's and the father's rules (timeline.py).

- Sick leave in pregnancy (e-ZLA, code "B"): the right to the sickness benefit arises, as a rule,
  after 30 days of uninterrupted obligatory insurance (employment) or after 90 days of voluntary
  insurance (contract, business). An employee gets her pay from the employer (wynagrodzenie
  chorobowe, 100% in pregnancy) for the first 33 days of incapacity in a calendar year (14 after
  the year in which she turned 50), then the sickness benefit; a woman who is not an employee
  gets the benefit from the first day. 100% with code "B", at most 270 days (okres zasiłkowy).
  When the incapacity lasts until the birth, maternity leave follows it. Without sickness
  insurance there is no benefit.
- Losing the job in pregnancy through the employer's bankruptcy, liquidation or death (and no
  other employment offered), or through a termination that broke the law, confirmed by a final
  court judgment: a benefit equal to the maternity benefit, 100%, paid until the birth after the
  insurance has ended.
- Any other end of work before the birth: no sickness insurance on the day of the birth
  (insurance.py), so no maternity benefit (section H, risk 3).
- Section H, risks 1 and 2 (a contract or business "dla pozoru", raising the contribution base
  in pregnancy): notes, only when the parent said so.
- The rehabilitation benefit (świadczenie rehabilitacyjne; guide page 1, ustawa art. 18-19, 22):
  when the sick leave outlasts the 270 days, the incapacity may go on with this benefit if
  further treatment or medical rehabilitation promises the recovery of the ability to work; the
  ZUS medical examiner rules on it; at most 12 months of 30 days; 100% of the sickness benefit
  base when the incapacity falls in pregnancy. A note explains it; a period is drawn only when
  the parent said it was applied for or granted (never asked).

Our readings, not settled by the guide (CLAUDE.md, open questions):
- the 30 (90) days count from the first day of insurance, so the right begins on that day + 30;
- the employer's 33 (14) days count only days of this sick leave with the right to the benefit,
  afresh in each calendar year; 14 apply to the whole leave when the mother turned 50 before the
  calendar year in which it began;
- the 270 days count every day of this sick leave with pay or benefit (the employer's days too);
- sick leave without an end runs until the day before the birth; when maternity leave before the
  birth starts earlier, the sick leave ends the day before it;
- the benefit after losing the job runs from the day after the last day of work until the day
  before the birth; from the birth the timeline shows the maternity benefit;
- the rehabilitation benefit runs from the day after the 270 days to the last day of the sick
  leave we count (the day before the birth or the leave before it, or the last day of work);
  from the birth the timeline shows the maternity benefit: how the two meet, the materials do
  not say.
"""

import datetime as dt
from dataclasses import dataclass
from typing import Literal

from app.engine.draft import DAY, Draft, days_between, merge_sources
from app.engine.insurance import NOT_INSURED, coverage, work_coverage
from app.engine.models import (
    CaseNote,
    JobLossReason,
    Marker,
    Scenario,
    ScenarioError,
    Segment,
    Timeline,
)
from app.engine.params import Params
from app.engine.wording import fmt, long_date

PayKind = Literal["employer", "benefit"]

EMPLOYER_GONE: frozenset[JobLossReason] = frozenset({"bankruptcy", "liquidation", "employer-death"})
LOSS_REASON = {
    "bankruptcy": "upadłości pracodawcy",
    "liquidation": "likwidacji pracodawcy",
    "employer-death": "śmierci pracodawcy",
    "unlawful": "rozwiązania umowy o pracę z naruszeniem przepisów prawa",
}
"""After "z powodu"."""

SEGMENT_IDS = {"employer": "sick-pay", "benefit": "sick-benefit"}
PAY_NAME = {"employer": "wynagrodzenie od pracodawcy", "benefit": "zasiłek chorobowy"}
JOB_LOSS_SEGMENT = "job-loss-benefit"
REHAB_SEGMENT = "rehab-benefit"


@dataclass(frozen=True)
class Piece:
    """Days of sick leave with one payer: the employer, or the sickness benefit."""

    kind: PayKind
    start: dt.date
    end: dt.date


@dataclass(frozen=True)
class SickLeave:
    start: dt.date
    end: dt.date
    """The last day we count: the end given, the day before the birth, the day before maternity
    leave before the birth, or the last day of work."""
    open_end: bool
    """No end was given: we count until the day before the birth."""
    until_birth: bool
    """The incapacity lasts until the birth."""
    leave_from: dt.date | None
    """Maternity leave before the birth starts on this day and ends the sick leave."""
    work_ended: dt.date | None
    """The mother's work ended on this day, during the sick leave or before it."""
    insured: bool
    """Covered by sickness insurance while working (not known = assumed so)."""
    employee: bool
    voluntary: bool
    right_from: dt.date | None
    """The first day with the right to the benefit, when the start of insurance is known."""
    employer_days: int
    pieces: tuple[Piece, ...]
    limit_day: dt.date | None
    """The last day of the 270 days, when the sick leave lasts longer."""


def sick_leave(scenario: Scenario, params: Params, birth: dt.date) -> SickLeave | None:
    """The mother's sick leave in pregnancy, split by who pays, or None if there is none."""
    start = scenario.sick_leave_start
    if not scenario.sick_leave or start is None:
        return None
    p = params.pregnancy
    last = birth - DAY
    given = scenario.sick_leave_end
    if start > last:
        raise ScenarioError(
            f"Zwolnienie lekarskie w ciąży musi zacząć się przed porodem ({fmt(birth)}). "
            "Sprawdź datę."
        )
    if given is not None and given < start:
        raise ScenarioError("Zwolnienie lekarskie nie może skończyć się przed swoim początkiem.")
    end = last if given is None else min(given, last)
    until_birth = end == last

    leave_from = _prenatal_start(scenario, birth)
    if leave_from is not None and leave_from <= end:
        if leave_from <= start:
            raise ScenarioError(
                f"Zwolnienie lekarskie zaczyna się {fmt(start)}, już w czasie urlopu "
                f"macierzyńskiego przed porodem (od {fmt(leave_from)}). Sprawdź daty albo liczbę "
                "tygodni urlopu przed porodem."
            )
        end, until_birth = leave_from - DAY, False
    else:
        leave_from = None

    loss = scenario.job_loss
    work_ended = loss.ended_on if loss is not None and loss.ended_on < end else None
    paid_end = end if work_ended is None else work_ended

    cover = work_coverage(scenario.mothers_work, scenario.mother_insured)
    insured = cover not in NOT_INSURED
    employee = scenario.mothers_work in ("employment", None)
    voluntary = cover in ("voluntary", "unknown-voluntary")
    waiting = (p.waiting_days_voluntary if voluntary else p.waiting_days_obligatory).value
    right_from = (
        scenario.insured_since + waiting * DAY if scenario.insured_since is not None else None
    )
    employer_days = (p.employer_days_from_50 if scenario.mother_over_50 else p.employer_days).value

    pieces: list[Piece] = []
    limit_day = None
    if insured:
        day = start if right_from is None else max(start, right_from)
        counted = 0
        per_year: dict[int, int] = {}
        while day <= paid_end:
            if counted == p.max_days.value:
                limit_day = day - DAY
                break
            kind: PayKind = "benefit"
            if employee and per_year.get(day.year, 0) < employer_days:
                kind = "employer"
                per_year[day.year] = per_year.get(day.year, 0) + 1
            if pieces and pieces[-1].kind == kind and pieces[-1].end == day - DAY:
                pieces[-1] = Piece(kind, pieces[-1].start, day)
            else:
                pieces.append(Piece(kind, day, day))
            counted += 1
            day += DAY
    return SickLeave(
        start=start,
        end=end,
        open_end=given is None,
        until_birth=until_birth,
        leave_from=leave_from,
        work_ended=work_ended,
        insured=insured,
        employee=employee,
        voluntary=voluntary,
        right_from=right_from,
        employer_days=employer_days,
        pieces=tuple(pieces),
        limit_day=limit_day,
    )


def employer_days_by_year(sick: SickLeave) -> dict[int, int]:
    """Days the employer pays in each calendar year. For the interview: the mother's age
    matters only when they run past the shorter limit."""
    days: dict[int, int] = {}
    for piece in sick.pieces:
        if piece.kind == "employer":
            year = piece.start.year
            days[year] = days.get(year, 0) + days_between(piece.start, piece.end)
    return days


def _prenatal_start(scenario: Scenario, birth: dt.date) -> dt.date | None:
    """The first day of maternity leave before the birth, if the mother takes (took) it."""
    if scenario.child_born:
        days = scenario.prenatal_days(birth)
        return birth - days * DAY if days else None
    weeks = scenario.leave_before_birth_weeks
    return birth - weeks * 7 * DAY if weeks else None


def pregnancy_rules(draft: Draft, scenario: Scenario, params: Params, birth: dt.date) -> list[str]:
    """Draw the sick leave and the benefit after losing the job; return our assumptions."""
    sick = sick_leave(scenario, params, birth)
    job = _job_loss_segment(scenario, params, birth)
    busy: list[tuple[dt.date, dt.date]] = []
    mine: list[Segment] = []
    rehab = None
    if sick is not None:
        busy.append((sick.start, sick.end))
        mine += _sick_segments(sick, scenario, params)
        rehab = _rehab_segment(sick, scenario, params)
        if rehab is not None:
            mine.append(rehab)
        draft.markers += _sick_markers(sick, params)
    if job is not None:
        busy.append((job.start, job.end))
        mine.append(job)
    _trim_work(draft, busy)
    draft.segments[0:0] = mine
    return _assumptions(scenario, sick, job) + _rehab_assumptions(scenario, rehab)


def _sick_segments(sick: SickLeave, scenario: Scenario, params: Params) -> list[Segment]:
    p = params.pregnancy
    born = scenario.child_born is True
    segments = []
    seen: dict[PayKind, int] = {}
    for index, piece in enumerate(sick.pieces):
        seen[piece.kind] = seen.get(piece.kind, 0) + 1
        segment_id = SEGMENT_IDS[piece.kind] + (
            f"-{seen[piece.kind]}" if seen[piece.kind] > 1 else ""
        )
        days = days_between(piece.start, piece.end)
        last = index == len(sick.pieces) - 1
        details = []
        if piece.kind == "employer":
            limit = p.employer_days_from_50 if scenario.mother_over_50 else p.employer_days
            title = "Zwolnienie lekarskie w ciąży: wynagrodzenie chorobowe"
            summary = (
                f"Pracodawca wypłaca mamie wynagrodzenie chorobowe za pierwsze {limit.value} dni "
                f"niezdolności do pracy w roku kalendarzowym; w ciąży to 100% wynagrodzenia. "
                f"Tu: {days} {_days(days)} w roku {piece.start.year}."
            )
            sources = merge_sources(
                limit.sources, p.employer_pay_in_pregnancy.sources, p.e_zla.sources
            )
        else:
            title = "Zwolnienie lekarskie w ciąży: zasiłek chorobowy"
            rate = p.rate_percent.value
            if sick.employee:
                summary = (
                    f"Od kolejnego dnia po dniach płaconych przez pracodawcę mama dostaje zasiłek "
                    f"chorobowy: {rate}% podstawy wymiaru zasiłku, bo zaświadczenie lekarskie ma "
                    "kod „B” (ciąża)."
                )
                who = p.benefit_after_employer.sources
            elif piece.start > sick.start:
                summary = (
                    f"Od {fmt(piece.start)}, gdy powstało prawo do zasiłku, mama dostaje zasiłek "
                    f"chorobowy: {rate}% podstawy wymiaru zasiłku, bo zaświadczenie lekarskie ma "
                    "kod „B” (ciąża). Nie jest pracownicą, więc nie ma dni płaconych przez "
                    "pracodawcę."
                )
                who = p.non_employee_from_day_one.sources
            else:
                summary = (
                    "Mama nie jest pracownicą, więc zasiłek chorobowy dostaje od pierwszego dnia "
                    f"niezdolności do pracy: {rate}% podstawy wymiaru zasiłku, bo zaświadczenie "
                    "lekarskie ma kod „B” (ciąża)."
                )
                who = p.non_employee_from_day_one.sources
            details.append(
                "Zasiłek wypłaca ZUS albo uprawniony płatnik składek, z Funduszu Ubezpieczeń "
                "Społecznych."
            )
            details.append(
                "Przysługuje za okres niezdolności do pracy wskazany w zaświadczeniu e-ZLA, "
                f"najwyżej przez {p.max_days.value} dni (okres zasiłkowy)."
            )
            sources = merge_sources(
                p.sick_benefit.sources,
                who,
                p.rate_percent.sources,
                p.period.sources,
                p.max_days.sources,
            )
        details.append(
            "Zaświadczenie lekarskie e-ZLA trafia samo do ZUS"
            + (" i do pracodawcy." if sick.employee else ".")
        )
        if last and sick.until_birth and sick.work_ended is None:
            details.append(
                "Niezdolność do pracy trwa do porodu, więc po porodzie zaczyna się urlop "
                "macierzyński (okres zasiłku macierzyńskiego)."
            )
            sources = merge_sources(sources, p.until_birth.sources)
            if not born:
                details.append("Liczymy do przewidywanej daty porodu.")
        if last and sick.leave_from is not None:
            details.append(
                f"Od {fmt(sick.leave_from)} mama jest na urlopie macierzyńskim przed porodem, "
                "więc zwolnienie liczymy do dnia wcześniej."
            )
        segments.append(
            Segment(
                id=segment_id,
                lane="mother",
                tone="leave",
                title=title,
                start=piece.start,
                end=piece.end,
                days=days,
                summary=summary,
                details=details,
                sources=merge_sources(sources, p.e_zla.sources),
            )
        )
    return segments


def _sick_markers(sick: SickLeave, params: Params) -> list[Marker]:
    p = params.pregnancy
    markers = []
    right = sick.right_from
    if right is not None and sick.start < right <= (sick.work_ended or sick.end) and sick.insured:
        waiting = p.waiting_days_voluntary if sick.voluntary else p.waiting_days_obligatory
        since = right - waiting.value * DAY
        details = ["Za wcześniejsze dni zwolnienia zasiłek chorobowy co do zasady nie przysługuje."]
        sources = waiting.sources
        if sick.employee:
            details.append(
                "Pracodawca nie wypłaca za nie wynagrodzenia chorobowego: nie przysługuje ono, "
                "gdy pracownik nie ma prawa do zasiłku chorobowego."
            )
            sources = merge_sources(sources, p.no_pay_without_right.sources)
        markers.append(
            Marker(
                id="sick-benefit-right",
                lane="child",
                label="Prawo do zasiłku",
                title="Prawo do zasiłku chorobowego",
                date=right,
                summary=(
                    f"Prawo do zasiłku chorobowego powstaje co do zasady po {waiting.value} dniach "
                    + ("" if sick.voluntary else "nieprzerwanego ")
                    + f"ubezpieczenia; mama jest ubezpieczona od {fmt(since)}."
                ),
                details=details,
                sources=sources,
            )
        )
    if sick.limit_day is not None:
        markers.append(
            Marker(
                id="sick-benefit-limit",
                lane="child",
                label=f"{p.max_days.value} dni",
                title="Koniec okresu zasiłkowego",
                date=sick.limit_day,
                summary=(
                    f"Zasiłek chorobowy przysługuje najwyżej przez {p.max_days.value} dni (okres "
                    "zasiłkowy). Za dalsze dni zwolnienia już nie przysługuje."
                ),
                details=[f"Potem przysługuje świadczenie rehabilitacyjne, jeśli {REHAB_IF}."],
                sources=merge_sources(p.max_days.sources, p.rehab_benefit.sources),
            )
        )
    return markers


# The rehabilitation benefit after the 270 days (ustawa art. 18-19, 22).

REHAB_IF = (
    "po wyczerpaniu zasiłku chorobowego mama jest nadal niezdolna do pracy, a dalsze leczenie "
    "lub rehabilitacja lecznicza rokują odzyskanie zdolności do pracy"
)
"""The conditions of art. 18 ust. 1, after "jeśli"."""
REHAB_DECIDES = (
    "O tych warunkach i o tym, na jak długo, orzeka lekarz orzecznik ZUS; jego orzeczenie jest "
    "podstawą decyzji w sprawie świadczenia."
)


def rehab_period(
    sick: SickLeave, scenario: Scenario, params: Params
) -> tuple[dt.date, dt.date] | None:
    """The days the rehabilitation benefit can cover: from the day after the 270 days to the
    last day of the sick leave we count (or of work), at most 12 months of 30 days, and not
    after the end the parent gave. None when the sick leave does not outlast the 270 days."""
    if sick.limit_day is None:
        return None
    p = params.pregnancy
    start = sick.limit_day + DAY
    end = sick.work_ended if sick.work_ended is not None else sick.end
    longest = p.rehab_max_months.value * p.rehab_month_days.value
    end = min(end, start + (longest - 1) * DAY)
    given = scenario.rehab_benefit_end
    if given is not None and scenario.rehab_benefit in ("applied", "granted"):
        if given < start:
            raise ScenarioError(
                "Świadczenie rehabilitacyjne przysługuje po wyczerpaniu zasiłku chorobowego, czyli "
                f"od {fmt(start)}. Sprawdź datę jego końca."
            )
        end = min(end, given)
    return start, end


def _rehab_segment(sick: SickLeave, scenario: Scenario, params: Params) -> Segment | None:
    """Drawn only when the parent said it was applied for (an option) or granted."""
    status = scenario.rehab_benefit
    period = rehab_period(sick, scenario, params)
    if period is None or status not in ("applied", "granted"):
        return None
    p = params.pregnancy
    start, end = period
    pay = (
        f"{p.rehab_rate_percent.value}% podstawy wymiaru zasiłku chorobowego, bo niezdolność do "
        "pracy przypada w ciąży"
    )
    if status == "granted":
        summary = f"Po wyczerpaniu zasiłku chorobowego mama ma świadczenie rehabilitacyjne: {pay}."
    else:
        summary = (
            f"Mama ubiega się o świadczenie rehabilitacyjne. Przysługuje, jeśli {REHAB_IF}; "
            f"wynosi wtedy {pay}."
        )
    details = [
        "Przysługuje przez okres niezbędny do przywrócenia zdolności do pracy, nie dłużej niż "
        f"{p.rehab_max_months.value} miesięcy.",
        REHAB_DECIDES,
    ]
    if end == scenario.rehab_benefit_end:
        details.append(f"Pokazujemy je do {fmt(end)}: taki koniec podano.")
    elif end == sick.work_ended:
        details.append(
            f"Praca ustała {fmt(end)}. Świadczenia po ustaniu ubezpieczenia ten etap aplikacji "
            "jeszcze nie pokazuje."
        )
    elif end == sick.end and sick.leave_from is not None:
        details.append(
            f"Od {fmt(sick.leave_from)} mama jest na urlopie macierzyńskim przed porodem, więc "
            "liczymy do dnia wcześniej."
        )
    elif end == sick.end and sick.until_birth:
        details.append(
            "Od dnia porodu oś pokazuje urlop macierzyński, więc liczymy do dnia przed "
            + ("porodem." if scenario.child_born else "przewidywaną datą porodu.")
        )
    return Segment(
        id=REHAB_SEGMENT,
        lane="mother",
        tone="leave" if status == "granted" else "option",
        title="Świadczenie rehabilitacyjne"
        + ("" if status == "granted" else " — jeśli zostanie przyznane"),
        start=start,
        end=end,
        days=days_between(start, end),
        summary=summary,
        details=details,
        sources=merge_sources(
            p.rehab_benefit.sources,
            p.rehab_rate_percent.sources,
            p.rehab_max_months.sources,
            p.rehab_decides.sources,
        ),
    )


def _rehab_assumptions(scenario: Scenario, rehab: Segment | None) -> list[str]:
    if rehab is not None:
        return [
            "Świadczenie rehabilitacyjne pokazujemy od dnia po okresie zasiłkowym do końca "
            "zwolnienia lekarskiego, najpóźniej do dnia przed porodem: od dnia porodu oś pokazuje "
            "urlop macierzyński. Jak te świadczenia się łączą, materiały nie mówią."
        ]
    if scenario.rehab_benefit in ("applied", "granted"):
        return [
            "Świadczenie rehabilitacyjne przysługuje dopiero po wyczerpaniu zasiłku chorobowego, "
            "a podane zwolnienie lekarskie go nie wyczerpuje, więc go nie pokazujemy."
        ]
    return []


def _job_loss_segment(scenario: Scenario, params: Params, birth: dt.date) -> Segment | None:
    """Guide page 4: a benefit equal to the maternity benefit until the birth."""
    loss = scenario.job_loss
    if loss is None:
        return None
    if loss.ended_on >= birth:
        raise ScenarioError(
            f"Tu liczy się utrata pracy w czasie ciąży, przed porodem ({fmt(birth)}). Sprawdź datę."
        )
    if loss.reason == "other":
        return None
    if scenario.mothers_work not in ("employment", None):
        raise ScenarioError(
            "Zasiłek w wysokości zasiłku macierzyńskiego dotyczy rozwiązania umowy o pracę. "
            "Sprawdź, jak pracowała mama."
        )
    start, end = loss.ended_on + DAY, birth - DAY
    if start > end:
        return None
    p = params.pregnancy
    confirmed = loss.reason != "unlawful" or loss.court_confirmed is True
    reason = LOSS_REASON[loss.reason]
    rate = p.job_loss_rate_percent.value
    if confirmed:
        summary = (
            f"Mama straciła pracę w ciąży z powodu {reason}. Do dnia porodu przysługuje jej "
            f"zasiłek w wysokości zasiłku macierzyńskiego: {rate}% podstawy wymiaru zasiłku."
        )
    else:
        summary = (
            f"Mama straciła pracę w ciąży z powodu {reason}. Zasiłek w wysokości zasiłku "
            f"macierzyńskiego ({rate}% podstawy wymiaru zasiłku, do dnia porodu) przysługuje, "
            "gdy naruszenie prawa potwierdzi prawomocny wyrok sądu."
        )
    details = []
    if loss.reason in EMPLOYER_GONE:
        details.append("Warunek: nie zapewniono jej innego zatrudnienia.")
    details.append(
        f"Zasiłek wypłaca się po ustaniu ubezpieczenia: od {fmt(start)}, dnia po ustaniu "
        "zatrudnienia, do dnia porodu."
    )
    if not scenario.child_born:
        details.append("Liczymy do przewidywanej daty porodu.")
    return Segment(
        id=JOB_LOSS_SEGMENT,
        lane="mother",
        tone="leave" if confirmed else "option",
        title="Zasiłek w wysokości zasiłku macierzyńskiego"
        + ("" if confirmed else " — po wyroku sądu"),
        start=start,
        end=end,
        days=days_between(start, end),
        summary=summary,
        details=details,
        sources=merge_sources(
            p.job_loss_benefit.sources,
            (
                p.job_loss_employer_gone if loss.reason in EMPLOYER_GONE else p.job_loss_unlawful
            ).sources,
            p.job_loss_rate_percent.sources,
        ),
    )


def _trim_work(draft: Draft, busy: list[tuple[dt.date, dt.date]]) -> None:
    """ "Work until the birth" does not cover days of sick leave or after the job ended."""
    work = draft.segment("work-until-birth")
    if work is None or not busy:
        return
    first = min(start for start, _ in busy)
    if first > work.end:
        return
    if first <= work.start:
        draft.replace(work.id)
        return
    end = first - DAY
    draft.replace(
        work.id, work.model_copy(update={"end": end, "days": days_between(work.start, end)})
    )


def _assumptions(scenario: Scenario, sick: SickLeave | None, job: Segment | None) -> list[str]:
    assumptions = []
    if sick is not None and sick.insured:
        assumptions.append(
            "Zwolnienie lekarskie w ciąży liczymy samo: wcześniejszych dni choroby w tym samym "
            "roku nie uwzględniamy."
        )
        if scenario.mothers_work is None:
            assumptions.append(
                "Na razie zakładamy, że mama pracuje na umowie o pracę: od tego zależy, kto płaci "
                "za zwolnienie."
            )
        if sick.employee:
            assumptions.append(
                f"{sick.employer_days} dni wynagrodzenia chorobowego liczymy osobno w każdym "
                "roku kalendarzowym, od dnia, w którym powstało prawo do zasiłku. Do okresu "
                "zasiłkowego wliczamy też dni wynagrodzenia chorobowego."
            )
        if scenario.mother_over_50:
            assumptions.append(
                "Krótszy limit wynagrodzenia chorobowego stosujemy do całego zwolnienia: mama "
                "skończyła 50 lat przed rokiem, w którym zwolnienie się zaczęło."
            )
        if sick.right_from is None:
            assumptions.append(
                "Zakładamy, że prawo do zasiłku chorobowego mama miała już w pierwszym dniu "
                "zwolnienia: ubezpieczenie trwało wystarczająco długo."
            )
        else:
            assumptions.append(
                "Dni ubezpieczenia liczymy od podanego dnia jego początku; prawo do zasiłku "
                "powstaje następnego dnia po ich upływie. Przewodnik mówi „co do zasady”: "
                "wyjątków ten etap aplikacji nie obejmuje."
            )
        if sick.open_end:
            assumptions.append(
                "Zwolnienie bez podanej daty końca liczymy do dnia przed "
                + ("porodem." if scenario.child_born else "przewidywaną datą porodu.")
            )
    if job is not None:
        assumptions.append(
            "Zasiłek w wysokości zasiłku macierzyńskiego pokazujemy od dnia po ustaniu "
            "zatrudnienia do dnia przed porodem; od dnia porodu liczymy zasiłek macierzyński."
        )
        if sick is not None and sick.work_ended is not None:
            assumptions.append(
                "Za dni zwolnienia lekarskiego po ustaniu zatrudnienia pokazujemy zasiłek "
                "w wysokości zasiłku macierzyńskiego. Jak te świadczenia się łączą, Przewodnik "
                "nie mówi."
            )
    return assumptions


def _days(count: int) -> str:
    return "dzień" if count == 1 else "dni"


# The case explanation (explain.py calls this right after the mother's insurance).


def pregnancy_notes(scenario: Scenario, timeline: Timeline, params: Params) -> list[CaseNote]:
    """What sick leave, the loss of the job and the risks of section H mean for the family."""
    notes = []
    sick = sick_leave(scenario, params, timeline.birth_date)
    if sick is not None:
        notes.append(_sick_note(scenario, timeline, params, sick))
        rehab = _rehab_note(scenario, timeline, params, sick)
        if rehab is not None:
            notes.append(rehab)
    if scenario.job_loss is not None:
        notes.append(_job_loss_note(scenario, timeline, params))
    p = params.pregnancy
    if scenario.insured_in_pregnancy:
        notes.append(
            CaseNote(
                id="risk-sham",
                kind="risk",
                title="Umowa albo działalność zaczęta w ciąży",
                text=(
                    "Umowa albo działalność zaczęła się w czasie ciąży. ZUS może po postępowaniu "
                    "uznać, że zawarto ją dla pozoru, tylko po to, by zgłosić się do ubezpieczenia "
                    "chorobowego i dostać zasiłki. Wtedy wydaje decyzję o niepodleganiu "
                    "ubezpieczeniom społecznym, a kto nie podlega ubezpieczeniu chorobowemu, nie "
                    "ma prawa do zasiłków."
                ),
                sources=p.risk_sham.sources,
            )
        )
    if scenario.contribution_base_raised:
        notes.append(
            CaseNote(
                id="risk-base",
                kind="risk",
                title="Podwyższenie podstawy składek w ciąży",
                text=(
                    "Podstawa wymiaru składek wzrosła w czasie ciąży. Jeśli ZUS po postępowaniu "
                    "uzna, że chodziło wyłącznie o wyższe zasiłki, może ustalić niższą podstawę, "
                    "a to obniży zasiłki."
                ),
                sources=p.risk_base_raised.sources,
            )
        )
    return notes


def _sick_note(scenario: Scenario, timeline: Timeline, params: Params, sick: SickLeave) -> CaseNote:
    p = params.pregnancy
    b = params.benefit
    if not sick.insured:
        if scenario.mothers_work == "none":
            why = "Z odpowiedzi wynika, że mama nie pracuje, więc nie ma tego ubezpieczenia"
            sources = merge_sources(p.insured_needed.sources)
        else:
            why = (
                "Przy umowie zlecenia i działalności gospodarczej ubezpieczenie chorobowe jest "
                "dobrowolne, a mama nie jest do niego zgłoszona"
            )
            sources = merge_sources(p.insured_needed.sources, b.voluntary_insurance.sources)
        return CaseNote(
            id="sick-leave",
            kind="risk",
            title="Zasiłek chorobowy wymaga ubezpieczenia chorobowego",
            text=(
                "Aby dostać zasiłek chorobowy za zwolnienie lekarskie, kobieta w ciąży musi "
                f"podlegać ubezpieczeniu chorobowemu. {why}, dlatego zasiłek chorobowy jej nie "
                "przysługuje."
            ),
            sources=sources,
        )

    waiting = p.waiting_days_voluntary if sick.voluntary else p.waiting_days_obligatory
    rate = p.rate_percent.value
    if sick.employee:
        rule = (
            "Na zwolnieniu lekarskim w ciąży pracodawca wypłaca mamie wynagrodzenie chorobowe "
            f"(100% wynagrodzenia) przez pierwsze {sick.employer_days} dni niezdolności do pracy "
            "w roku kalendarzowym. Od kolejnego dnia dostaje zasiłek chorobowy: "
            f"{rate}% podstawy wymiaru, bo zaświadczenie e-ZLA w ciąży ma kod „B”."
        )
        limit = p.employer_days_from_50 if scenario.mother_over_50 else p.employer_days
        sources = [
            *limit.sources,
            *p.employer_pay_in_pregnancy.sources,
            *p.benefit_after_employer.sources,
        ]
    else:
        rule = (
            "Mama nie jest pracownicą, więc na zwolnieniu lekarskim w ciąży zasiłek chorobowy "
            f"wypłaca się od pierwszego dnia niezdolności do pracy: {rate}% podstawy wymiaru, bo "
            "zaświadczenie e-ZLA w ciąży ma kod „B”."
        )
        sources = list(p.non_employee_from_day_one.sources)
    sources += [*p.e_zla.sources, *p.rate_percent.sources, *p.max_days.sources]
    parts = [rule, f"Zasiłek przysługuje najwyżej przez {p.max_days.value} dni."]

    pieces = [
        s
        for s in timeline.segments
        if s.id.startswith(SEGMENT_IDS["employer"]) or s.id.startswith(SEGMENT_IDS["benefit"])
    ]
    if pieces:
        listed = "; ".join(
            f"{PAY_NAME['employer' if s.id.startswith('sick-pay') else 'benefit']}"
            f" od {long_date(s.start)} do {long_date(s.end)} ({s.days} {_days(s.days)})"
            for s in pieces
        )
        parts.append(f"Policzyliśmy: {listed}.")
    if sick.right_from is not None and sick.right_from > sick.start:
        continuous = "" if sick.voluntary else "nieprzerwanego "
        unpaid = (
            ", a pracodawca nie płaci za nie wynagrodzenia chorobowego" if sick.employee else ""
        )
        right = (
            f"Prawo do zasiłku powstaje co do zasady po {waiting.value} dniach {continuous}"
            f"ubezpieczenia, czyli od {long_date(sick.right_from)}."
        )
        if pieces:
            parts.append(
                f"{right.replace('powstaje co', 'powstaje jednak co')} Za wcześniejsze dni "
                f"zwolnienia zasiłek nie przysługuje{unpaid}."
            )
        else:
            parts = [
                f"{right} Zwolnienie lekarskie kończy się wcześniej, więc za jego dni zasiłek "
                f"chorobowy nie przysługuje{unpaid}."
            ]
            sources = []
        sources += waiting.sources
        if sick.employee:
            sources += p.no_pay_without_right.sources
    if sick.limit_day is not None:
        parts.append(
            f"Okres zasiłkowy kończy się {long_date(sick.limit_day)}; za dalsze dni zwolnienia "
            "zasiłek już nie przysługuje."
        )
    if sick.leave_from is not None:
        parts.append(
            f"Od {long_date(sick.leave_from)} mama jest na urlopie macierzyńskim przed porodem, "
            "więc zwolnienie liczymy do dnia wcześniej."
        )
    if sick.work_ended is not None:
        loss = scenario.job_loss
        if loss is not None and loss.reason != "other":
            parts.append(
                f"Zatrudnienie ustało {long_date(sick.work_ended)}; od następnego dnia oś "
                "pokazuje zasiłek w wysokości zasiłku macierzyńskiego."
            )
        else:
            parts.append(
                f"Praca ustała {long_date(sick.work_ended)}. Zasiłek chorobowy przysługuje "
                "w określonych sytuacjach również po ustaniu ubezpieczenia; tych sytuacji ten "
                "etap aplikacji jeszcze nie obejmuje."
            )
            sources += p.sick_benefit.sources
    elif sick.until_birth and coverage(scenario) not in NOT_INSURED:
        parts.append(
            "Jeśli niezdolność do pracy trwa do porodu, po porodzie zaczyna się urlop "
            "macierzyński (okres zasiłku macierzyńskiego)."
        )
        sources += p.until_birth.sources
    if pieces:
        title = (
            "Zwolnienie lekarskie w ciąży: wynagrodzenie i zasiłek chorobowy"
            if sick.employee
            else "Zwolnienie lekarskie w ciąży: zasiłek chorobowy"
        )
    elif sick.work_ended is not None and sick.work_ended < sick.start:
        title = "Zwolnienie lekarskie po ustaniu pracy"
    else:
        title = "Zwolnienie lekarskie przed prawem do zasiłku"
    return CaseNote(
        id="sick-leave",
        kind="right" if pieces else "risk",
        title=title,
        text=" ".join(parts),
        sources=merge_sources(sources),
    )


def _rehab_note(
    scenario: Scenario, timeline: Timeline, params: Params, sick: SickLeave
) -> CaseNote | None:
    """After the 270 days: the rehabilitation benefit, its conditions and who rules on them."""
    period = rehab_period(sick, scenario, params)
    if period is None or sick.limit_day is None:
        return None
    p = params.pregnancy
    limit = long_date(sick.limit_day)
    rule = f"Jeśli {REHAB_IF}, przysługuje jej świadczenie rehabilitacyjne"
    length = (
        "przez okres niezbędny do przywrócenia zdolności do pracy, nie dłużej niż "
        f"{p.rehab_max_months.value} miesięcy"
    )
    pay = (
        f"Gdy niezdolność do pracy przypada w ciąży, wynosi {p.rehab_rate_percent.value}% "
        "podstawy wymiaru zasiłku chorobowego."
    )
    segment = next((s for s in timeline.segments if s.id == REHAB_SEGMENT), None)
    shown = (
        f" od {long_date(segment.start)} do {long_date(segment.end)}" if segment is not None else ""
    )
    match scenario.rehab_benefit:
        case "refused":
            return CaseNote(
                id="rehab-benefit",
                kind="risk",
                title="Świadczenia rehabilitacyjnego nie przyznano",
                text=(
                    f"Po {limit} zasiłek chorobowy już nie przysługuje, a świadczenia "
                    "rehabilitacyjnego nie przyznano. Przysługuje ono, gdy dalsze leczenie lub "
                    "rehabilitacja lecznicza rokują odzyskanie zdolności do pracy; orzeka o tym "
                    "lekarz orzecznik ZUS. Od jego orzeczenia przysługuje sprzeciw do komisji "
                    "lekarskiej ZUS."
                ),
                sources=merge_sources(
                    p.rehab_benefit.sources, p.rehab_decides.sources, p.rehab_objection.sources
                ),
            )
        case "granted":
            title = "Świadczenie rehabilitacyjne po zasiłku chorobowym"
            text = (
                f"Okres zasiłkowy kończy się {limit}, a po nim mama ma świadczenie "
                f"rehabilitacyjne{shown}. {pay} Przysługuje {length}."
            )
        case "applied":
            title = "Świadczenie rehabilitacyjne: wniosek złożony"
            text = (
                f"Okres zasiłkowy kończy się {limit}. {rule} {length}. {pay} {REHAB_DECIDES} "
                f"Na osi pokazujemy je jako możliwe{shown}."
            )
        case _:
            title = "Po okresie zasiłkowym: świadczenie rehabilitacyjne"
            text = (
                f"Okres zasiłkowy kończy się {limit}, a zwolnienie trwa dłużej. {rule} "
                f"{length}. {pay} {REHAB_DECIDES}"
            )
    return CaseNote(
        id="rehab-benefit",
        kind="right",
        title=title,
        text=text,
        sources=merge_sources(
            p.rehab_benefit.sources,
            p.rehab_max_months.sources,
            p.rehab_rate_percent.sources,
            p.rehab_decides.sources,
        ),
    )


def _job_loss_note(scenario: Scenario, timeline: Timeline, params: Params) -> CaseNote:
    loss = scenario.job_loss
    assert loss is not None
    p = params.pregnancy
    b = params.benefit
    born = timeline.child_born
    if loss.reason == "other":
        state = (
            "więc w dniu porodu nie podlegała ubezpieczeniu chorobowemu, a bez niego zasiłek "
            "macierzyński nie przysługuje"
            if born
            else "a liczy się dzień porodu: jeśli mama nie będzie wtedy podlegać ubezpieczeniu "
            "chorobowemu, zasiłek macierzyński nie będzie jej przysługiwał"
        )
        return CaseNote(
            id="job-loss",
            kind="risk",
            title="Koniec pracy przed porodem",
            text=(
                f"Praca mamy skończyła się {long_date(loss.ended_on)}, przed porodem, {state}. "
                "Zasiłek w wysokości zasiłku macierzyńskiego do dnia porodu przysługuje tylko "
                "wtedy, gdy umowę o pracę rozwiązano z powodu upadłości, likwidacji albo śmierci "
                "pracodawcy albo z naruszeniem przepisów prawa, potwierdzonym prawomocnym wyrokiem "
                "sądu."
            ),
            sources=merge_sources(
                b.work_ended_before_birth.sources,
                b.insured_on_birth_day.sources,
                b.without_insurance.sources,
                p.job_loss_employer_gone.sources,
                p.job_loss_unlawful.sources,
            ),
        )
    segment = next((s for s in timeline.segments if s.id == JOB_LOSS_SEGMENT), None)
    reason = LOSS_REASON[loss.reason]
    confirmed = loss.reason != "unlawful" or loss.court_confirmed is True
    rate = p.job_loss_rate_percent.value
    parts = [f"Mama straciła pracę w ciąży z powodu {reason}."]
    if loss.reason in EMPLOYER_GONE:
        parts.append(
            "Jeśli nie zapewniono jej innego zatrudnienia, do dnia porodu przysługuje jej "
            f"zasiłek w wysokości zasiłku macierzyńskiego: {rate}% podstawy wymiaru, wypłacany "
            "po ustaniu ubezpieczenia."
        )
        rule = p.job_loss_employer_gone
    elif confirmed:
        parts.append(
            "Sąd potwierdził to prawomocnym wyrokiem, więc do dnia porodu przysługuje jej "
            f"zasiłek w wysokości zasiłku macierzyńskiego: {rate}% podstawy wymiaru, wypłacany "
            "po ustaniu ubezpieczenia."
        )
        rule = p.job_loss_unlawful
    else:
        parts.append(
            "Zasiłek w wysokości zasiłku macierzyńskiego do dnia porodu przysługuje wtedy, gdy "
            "naruszenie prawa potwierdzi prawomocny wyrok sądu."
        )
        rule = p.job_loss_unlawful
    if segment is not None:
        parts.append(
            f"Na osi: od {long_date(segment.start)} do {long_date(segment.end)}"
            + (", dnia przed porodem." if born else ", dnia przed przewidywaną datą porodu.")
        )
    parts.append(
        "Zasiłek macierzyński przysługuje w określonych sytuacjach również po ustaniu "
        "ubezpieczenia; po porodzie oś pokazuje go tak jak dotąd, a szczegóły tych sytuacji "
        "dodamy w kolejnym etapie."
    )
    return CaseNote(
        id="job-loss",
        kind="right",
        title="Zasiłek w wysokości zasiłku macierzyńskiego do porodu",
        text=" ".join(parts),
        sources=merge_sources(
            p.job_loss_benefit.sources,
            rule.sources,
            p.job_loss_rate_percent.sources,
            b.paid_to_the_insured.sources,
        ),
    )
