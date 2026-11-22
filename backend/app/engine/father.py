"""Guide section B (pages 7-8), the father, and the Labour Code behind it.

Applied after the mother's rules (section A), in this order:
1. Special situations (B.2; art. 180 § 6, § 10-§ 14): the mother has a certificate of inability
   to live independently, is in hospital, died, or abandoned the child. The father takes the
   rest of maternity leave (for a hospital stay: the part the stay lasts) earlier than after
   14 weeks: once the mother has used 8 weeks after the birth, after her death with no minimum.
   After abandoning the child the mother loses the rest of maternity leave, but not below 8 weeks
   after the birth (art. 182), whether or not the father can take it.
   A mother without sickness insurance (art. 180 § 15-16; ustawa art. 29 ust. 9): after her
   death, after she abandoned the child, or after the day her incapacity arose, the father has
   the part of maternity leave after that day, counted from the birth, with no 8-week minimum.
   Her stay in hospital is not among these cases.
2. Otherwise, taking over maternity leave (B.1; art. 180 § 4-5): after at least 14 weeks after
   the birth the mother leaves the rest to the father; his leave starts right after hers.
   In both cases the total length of maternity leave does not change (§ 14), so supplementary
   and parental leave stay where they were.
3. Paternity leave (B.4; art. 182³): 14 days, once or in 2 parts of at least 7 days, until the
   child completes 12 months of life; the number of children does not extend it, and it does not
   depend on the mother's insurance.
4. The father's parental leave (B.3; art. 182¹ᵃ § 4, § 6): 9 weeks that are his alone, drawn
   after the mother's share. When the mother was not insured on the day of birth, the father has
   the benefit for parental leave.
5. A father on a contract or with a business gets the benefit for these periods, not leave
   (guide pages 4-5), and the benefit needs sickness insurance: when nobody said how the father
   works, we assume he has it, as for the mother. For the mother's maternity leave he has it once
   he interrupted his work to look after the child (ustawa art. 29 ust. 3, 5-7, 9). Without a
   living child none of this applies.

Our readings, not settled by the materials (CLAUDE.md, open questions):
- "until the child completes 12 months of life" ends on the day before the first birthday;
- 8 weeks after the birth are 56 days with the day of birth as the first, so the father takes
  over from the 57th day at the earliest; a stay in hospital or a ruling of incapacity that
  starts earlier gives him the leave from the 57th day (a stay over by then gives nothing);
- a hospital stay runs from the day of admission to the day of discharge: the father takes the
  leave from the admission (not before the 57th day), the mother comes back the day after the
  discharge;
- with an uninsured mother, or after the mother died or abandoned the child, the father's
  parental leave leaves out the 9 weeks art. 182¹ᵃ § 4 keeps for the other parent; after she
  died or abandoned the child during her parental leave, the father has what is left of the
  pool once her days, but at least her 9 weeks, are taken out;
- after the mother's death (or once the father takes over after she abandoned the child) her
  lane ends: supplementary leave, which either parent may take, passes to the father;
- with an uninsured mother, "maternity leave" for art. 180 § 15 is the length of art. 180 § 1
  counted from the day of the birth (she had no leave before it).
"""

import datetime as dt

from app.engine.draft import DAY, WEEK, Draft, days_between, merge_sources
from app.engine.insurance import NOT_INSURED, Coverage, father_coverage
from app.engine.loss import Loss, maternity_end_after_loss
from app.engine.models import Marker, Scenario, ScenarioError, Segment, SourceRef
from app.engine.params import Params, Rule
from app.engine.parental import (
    deadline_marker,
    deadline_passed,
    parental_deadline,
    parental_table,
    parental_weeks,
)
from app.engine.wording import children_phrase, fmt, weeks_or_days

ESTIMATE = "Liczymy od przewidywanej daty porodu. Po porodzie oś przeliczy się od faktycznej daty."
WEEK_IS_7_DAYS = "Tydzień urlopu to 7 dni kalendarzowych."
MATERNITY_PARTS = ("maternity", "maternity-father", "maternity-resumed")
"""The pieces maternity leave after the birth is split into when the father takes part of it."""


def father_rules(
    draft: Draft,
    scenario: Scenario,
    params: Params,
    birth: dt.date,
    today: dt.date,
    cover: Coverage,
    loss: Loss | None,
) -> None:
    """Section B on top of the mother's timeline. `cover` is the mother's insurance."""
    father = father_coverage(scenario)
    covered = father not in NOT_INSURED
    child_lives = loss is None or not loss.none_survived
    mother_left = False
    if scenario.mother_event is not None:
        mother_left = _mother_event(draft, scenario, params, birth, today, cover, covered, loss)
    elif scenario.father_takes_over:
        _take_over(draft, scenario, params, birth, cover, covered, child_lives)
    if covered and child_lives and scenario.children_count is not None:
        paternity = _paternity(draft, scenario, params, birth, today)
        _parental(draft, scenario, params, birth, today, cover, paternity, mother_left)
        _insurance_lines(draft, scenario, params, father, cover)
    if not any(s.id in ("parental", "parental-father") for s in draft.segments):
        _drop_marker(draft, "parental-deadline")  # nobody left to take parental leave
    # The mother's lane first, as the rules built it; the father's in the order of time.
    mother = [s for s in draft.segments if s.lane != "father"]
    draft.segments = mother + sorted(
        (s for s in draft.segments if s.lane == "father"), key=lambda s: s.start
    )


def paternity_deadline(birth: dt.date, params: Params) -> dt.date:
    """The last day for paternity leave: the day before the child completes N months of life
    (our reading of "do ukończenia przez dziecko 12 miesięcy życia")."""
    year, month = divmod(birth.month - 1 + params.father.paternity_months.value, 12)
    try:
        completed = birth.replace(year=birth.year + year, month=month + 1)
    except ValueError:  # 29 February, 31st: the month is shorter, so the next month's first day
        completed = dt.date(birth.year + year + (month + 1) // 12, (month + 1) % 12 + 1, 1)
    return completed - DAY


def uninsured_maternity_end(
    scenario: Scenario, params: Params, birth: dt.date, loss: Loss | None
) -> dt.date | None:
    """Art. 180 § 15 with a mother who had no sickness insurance: the last day of maternity leave
    as art. 180 § 1 gives it, counted from the day of the birth (after a loss, by the children
    who live, art. 180¹). None until the number of children is known."""
    count = scenario.children_count
    if count is None:
        return None
    table = params.maternity.weeks_by_children.value

    def end_for(children: int) -> dt.date:
        return birth + table[min(children, len(table)) - 1] * WEEK - DAY

    if loss is not None:
        return maternity_end_after_loss(loss, params, birth, end_for)
    return end_for(count)


def interrupted_work_rule(scenario: Scenario, params: Params, cover: Coverage) -> Rule:
    """A father who is not an employee: the provision that gives him the maternity benefit for
    the mother's maternity leave once he interrupted his work to look after the child."""
    f = params.father
    event = scenario.mother_event
    if cover in NOT_INSURED:
        return f.special_uninsured_benefit
    if event is None:
        return f.interrupted_work_takeover
    return {
        "incapacity": f.interrupted_work_incapacity,
        "hospital": f.interrupted_work_hospital,
        "death": f.interrupted_work_death,
        "abandonment": f.interrupted_work_death,
    }[event.kind]


INTERRUPTED_WORK = (
    "Tata nie jest pracownikiem: zasiłek macierzyński za ten okres przysługuje mu, jeśli "
    "przerwał działalność zarobkową w celu sprawowania osobistej opieki nad dzieckiem."
)


# 1-2. Maternity leave: special situations, taking over.


def _take_over(
    draft: Draft,
    scenario: Scenario,
    params: Params,
    birth: dt.date,
    cover: Coverage,
    covered: bool,
    child_lives: bool,
) -> None:
    """Guide B.1: after at least 14 weeks after the birth the father takes the rest."""
    maternity = draft.segment("maternity")
    if maternity is None or cover in NOT_INSURED or not child_lives:
        return
    f = params.father
    minimum = f.takeover_after_weeks.value
    weeks = scenario.mother_weeks_before_takeover or minimum
    if weeks < minimum:
        raise ScenarioError(
            f"Mama musi wykorzystać co najmniej {minimum} tygodni urlopu macierzyńskiego po "
            "porodzie."
        )
    mother_end = birth + weeks * WEEK - DAY
    end = maternity.end
    if mother_end >= end:
        raise ScenarioError(
            f"Urlop macierzyński kończy się {fmt(end)}, więc po {weeks} tyg. po porodzie nie "
            "zostaje nic, co tata mógłby przejąć."
        )
    if not covered:
        return
    start = mother_end + DAY
    rule = [f.takeover_after_weeks.sources, f.takeover_starts_after.sources]
    _shorten_maternity(
        draft,
        params,
        maternity,
        mother_end,
        f"Mama wykorzystuje {weeks} tyg. urlopu macierzyńskiego po porodzie, do "
        f"{fmt(mother_end)}. Dalszą część, od {fmt(start)} do {fmt(end)}, przejmuje tata.",
        whole=end,
        sources=rule,
    )
    details = [
        f"Mama musi najpierw wykorzystać co najmniej {minimum} tygodni urlopu macierzyńskiego "
        "po porodzie.",
        "Łączny wymiar urlopu macierzyńskiego mamy i taty się nie zmienia.",
        WEEK_IS_7_DAYS,
    ]
    if not scenario.child_born:
        details.append(ESTIMATE)
    draft.segments.append(
        _father_maternity(
            params,
            start,
            end,
            f"Tata przejmuje dalszą część urlopu macierzyńskiego: od {fmt(start)} do {fmt(end)}. "
            "Jego urlop zaczyna się bezpośrednio po zakończeniu urlopu mamy.",
            details,
            rule,
        )
    )


def _mother_event(
    draft: Draft,
    scenario: Scenario,
    params: Params,
    birth: dt.date,
    today: dt.date,
    cover: Coverage,
    covered: bool,
    loss: Loss | None,
) -> bool:
    """Guide B.2: the father takes maternity leave over early. Returns True when the mother's
    lane ends here (her death, or the father taking over after she abandoned the child)."""
    event = scenario.mother_event
    assert event is not None
    if not scenario.child_born:
        raise ScenarioError(
            "Sytuację mamy po porodzie uwzględniamy, gdy dziecko już się urodziło. Podaj najpierw "
            "datę urodzenia."
        )
    if event.start < birth:
        raise ScenarioError(
            f"Data {fmt(event.start)} jest wcześniejsza niż data porodu ({fmt(birth)}). "
            "Sprawdź datę."
        )
    if event.kind in ("death", "abandonment") and event.start > today:
        raise ScenarioError(f"Data {fmt(event.start)} jest w przyszłości (dziś {fmt(today)}).")
    child_lives = loss is None or not loss.none_survived
    # Out of scope: a birth after which no child lives (see the assumptions).
    if not child_lives:
        return False
    if cover in NOT_INSURED:
        _uninsured_mother(draft, scenario, params, birth, loss, covered)
        return False
    maternity = draft.segment("maternity")
    if maternity is None:
        return False
    f = params.father
    after = f.special_after_weeks.value
    earliest = birth + after * WEEK
    whole = maternity.end
    match event.kind:
        case "incapacity" | "hospital":
            # Art. 180 § 6, § 10: only after 8 weeks of leave after the birth.
            start = max(event.start, earliest)
        case "death":
            start = event.start + DAY
        case "abandonment":
            start = max(event.start + DAY, earliest)
    applies = start <= whole
    personal = params.maternity.mother_personal_weeks.value
    personal_end = birth + personal * WEEK - DAY

    if event.kind == "death":
        # Whether or not the father can take anything, the mother's leave ends with her death;
        # the notes say when, so no warning that "her" leave is over.
        _end_mother_lane(draft, params, event.start, covered)
        draft.warnings = [w for w in draft.warnings if not w.startswith("Urlop macierzyński")]
        if event.start < whole:
            _shorten_maternity(
                draft,
                params,
                maternity,
                event.start,
                f"Urlop macierzyński mamy trwał do {fmt(event.start)}.",
                whole=whole if covered else None,
                sources=[f.special_death.sources],
            )
            _drop_marker(draft, "personal-weeks")
        if not covered or not applies:
            return True
        draft.segments.append(
            _father_maternity(
                params,
                start,
                whole,
                "Tacie przysługuje część urlopu macierzyńskiego przypadająca po dniu śmierci "
                f"mamy: od {fmt(start)} do {fmt(whole)}.",
                ["Łączny wymiar urlopu macierzyńskiego się nie zmienia.", WEEK_IS_7_DAYS],
                [f.special.sources, f.special_death.sources],
            )
        )
        return True

    if event.kind == "abandonment":
        # Art. 182: the mother loses the rest of maternity leave (not below 8 weeks after the
        # birth) and, through art. 180² § 7 and 182¹ᵍ, the rest of her later leave, whoever
        # takes it.
        _end_mother_lane(draft, params, start - DAY if applies else event.start, covered)
        if not applies:
            return True
        if not covered:
            _shorten_maternity(
                draft,
                params,
                maternity,
                start - DAY,
                f"Mama porzuciła dziecko {fmt(event.start)}, więc część urlopu macierzyńskiego "
                f"po tym dniu jej nie przysługuje. Urlop trwa do {fmt(start - DAY)}.",
                whole=None,
                sources=[f.abandonment_mother_loses.sources],
            )
            if start <= personal_end:
                _drop_marker(draft, "personal-weeks")
            return True
    elif not covered:
        return False
    if event.kind == "hospital" and event.end is not None and event.end < start:
        return False  # the stay ended before the mother used 8 weeks: nothing to interrupt
    if not applies:
        return False

    early = (
        f"Wcześniej niż po {f.takeover_after_weeks.value} tygodniach tata może przejąć urlop "
        f"w tej sytuacji, gdy mama wykorzystała po porodzie co najmniej {after} tygodni urlopu "
        "macierzyńskiego."
    )
    waits = (
        [
            f"Mama musi najpierw wykorzystać po porodzie co najmniej {after} tygodni urlopu "
            f"macierzyńskiego, dlatego urlop taty zaczyna się {fmt(start)}."
        ]
        if start > (event.start + DAY if event.kind == "abandonment" else event.start)
        else []
    )
    end = whole
    resumed: Segment | None = None
    mother_sources: list[list[SourceRef]] = []
    match event.kind:
        case "incapacity":
            rule = [f.special.sources, f.special_incapacity.sources]
            mother = (
                f"Mama wykorzystuje urlop macierzyński do {fmt(start - DAY)}. Ma orzeczenie "
                "o niezdolności do samodzielnej egzystencji, więc może zrezygnować z pozostałej "
                "części, którą wykorzystuje tata."
            )
            summary = (
                "Mama ma orzeczenie o niezdolności do samodzielnej egzystencji i rezygnuje "
                "z pozostałej części urlopu macierzyńskiego. Wykorzystuje ją tata: od "
                f"{fmt(start)} do {fmt(end)}."
            )
            details = [early, *waits]
        case "hospital":
            rule = [f.special.sources, f.special_hospital.sources]
            if event.end is not None and event.end < whole:
                end = event.end
                resumed = _resumed(params, end + DAY, whole)
            mother = (
                f"Mama wykorzystuje urlop macierzyński do {fmt(start - DAY)}, potem przerywa go "
                "na okres pobytu w szpitalu."
            )
            summary = (
                "Mama przerywa urlop macierzyński na okres pobytu w szpitalu. Tę część urlopu "
                f"wykorzystuje tata: od {fmt(start)} do {fmt(end)}."
            )
            stay = (
                f"Pobyt mamy w szpitalu: od {fmt(event.start)} do {fmt(event.end)}."
                if event.end is not None
                else "Mama jest jeszcze w szpitalu, więc urlop taty pokazujemy do końca urlopu "
                "macierzyńskiego. Gdy mama wyjdzie ze szpitala, wróci na urlop, a oś się "
                "przeliczy."
            )
            details = [early, *waits, stay]
        case _:
            rule = [f.special.sources, f.special_abandonment.sources]
            mother_sources = [f.abandonment_mother_loses.sources]
            mother = f"Mama wykorzystuje urlop macierzyński do {fmt(start - DAY)}."
            summary = (
                "Tacie przysługuje część urlopu macierzyńskiego przypadająca po dniu porzucenia "
                f"dziecka: od {fmt(start)} do {fmt(end)}."
            )
            details = waits
    _shorten_maternity(
        draft, params, maternity, start - DAY, mother, whole=whole, sources=rule + mother_sources
    )
    if resumed is not None:
        index = next(i for i, s in enumerate(draft.segments) if s.id == "maternity")
        draft.segments.insert(index + 1, resumed)
    if start <= personal_end:
        _drop_marker(draft, "personal-weeks")
    draft.segments.append(
        _father_maternity(
            params,
            start,
            end,
            summary,
            [
                *details,
                "Łączny wymiar urlopu macierzyńskiego mamy i taty się nie zmienia.",
                WEEK_IS_7_DAYS,
            ],
            rule,
        )
    )
    return event.kind == "abandonment"


UNINSURED_AFTER = {
    "death": "po dniu śmierci mamy",
    "abandonment": "po dniu porzucenia przez nią dziecka",
    "incapacity": "po dniu powstania jej niezdolności do samodzielnej egzystencji",
}
"""Art. 180 § 15: the part of maternity leave the father has, after which day."""


def _uninsured_mother(
    draft: Draft,
    scenario: Scenario,
    params: Params,
    birth: dt.date,
    loss: Loss | None,
    covered: bool,
) -> None:
    """Art. 180 § 15-16, ustawa art. 29 ust. 9: the mother had no sickness insurance and died,
    abandoned the child, or cannot look after it with a ruling of incapacity. The father has the
    part of maternity leave after that day, with no 8-week minimum."""
    event = scenario.mother_event
    assert event is not None
    end = uninsured_maternity_end(scenario, params, birth, loss)
    if event.kind == "hospital" or end is None or not covered:
        return
    start = event.start + DAY
    if start > end:
        return
    f = params.father
    count = scenario.children_count
    assert count is not None
    weeks = params.maternity.weeks_by_children.value[
        min(count, len(params.maternity.weeks_by_children.value)) - 1
    ]
    whole = (
        f"Urlop macierzyński liczymy od dnia porodu: {weeks} tyg. przy urodzeniu "
        f"{children_phrase(count)}, do {fmt(end)}."
        if loss is None
        else f"Urlop macierzyński liczymy od dnia porodu, do {fmt(end)}."
    )
    draft.segments.append(
        _father_maternity(
            params,
            start,
            end,
            "Mama nie podlegała ubezpieczeniu chorobowemu. Tacie przysługuje część urlopu "
            f"macierzyńskiego przypadająca {UNINSURED_AFTER[event.kind]}: od {fmt(start)} do "
            f"{fmt(end)}.",
            [whole, WEEK_IS_7_DAYS],
            [f.special_uninsured.sources, params.maternity.weeks_by_children.sources],
            cap=False,
        )
    )


def _shorten_maternity(
    draft: Draft,
    params: Params,
    maternity: Segment,
    end: dt.date,
    summary: str,
    *,
    whole: dt.date | None,
    sources: list[list[SourceRef]],
) -> None:
    """The mother's maternity leave now ends on `end`; `whole` is where it ended before, when the
    father uses the rest."""
    together = (
        [
            f"Razem z częścią taty urlop macierzyński trwa po porodzie do {fmt(whole)}: łączny "
            "wymiar się nie zmienia."
        ]
        if whole is not None
        else []
    )
    draft.replace(
        "maternity",
        maternity.model_copy(
            update={
                "end": end,
                "days": days_between(maternity.start, end),
                "summary": summary,
                "details": [*together, *maternity.details],
                "sources": merge_sources(
                    maternity.sources,
                    *sources,
                    params.father.total_cap.sources if whole is not None else [],
                ),
            }
        ),
    )


def _father_maternity(
    params: Params,
    start: dt.date,
    end: dt.date,
    summary: str,
    details: list[str],
    sources: list[list[SourceRef]],
    *,
    cap: bool = True,
) -> Segment:
    """The father's part of maternity leave. `cap`: the total length of maternity leave does not
    change (art. 180 § 14, not for an uninsured mother, § 15)."""
    f = params.father
    return Segment(
        id="maternity-father",
        lane="father",
        tone="leave",
        title="Urlop macierzyński taty",
        start=start,
        end=end,
        days=days_between(start, end),
        summary=summary,
        details=details,
        sources=merge_sources(
            f.benefit.sources,
            *sources,
            f.total_cap.sources if cap else [],
            params.rules.week_is_7_days.sources,
        ),
    )


def _resumed(params: Params, start: dt.date, end: dt.date) -> Segment:
    """After her hospital stay the mother goes back to the leave she interrupted (art. 180 § 10:
    she interrupts it "na okres pobytu")."""
    return Segment(
        id="maternity-resumed",
        lane="mother",
        tone="leave",
        title="Urlop macierzyński mamy — dalsza część",
        start=start,
        end=end,
        days=days_between(start, end),
        summary=(
            f"Po wyjściu ze szpitala mama wraca na urlop macierzyński: od {fmt(start)} do "
            f"{fmt(end)}."
        ),
        details=[
            "Urlop był przerwany na okres pobytu mamy w szpitalu; w tym czasie wykorzystywał go "
            "tata.",
            "Łączny wymiar urlopu macierzyńskiego mamy i taty się nie zmienia.",
            WEEK_IS_7_DAYS,
        ],
        sources=merge_sources(
            params.father.special_hospital.sources,
            params.father.total_cap.sources,
            params.rules.week_is_7_days.sources,
        ),
    )


def _end_mother_lane(draft: Draft, params: Params, last: dt.date, to_father: bool) -> None:
    """The mother takes no leave after `last`. Her later periods go; one under way ends on
    `last` (the Labour Code applies art. 180 § 6-17 to supplementary and parental leave too).
    Supplementary leave, which either parent may take, passes to the father when he can take
    it. Maternity leave itself is shortened by the caller."""
    kept = []
    for segment in draft.segments:
        if segment.lane != "mother" or segment.id == "maternity" or segment.end <= last:
            kept.append(segment)
        elif segment.start <= last:
            kept.append(
                segment.model_copy(
                    update={
                        "end": last,
                        "days": days_between(segment.start, last),
                        "summary": f"{segment.title.split(' —')[0]} mamy: do {fmt(last)}.",
                        "details": [],
                        "sources": merge_sources(segment.sources, params.loss.other_leaves.sources),
                    }
                )
            )
        elif segment.id == "supplementary" and to_father:
            s = params.supplementary
            kept.append(
                segment.model_copy(
                    update={
                        "lane": "father",
                        "summary": (
                            "Uzupełniający urlop macierzyński przysługuje mamie albo tacie. Po "
                            f"urlopie macierzyńskim tata może wziąć {segment.days // 7} tyg.: "
                            "tydzień za każdy tydzień pobytu dziecka w szpitalu."
                        ),
                        "sources": merge_sources(segment.sources, s.one_parent.sources),
                    }
                )
            )
    draft.segments = kept


def _drop_marker(draft: Draft, marker_id: str) -> None:
    draft.markers = [m for m in draft.markers if m.id != marker_id]


# 3. Paternity leave.


def _paternity(
    draft: Draft, scenario: Scenario, params: Params, birth: dt.date, today: dt.date
) -> Segment | None:
    """Guide B.4: 14 days until the child completes 12 months of life. Drawn whole from the
    birth (from today, once the child is born); when and in how many parts is his choice."""
    f = params.father
    born = scenario.child_born is True
    deadline = paternity_deadline(birth, params)
    months = f.paternity_months.value
    if deadline < today:
        draft.warnings.append(
            f"Czas na urlop ojcowski minął {fmt(deadline)}: można go wykorzystać do ukończenia "
            f"przez dziecko {months} miesięcy życia."
        )
        return None
    draft.markers.append(
        Marker(
            id="paternity-deadline",
            lane="child",
            label="Ojcowski najpóźniej do",
            title="Koniec czasu na urlop ojcowski",
            date=deadline,
            summary=(
                f"Urlop ojcowski można wykorzystać do ukończenia przez dziecko {months} miesięcy "
                "życia. Potem prawo do niego wygasa."
            ),
            details=[
                "Przyjmujemy, że ostatnim dniem jest dzień przed pierwszymi urodzinami dziecka."
            ]
            + ([] if born else ["Liczymy od przewidywanej daty porodu."]),
            sources=merge_sources(f.paternity_months.sources, f.paternity_expires.sources),
        )
    )
    days = f.paternity_days.value
    shortest = f.paternity_min_part_days.value
    start = max(birth, today) if born else birth
    # He cannot be on paternity leave and on his part of maternity leave at once: shown right
    # after that part (paternity leave can be used any time until the deadline).
    after_his_part = False
    for part in (s for s in draft.segments if s.id == "maternity-father"):
        if part.start <= start + (days - 1) * DAY and part.end >= start:
            start, after_his_part = part.end + DAY, True
    if start > deadline:
        return None
    end = min(start + (days - 1) * DAY, deadline)
    left = days_between(start, end)
    if left < shortest:
        draft.warnings.append(
            f"Do końca czasu na urlop ojcowski ({fmt(deadline)}) zostało {left} "
            f"{'dzień' if left == 1 else 'dni'}, a żadna część tego urlopu nie może być krótsza "
            f"niż {shortest} dni."
        )
        return None
    if after_his_part:
        when = "po jego części urlopu macierzyńskiego"
    elif not born:
        when = "od przewidywanej daty porodu"
    elif start == birth:
        when = "od dnia porodu"
    else:
        when = "od dziś"
    shorter = (
        f" Do końca tego czasu zostało {left} dni, więc pokazujemy {left} dni."
        if left < days
        else ""
    )
    details = [
        f"Można go wykorzystać jednorazowo ({days} dni) albo w {f.paternity_parts.value} "
        f"częściach po co najmniej {shortest} dni.",
        "Liczba dzieci urodzonych przy jednym porodzie nie wydłuża urlopu.",
        f"Jeśli tata nie wykorzysta urlopu do {fmt(deadline)}, prawo do niego wygasa.",
        "To wyłączne prawo taty. Przysługuje także wtedy, gdy mama nie podlega ubezpieczeniu "
        "chorobowemu.",
    ]
    if not born:
        details.append(ESTIMATE)
    segment = Segment(
        id="paternity",
        lane="father",
        tone="option",
        title="Urlop ojcowski — do wyboru",
        start=start,
        end=end,
        days=left,
        summary=(
            f"Urlop ojcowski taty to najwyżej {days} dni kalendarzowych, wliczając weekendy. "
            f"Można go wykorzystać do {fmt(deadline)}; pokazujemy go {when}.{shorter}"
        ),
        details=details,
        sources=merge_sources(
            f.paternity_days.sources,
            f.paternity_parts.sources,
            f.paternity_children.sources,
            f.paternity_months.sources,
            f.paternity_expires.sources,
            f.paternity_who.sources,
        ),
    )
    draft.segments.append(segment)
    return segment


# 4. The father's parental leave.


def _parental(
    draft: Draft,
    scenario: Scenario,
    params: Params,
    birth: dt.date,
    today: dt.date,
    cover: Coverage,
    paternity: Segment | None,
    mother_left: bool,
) -> None:
    """Guide B.3: his 9 weeks after the mother's share. With an uninsured mother, or after the
    mother's lane ended, the most one parent can use; after the mother died or abandoned the
    child during her parental leave, what is left of the pool once her days (at least her 9
    weeks, art. 182¹ᵃ § 4) are taken out. For a born child not before today; after his own
    leave, and after paternity leave when they would overlap (two options of his are not drawn
    over each other)."""
    p = params.parental
    f = params.father
    born = scenario.child_born is True
    total, one_parent = parental_weeks(scenario, params)
    exclusive = p.exclusive_weeks.value
    deadline = parental_deadline(birth, params)
    mothers = draft.segment("parental")
    later = scenario.mother_parental_after_first_year is True and not mother_left
    table = parental_table(scenario, params)
    used = 0  # days of parental leave the mother used before her lane ended
    his = [s.end + DAY for s in draft.segments if s.lane == "father"]
    if cover in NOT_INSURED:
        if deadline < today:
            draft.warnings.append(deadline_passed(deadline, params))
            return
        draft.markers.append(deadline_marker(birth, born, params))
        length = one_parent * 7
        if paternity is not None:
            start = paternity.end + DAY
        else:
            start = max(birth + DAY, today) if born else birth + DAY
        start = max([start, *his])  # after his part of maternity leave (art. 180 § 15)
    elif mother_left:
        if deadline < today:
            return
        used = mothers.days if mothers is not None else 0
        length = total * 7 - max(used, exclusive * 7)
        ids = (*MATERNITY_PARTS, "supplementary", "parental")
        start = max(s.end for s in draft.segments if s.id in ids) + DAY
    elif mothers is not None:
        length = exclusive * 7
        start = mothers.end + DAY
        if later:
            # The mother's share waits for the first birthday: his weeks right after maternity
            # (and supplementary) leave, not after her share.
            ids = (*MATERNITY_PARTS, "supplementary")
            start = max((s.end for s in draft.segments if s.id in ids), default=birth - DAY) + DAY
    else:
        return
    if born:
        start = max(start, today)
    if (
        paternity is not None
        and paternity.end >= start
        and paternity.start <= start + (length - 1) * DAY
    ):
        start = paternity.end + DAY
    if start > deadline or length <= 0:
        return
    full_end = start + (length - 1) * DAY
    end = min(full_end, deadline)
    shown = weeks_or_days(days_between(start, end))
    sources: list[list[SourceRef]]
    if cover in NOT_INSURED:
        rule = (
            "Mama nie była ubezpieczona w dniu porodu, a zasiłek macierzyński za okres urlopu "
            "rodzicielskiego przysługuje wtedy tacie."
            if born
            else "Jeśli mama nie będzie ubezpieczona w dniu porodu, zasiłek macierzyński za okres "
            "urlopu rodzicielskiego przysługuje tacie."
        )
        summary = f"{rule} Pokazujemy {shown}: od {fmt(start)} do {fmt(end)}."
        sources = [f.parental_uninsured_mother.sources, table.sources, p.exclusive_weeks.sources]
    elif not mother_left:
        where = (
            "Mama nie bierze urlopu rodzicielskiego w pierwszym roku życia dziecka, więc urlop "
            f"taty pokazujemy zaraz po urlopie macierzyńskim: {shown}, od {fmt(start)} do "
            f"{fmt(end)}."
            if later
            else "Rodzice mogą korzystać z urlopu jednocześnie albo naprzemiennie, a tata może "
            f"też wziąć go po mamie — tak go tu pokazujemy: {shown}, od {fmt(start)} do "
            f"{fmt(end)}."
        )
        summary = (
            f"Tata ma {exclusive} tyg. urlopu rodzicielskiego wyłącznie dla siebie: nie można "
            f"ich przenieść na mamę. Pozostała część z {total} tyg. jest wspólna. {where}"
        )
        sources = [
            f.parental_together.sources,
            p.exclusive_weeks.sources,
            table.sources,
            p.joint.sources,
        ]
    else:
        summary = (
            f"Urlop rodzicielski może wykorzystać tata. Pokazujemy {shown}: od {fmt(start)} do "
            f"{fmt(end)}."
        )
        sources = [
            f.parental_together.sources,
            table.sources,
            p.exclusive_weeks.sources,
            p.joint.sources,
        ]
    details = [
        f"Urlop jest udzielany jednorazowo albo w nie więcej niż {p.max_parts.value} częściach, "
        f"najpóźniej do {fmt(deadline)}: to koniec roku kalendarzowego, w którym dziecko kończy "
        f"{p.deadline_age.value} lat."
    ]
    most = weeks_or_days(length)
    most += "" if most.endswith(".") else "."  # "32 tyg." ends the sentence itself
    if cover not in NOT_INSURED and not mother_left:
        details.append(
            f"Gdy rodzice korzystają z urlopu jednocześnie, razem nie mogą przekroczyć {total} tyg."
        )
    elif used > exclusive * 7:
        details.append(
            f"Rodzice mają razem do {total} tyg. Mama wykorzystała {weeks_or_days(used)} urlopu "
            f"rodzicielskiego, więcej niż {exclusive} tyg., których nie można przenieść na "
            f"drugiego z rodziców. Dlatego pokazujemy najwięcej {most}"
        )
    else:
        details.append(
            f"Rodzice mają razem do {total} tyg., a {exclusive} tyg. z nich należy wyłącznie do "
            "każdego z rodziców i nie można ich przenieść na drugiego. Dlatego pokazujemy "
            f"najwięcej {most}"
        )
    if end < full_end:
        details.append(f"Urlop musi się skończyć do {fmt(deadline)}, dlatego pokazujemy go krócej.")
    details.append(WEEK_IS_7_DAYS)
    if not born:
        details.append(ESTIMATE)
    draft.segments.append(
        Segment(
            id="parental-father",
            lane="father",
            tone="option",
            title="Urlop rodzicielski taty — do wyboru",
            start=start,
            end=end,
            days=days_between(start, end),
            summary=summary,
            details=details,
            sources=merge_sources(
                *sources,
                p.max_parts.sources,
                p.week_is_7_days.sources,
                params.rules.week_is_7_days.sources,
            ),
        )
    )


# 5. The benefit, not leave; insurance assumed.


def _insurance_lines(
    draft: Draft, scenario: Scenario, params: Params, father: Coverage, cover: Coverage
) -> None:
    """Every period on the father's lane says when he only gets the benefit, and when we assume
    his sickness insurance. His part of maternity leave, for a father who is not an employee,
    also says the benefit needs him to interrupt his work (ustawa art. 29 ust. 3, 5-7, 9)."""
    b = params.benefit
    lines = []
    sources = []
    if father in ("unknown-work", "unknown-voluntary"):
        lines.append(
            "Zasiłek macierzyński jest wypłacany osobom podlegającym ubezpieczeniu chorobowemu. "
            "Na razie zakładamy, że tata mu podlega."
        )
        sources.append(b.paid_to_the_insured.sources)
    not_employee = scenario.fathers_work in ("contract", "business")
    if not_employee:
        lines.append(
            "Tata nie jest pracownikiem, więc nie dostaje urlopu: ma prawo do zasiłku "
            "macierzyńskiego za okres odpowiadający urlopowi, na tych samych zasadach co do "
            "wymiaru."
        )
        sources += [b.non_employees.sources, b.same_rules_for_non_employees.sources]
    if not lines:
        return
    interrupted = interrupted_work_rule(scenario, params, cover).sources

    def with_lines(segment: Segment) -> Segment:
        added, cited = lines, sources
        if not_employee and segment.id == "maternity-father":
            added, cited = [*lines, INTERRUPTED_WORK], [*sources, interrupted]
        return segment.model_copy(
            update={
                "details": [*segment.details, *added],
                "sources": merge_sources(segment.sources, *cited),
            }
        )

    draft.segments = [
        with_lines(segment) if segment.lane == "father" else segment for segment in draft.segments
    ]
