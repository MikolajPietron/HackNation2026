"""The case explanation for a child taken in for upbringing (guide section D, pages 8-9).

Same order as for a birth (CLAUDE.md, "Wyjaśnianie przypadku"): the situation, the right and
whose it is, the options and reliefs and why, what we computed. Dates are read from the finished
timeline; every legal claim quotes its source.
"""

import datetime as dt

from app.engine.adoption import (
    PERSON,
    TakenInLeave,
    age_limit,
    birthday,
    children_taken_in,
    cover_of,
    filler,
    foster_leave_used,
    foster_parental_used,
    kind_params,
    limit_reached,
    other,
    parental_deadline,
    parental_total,
    paternity_barred,
    paternity_deadline,
    taken_in_leave,
    taken_in_supplementary,
    taker,
    work_of,
)
from app.engine.adoption_applications import TAKEN_IN_REQUEST, taken_in_application_notes
from app.engine.draft import DAY, merge_sources
from app.engine.insurance import NOT_INSURED, father_coverage
from app.engine.models import CaseNote, Marker, Scenario, Segment, SourceRef, Timeline
from app.engine.params import Params
from app.engine.supplementary import describe_case
from app.engine.wording import long_date, multiples, weeks_or_days

_WHO = {
    "foster": "przyjęła dziecko na wychowanie jako rodzina zastępcza niezawodowa",
    "adoption": "przyjęła dziecko i wystąpiła do sądu o wszczęcie postępowania w sprawie "
    "przysposobienia",
}
_WORK = {"contract": "umowie zlecenia", "business": "własnej działalności gospodarczej"}


def taken_in_notes(scenario: Scenario, timeline: Timeline, params: Params) -> list[CaseNote]:
    leave = taken_in_leave(scenario, params)
    notes = [_situation(scenario, timeline), _right(scenario, params)]
    too_old = limit_reached(scenario, params) is not None  # the "insurance" point says why
    if cover_of(scenario, taker(scenario)) not in NOT_INSURED and not too_old:
        optional = [
            _leave(scenario, params, leave),
            _after_foster(scenario, params, leave),
            _minimum(scenario, params, leave),
            _school(scenario, params, leave),
            _start(scenario, timeline, params),
            _handover(scenario, timeline, params),
            _supplementary(scenario, timeline, params),
            _parental(scenario, timeline, params, leave),
            _more_children(scenario, timeline, params),
            _za_zyciem(scenario, timeline, params, leave),
        ]
        notes += [note for note in optional if note is not None]
    paternity = _paternity(scenario, timeline, params)
    if paternity is not None:
        notes.append(paternity)
    notes.append(_computed(scenario, timeline, params, leave))
    # What to file and by when, who pays, the protection (adoption_applications.py).
    return notes + taken_in_application_notes(scenario, timeline, params)


def _segment(timeline: Timeline, segment_id: str) -> Segment | None:
    return next((s for s in timeline.segments if s.id == segment_id), None)


def _marker(timeline: Timeline, marker_id: str) -> Marker | None:
    return next((m for m in timeline.markers if m.id == marker_id), None)


def _situation(scenario: Scenario, timeline: Timeline) -> CaseNote:
    kind = "adopcja" if scenario.taken_in == "adoption" else "rodzina zastępcza"
    birth = scenario.birth_date
    count = scenario.children_count or 1
    born = ""
    if birth is not None:
        whose = "Najmłodsze dziecko" if count > 1 else "Dziecko"
        born = f" {whose} urodziło się {long_date(birth)}."
    return CaseNote(
        id="situation",
        kind="situation",
        title=f"Przyjęcie dziecka na wychowanie: {kind}",
        text=(
            f"Liczymy od dnia przyjęcia dziecka: {long_date(timeline.birth_date)}, a nie od "
            f"porodu.{born} Od wieku dziecka zależy, jak długo trwa urlop."
        ),
    )


def _right(scenario: Scenario, params: Params) -> CaseNote:
    """Who has the right (guide D) and whether the person who takes the leave is insured."""
    t = params.taken_in
    b = params.benefit
    role = taker(scenario)
    who = PERSON[role]
    kind = kind_params(scenario.taken_in or "foster", params)
    who_took = _WHO[scenario.taken_in or "foster"]
    rule = f"Zasiłek macierzyński przysługuje osobie ubezpieczonej, która {who_took}."
    base = [t.insured.sources, kind.who.sources, t.benefit.sources]
    if role != filler(scenario):
        # The person filling in has no sickness insurance; the other parent took the child in
        # too and has it, so the leave is theirs.
        rule = (
            "Mama nie podlega ubezpieczeniu chorobowemu, więc oś pokazuje urlop taty, który "
            "przyjął dziecko razem z nią. "
            if role == "father"
            else "Tata nie podlega ubezpieczeniu chorobowemu, więc oś pokazuje urlop mamy, która "
            "przyjęła dziecko razem z nim. "
        ) + rule
        base.append(b.paid_to_the_insured.sources)
    work = _WORK.get(work_of(scenario, role) or "", "")
    reached = limit_reached(scenario, params)
    if reached is not None:
        return _too_old(scenario, params, reached)
    match cover_of(scenario, role):
        case "obligatory":
            return CaseNote(
                id="insurance",
                kind="right",
                title=f"{who.capitalize()} ma prawo do zasiłku macierzyńskiego",
                text=f"{rule} Umowa o pracę daje obowiązkowe ubezpieczenie chorobowe.",
                sources=merge_sources(*base, b.obligatory_insurance.sources),
            )
        case "voluntary":
            return CaseNote(
                id="insurance",
                kind="right",
                title=f"{who.capitalize()} ma prawo do zasiłku macierzyńskiego",
                text=(
                    f"{rule} Przy {work} ubezpieczenie chorobowe jest dobrowolne, a {who} jest "
                    "do niego zgłoszona. Kto nie jest pracownikiem, nie dostaje urlopu: ma prawo "
                    "do zasiłku za okres odpowiadający urlopowi, na tych samych zasadach co do "
                    "wymiaru."
                    if role == "mother"
                    else f"{rule} Przy {work} ubezpieczenie chorobowe jest dobrowolne, a {who} "
                    "jest do niego zgłoszony. Kto nie jest pracownikiem, nie dostaje urlopu: ma "
                    "prawo do zasiłku za okres odpowiadający urlopowi, na tych samych zasadach co "
                    "do wymiaru."
                ),
                sources=merge_sources(
                    *base,
                    b.voluntary_insurance.sources,
                    b.non_employees.sources,
                    b.same_rules_for_non_employees.sources,
                ),
            )
        case "unknown-voluntary":
            return CaseNote(
                id="insurance",
                kind="right",
                title="Zasiłek macierzyński: potrzebne ubezpieczenie chorobowe",
                text=(
                    f"{rule} Przy {work} ubezpieczenie chorobowe jest dobrowolne, więc trzeba "
                    "ustalić, czy jest się do niego zgłoszonym. Na razie oś zakłada, że tak."
                ),
                sources=merge_sources(*base, b.voluntary_insurance.sources),
            )
        case "unknown-work":
            return CaseNote(
                id="insurance",
                kind="right",
                title="Zasiłek macierzyński: potrzebne ubezpieczenie chorobowe",
                text=f"{rule} Na razie oś zakłada, że {who} podlega ubezpieczeniu chorobowemu.",
                sources=merge_sources(*base, b.paid_to_the_insured.sources),
            )
        case _:
            why = (
                f"Przy {work} ubezpieczenie chorobowe jest dobrowolne, a {who} nie jest do niego "
                "zgłoszon" + ("a." if role == "mother" else "y.")
                if work
                else f"Z odpowiedzi wynika, że {who} nie pracuje, więc nie ma umowy ani "
                "działalności, z której wynikałoby ubezpieczenie chorobowe."
            )
            return CaseNote(
                id="insurance",
                kind="risk",
                title="Zasiłek macierzyński wymaga ubezpieczenia chorobowego",
                text=(
                    f"{rule} {why} Jeśli ubezpieczony jest drugi rodzic, "
                    f"{PERSON[other(role)]}, zacznij wywiad jako on."
                ),
                sources=merge_sources(
                    *base,
                    b.paid_to_the_insured.sources,
                    b.obligatory_insurance.sources,
                    b.voluntary_insurance.sources,
                ),
            )


def _too_old(scenario: Scenario, params: Params, reached: dt.date) -> CaseNote:
    """The child had reached the age limit on the day of taking in: neither the benefit (ustawa
    art. 29 ust. 1 pkt 2-3) nor the leave (art. 183 § 1, § 1¹) is due."""
    kind = kind_params(scenario.taken_in or "foster", params)
    limit = age_limit(scenario, params)
    adoption = scenario.taken_in == "adoption"
    rule = (
        "Zasiłek macierzyński przysługuje osobie ubezpieczonej, która przyjęła na wychowanie "
        "dziecko w wieku do 14 lat i wystąpiła do sądu opiekuńczego w sprawie jego "
        "przysposobienia."
        if adoption
        else "Zasiłek macierzyński przysługuje osobie ubezpieczonej, która przyjęła na wychowanie "
        "w ramach rodziny zastępczej (innej niż zawodowa) dziecko w wieku do 7 lat, a gdy wobec "
        "dziecka podjęto decyzję o odroczeniu obowiązku szkolnego — do 10 lat."
    )
    taken = scenario.taken_in_on
    assert taken is not None
    return CaseNote(
        id="insurance",
        kind="risk",
        title=f"Zasiłek nie przysługuje: dziecko skończyło {limit.age} lat przed przyjęciem",
        text=(
            f"{rule} Urlop na warunkach urlopu macierzyńskiego też przysługuje nie dłużej niż do "
            f"ukończenia przez dziecko {limit.age} lat. Dziecko skończyło {limit.age} lat "
            f"{long_date(reached)}, a zostało przyjęte {long_date(taken)}, więc ani zasiłek, ani "
            "ten urlop nie przysługują."
        ),
        sources=merge_sources(kind.benefit_age.sources, limit.sources),
    )


def _leave(scenario: Scenario, params: Params, leave: TakenInLeave | None) -> CaseNote | None:
    if leave is None or leave.used_up or leave.too_old:
        return None
    t = params.taken_in
    kind = kind_params(scenario.taken_in or "foster", params)
    limit = age_limit(scenario, params)
    count = scenario.children_count or 1
    phrase = "przyjęciu" if count == 1 else "jednoczesnym przyjęciu"
    here = ""
    sources = [t.leave.sources, kind.weeks_by_children.sources, limit.sources]
    if leave.cut and not leave.minimum and not leave.used_days and leave.limit is not None:
        here = (
            f" Dziecko kończy {limit.age} lat {long_date(leave.limit)}, więc urlop trwa "
            f"{weeks_or_days(leave.days)}."
        )
    return CaseNote(
        id="taken-in-leave",
        kind="right",
        # What is on the timeline; the length by the number of children is in the text.
        title=f"Urlop na warunkach urlopu macierzyńskiego: {weeks_or_days(leave.days)}",
        text=(
            "To odpowiednik urlopu macierzyńskiego przy przyjęciu dziecka na wychowanie. Przy "
            f"{phrase} {children_taken_in(count)} trwa {leave.weeks} tyg., nie dłużej jednak "
            f"niż do ukończenia przez dziecko {limit.age} lat.{here}"
        ),
        sources=merge_sources(*sources),
    )


def _minimum(scenario: Scenario, params: Params, leave: TakenInLeave | None) -> CaseNote | None:
    """§ 3: taken in under the age limit, at least 9 weeks."""
    if leave is None or not leave.minimum or leave.limit is None:
        return None
    t = params.taken_in
    limit = age_limit(scenario, params)
    return CaseNote(
        id="taken-in-minimum",
        kind="relief",
        title=f"Co najmniej {t.minimum_weeks.value} tygodni urlopu",
        text=(
            f"Dziecko kończy {limit.age} lat {long_date(leave.limit)}, więc pełny urlop by się "
            f"nie zmieścił. Kto przyjął dziecko przed tym wiekiem, ma prawo do "
            f"{t.minimum_weeks.value} tygodni urlopu na warunkach urlopu macierzyńskiego."
        ),
        sources=t.minimum_weeks.sources,
    )


def _after_foster(
    scenario: Scenario, params: Params, leave: TakenInLeave | None
) -> CaseNote | None:
    """§ 7-§ 8: adoption after foster care, less the leave used as a foster family."""
    used, parental = foster_leave_used(scenario), foster_parental_used(scenario)
    if leave is None or not (used or parental):
        return None
    t = params.taken_in
    parts = [
        "Dziecko było najpierw w rodzinie zastępczej, a potem wystąpiliście o przysposobienie."
    ]
    sources = []
    if used:
        rule = (
            f"Urlop na warunkach urlopu macierzyńskiego przysługuje wtedy w wymiarze "
            f"{leave.weeks} tyg. obniżonym o urlop wykorzystany jako rodzina zastępcza: "
            f"{used} dni"
        )
        if leave.used_up:
            parts.append(f"{rule}, więc z tego urlopu nic już nie zostaje.")
        else:
            parts.append(f"{rule}, więc zostaje {weeks_or_days(leave.weeks * 7 - used)}.")
        sources.append(t.after_foster_leave.sources)
    if parental:
        total = parental_total(scenario, params, leave)
        parts.append(
            f"Urlop rodzicielski przysługuje w wymiarze do {total.value} tyg. obniżonym "
            f"o {parental} tyg. wykorzystane w rodzinie zastępczej."
        )
        sources += [t.after_foster_parental.sources, total.sources]
    return CaseNote(
        id="after-foster",
        kind="risk" if leave.used_up else "right",
        title="Najpierw rodzina zastępcza: urlop krótszy o wykorzystaną część",
        text=" ".join(parts),
        sources=merge_sources(*sources),
    )


def _handover(scenario: Scenario, timeline: Timeline, params: Params) -> CaseNote | None:
    """§ 2 with art. 180 § 4: the other parent takes the rest of the leave."""
    if not scenario.taken_in_handover:
        return None
    own = _segment(timeline, "adoption-leave")
    if own is None:
        return None
    t = params.taken_in
    role = taker(scenario)
    partner = other(role)
    rule = (
        f"Po wykorzystaniu co najmniej {t.handover_after_weeks.value} tygodni urlopu na "
        "warunkach urlopu macierzyńskiego można zrezygnować z jego dalszej części, jeśli "
        "wykorzysta ją drugi rodzic."
    )
    sources = merge_sources(t.handover_after_weeks.sources, params.father.total_cap.sources)
    passed = _segment(timeline, "adoption-leave-other")
    if passed is None:
        return CaseNote(
            id="handover",
            kind="risk",
            title="Dalszej części urlopu nie przejmie drugi rodzic",
            text=(
                f"{rule} Może to być pracownik albo osoba ubezpieczona, która przerwie pracę, "
                f"żeby opiekować się dzieckiem, a {PERSON[partner]} nie podlega ubezpieczeniu "
                f"chorobowemu, więc urlop zostaje u {'mamy' if role == 'mother' else 'taty'}."
            ),
            sources=sources,
        )
    return CaseNote(
        id="handover",
        kind="choice",
        title=f"Dalszą część urlopu wykorzysta {PERSON[partner]}",
        text=(
            f"{rule} {PERSON[role].capitalize()} wykorzystuje urlop do {long_date(own.end)}, "
            f"a {PERSON[partner]} od {long_date(passed.start)} do {long_date(passed.end)}. "
            "Łączny wymiar urlopu się nie zmienia."
        ),
        sources=sources,
    )


def _supplementary(scenario: Scenario, timeline: Timeline, params: Params) -> CaseNote | None:
    """§ 3¹: supplementary leave for the days in hospital after taking the child in."""
    if _segment(timeline, "adoption-leave") is None:
        return None
    t = params.taken_in
    s = params.supplementary
    segment = _segment(timeline, "supplementary")
    found = taken_in_supplementary(scenario, params, timeline.today)
    rule = (
        "Za pobyt dziecka w szpitalu po przyjęciu na wychowanie przysługuje uzupełniający urlop "
        "macierzyński, na tych samych zasadach co po porodzie."
    )
    if segment is None or found is None:
        if not (scenario.hospital_care and scenario.hospital_stays):
            return None
        return CaseNote(
            id="supplementary",
            kind="risk",
            title="Uzupełniający urlop macierzyński: pobyt w szpitalu się nie liczy",
            text=(
                f"{rule} Liczą się tylko dni w szpitalu od dnia przyjęcia dziecka, w okresie "
                "liczonym od porodu; z podanych pobytów nie wychodzi żaden taki dzień."
            ),
            sources=merge_sources(t.supplementary.sources, s.situations.sources),
        )
    case_sources = {
        "early": s.limit_weeks_early.sources,
        "preterm": s.limit_weeks_preterm.sources,
        "term": s.term.sources,
    }[found.case]
    return CaseNote(
        id="supplementary",
        kind="relief",
        title=f"Uzupełniający urlop macierzyński: {found.weeks} tyg.",
        text=(
            f"{rule} {describe_case(found, params)} Po przyjęciu dziecka liczy się {found.days} "
            f"{'dzień' if found.days == 1 else 'dni'} w szpitalu, więc {found.weeks} tyg. "
            "urlopu, bezpośrednio po urlopie na warunkach urlopu macierzyńskiego: od "
            f"{long_date(segment.start)} do {long_date(segment.end)}."
        ),
        sources=merge_sources(
            t.supplementary.sources,
            case_sources,
            s.sum_and_round.sources,
            s.once_after_maternity.sources,
        ),
    )


def _school(scenario: Scenario, params: Params, leave: TakenInLeave | None) -> CaseNote | None:
    """Foster family: postponed schooling moves the age limit from 7 to 10."""
    postponed = params.taken_in.foster.age_school_postponed
    if scenario.taken_in != "foster" or postponed is None or not scenario.school_postponed:
        return None
    if leave is None:
        return None
    return CaseNote(
        id="school-postponed",
        kind="relief",
        title=f"Odroczony obowiązek szkolny: granica {postponed.value} lat",
        text=(
            "Wobec dziecka podjęto decyzję o odroczeniu obowiązku szkolnego, więc urlop "
            f"przysługuje nie dłużej niż do ukończenia przez nie {postponed.value} lat, a nie "
            f"{params.taken_in.foster.age.value}."
        ),
        sources=merge_sources(postponed.sources, params.taken_in.foster.age.sources),
    )


def _start(scenario: Scenario, timeline: Timeline, params: Params) -> CaseNote | None:
    """§ 6: the request within 7 days, the start at the latest after 21 days."""
    marker = _marker(timeline, "leave-request-deadline")
    document = next((d for d in timeline.documents if d.id == TAKEN_IN_REQUEST), None)
    request = marker.date if marker is not None else document.deadline if document else None
    latest = _marker(timeline, "start-limit")
    if request is None or latest is None or _segment(timeline, "adoption-leave") is None:
        return None
    t = params.taken_in
    return CaseNote(
        id="taken-in-start",
        kind="choice",
        title="Kiedy zacząć urlop",
        text=(
            f"Wniosek o urlop składa się w ciągu {t.request_days.value} dni od dnia przyjęcia "
            f"dziecka, czyli do {long_date(request)}. Urlop zaczyna się w dniu wskazanym "
            f"we wniosku, nie później niż {t.latest_start_days.value} dni od dnia przyjęcia: "
            f"najpóźniej {long_date(latest.date)}."
        ),
        sources=merge_sources(t.request_days.sources, t.latest_start_days.sources),
    )


def _parental(
    scenario: Scenario, timeline: Timeline, params: Params, leave: TakenInLeave | None
) -> CaseNote | None:
    if leave is None:
        return None
    role = taker(scenario)
    mine = _segment(timeline, "parental" if role == "mother" else "parental-father")
    if mine is None:
        return None
    theirs = _segment(timeline, "parental-father" if role == "mother" else "parental")
    t = params.taken_in
    p = params.parental
    total = parental_total(scenario, params, leave)
    used = foster_parental_used(scenario)
    pool = total.value - used
    exclusive = p.exclusive_weeks.value
    deadline = parental_deadline(scenario, params, leave)
    until = (
        f" Trzeba go wykorzystać najpóźniej do {long_date(deadline.date)}: to {deadline.rule}."
        if deadline is not None
        else ""
    )
    sources: list[list[SourceRef]] = [
        t.parental.sources,
        total.sources,
        p.exclusive_weeks.sources,
        t.parental_parts.sources,
    ]
    if deadline is not None:
        sources.append(deadline.sources)
    after_minimum = (
        f" Po {t.minimum_weeks.value}-tygodniowym urlopie urlop rodzicielski jest krótszy."
        if leave.minimum
        else ""
    )
    if used:
        after_minimum += f" Po odjęciu tygodni wykorzystanych w rodzinie zastępczej: do {pool} tyg."
        sources.append(t.after_foster_parental.sources)
    most = pool - exclusive
    text = (
        "Urlop rodzicielski przysługuje tak jak przy urodzeniu dziecka, z uwzględnieniem "
        f"jego wieku. Rodzice mają razem do {total.value} tyg.{after_minimum} Każde z nich ma "
        f"{exclusive} tyg. wyłącznie dla siebie, więc {PERSON[role]} może wykorzystać "
        f"najwięcej {most} tyg. Urlop można wziąć jednorazowo albo "
        f"w nie więcej niż {p.max_parts.value} częściach.{until}"
    )
    if deadline is not None and mine.end == deadline.date and mine.days < most * 7:
        # The last day cuts the share: what is really left from the first possible day.
        text += (
            f" Od {long_date(mine.start)} do tego dnia zostaje {weeks_or_days(mine.days)}, więc "
            f"tyle najwięcej może wziąć {PERSON[role]}."
        )
    if theirs is not None and theirs.start <= mine.end:
        text += (
            " Rodzice mogą korzystać z urlopu rodzicielskiego jednocześnie, więc "
            f"{PERSON[other(role)]} może wziąć swoje tygodnie w tym samym czasie: "
            f"{weeks_or_days(theirs.days)}, od {long_date(theirs.start)} do "
            f"{long_date(theirs.end)}."
        )
        sources.append(params.parental_plan.both_at_once.sources)
    if deadline is None and leave.minimum:
        text += " Do kiedy trzeba go wykorzystać, materiały nie podają."
    return CaseNote(
        id="parental",
        kind="choice",
        title="Potem: urlop rodzicielski",
        text=text,
        sources=merge_sources(*sources),
    )


def _more_children(scenario: Scenario, timeline: Timeline, params: Params) -> CaseNote | None:
    count = scenario.children_count
    if count is None or count < 2 or _segment(timeline, "adoption-leave") is None:
        return None
    kind = kind_params(scenario.taken_in or "foster", params)
    weeks = kind.weeks_by_children.value
    text = (
        f"Przy jednoczesnym przyjęciu {children_taken_in(count)} urlop na warunkach urlopu "
        f"macierzyńskiego trwa {weeks[min(count, len(weeks)) - 1]} tyg. zamiast {weeks[0]}"
    )
    sources = [kind.weeks_by_children.sources]
    leave = taken_in_leave(scenario, params)
    has_parental = any(s.id.startswith("parental") for s in timeline.segments)
    if has_parental and leave is not None and not leave.minimum and not scenario.za_zyciem:
        table = kind.parental_weeks_by_children
        text += (
            f", a urlop rodzicielski obojga rodziców — do {table.value[1]} tyg. zamiast "
            f"{table.value[0]}"
        )
        sources.append(table.sources)
    return CaseNote(
        id="more-children",
        kind="relief",
        title=f"{multiples(count)}: dłuższy urlop",
        text=f"{text}.",
        sources=merge_sources(*sources),
    )


def _za_zyciem(
    scenario: Scenario, timeline: Timeline, params: Params, leave: TakenInLeave | None
) -> CaseNote | None:
    if not scenario.za_zyciem or leave is None:
        return None
    if not any(s.id.startswith("parental") for s in timeline.segments):
        return None
    total = parental_total(scenario, params, leave)
    return CaseNote(
        id="za-zyciem",
        kind="relief",
        title="Zaświadczenie „Za życiem”: dłuższy urlop rodzicielski",
        text=(
            f"Dziecko ma zaświadczenie „Za życiem”, więc rodzice mają razem do {total.value} tyg. "
            "urlopu rodzicielskiego."
        ),
        sources=total.sources,
    )


def _paternity(scenario: Scenario, timeline: Timeline, params: Params) -> CaseNote | None:
    """Adoption: the adoptive father's paternity leave (guide B.4; art. 182³ § 1 pkt 2)."""
    if scenario.taken_in != "adoption":
        return None
    if father_coverage(scenario) in NOT_INSURED:
        return None
    f = params.father
    t = params.taken_in
    age = t.paternity_age.value
    barred = paternity_barred(scenario, params)
    if barred is not None:
        return CaseNote(
            id="paternity",
            kind="risk",
            title="Urlop ojcowski nie przysługuje",
            text=(
                "Urlop ojcowski po adopcji przysługuje nie dłużej niż do ukończenia przez dziecko "
                f"{age} lat. Dziecko skończyło {age} lat {long_date(barred)}, zanim zostało "
                "przyjęte, więc urlop ojcowski nie przysługuje."
            ),
            sources=merge_sources(t.paternity_months.sources, t.paternity_age.sources),
        )
    employee = scenario.fathers_work in ("employment", None)
    sources = [
        f.paternity_who.sources,
        f.paternity_days.sources,
        t.paternity_months.sources,
        t.paternity_age.sources,
    ]
    window = (
        f"w ciągu {t.paternity_months.value} miesięcy od uprawomocnienia się przysposobienia, ale "
        f"nie później niż do ukończenia przez dziecko {age} lat."
    )
    if employee:
        rule = f"Tata adopcyjny ma prawo do urlopu ojcowskiego: do {f.paternity_days.value} dni, "
    else:
        rule = (
            "Tata adopcyjny nie jest pracownikiem, więc nie dostaje urlopu: ma prawo do zasiłku "
            "macierzyńskiego za okres odpowiadający urlopowi ojcowskiemu, do "
            f"{f.paternity_days.value} dni, "
        )
        sources += [params.benefit.non_employees.sources]
    rule += window
    kind = "choice"
    limit = paternity_deadline(scenario, params)
    deadline = _marker(timeline, "paternity-deadline")
    birth = scenario.birth_date
    if deadline is not None:
        when = f" Może go wykorzystać do {long_date(deadline.date)}."
    elif limit is not None and limit.date < timeline.today:
        kind = "risk"
        when = f" Czas na niego minął {long_date(limit.date)}" + (
            f": dziecko skończyło {age} lat {long_date(limit.date + DAY)}." if limit.by_age else "."
        )
    elif scenario.adoption_final:
        when = ""
    elif birth is not None and birthday(birth, age) <= timeline.today:
        kind = "risk"
        when = (
            f" Dziecko skończyło {age} lat {long_date(birthday(birth, age))}, więc po "
            "uprawomocnieniu się postanowienia nie będzie już czasu na ten urlop."
        )
    else:
        starts = " Czas na niego zacznie biec, gdy postanowienie o przysposobieniu się uprawomocni"
        when = starts + (
            f", i skończy się najpóźniej {long_date(birthday(birth, age) - DAY)}."
            if birth is not None
            else "."
        )
    return CaseNote(
        id="paternity",
        kind=kind,
        title="Urlop ojcowski po adopcji",
        text=f"{rule}{when}",
        sources=merge_sources(*sources),
    )


def _computed(
    scenario: Scenario, timeline: Timeline, params: Params, leave: TakenInLeave | None
) -> CaseNote:
    kind = kind_params(scenario.taken_in or "foster", params)
    own = _segment(timeline, "adoption-leave")
    if own is None and leave is not None and leave.used_up:
        # § 7: nothing of the leave is left; parental leave may still be on the timeline.
        text = "Urlopu na warunkach urlopu macierzyńskiego nie ma na osi: wykorzystano go."
        for segment_id, whose in (("parental", "mamy"), ("parental-father", "taty")):
            segment = _segment(timeline, segment_id)
            if segment is not None:
                text += (
                    f" Urlop rodzicielski {whose}: {weeks_or_days(segment.days)}, od "
                    f"{long_date(segment.start)} do {long_date(segment.end)}."
                )
        return CaseNote(
            id="computed",
            kind="computed",
            title="Co policzyliśmy",
            text=f"{text} Tydzień urlopu to 7 dni kalendarzowych.",
            sources=merge_sources(
                params.taken_in.after_foster_leave.sources, params.rules.week_is_7_days.sources
            ),
        )
    if own is None:
        if leave is None and scenario.children_count is None:
            return CaseNote(
                id="computed",
                kind="computed",
                title="Co jeszcze policzymy",
                text=(
                    "Długość urlopu zależy od liczby dzieci przyjętych jednocześnie. Gdy będzie "
                    "wiadomo, ile ich jest, oś pokaże urlop."
                ),
                sources=kind.weeks_by_children.sources,
            )
        return CaseNote(
            id="computed",
            kind="computed",
            title="Co policzyliśmy",
            text=(
                "Urlopu na warunkach urlopu macierzyńskiego nie ma na osi: zasady opisują punkty "
                "wyżej."
            ),
            sources=params.taken_in.insured.sources,
        )
    text = (
        f"Urlop na warunkach urlopu macierzyńskiego: {weeks_or_days(own.days)}, od "
        f"{long_date(own.start)} do {long_date(own.end)}."
    )
    sources = [kind.weeks_by_children.sources, params.rules.week_is_7_days.sources]
    if leave is not None and leave.minimum:
        sources.append(params.taken_in.minimum_weeks.sources)
    elif leave is not None and leave.cut and leave.limit is not None:
        limit = age_limit(scenario, params)
        text += (
            f" Dziecko kończy {limit.age} lat {long_date(leave.limit)}, więc urlop kończy się "
            "dzień wcześniej."
        )
        sources.append(limit.sources)
    passed = _segment(timeline, "adoption-leave-other")
    if passed is not None:
        text += (
            f" Dalsza część tego urlopu ({PERSON[passed.lane]}): {weeks_or_days(passed.days)}, "
            f"od {long_date(passed.start)} do {long_date(passed.end)}."
        )
        sources.append(params.taken_in.handover_after_weeks.sources)
    supplementary = _segment(timeline, "supplementary")
    if supplementary is not None:
        text += (
            f" Uzupełniający urlop macierzyński: {weeks_or_days(supplementary.days)}, od "
            f"{long_date(supplementary.start)} do {long_date(supplementary.end)}."
        )
        sources.append(params.taken_in.supplementary.sources)
    for segment_id, whose in (("parental", "mamy"), ("parental-father", "taty")):
        segment = _segment(timeline, segment_id)
        if segment is not None:
            text += (
                f" Urlop rodzicielski {whose}: {weeks_or_days(segment.days)}, od "
                f"{long_date(segment.start)} do {long_date(segment.end)}."
            )
    if any(s.id.startswith("parental") for s in timeline.segments) and leave is not None:
        total = parental_total(scenario, params, leave)
        sources += [total.sources, params.parental.exclusive_weeks.sources]
    paternity = _segment(timeline, "paternity")
    if paternity is not None:
        text += f" Urlop ojcowski taty: {paternity.days} dni, od {long_date(paternity.start)}."
        sources.append(params.father.paternity_days.sources)
    return CaseNote(
        id="computed",
        kind="computed",
        title="Co policzyliśmy",
        text=f"{text} Tydzień urlopu to 7 dni kalendarzowych.",
        sources=merge_sources(*sources),
    )
