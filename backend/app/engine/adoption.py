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
   (guide, "Zasiłek macierzyński"); the benefit needs sickness insurance. The right belongs to
   the insured person who took the child in (guide D): when the person filling in has no
   sickness insurance and the other parent works with it, the leave is the other parent's.
6. Supplementary maternity leave (§ 3¹): on the terms of art. 180², when the child's stay in
   hospital took place after the child was taken in; right after the leave.
7. Passing the leave on (§ 2: art. 180 § 4-17 apply accordingly): after at least 14 weeks of
   the leave the rest passes to the other parent, if insured; the total does not change.
8. Adoption after foster care (§ 7-§ 8): the leave of § 1¹ less the leave used as a foster
   family, and parental leave less the parental leave used as a foster family.

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
- an uninsured person's partner took the child in too, so the leave is theirs once we know they
  work (until then the interview asks; nobody is assumed);
- supplementary leave: the windows of art. 180² still count from the child's birth, and only
  the days in hospital from the day of taking in count;
- passing the leave on: "14 weeks after the birth" of art. 180 § 4 is read as 14 weeks of the
  leave, and either parent may pass it to the other (the Code names the mother and the father);
- adoption after foster care: the foster leave counts up to the day before the court
  application; the 9-week minimum of § 3 is not applied to the reduced leave (§ 7 reduces the
  length of § 1¹); the foster parental weeks come out of the share of the person on leave first,
  the other parent's 9 weeks stay while the pool allows.
"""

import datetime as dt
from dataclasses import dataclass

from app.engine.draft import DAY, WEEK, Draft, days_between, merge_sources
from app.engine.insurance import NOT_INSURED, Coverage, coverage, father_coverage
from app.engine.models import (
    HospitalStay,
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
from app.engine.supplementary import Supplementary, describe_case, supplementary_leave
from app.engine.wording import fmt, weeks_or_days

WEEK_IS_7_DAYS = "Tydzień urlopu to 7 dni kalendarzowych."
PERSON = {"mother": "mama", "father": "tata"}


def kind_params(kind: TakenIn, params: Params) -> TakenInKindParams:
    return params.taken_in.adoption if kind == "adoption" else params.taken_in.foster


def filler(scenario: Scenario) -> Role:
    """The person filling in (the mother when nobody said)."""
    return scenario.role or "mother"


def taker(scenario: Scenario) -> Role:
    """Who takes the leave: the person filling in; when they have no sickness insurance and the
    other parent works with it (or presumably, on a contract or with a business), the other
    parent, who took the child in too (guide D: the insured person who took the child in)."""
    me = filler(scenario)
    partner = other(me)
    if cover_of(scenario, me) in NOT_INSURED and cover_of(scenario, partner) not in (
        NOT_INSURED | {"unknown-work"}
    ):
        return partner
    return me


def other(role: Role) -> Role:
    return "father" if role == "mother" else "mother"


def cover_of(scenario: Scenario, role: Role) -> Coverage:
    return coverage(scenario) if role == "mother" else father_coverage(scenario)


def foster_leave_used(scenario: Scenario) -> int:
    """Art. 183 § 7: days of leave on the terms of maternity leave used as a foster family, up
    to the day before the adoption application (the day of taking in on this path)."""
    before, taken = scenario.foster_before, scenario.taken_in_on
    if scenario.taken_in != "adoption" or before is None or taken is None:
        return 0
    if before.leave_start is None or before.leave_end is None:
        return 0
    last = min(before.leave_end, taken - DAY)
    return max(0, days_between(before.leave_start, last))


def foster_parental_used(scenario: Scenario) -> int:
    """Art. 183 § 8: weeks of parental leave used as a foster family."""
    before = scenario.foster_before
    if scenario.taken_in != "adoption" or before is None:
        return 0
    return before.parental_weeks or 0


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
    used_days: int = 0
    """Adoption after foster care (§ 7): days of the foster leave taken off the length."""
    used_up: bool = False
    """...and nothing of the length is left: no leave."""

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
    used = foster_leave_used(scenario)
    length = weeks * 7 - used
    if length <= 0:
        return TakenInLeave(weeks, start, start, start, None, False, False, used, used_up=True)
    full_end = start + (length - 1) * DAY
    if scenario.birth_date is None:
        return TakenInLeave(weeks, start, full_end, full_end, None, False, False, used)
    limit = birthday(scenario.birth_date, age_limit(scenario, params).age)
    if start >= limit:
        return TakenInLeave(weeks, start, start, full_end, limit, False, True, used)
    end = min(full_end, limit - DAY)
    minimum = params.taken_in.minimum_weeks.value
    # § 7 reduces the length of § 1¹; the minimum of § 3 is for a leave the age limit cuts.
    if not used and days_between(start, end) < minimum * 7:
        return TakenInLeave(
            weeks, start, start + minimum * WEEK - DAY, full_end, limit, True, False
        )
    return TakenInLeave(weeks, start, end, full_end, limit, False, False, used)


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


def taken_in_supplementary(
    scenario: Scenario, params: Params, today: dt.date
) -> Supplementary | None:
    """§ 3¹: art. 180² with only the days in hospital from the day of taking in. None while the
    facts are not known or no stay reaches that day."""
    taken, birth = scenario.taken_in_on, scenario.birth_date
    if taken is None or birth is None:
        return None
    stays = [
        HospitalStay(start=max(stay.start, taken), end=stay.end)
        for stay in scenario.hospital_stays
        if stay.end is None or stay.end >= taken
    ]
    if not stays:
        return None
    return supplementary_leave(
        scenario.model_copy(update={"hospital_stays": stays}), params, birth, today
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
    before = scenario.foster_before
    if before is not None and scenario.taken_in != "adoption":
        raise ScenarioError(
            "Urlop wykorzystany w rodzinie zastępczej odejmuje się od urlopu związanego "
            "z przysposobieniem, więc ma znaczenie tylko przy adopcji."
        )
    if before is not None and before.leave_start is not None:
        if before.leave_start >= taken:
            raise ScenarioError(
                f"Urlop w rodzinie zastępczej zaczął się {fmt(before.leave_start)}, a liczy się "
                f"urlop sprzed wystąpienia do sądu o przysposobienie ({fmt(taken)}). Sprawdź daty."
            )
        if birth is not None and before.leave_start < birth:
            raise ScenarioError(
                f"Urlop w rodzinie zastępczej nie mógł zacząć się ({fmt(before.leave_start)}) "
                f"przed urodzeniem dziecka ({fmt(birth)}). Sprawdź daty."
            )


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
    no_leave = leave is not None and (leave.too_old or leave.used_up)
    if insured and work_of(scenario, role) in ("employment", None) and not no_leave:
        _request_markers(draft, params, taken)
    if insured and leave is not None:
        if leave.too_old:
            assert leave.limit is not None
            draft.warnings.append(
                f"Dziecko skończyło {age_limit(scenario, params).age} lat {fmt(leave.limit)}, "
                "zanim zostało przyjęte: urlop na warunkach urlopu macierzyńskiego przysługuje "
                "tylko do tego wieku."
            )
        elif leave.used_up:
            # § 7: the whole leave was used as a foster family; parental leave can follow from
            # the day of the court application.
            _parental(draft, scenario, params, leave, today, after=taken - DAY)
        else:
            _leave(draft, scenario, params, leave, today)
            _handover(draft, scenario, params, leave)
            after = _supplementary(draft, scenario, params, leave, today)
            _parental(draft, scenario, params, leave, today, after=after)
    _paternity(draft, scenario, params, today)
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
    if leave.used_days:
        details.append(
            f"Wcześniej {leave.used_days} dni tego urlopu wykorzystano jako rodzina zastępcza, "
            "a o wykorzystany urlop wymiar się obniża."
        )
        sources.append(t.after_foster_leave.sources)
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


def _handover(draft: Draft, scenario: Scenario, params: Params, leave: TakenInLeave) -> None:
    """§ 2 with art. 180 § 4-5: after at least 14 weeks the rest of the leave passes to the
    other parent, if insured (the note says why not otherwise); the total does not change."""
    if not scenario.taken_in_handover:
        return
    t = params.taken_in
    minimum = t.handover_after_weeks.value
    weeks = scenario.taken_in_handover_after_weeks or minimum
    if weeks < minimum:
        raise ScenarioError(
            "Dalszą część urlopu na warunkach urlopu macierzyńskiego można przekazać drugiemu "
            f"rodzicowi dopiero po wykorzystaniu co najmniej {minimum} tygodni."
        )
    own_end = leave.start + weeks * WEEK - DAY
    if own_end >= leave.end:
        raise ScenarioError(
            f"Urlop na warunkach urlopu macierzyńskiego kończy się {fmt(leave.end)}, więc po "
            f"{weeks} tyg. nie zostaje nic, co mógłby przejąć drugi rodzic."
        )
    role = taker(scenario)
    partner = other(role)
    if cover_of(scenario, partner) in NOT_INSURED:
        return
    own = draft.segment("adoption-leave")
    assert own is not None
    start = own_end + DAY
    rule = [t.handover_after_weeks.sources, params.father.total_cap.sources]
    together = (
        f"Razem urlop trwa do {fmt(leave.end)}: łączny wymiar się nie zmienia. {WEEK_IS_7_DAYS}"
    )
    draft.replace(
        "adoption-leave",
        own.model_copy(
            update={
                "end": own_end,
                "days": days_between(own.start, own_end),
                "summary": (
                    f"{PERSON[role].capitalize()} wykorzystuje {weeks} tyg. urlopu na warunkach "
                    f"urlopu macierzyńskiego, od {fmt(own.start)} do {fmt(own_end)}. Dalszą "
                    f"część, od {fmt(start)} do {fmt(leave.end)}, wykorzystuje {PERSON[partner]}."
                ),
                "details": [together, *own.details],
                "sources": merge_sources(own.sources, *rule),
            }
        ),
        Segment(
            id="adoption-leave-other",
            lane=partner,
            tone="leave",
            title="Urlop na warunkach urlopu macierzyńskiego — dalsza część",
            start=start,
            end=leave.end,
            days=days_between(start, leave.end),
            summary=(
                f"{PERSON[partner].capitalize()} wykorzystuje dalszą część urlopu na warunkach "
                f"urlopu macierzyńskiego: od {fmt(start)} do {fmt(leave.end)}, bezpośrednio po "
                f"{'mamie' if role == 'mother' else 'tacie'}."
            ),
            details=[
                f"Najpierw trzeba wykorzystać co najmniej {minimum} tygodni tego urlopu.",
                together,
            ],
            sources=merge_sources(*rule, params.rules.week_is_7_days.sources),
        ),
    )


def _supplementary(
    draft: Draft, scenario: Scenario, params: Params, leave: TakenInLeave, today: dt.date
) -> dt.date:
    """§ 3¹: supplementary leave right after the leave, for the days in hospital after the child
    was taken in. Returns the last day before parental leave."""
    found = taken_in_supplementary(scenario, params, today)
    if found is None or found.weeks == 0:
        return leave.end
    s = params.supplementary
    role = taker(scenario)
    start = leave.end + DAY
    end = start + found.weeks * WEEK - DAY
    details = [
        describe_case(found, params),
        "Liczy się tylko pobyt w szpitalu od dnia przyjęcia dziecka na wychowanie: "
        f"{found.days} {'dzień' if found.days == 1 else 'dni'} między "
        f"{fmt(max(found.first_day, leave.start))} a {fmt(found.last_day)}. Okresy pobytu "
        f"sumuje się, a niepełny tydzień zaokrągla w górę: stąd {found.weeks} tyg.",
    ]
    if found.ongoing:
        grow = (
            f" Wymiar może jeszcze wzrosnąć, najwyżej do {found.max_weeks} tyg."
            if found.max_weeks > found.weeks
            else ""
        )
        details.append(
            f"Dziecko jest jeszcze w szpitalu, więc liczymy do dziś ({fmt(today)}).{grow}"
        )
    details += [
        "Urlop jest udzielany jednorazowo, bez dzielenia na części, bezpośrednio po urlopie na "
        "warunkach urlopu macierzyńskiego.",
        WEEK_IS_7_DAYS,
    ]
    case_sources = {
        "early": s.limit_weeks_early.sources,
        "preterm": s.limit_weeks_preterm.sources,
        "term": s.term.sources,
    }[found.case]
    draft.segments.append(
        Segment(
            id="supplementary",
            lane=role,
            tone="option",
            title="Uzupełniający urlop macierzyński",
            start=start,
            end=end,
            days=found.weeks * 7,
            summary=(
                f"Po urlopie na warunkach urlopu macierzyńskiego {PERSON[role]} może wziąć "
                f"{found.weeks} tyg. uzupełniającego urlopu macierzyńskiego: tydzień za każdy "
                "tydzień pobytu dziecka w szpitalu po przyjęciu na wychowanie."
            ),
            details=details,
            sources=merge_sources(
                params.taken_in.supplementary.sources,
                case_sources,
                s.sum_and_round.sources,
                s.once_after_maternity.sources,
                params.rules.week_is_7_days.sources,
            ),
        )
    )
    return end


def _parental(
    draft: Draft,
    scenario: Scenario,
    params: Params,
    leave: TakenInLeave,
    today: dt.date,
    after: dt.date,
) -> None:
    """Parental leave from the day after `after` (the leave, or supplementary leave after it):
    the taker's whole share first, the other parent's 9 weeks after it (both are options).
    After foster care (§ 8) the pool is smaller by the foster parental weeks."""
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
    start = after + DAY
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
    used = foster_parental_used(scenario)
    pool = total.value - used
    if used:
        common.insert(
            0,
            f"Rodzice mieli razem do {total.value} tyg.; {used} tyg. wykorzystano w rodzinie "
            f"zastępczej, więc zostaje do {max(pool, 0)} tyg.",
        )
        sources.append(t.after_foster_parental.sources)
    shares = [(role, pool - exclusive), (other(role), min(exclusive, pool))]
    for person, weeks in shares:
        if weeks <= 0 or person != role and cover_of(scenario, person) in NOT_INSURED:
            continue
        if deadline is not None and start > deadline.date:
            break
        full_end = start + weeks * WEEK - DAY
        end = full_end if deadline is None else min(full_end, deadline.date)
        shown = f"{weeks} tyg." if end == full_end else f"{days_between(start, end)} dni"
        if person == role:
            summary = (
                f"Po urlopie na warunkach urlopu macierzyńskiego rodzice mają razem do "
                f"{pool} tyg. urlopu rodzicielskiego, a każde z nich {exclusive} tyg. "
                f"wyłącznie dla siebie. {PERSON[person].capitalize()} może więc wykorzystać "
                f"najwięcej {weeks} tyg.; wzięte w całości od razu: {shown}, "
                f"od {fmt(start)} do {fmt(end)}."
            )
        else:
            summary = (
                f"{PERSON[person].capitalize()} ma {exclusive} tyg. urlopu rodzicielskiego "
                "wyłącznie dla siebie: nie można ich przenieść na drugiego rodzica. Pokazujemy "
                f"je po urlopie {'mamy' if role == 'mother' else 'taty'}: {shown}, od "
                f"{fmt(start)} do {fmt(end)}."
                + (f" Z łącznej puli zostało tylko {weeks} tyg." if weeks < exclusive else "")
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


def _paternity(draft: Draft, scenario: Scenario, params: Params, today: dt.date) -> None:
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
    # Not on the father's own leave on the terms of maternity leave (or its part passed to him).
    own = sorted(
        (
            s
            for s in draft.segments
            if s.lane == "father" and s.id in ("adoption-leave", "adoption-leave-other")
        ),
        key=lambda s: s.start,
    )
    for busy in own:
        if busy.start <= start + (days - 1) * DAY and busy.end >= start:
            start = busy.end + DAY
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
        "i z Kodeksu pracy: urlop na warunkach urlopu macierzyńskiego, uzupełniający urlop "
        "macierzyński, urlop rodzicielski i przy adopcji urlop ojcowski, z kwotą zasiłku, gdy "
        "jest podana kwota miesięczna. Wnioski o zasiłek dodamy w kolejnych etapach.",
        f"Urlop na warunkach urlopu macierzyńskiego pokazujemy u osoby, która wypełnia wywiad "
        f"({who}).",
    ]
    if role != filler(scenario):
        assumptions[1] = (
            f"Urlop na warunkach urlopu macierzyńskiego pokazujemy u osoby ubezpieczonej ({who}): "
            f"{PERSON[filler(scenario)]} nie podlega ubezpieczeniu chorobowemu. Zakładamy, że "
            "dziecko przyjęliście razem."
        )
    if not insured:
        assumptions.append(
            "Ten urlop przysługuje osobie ubezpieczonej, która przyjęła dziecko. Gdy ubezpieczony "
            "jest drugi rodzic, oś pokaże urlop u niego."
        )
    if "supplementary" in shown:
        assumptions.append(
            "Uzupełniający urlop macierzyński liczymy jak przy urodzeniu (okna od dnia urodzenia "
            "dziecka), ale tylko z dni w szpitalu od dnia przyjęcia dziecka na wychowanie."
        )
    if "adoption-leave-other" in shown:
        assumptions.append(
            f"Kodeks pracy stosuje do tego urlopu odpowiednio zasady przejęcia urlopu "
            f"macierzyńskiego: {params.taken_in.handover_after_weeks.value} tygodni po porodzie "
            "czytamy jako tyle tygodni urlopu na warunkach urlopu macierzyńskiego."
        )
    if leave is not None and leave.used_days:
        assumptions.append(
            "Urlop wykorzystany w rodzinie zastępczej liczymy do dnia przed wystąpieniem do sądu "
            "o przysposobienie. Najkrótszego urlopu (9 tygodni) wtedy nie stosujemy: Kodeks pracy "
            "odejmuje wykorzystany urlop od pełnego wymiaru (art. 183 § 7)."
        )
    if foster_parental_used(scenario):
        assumptions.append(
            "Tygodnie urlopu rodzicielskiego wykorzystane w rodzinie zastępczej odejmujemy od "
            "części osoby, która bierze urlop; drugi rodzic zachowuje swoje tygodnie, dopóki "
            "starcza ich w puli."
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
            "Urlop rodzicielski pokazujemy tak, jakby osoba, która brała urlop na warunkach urlopu "
            "macierzyńskiego, wzięła całą swoją część od razu, a drugi rodzic swoje tygodnie "
            "zaraz potem. Rodzice mogą też korzystać "
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
