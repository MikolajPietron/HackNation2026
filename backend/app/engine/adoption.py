"""Guide section D (pages 8-9): a child taken in for upbringing, and Labour Code art. 183.

Who: an insured person who took the child in as a non-professional foster family, or took the
child in and asked the guardianship court to start adoption proceedings. The leave belongs to
the person filling in (`role`); it is drawn on their lane, the other parent's share of parental
leave on the other lane. Nothing about pregnancy or the birth applies.

1. Leave on the terms of maternity leave (urlop na warunkach urlopu macierzyńskiego, art. 183
   § 1, § 1¹): 20/31/33/35/37 weeks by the number of children taken in at once, at most until
   the child turns 7 (10 with postponed schooling) in a foster family, 14 for adoption. Taken in
   under that age, the person has the right to 9 weeks (§ 3).
2. The leave is requested within 7 days of taking the child in and starts on the day the
   request names, at the latest 21 days after taking the child in (§ 6). A week is 7 days
   (art. 183¹ § 1).
3. Parental leave "as after a birth, taking the child's age into account" (D.2; § 4-§ 5):
   41/43 weeks for both parents together, 38 after the 9-week leave, longer with "Za życiem";
   9 weeks belong to each parent alone (art. 182¹ᵃ § 4 via § 5); at most 5 parts (§ 4⁶).
   Adoption: not after the child turns 14 (§ 4¹). Foster family: the rule for a born child, the
   end of the calendar year in which the child turns 6 (art. 182¹ᶜ via § 5).
4. Adoption: the adoptive father's paternity leave, within 12 months of the final adoption
   ruling and not after the child turns 14 (guide B.4; art. 182³ § 1 pkt 2).
5. A person on a contract or with a business gets the benefit for the same periods, not leave
   (guide, "Zasiłek macierzyński"); the benefit needs sickness insurance.

Our readings, not settled by the materials (CLAUDE.md, open questions):
- "until the child turns N" ends on the day before the Nth birthday; "12 months from the final
  ruling" ends on the day before the same date 12 months later (as for 12 months of life);
- the 9 weeks of § 3 are a minimum (the annex: the benefit "nie może trwać krócej niż 9
  tygodni"): when the age limit would leave less, the leave lasts 9 weeks, and only then is it
  "the case of § 3" with 38 (62) weeks of parental leave;
- the leave is drawn from the day of taking in (the earliest start; the request may name a
  later one, up to 21 days later);
- with several children taken in at once the age limits follow the youngest child;
- a foster father has no paternity leave: the guide names the biological and the adoptive
  father;
- supplementary leave (§ 3¹), passing the leave to the other parent (§ 2) and adoption after
  foster care (§ 7-§ 8) are not drawn yet.
"""

import datetime as dt
from dataclasses import dataclass

from app.engine.draft import DAY, WEEK, Draft, days_between, merge_sources
from app.engine.insurance import NOT_INSURED, Coverage, coverage, father_coverage
from app.engine.models import (
    Lane,
    Marker,
    Role,
    Scenario,
    ScenarioError,
    Segment,
    SourceRef,
    TakenIn,
    Timeline,
    Work,
)
from app.engine.params import Param, Params, TakenInKindParams
from app.engine.wording import fmt, weeks_or_days

WEEK_IS_7_DAYS = "Tydzień urlopu to 7 dni kalendarzowych."
PERSON = {"mother": "mama", "father": "tata"}


def kind_params(kind: TakenIn, params: Params) -> TakenInKindParams:
    return params.taken_in.adoption if kind == "adoption" else params.taken_in.foster


def taker(scenario: Scenario) -> Role:
    """Who takes the leave: the person filling in (the mother when nobody said)."""
    return scenario.role or "mother"


def other(role: Role) -> Role:
    return "father" if role == "mother" else "mother"


def cover_of(scenario: Scenario, role: Role) -> Coverage:
    return coverage(scenario) if role == "mother" else father_coverage(scenario)


def work_of(scenario: Scenario, role: Role) -> Work | None:
    return scenario.mothers_work if role == "mother" else scenario.fathers_work


def birthday(birth: dt.date, age: int) -> dt.date:
    """The day the child turns `age` (29 February: 1 March)."""
    try:
        return birth.replace(year=birth.year + age)
    except ValueError:
        return dt.date(birth.year + age, 3, 1)


def months_later(day: dt.date, months: int) -> dt.date:
    """The same day `months` later (a shorter month: its first day after)."""
    year, month = divmod(day.month - 1 + months, 12)
    try:
        return day.replace(year=day.year + year, month=month + 1)
    except ValueError:
        return dt.date(day.year + year + (month + 1) // 12, (month + 1) % 12 + 1, 1)


@dataclass(frozen=True)
class AgeLimit:
    age: int
    sources: list[SourceRef]


def age_limit(scenario: Scenario, params: Params) -> AgeLimit:
    """The age until which the leave lasts: 7 (10 with postponed schooling) or 14."""
    kind = kind_params(scenario.taken_in or "foster", params)
    postponed = kind.age_school_postponed
    if scenario.school_postponed and postponed is not None:
        return AgeLimit(postponed.value, merge_sources(kind.age.sources, postponed.sources))
    return AgeLimit(kind.age.value, kind.age.sources)


@dataclass(frozen=True)
class TakenInLeave:
    """Leave on the terms of maternity leave, computed (dates inclusive)."""

    weeks: int
    """The length by the number of children (20, 31, ...)."""
    start: dt.date
    end: dt.date
    full_end: dt.date
    """Where the leave would end without the age limit."""
    limit: dt.date | None
    """The child's birthday at the age limit; None = the date of birth is not known yet."""
    minimum: bool
    """The age limit would leave less than the minimum: the leave lasts the minimum (§ 3)."""
    too_old: bool
    """The child had reached the age limit when taken in: no leave."""

    @property
    def days(self) -> int:
        return days_between(self.start, self.end)

    @property
    def cut(self) -> bool:
        """Shortened by the age limit (to the day before it, or to the minimum)."""
        return self.end < self.full_end


def taken_in_leave(scenario: Scenario, params: Params) -> TakenInLeave | None:
    """None until the kind, the day of taking in and the number of children are known."""
    if scenario.taken_in is None or scenario.taken_in_on is None:
        return None
    count = scenario.children_count
    if count is None:
        return None
    kind = kind_params(scenario.taken_in, params)
    table = kind.weeks_by_children.value
    weeks = table[min(count, len(table)) - 1]
    start = scenario.taken_in_on
    full_end = start + weeks * WEEK - DAY
    if scenario.birth_date is None:
        return TakenInLeave(weeks, start, full_end, full_end, None, False, False)
    limit = birthday(scenario.birth_date, age_limit(scenario, params).age)
    if start >= limit:
        return TakenInLeave(weeks, start, start, full_end, limit, False, True)
    end = min(full_end, limit - DAY)
    minimum = params.taken_in.minimum_weeks.value
    if days_between(start, end) < minimum * 7:
        return TakenInLeave(
            weeks, start, start + minimum * WEEK - DAY, full_end, limit, True, False
        )
    return TakenInLeave(weeks, start, end, full_end, limit, False, False)


def parental_total(scenario: Scenario, params: Params, leave: TakenInLeave) -> Param[int]:
    """Parental leave of both parents together, as a parameter with its sources."""
    kind = kind_params(scenario.taken_in or "foster", params)
    if leave.minimum and scenario.za_zyciem:
        return kind.parental_weeks_za_zyciem_minimum
    if leave.minimum:
        return kind.parental_weeks_minimum
    table = kind.parental_weeks_za_zyciem if scenario.za_zyciem else kind.parental_weeks_by_children
    weeks = table.value[0 if scenario.children_count == 1 else 1]
    return Param[int](value=weeks, sources=table.sources)


@dataclass(frozen=True)
class ParentalDeadline:
    date: dt.date
    """The last day of parental leave."""
    rule: str
    """In words, after "najpóźniej do …:"."""
    sources: list[SourceRef]


def parental_deadline(scenario: Scenario, params: Params) -> ParentalDeadline | None:
    """Adoption: the day before the child turns 14. Foster family: as for a born child, the end
    of the calendar year in which the child turns 6. None without the date of birth."""
    birth = scenario.birth_date
    if birth is None or scenario.taken_in is None:
        return None
    kind = kind_params(scenario.taken_in, params)
    if kind.parental_age is not None:
        age = kind.parental_age.value
        return ParentalDeadline(
            birthday(birth, age) - DAY,
            f"dzień przed {age}. urodzinami dziecka",
            merge_sources(params.taken_in.parental.sources, kind.parental_age.sources),
        )
    age = params.parental.deadline_age.value
    return ParentalDeadline(
        dt.date(birth.year + age, 12, 31),
        f"koniec roku kalendarzowego, w którym dziecko kończy {age} lat",
        merge_sources(params.taken_in.parental.sources, params.parental.deadline_age.sources),
    )


def paternity_deadline(scenario: Scenario, params: Params) -> dt.date | None:
    """Adoption, the ruling final: 12 months from it, not after the child turns 14."""
    t = params.taken_in
    final = scenario.adoption_final_on
    if scenario.taken_in != "adoption" or not scenario.adoption_final or final is None:
        return None
    last = months_later(final, t.paternity_months.value) - DAY
    if scenario.birth_date is not None:
        last = min(last, birthday(scenario.birth_date, t.paternity_age.value) - DAY)
    return last


def check(scenario: Scenario, today: dt.date) -> None:
    """Answers that cannot be true together."""
    taken, birth = scenario.taken_in_on, scenario.birth_date
    if taken is None:
        raise ScenarioError("Najpierw potrzebny jest dzień przyjęcia dziecka na wychowanie.")
    if birth is not None and birth > taken:
        raise ScenarioError(
            f"Dziecko urodziło się {fmt(birth)}, a zostało przyjęte {fmt(taken)}: data przyjęcia "
            "nie może być wcześniejsza niż data urodzenia. Sprawdź daty."
        )
    if birth is not None and birth > today:
        raise ScenarioError(f"Data urodzenia {fmt(birth)} jest w przyszłości (dziś {fmt(today)}).")
    final = scenario.adoption_final_on
    if final is not None and final < taken:
        raise ScenarioError(
            f"Przysposobienie nie mogło uprawomocnić się ({fmt(final)}) przed przyjęciem dziecka "
            f"({fmt(taken)}). Sprawdź datę."
        )
    if final is not None and final > today:
        raise ScenarioError(f"Data {fmt(final)} jest w przyszłości (dziś {fmt(today)}).")


def taken_in_timeline(scenario: Scenario, params: Params, today: dt.date) -> Timeline:
    """The timeline of a child taken in for upbringing. The case notes are added by the caller."""
    assert scenario.taken_in is not None
    check(scenario, today)
    taken = scenario.taken_in_on
    assert taken is not None
    draft = Draft()
    draft.markers.append(_taken_in_marker(scenario, params, taken))
    role = taker(scenario)
    insured = cover_of(scenario, role) not in NOT_INSURED
    leave = taken_in_leave(scenario, params)
    too_old = leave is not None and leave.too_old
    if insured and work_of(scenario, role) in ("employment", None) and not too_old:
        _request_markers(draft, params, taken)
    if insured and leave is not None:
        if leave.too_old:
            assert leave.limit is not None
            draft.warnings.append(
                f"Dziecko skończyło {age_limit(scenario, params).age} lat {fmt(leave.limit)}, "
                "zanim zostało przyjęte: urlop na warunkach urlopu macierzyńskiego przysługuje "
                "tylko do tego wieku."
            )
        else:
            _leave(draft, scenario, params, leave, today)
            _parental(draft, scenario, params, leave, today)
    _paternity(draft, scenario, params, leave, today)
    _person_lines(draft, scenario, params)
    draft.markers.sort(key=lambda m: m.date)
    return Timeline(
        params_version=params.version,
        today=today,
        birth_date=taken,
        child_born=True,
        children_count=scenario.children_count,
        segments=draft.segments,
        markers=draft.markers,
        documents=draft.documents,
        warnings=draft.warnings,
        assumptions=_assumptions(scenario, params, leave, insured, draft),
        taken_in=scenario.taken_in,
    )


def _taken_in_marker(scenario: Scenario, params: Params, taken: dt.date) -> Marker:
    kind = kind_params(scenario.taken_in or "foster", params)
    adoption = scenario.taken_in == "adoption"
    return Marker(
        id="taken-in",
        lane="child",
        label="Przyjęcie dziecka",
        title="Przyjęcie dziecka i wniosek o przysposobienie"
        if adoption
        else "Przyjęcie dziecka do rodziny zastępczej",
        date=taken,
        summary="Od tego dnia liczymy urlop na warunkach urlopu macierzyńskiego.",
        details=[
            "Liczy się dzień, w którym dziecko zostało przyjęte na wychowanie, a wniosek do sądu "
            "o przysposobienie złożony (późniejszy z nich)."
        ]
        if adoption
        else [],
        sources=merge_sources(params.taken_in.insured.sources, kind.who.sources),
    )


def _request_markers(draft: Draft, params: Params, taken: dt.date) -> None:
    """Art. 183 § 6: the request within 7 days, the start at the latest after 21 days."""
    t = params.taken_in
    request = taken + t.request_days.value * DAY
    latest = taken + t.latest_start_days.value * DAY
    draft.markers += [
        Marker(
            id="leave-request-deadline",
            lane="child",
            label="Wniosek o urlop",
            title="Wniosek o urlop na warunkach urlopu macierzyńskiego",
            date=request,
            summary=(
                f"Pracownik składa wniosek o ten urlop w terminie {t.request_days.value} dni od "
                "dnia przyjęcia dziecka."
            ),
            sources=t.request_days.sources,
        ),
        Marker(
            id="start-limit",
            lane="child",
            label="Start urlopu najpóźniej",
            title="Najpóźniejszy początek urlopu",
            date=latest,
            summary=(
                "Urlop zaczyna się w dniu wskazanym we wniosku, nie później niż "
                f"{t.latest_start_days.value} dni od dnia przyjęcia dziecka."
            ),
            sources=t.latest_start_days.sources,
        ),
    ]


def _leave(
    draft: Draft, scenario: Scenario, params: Params, leave: TakenInLeave, today: dt.date
) -> None:
    t = params.taken_in
    kind = kind_params(scenario.taken_in or "foster", params)
    role = taker(scenario)
    who = PERSON[role].capitalize()
    limit = age_limit(scenario, params)
    count = scenario.children_count or 1
    details = [
        f"Przy przyjęciu {children_taken_in(count)} urlop trwa {leave.weeks} tyg., nie dłużej "
        f"jednak niż do ukończenia przez dziecko {limit.age} lat."
    ]
    sources = [t.leave.sources, kind.weeks_by_children.sources, limit.sources]
    if leave.limit is None:
        details.append("Granicę wieku sprawdzimy, gdy będzie znana data urodzenia dziecka.")
    elif leave.minimum:
        details.append(
            f"Dziecko kończy {limit.age} lat {fmt(leave.limit)}, ale kto przyjął dziecko przed "
            f"tym wiekiem, ma prawo do {t.minimum_weeks.value} tygodni urlopu."
        )
        sources.append(t.minimum_weeks.sources)
    elif leave.cut:
        details.append(
            f"Dziecko kończy {limit.age} lat {fmt(leave.limit)}, dlatego urlop kończy się dzień "
            f"wcześniej: trwa {weeks_or_days(leave.days)} zamiast {leave.weeks} tyg."
        )
    if work_of(scenario, role) in ("employment", None):
        details.append(
            "Pokazujemy go od dnia przyjęcia dziecka. Może też zacząć się później, w dniu "
            f"wskazanym we wniosku, nie później niż {t.latest_start_days.value} dni od dnia "
            "przyjęcia."
        )
        sources.append(t.latest_start_days.sources)
    details.append(WEEK_IS_7_DAYS)
    sources.append(params.rules.week_is_7_days.sources)
    draft.segments.append(
        Segment(
            id="adoption-leave",
            lane=role,
            tone="leave",
            title="Urlop na warunkach urlopu macierzyńskiego",
            start=leave.start,
            end=leave.end,
            days=leave.days,
            summary=(
                f"{who} ma urlop na warunkach urlopu macierzyńskiego — odpowiednik urlopu "
                f"macierzyńskiego przy przyjęciu dziecka na wychowanie: "
                f"{weeks_or_days(leave.days)}, od {fmt(leave.start)} do {fmt(leave.end)}."
            ),
            details=details,
            sources=merge_sources(*sources),
        )
    )
    if leave.end < today:
        draft.warnings.append(
            f"Urlop na warunkach urlopu macierzyńskiego skończył się {fmt(leave.end)}."
        )
    if leave.limit is not None and leave.cut:
        draft.markers.append(
            Marker(
                id="age-limit",
                lane="child",
                label=f"{limit.age}. urodziny",
                title=f"Dziecko kończy {limit.age} lat",
                date=leave.limit,
                summary=(
                    "Urlop na warunkach urlopu macierzyńskiego przysługuje nie dłużej niż do "
                    f"ukończenia przez dziecko {limit.age} lat"
                    + (
                        f", ale nie krócej niż {t.minimum_weeks.value} tygodni."
                        if leave.minimum
                        else "."
                    )
                ),
                sources=merge_sources(
                    limit.sources, t.minimum_weeks.sources if leave.minimum else []
                ),
            )
        )


def _parental(
    draft: Draft, scenario: Scenario, params: Params, leave: TakenInLeave, today: dt.date
) -> None:
    """Parental leave after the leave on the terms of maternity leave: the taker's whole share
    first, the other parent's 9 weeks after it (both are options)."""
    deadline = parental_deadline(scenario, params)
    p = params.parental
    t = params.taken_in
    total = parental_total(scenario, params, leave)
    exclusive = p.exclusive_weeks.value
    role = taker(scenario)
    if deadline is not None and deadline.date < today:
        draft.warnings.append(
            f"Czas na urlop rodzicielski minął {fmt(deadline.date)} ({deadline.rule})."
        )
        return
    start = leave.end + DAY
    if deadline is not None and start > deadline.date:
        draft.warnings.append(
            f"Urlop rodzicielski trzeba wykorzystać najpóźniej do {fmt(deadline.date)} "
            f"({deadline.rule}), a urlop na warunkach urlopu macierzyńskiego trwa dłużej."
        )
        return
    sources = [
        t.parental.sources,
        total.sources,
        p.exclusive_weeks.sources,
        t.parental_parts.sources,
    ]
    if deadline is not None:
        sources.append(deadline.sources)
        draft.markers.append(
            Marker(
                id="parental-deadline",
                lane="child",
                label="Rodzicielski najpóźniej do",
                title="Koniec czasu na urlop rodzicielski",
                date=deadline.date,
                summary=f"Urlop rodzicielski można wykorzystać najpóźniej do: {deadline.rule}.",
                sources=deadline.sources,
            )
        )
    common = [
        f"Urlop jest udzielany jednorazowo albo w nie więcej niż {p.max_parts.value} częściach.",
        WEEK_IS_7_DAYS,
    ]
    if deadline is not None:
        common.insert(1, f"Trzeba go wykorzystać najpóźniej do {fmt(deadline.date)}.")
    shares = [(role, total.value - exclusive), (other(role), exclusive)]
    for person, weeks in shares:
        if person != role and cover_of(scenario, person) in NOT_INSURED:
            continue
        if deadline is not None and start > deadline.date:
            break
        full_end = start + weeks * WEEK - DAY
        end = full_end if deadline is None else min(full_end, deadline.date)
        shown = f"{weeks} tyg." if end == full_end else f"{days_between(start, end)} dni"
        if person == role:
            summary = (
                f"Po urlopie na warunkach urlopu macierzyńskiego rodzice mają razem do "
                f"{total.value} tyg. urlopu rodzicielskiego, a każde z nich {exclusive} tyg. "
                f"wyłącznie dla siebie. {PERSON[person].capitalize()} może więc wykorzystać "
                f"najwięcej {total.value - exclusive} tyg.; wzięte w całości od razu: {shown}, "
                f"od {fmt(start)} do {fmt(end)}."
            )
        else:
            summary = (
                f"{PERSON[person].capitalize()} ma {exclusive} tyg. urlopu rodzicielskiego "
                "wyłącznie dla siebie: nie można ich przenieść na drugiego rodzica. Pokazujemy "
                f"je po urlopie {'mamy' if role == 'mother' else 'taty'}: {shown}, od "
                f"{fmt(start)} do {fmt(end)}."
            )
        details = list(common)
        if end < full_end:
            details.insert(0, "Urlop musi się skończyć do tego dnia, dlatego pokazujemy go krócej.")
        draft.segments.append(
            Segment(
                id="parental" if person == "mother" else "parental-father",
                lane=person,
                tone="option",
                title="Urlop rodzicielski — do wyboru"
                if person == "mother"
                else "Urlop rodzicielski taty — do wyboru",
                start=start,
                end=end,
                days=days_between(start, end),
                summary=summary,
                details=details,
                sources=merge_sources(*sources, params.rules.week_is_7_days.sources),
            )
        )
        start = end + DAY


def _paternity(
    draft: Draft,
    scenario: Scenario,
    params: Params,
    leave: TakenInLeave | None,
    today: dt.date,
) -> None:
    """Guide B.4, adoption: 14 days within 12 months of the final ruling, before the child
    turns 14. Drawn from the ruling (from today when it was earlier), after the father's own
    leave on the terms of maternity leave when they would meet."""
    deadline = paternity_deadline(scenario, params)
    if deadline is None or father_coverage(scenario) in NOT_INSURED:
        return
    f = params.father
    t = params.taken_in
    final = scenario.adoption_final_on
    assert final is not None
    sources = merge_sources(
        f.paternity_who.sources,
        f.paternity_days.sources,
        f.paternity_parts.sources,
        t.paternity_months.sources,
        t.paternity_age.sources,
        f.paternity_expires.sources,
    )
    if deadline < today:
        draft.warnings.append(
            f"Czas na urlop ojcowski minął {fmt(deadline)}: można go wykorzystać w ciągu "
            f"{t.paternity_months.value} miesięcy od uprawomocnienia się przysposobienia."
        )
        return
    draft.markers.append(
        Marker(
            id="paternity-deadline",
            lane="child",
            label="Ojcowski najpóźniej do",
            title="Koniec czasu na urlop ojcowski",
            date=deadline,
            summary=(
                f"Urlop ojcowski można wykorzystać w ciągu {t.paternity_months.value} miesięcy "
                "od uprawomocnienia się przysposobienia, ale nie później niż do ukończenia przez "
                f"dziecko {t.paternity_age.value} lat. Potem prawo do niego wygasa."
            ),
            sources=sources,
        )
    )
    days = f.paternity_days.value
    start = max(final, today)
    own = leave is not None and taker(scenario) == "father" and not leave.too_old
    if own and leave is not None and leave.start <= start + (days - 1) * DAY and leave.end >= start:
        start = leave.end + DAY
    if start > deadline:
        return
    end = min(start + (days - 1) * DAY, deadline)
    left = days_between(start, end)
    if left < f.paternity_min_part_days.value:
        draft.warnings.append(
            f"Do końca czasu na urlop ojcowski ({fmt(deadline)}) zostało {left} dni, a żadna "
            f"część tego urlopu nie może być krótsza niż {f.paternity_min_part_days.value} dni."
        )
        return
    draft.segments.append(
        Segment(
            id="paternity",
            lane="father",
            tone="option",
            title="Urlop ojcowski — do wyboru",
            start=start,
            end=end,
            days=left,
            summary=(
                f"Urlop ojcowski taty to najwyżej {days} dni kalendarzowych. Przy adopcji można "
                f"go wykorzystać w ciągu {t.paternity_months.value} miesięcy od uprawomocnienia "
                f"się przysposobienia ({fmt(final)}), najpóźniej do {fmt(deadline)}."
                + (
                    f" Do końca tego czasu zostało {left} dni, więc pokazujemy {left} dni."
                    if left < days
                    else ""
                )
            ),
            details=[
                f"Można go wykorzystać jednorazowo ({days} dni) albo w "
                f"{f.paternity_parts.value} częściach po co najmniej "
                f"{f.paternity_min_part_days.value} dni.",
                f"Jeśli tata nie wykorzysta urlopu do {fmt(deadline)}, prawo do niego wygasa.",
            ],
            sources=sources,
        )
    )


def _person_lines(draft: Draft, scenario: Scenario, params: Params) -> None:
    """Every period on a parent's lane says when that parent only gets the benefit, and when we
    assume sickness insurance."""
    b = params.benefit
    for role in ("mother", "father"):
        lane: Lane = role
        who = PERSON[role]
        lines, sources = [], []
        if cover_of(scenario, role) in ("unknown-work", "unknown-voluntary"):
            lines.append(
                "Zasiłek macierzyński jest wypłacany osobom podlegającym ubezpieczeniu "
                f"chorobowemu. Na razie zakładamy, że {who} mu podlega."
            )
            sources.append(b.paid_to_the_insured.sources)
        if work_of(scenario, role) in ("contract", "business"):
            lines.append(
                f"{who.capitalize()} nie jest pracownikiem, więc nie dostaje urlopu: ma prawo do "
                "zasiłku macierzyńskiego za okres odpowiadający urlopowi, na tych samych zasadach "
                "co do wymiaru."
            )
            sources += [b.non_employees.sources, b.same_rules_for_non_employees.sources]
        if not lines:
            continue
        draft.segments = [
            s.model_copy(
                update={
                    "details": [*s.details, *lines],
                    "sources": merge_sources(s.sources, *sources),
                }
            )
            if s.lane == lane
            else s
            for s in draft.segments
        ]


def children_taken_in(count: int) -> str:
    """After "przy przyjęciu": the Labour Code's wording (art. 183 § 1)."""
    words = {1: "jednego dziecka", 2: "dwojga dzieci", 3: "trojga dzieci", 4: "czworga dzieci"}
    return words.get(count, f"{count} dzieci")


def _assumptions(
    scenario: Scenario,
    params: Params,
    leave: TakenInLeave | None,
    insured: bool,
    draft: Draft,
) -> list[str]:
    role = taker(scenario)
    who = PERSON[role]
    shown = {s.id for s in draft.segments} | {m.id for m in draft.markers}
    assumptions = [
        "Pokazujemy to, co wynika z części D Przewodnika ZUS (przyjęcie dziecka na wychowanie) "
        "i z Kodeksu pracy: urlop na warunkach urlopu macierzyńskiego, urlop rodzicielski i przy "
        "adopcji urlop ojcowski. Kwoty zasiłku, wnioski o zasiłek i uzupełniający urlop "
        "macierzyński dodamy w kolejnych etapach.",
        f"Urlop na warunkach urlopu macierzyńskiego pokazujemy u osoby, która wypełnia wywiad "
        f"({who}).",
    ]
    if not insured:
        assumptions.append(
            "Ten urlop przysługuje osobie ubezpieczonej, która przyjęła dziecko. Jeśli drugi "
            "rodzic podlega ubezpieczeniu chorobowemu, zacznij wywiad jako on, a oś pokaże jego "
            "uprawnienia."
        )
    if leave is not None and "adoption-leave" in shown:
        assumptions.append(
            "Urlop pokazujemy od dnia przyjęcia dziecka. „Do ukończenia przez dziecko” danego "
            "wieku liczymy do dnia przed tymi urodzinami."
        )
        if (scenario.children_count or 1) > 1:
            assumptions.append(
                "Przy kilkorgu dzieciach granicę wieku liczymy od daty urodzenia najmłodszego "
                "z nich."
            )
        if leave.minimum:
            assumptions.append(
                f"{params.taken_in.minimum_weeks.value} tygodni z art. 183 § 3 Kodeksu pracy "
                "czytamy jako najkrótszy urlop: gdy granica wieku zostawiłaby mniej, urlop trwa "
                "tyle. Wtedy urlop rodzicielski jest krótszy (art. 183 § 4 pkt 3)."
            )
    if "parental" in shown or "parental-father" in shown:
        assumptions.append(
            "Urlop rodzicielski pokazujemy tak, jakby osoba wypełniająca wzięła całą swoją część "
            "od razu, a drugi rodzic swoje tygodnie zaraz potem. Rodzice mogą też korzystać "
            "z niego jednocześnie albo naprzemiennie i dzielić go na części."
        )
    if scenario.taken_in == "foster" and "adoption-leave" in shown:
        assumptions.append(
            "W rodzinie zastępczej termin urlopu rodzicielskiego liczymy jak przy urodzeniu "
            "dziecka (koniec roku, w którym dziecko kończy 6 lat), bo Kodeks pracy odsyła do "
            "art. 182¹ᶜ. Dla starszych dzieci materiały nie mówią tego wprost."
        )
    if scenario.taken_in == "foster":
        assumptions.append(
            "Urlopu ojcowskiego nie pokazujemy: Przewodnik przyznaje go ojcu biologicznemu "
            "i adopcyjnemu, a o rodzinie zastępczej nie mówi."
        )
    if "paternity-deadline" in shown:
        assumptions.append(
            f"{params.taken_in.paternity_months.value} miesięcy od uprawomocnienia się "
            "przysposobienia liczymy do dnia przed tą samą datą rok później."
        )
    return assumptions
