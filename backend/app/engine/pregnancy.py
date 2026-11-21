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
  (insurance.py), so no maternity benefit (section H, risk 3). Sick leave that goes on after
  such an end: the sickness benefit after the insurance ended (guide page 2: "w określonych
  sytuacjach również po ustaniu tego ubezpieczenia"; ustawa art. 8 ust. 2: in pregnancy without
  the 91-day cap), paid by ZUS (art. 61 ust. 1), not when the right was not acquired during the
  insurance (art. 13 ust. 1 pkt 3); incapacity that began after the end only when it began within
  14 days and lasted at least 30 (art. 7 pkt 1).
- Section H, risks 1 and 2 (a contract or business "dla pozoru", raising the contribution base
  in pregnancy): notes, only when the parent said so.

Our readings, not settled by the guide (CLAUDE.md, open questions):
- the 30 (90) days count from the first day of insurance, so the right begins on that day + 30;
- the employer's 33 (14) days count only days of this sick leave with the right to the benefit,
  afresh in each calendar year; 14 apply to the whole leave when the mother turned 50 before the
  calendar year in which it began;
- the 270 days count every day of this sick leave with pay or benefit (the employer's days too);
- sick leave without an end runs until the day before the birth; when maternity leave before the
  birth starts earlier, the sick leave ends the day before it;
- the benefit after losing the job runs from the day after the last day of work until the day
  before the birth; from the birth the timeline shows the maternity benefit (after_insurance.py);
- the sickness benefit after the insurance ended counts on in the same 270 days; the exclusions
  of art. 13 ust. 1 we cannot know (other work, unemployment benefit, a pension) are assumed not
  to apply.
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
    SourceRef,
    Timeline,
)
from app.engine.params import Params
from app.engine.wording import fmt, long_date

PayKind = Literal["employer", "benefit", "after"]
"""Who pays a day of sick leave: the employer (sick pay), the sickness benefit, or the sickness
benefit after the insurance ended (paid by ZUS)."""
AfterRefused = Literal["right", "late", "short"]
"""Why no sickness benefit after the insurance ended: the right was not acquired during the
insurance (art. 13 ust. 1 pkt 3); the incapacity began more than 14 days after the end, or
lasted less than 30 days (art. 7)."""

EMPLOYER_GONE: frozenset[JobLossReason] = frozenset({"bankruptcy", "liquidation", "employer-death"})
LOSS_REASON = {
    "bankruptcy": "upadłości pracodawcy",
    "liquidation": "likwidacji pracodawcy",
    "employer-death": "śmierci pracodawcy",
    "unlawful": "rozwiązania umowy o pracę z naruszeniem przepisów prawa",
}
"""After "z powodu"."""

SEGMENT_IDS = {"employer": "sick-pay", "benefit": "sick-benefit", "after": "sick-after-insurance"}
PAY_NAME = {
    "employer": "wynagrodzenie od pracodawcy",
    "benefit": "zasiłek chorobowy",
    "after": "zasiłek chorobowy po ustaniu ubezpieczenia",
}
JOB_LOSS_SEGMENT = "job-loss-benefit"


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
    after_refused: AfterRefused | None = None
    """The work ended (for no reason that gives the benefit equal to the maternity benefit) and
    there is no sickness benefit after it."""


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
    refused = None
    if insured and work_ended is not None and loss is not None and loss.reason == "other":
        # The sickness benefit after the insurance ended (guide page 2; ustawa art. 7, 8, 13).
        refused = _after_refused(start, end, work_ended, right_from, params)
        if refused is None:
            paid_end = end
    if insured:
        day = start if right_from is None else max(start, right_from)
        counted = 0
        per_year: dict[int, int] = {}
        while day <= paid_end:
            if counted == p.max_days.value:
                limit_day = day - DAY
                break
            kind: PayKind = "benefit"
            if work_ended is not None and day > work_ended:
                kind = "after"
            elif employee and per_year.get(day.year, 0) < employer_days:
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
        after_refused=refused,
    )


def _after_refused(
    start: dt.date,
    end: dt.date,
    work_ended: dt.date,
    right_from: dt.date | None,
    params: Params,
) -> AfterRefused | None:
    """Ustawa art. 13 ust. 1 pkt 3 and art. 7 pkt 1: None when the sickness benefit goes on
    after the insurance ended."""
    p = params.pregnancy
    if right_from is not None and right_from > work_ended:
        return "right"
    if start > work_ended:
        if start > work_ended + p.sick_after_end_within_days.value * DAY:
            return "late"
        if days_between(start, end) < p.sick_after_end_min_days.value:
            return "short"
    return None


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
    if sick is not None:
        busy.append((sick.start, sick.end))
        mine += _sick_segments(sick, scenario, params)
        draft.markers += _sick_markers(sick, params)
    if job is not None:
        busy.append((job.start, job.end))
        mine.append(job)
    _trim_work(draft, busy)
    draft.segments[0:0] = mine
    return _assumptions(scenario, sick, job)


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
        elif piece.kind == "after":
            title = "Zwolnienie lekarskie po ustaniu ubezpieczenia: zasiłek chorobowy"
            summary, details, sources = _after_insurance(sick, piece, params)
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
            + (" i do pracodawcy." if sick.employee and piece.kind != "after" else ".")
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


def _after_insurance(
    sick: SickLeave, piece: Piece, params: Params
) -> tuple[str, list[str], list[SourceRef]]:
    """The sickness benefit after the insurance ended: summary, details, sources."""
    p = params.pregnancy
    ended = sick.work_ended
    assert ended is not None
    rate = p.rate_percent.value
    if sick.start > ended:
        within, least = p.sick_after_end_within_days.value, p.sick_after_end_min_days.value
        why = (
            f"Niezdolność do pracy powstała {fmt(sick.start)}, w ciągu {within} dni od ustania "
            f"pracy ({fmt(ended)}), i trwa bez przerwy co najmniej {least} dni, więc zasiłek "
            "chorobowy przysługuje także po ustaniu ubezpieczenia"
        )
        more = p.sick_after_end_within_days.sources
    else:
        why = (
            f"Praca mamy ustała {fmt(ended)}, a niezdolność do pracy trwa dalej. Zasiłek "
            "chorobowy przysługuje także za okres po ustaniu ubezpieczenia"
        )
        more = []
    summary = (
        f"{why}: {rate}% podstawy wymiaru zasiłku, bo zaświadczenie lekarskie ma kod „B” (ciąża). "
        "Wypłaca go ZUS."
    )
    details = [
        "Za okres po ustaniu ubezpieczenia zasiłek chorobowy przysługuje najwyżej przez 91 dni, "
        "ale nie wtedy, gdy niezdolność do pracy występuje w trakcie ciąży: wtedy liczy się "
        f"okres zasiłkowy, najwyżej {p.max_days.value} dni.",
        "Zasiłki za okres po ustaniu ubezpieczenia ustala i wypłaca ZUS.",
    ]
    sources = merge_sources(
        p.sick_after_insurance.sources,
        more,
        p.rate_percent.sources,
        p.max_days.sources,
        p.zus_after_insurance.sources,
    )
    return summary, details, sources


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
                sources=p.max_days.sources,
            )
        )
    return markers


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
    prenatal = _prenatal_start(scenario, birth)
    if prenatal is not None and prenatal <= loss.ended_on:
        return None  # maternity leave before the birth was already under way (our reading)
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
    details.append("Zasiłki za okres po ustaniu ubezpieczenia ustala i wypłaca ZUS.")
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
            p.job_loss_law.sources if loss.reason in EMPLOYER_GONE else [],
            p.job_loss_rate_percent.sources,
            p.zus_after_insurance.sources,
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
        if any(piece.kind == "after" for piece in sick.pieces):
            assumptions.append(
                "Zasiłek chorobowy po ustaniu ubezpieczenia pokazujemy, zakładając, że mama nie "
                "podjęła innej pracy i nie ma prawa do zasiłku dla bezrobotnych, emerytury ani "
                "renty: wtedy by nie przysługiwał (art. 13 ust. 1 ustawy zasiłkowej). Dni po "
                "ustaniu ubezpieczenia liczymy do tego samego okresu zasiłkowego."
            )
            if sick.work_ended is not None and sick.start > sick.work_ended:
                assumptions.append(
                    "Dla niezdolności do pracy, która powstała po ustaniu ubezpieczenia, "
                    "sprawdzamy termin 14 dni (art. 7 pkt 1). Dłuższego terminu przy chorobach "
                    "zakaźnych i podobnych (art. 7 pkt 2) nie uwzględniamy."
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
        if any(s.id.startswith(prefix) for prefix in SEGMENT_IDS.values())
    ]
    if pieces:
        name = {prefix: PAY_NAME[kind] for kind, prefix in SEGMENT_IDS.items()}
        listed = "; ".join(
            f"{name[next(x for x in name if s.id.startswith(x))]}"
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
            text, more = _after_insurance_text(sick, params)
            parts.append(text)
            sources += more
    elif sick.until_birth and coverage(scenario) not in NOT_INSURED:
        parts.append(
            "Jeśli niezdolność do pracy trwa do porodu, po porodzie zaczyna się urlop "
            "macierzyński (okres zasiłku macierzyńskiego)."
        )
        sources += p.until_birth.sources
    if pieces:
        title = (
            "Zwolnienie lekarskie w ciąży: wynagrodzenie i zasiłek chorobowy"
            if any(piece.kind == "employer" for piece in sick.pieces)
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


def _after_insurance_text(sick: SickLeave, params: Params) -> tuple[str, list[SourceRef]]:
    """The work ended for a reason that gives no benefit until the birth: is the sickness
    benefit due after the insurance ended?"""
    p = params.pregnancy
    ended = sick.work_ended
    assert ended is not None
    after = next((piece for piece in sick.pieces if piece.kind == "after"), None)
    if after is not None:
        return (
            f"Praca ustała {long_date(ended)}. Zasiłek chorobowy przysługuje również po ustaniu "
            "ubezpieczenia, a w ciąży bez limitu 91 dni: od "
            f"{long_date(after.start)} do {long_date(after.end)} wypłaca go ZUS.",
            merge_sources(p.sick_after_insurance.sources, p.zus_after_insurance.sources),
        )
    within, least = p.sick_after_end_within_days.value, p.sick_after_end_min_days.value
    match sick.after_refused:
        case "right":
            return (
                f"Praca ustała {long_date(ended)}. Za okres po ustaniu ubezpieczenia zasiłek "
                "chorobowy nie przysługuje, bo mama nie nabyła do niego prawa w czasie "
                "ubezpieczenia.",
                merge_sources(p.sick_after_insurance_not.sources),
            )
        case "late" | "short":
            return (
                f"Praca ustała {long_date(ended)}, a niezdolność do pracy powstała później. "
                f"Zasiłek chorobowy przysługuje wtedy, gdy powstała najpóźniej {within} dni po "
                f"ustaniu ubezpieczenia i trwała bez przerwy co najmniej {least} dni; tu tak nie "
                "jest.",
                merge_sources(p.sick_after_end_within_days.sources),
            )
        case _:  # the 270 days ran out before the work ended
            return f"Praca ustała {long_date(ended)}.", []


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
    elif any(s.id == "maternity-prenatal" and s.start <= loss.ended_on for s in timeline.segments):
        parts.append(
            "Urlop macierzyński przed porodem zaczął się wcześniej, więc oś pokazuje go dalej."
        )
    parts.append(
        "Po porodzie przysługuje jej zasiłek macierzyński, choć ubezpieczenie ustało, bo ustało "
        "w ciąży z tej przyczyny"
        + ("" if confirmed else " (po wyroku sądu)")
        + ". Zasiłki za okres po ustaniu ubezpieczenia wypłaca ZUS."
    )
    return CaseNote(
        id="job-loss",
        kind="right",
        title="Zasiłek w wysokości zasiłku macierzyńskiego do porodu",
        text=" ".join(parts),
        sources=merge_sources(
            p.job_loss_benefit.sources,
            rule.sources,
            p.job_loss_law.sources if loss.reason in EMPLOYER_GONE else [],
            p.job_loss_rate_percent.sources,
            b.paid_to_the_insured.sources,
            p.maternity_after_job_loss.sources,
            p.zus_after_insurance.sources,
        ),
    )
