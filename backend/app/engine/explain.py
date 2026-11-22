"""The case explanation: which situation the family is in, what the mother and the father are
entitled to, which options and reliefs the rules give them and why, and what exactly we computed.
Built from the finished timeline, so dates are read, never recalculated. Every legal claim
carries its source.

Every phase adds its notes here (CLAUDE.md, "Wyjaśnianie przypadku").
"""

import datetime as dt

from app.engine.after_insurance import after_job_loss, insurance_note, leave_before_cut
from app.engine.applications import application_notes
from app.engine.base import add_base_notes
from app.engine.debt import add_debt_notes
from app.engine.draft import DAY, days_between
from app.engine.explain_adoption import taken_in_notes
from app.engine.father import (
    INTERRUPTED_WORK,
    MATERNITY_PARTS,
    UNINSURED_AFTER,
    interrupted_work_rule,
    uninsured_maternity_end,
)
from app.engine.insurance import NOT_INSURED, Coverage, coverage, father_coverage
from app.engine.loss import Loss, child_loss
from app.engine.models import CaseNote, Marker, Scenario, Segment, SourceRef, Timeline
from app.engine.money import NOTE_ID as MONEY_NOTE
from app.engine.money import add_money_notes
from app.engine.no_right import add_way_notes
from app.engine.params import Params, Rule
from app.engine.parental import for_children, parental_table, parental_weeks
from app.engine.parental_plan import parental_plan_notes
from app.engine.pregnancy import pregnancy_notes
from app.engine.supplementary import describe_case, supplementary_leave
from app.engine.wording import children_phrase, long_date, multiples, weeks_or_days

WORK_LOCATIVE = {"contract": "umowie zlecenia", "business": "własnej działalności gospodarczej"}
"""After "przy": the two ways of working the guide names for voluntary sickness insurance."""


def case_notes(scenario: Scenario, timeline: Timeline, params: Params) -> list[CaseNote]:
    # Contribution debt of a parent with a business (debt.py), after that parent's right.
    return add_debt_notes(_all_notes(scenario, timeline, params), scenario, timeline, params)


def _all_notes(scenario: Scenario, timeline: Timeline, params: Params) -> list[CaseNote]:
    if scenario.taken_in is not None:
        # Section G for the leave of a child taken in, too.
        notes = add_money_notes(
            taken_in_notes(scenario, timeline, params), scenario, timeline, params
        )
        return add_way_notes(notes, scenario, timeline, params)  # F14 (no_right.py)
    notes = _case_notes(scenario, timeline, params)
    # Guide E and B.3: the parents' plan of parental leave, before "Co policzyliśmy".
    plan = parental_plan_notes(scenario, timeline, params)
    at = next((i for i, n in enumerate(notes) if n.id == "computed"), len(notes))
    notes = notes[:at] + plan + notes[at:]
    # Section G: the choice of rate joins the choices, the amounts come after the dates.
    notes = add_money_notes(notes, scenario, timeline, params)
    # The benefit base in detail (base.py): how it was computed, before the amounts.
    notes = add_base_notes(notes, timeline, before=MONEY_NOTE)
    # F14 (no_right.py): what instead and what would give the right, after each "no right".
    return add_way_notes(notes, scenario, timeline, params)


def _case_notes(scenario: Scenario, timeline: Timeline, params: Params) -> list[CaseNote]:
    cover = coverage(scenario)
    loss = child_loss(scenario, params, timeline.birth_date, timeline.today)
    if loss is not None:
        return _after_loss(scenario, timeline, params, cover, loss)
    notes = [
        _situation(scenario, timeline, params, cover),
        _insurance(scenario, timeline, params, cover),
        *pregnancy_notes(scenario, timeline, params),
    ]
    if cover in NOT_INSURED:
        return [
            *notes,
            *_father_notes(scenario, timeline, params, cover, loss),
            *_father_computed(scenario, timeline, params),
            *application_notes(scenario, timeline, params),
        ]
    if not timeline.child_born and not leave_before_cut(scenario):
        notes.append(_before_birth(scenario, timeline, params))
    optional = [
        _parental(scenario, timeline, params),
        _more_children(scenario, timeline, params),
        _za_zyciem(scenario, timeline, params),
        _supplementary(scenario, timeline, params),
    ]
    notes += [note for note in optional if note is not None]
    notes += _father_notes(scenario, timeline, params, cover, loss)
    notes.append(_computed(scenario, timeline, params))
    return notes + application_notes(scenario, timeline, params)


def changed_note_ids(old: Timeline | None, new: Timeline) -> list[str]:
    """Points of the explanation that are new or reworded since `old`. After a recalculation
    the assistant talks about these and the UI highlights them."""
    if old is None:
        return []
    before = {n.id: (n.kind, n.title, n.text) for n in old.notes}
    return [n.id for n in new.notes if before.get(n.id) != (n.kind, n.title, n.text)]


def _after_loss(
    scenario: Scenario, timeline: Timeline, params: Params, cover: Coverage, loss: Loss
) -> list[CaseNote]:
    """Phase 3: after a stillbirth or a death, the explanation says only what the mother needs,
    quietly: what happened, her right, how long the leave lasts and why, and the dates."""
    notes = [
        _loss_situation(scenario, timeline, loss),
        _insurance(scenario, timeline, params, cover),
    ]
    if cover in NOT_INSURED:
        return [
            *notes,
            *_father_notes(scenario, timeline, params, cover, loss),
            *_father_computed(scenario, timeline, params),
            *application_notes(scenario, timeline, params),
        ]
    notes.append(_loss_rule(scenario, timeline, params, loss))
    if loss.survivors:
        optional = [
            _parental(scenario, timeline, params),
            _za_zyciem(scenario, timeline, params),
            _supplementary(scenario, timeline, params),
        ]
        notes += [note for note in optional if note is not None]
    notes += _father_notes(scenario, timeline, params, cover, loss)
    notes.append(_loss_computed(scenario, timeline, params, loss))
    return notes + application_notes(scenario, timeline, params)


def _loss_situation(scenario: Scenario, timeline: Timeline, loss: Loss) -> CaseNote:
    count = scenario.children_count or loss.count
    if count == 1:
        title = (
            "Dziecko urodziło się martwe"
            if loss.stillborn
            else f"Dziecko zmarło {long_date(loss.last)}"
        )
    elif loss.survivors:
        what = "urodziło się martwe" if loss.stillborn == loss.count else "zmarło"
        title = f"Jedno z dzieci {what}" if loss.count == 1 else f"{loss.count} z dzieci {what}"
    else:
        title = "Dzieci zmarły"
    return CaseNote(
        id="situation",
        kind="situation",
        title=title,
        text=(
            "Bardzo nam przykro. Poniżej spokojnie wyjaśniamy tylko to, co w tej sytuacji "
            f"przysługuje mamie. Liczymy od dnia porodu: {long_date(timeline.birth_date)}."
        ),
    )


def _loss_rule(scenario: Scenario, timeline: Timeline, params: Params, loss: Loss) -> CaseNote:
    """Which rule of point A.3 applies, and what it gives."""
    rule = params.loss
    whole = _maternity_end(timeline)
    end = long_date(whole) if whole else ""
    days = rule.days_after_death.value
    weeks = rule.weeks_after_birth.value
    if loss.survivors:
        table = params.maternity.weeks_by_children.value
        living = table[min(loss.survivors, len(table)) - 1]
        born = table[min(loss.survivors + loss.count, len(table)) - 1]
        return CaseNote(
            id="loss",
            kind="right",
            title=f"Urlop macierzyński: {living} tyg., według liczby żyjących dzieci",
            text=(
                "Gdy przy jednym porodzie urodziło się więcej dzieci, urlop macierzyński "
                "przysługuje w wymiarze stosownym do liczby dzieci pozostałych przy życiu: "
                f"{living} tyg. zamiast {born}, nie krócej jednak niż {days} dni od dnia "
                f"śmierci dziecka. Urlop trwa do {end}."
            ),
            sources=_merge(rule.survivors.sources),
        )
    if loss.early:
        what = (
            "Gdy dziecko urodzi się martwe"
            if loss.stillborn == loss.count
            else f"Gdy dziecko umrze przed upływem {rule.life_weeks.value} tygodni życia"
        )
        return CaseNote(
            id="loss",
            kind="right",
            title=f"Urlop macierzyński: {weeks} tygodni po porodzie",
            text=(
                f"{what}, mamie przysługuje zasiłek macierzyński za {weeks} tygodni po porodzie, "
                f"nie krócej jednak niż przez {days} dni od dnia śmierci dziecka. Urlop trwa do "
                f"{end}. Urlopu rodzicielskiego oś nie pokazuje: przysługuje on w celu "
                "sprawowania opieki nad dzieckiem."
            ),
            sources=_merge(
                _guide(rule.weeks_after_birth.sources),
                _law(rule.weeks_after_birth.sources),
                rule.parental_for_care.sources,
            ),
        )
    kept = [s for s in timeline.segments if s.id in ("supplementary", "parental")]
    also = f" Tak samo przez {days} dni zostaje urlop, który wtedy trwał." if kept else ""
    return CaseNote(
        id="loss",
        kind="right",
        title=f"Urlop zostaje jeszcze przez {days} dni",
        text=(
            f"Gdy dziecko umrze po upływie {rule.life_weeks.value} tygodni życia, mama zachowuje "
            f"prawo do zasiłku macierzyńskiego za okres urlopu macierzyńskiego przez {days} dni "
            f"od dnia śmierci dziecka.{also} Urlopu rodzicielskiego później oś nie pokazuje: "
            "przysługuje on w celu sprawowania opieki nad dzieckiem."
        ),
        sources=_merge(
            [s for s in rule.days_after_death.sources if "po upływie" in s.quote],
            rule.other_leaves.sources if kept else [],
            rule.parental_for_care.sources,
        ),
    )


def _loss_computed(scenario: Scenario, timeline: Timeline, params: Params, loss: Loss) -> CaseNote:
    maternity = _segment(timeline, "maternity")
    if maternity is None or scenario.children_count is None:
        return CaseNote(
            id="computed",
            kind="computed",
            title="Co jeszcze policzymy",
            text=(
                "Gdy będzie wiadomo, ile dzieci urodziło się przy jednym porodzie, oś pokaże urlop."
            ),
            sources=_guide(params.maternity.weeks_by_children.sources),
        )
    prenatal_segment = _segment(timeline, "maternity-prenatal")
    weeks = weeks_or_days(prenatal_segment.days) if prenatal_segment else ""
    whole = _maternity_end(timeline) or maternity.end
    before = (
        f"Urlop zaczął się {weeks} przed porodem i trwa do {long_date(whole)}"
        if weeks
        else f"Urlop macierzyński trwa od dnia porodu do {long_date(whole)}"
    )
    text = f"{before} ({days_between(maternity.start, whole)} dni po porodzie)."
    split, split_sources = _split(scenario, timeline, params)
    text += split
    father_text, father_sources = _father_dates(scenario, timeline, params)
    if loss.survivors:
        personal = _marker(timeline, "personal-weeks")
        if personal is not None:
            text += (
                f" Pierwsze {params.maternity.mother_personal_weeks.value} tygodni po porodzie, "
                f"do {long_date(personal.date)}, mama wykorzystuje osobiście."
            )
        parental = _segment(timeline, "parental")
        if parental is not None:
            text += (
                f" Urlop rodzicielski mamy, wzięty w całości od razu potem: "
                f"{parental.days // 7} tyg., do {long_date(parental.end)}."
            )
    for kept in (s for s in timeline.segments if s.id in ("supplementary", "parental")):
        if not loss.survivors:
            text += f" {kept.title.split(' —')[0]}: do {long_date(kept.end)}."
    return CaseNote(
        id="computed",
        kind="computed",
        title="Co policzyliśmy",
        text=f"{text}{father_text} Tydzień urlopu to 7 dni kalendarzowych.",
        sources=_merge(
            params.rules.week_is_7_days.sources,
            _law(params.loss.days_after_death.sources),
            *split_sources,
            *father_sources,
        ),
    )


def _segment(timeline: Timeline, segment_id: str) -> Segment | None:
    return next((s for s in timeline.segments if s.id == segment_id), None)


def _mothers_parental(timeline: Timeline) -> bool:
    """The mother has parental leave on the timeline: the option or parts of the parents' plan."""
    return any(s.lane == "mother" and s.id.startswith("parental") for s in timeline.segments)


def _marker(timeline: Timeline, marker_id: str) -> Marker | None:
    return next((m for m in timeline.markers if m.id == marker_id), None)


def _total_weeks(count: int, params: Params) -> int:
    table = params.maternity.weeks_by_children.value
    return table[min(count, len(table)) - 1]


def _guide(sources: list[SourceRef]) -> list[SourceRef]:
    return [s for s in sources if s.doc == "przewodnik"]


def _law(sources: list[SourceRef]) -> list[SourceRef]:
    return [s for s in sources if s.doc == "kp"]


def _merge(*groups: list[SourceRef]) -> list[SourceRef]:
    """Sources of several rules in order, each quote once."""
    merged: dict[tuple[str, str], SourceRef] = {}
    for source in (source for group in groups for source in group):
        merged.setdefault((source.doc, source.quote), source)
    return list(merged.values())


def _situation(scenario: Scenario, timeline: Timeline, params: Params, cover: Coverage) -> CaseNote:
    birth, today = timeline.birth_date, timeline.today
    rules = params.rules
    if not timeline.child_born:
        return CaseNote(
            id="situation",
            kind="situation",
            title="Dziecko jest w drodze",
            text=(
                f"Liczymy od przewidywanej daty porodu: {long_date(birth)}. Gdy dziecko się "
                "urodzi, wystarczy podać faktyczną datę, a oś przeliczy się sama."
            ),
        )

    born_today = birth == today
    title = (
        "Dziecko urodziło się dzisiaj" if born_today else f"Dziecko urodziło się {long_date(birth)}"
    )
    event = scenario.mother_event
    if (
        cover in NOT_INSURED
        or (event is not None and event.kind == "death")
        or after_job_loss(scenario) is not None
    ):
        # After the mother's death (or her job) nothing here is "simpler": what we count from.
        return CaseNote(
            id="situation",
            kind="situation",
            title=title,
            text="Liczymy od faktycznej daty urodzenia.",
        )
    weeks = scenario.leave_before_birth_weeks
    prenatal = _segment(timeline, "maternity-prenatal")
    if prenatal is not None:
        verb = "trwa" if born_today else "zaczął się"
        before = weeks_or_days(prenatal.days)
        return CaseNote(
            id="situation",
            kind="situation",
            title=title,
            text=(
                f"Liczymy od faktycznej daty urodzenia. Urlop macierzyński {verb} od "
                f"{long_date(prenatal.start)}: mama zaczęła go {before} przed porodem."
                if born_today
                else f"Liczymy od faktycznej daty urodzenia. Urlop macierzyński zaczął się "
                f"{long_date(prenatal.start)}, {before} przed porodem."
            ),
            sources=rules.rest_after_birth.sources,
        )

    start = (
        "urlop macierzyński zaczyna się dziś, w dniu porodu"
        if born_today
        else "urlop macierzyński zaczął się w dniu porodu"
    )
    if weeks is None:
        start = f"jeśli mama nie była na urlopie przed porodem, {start}"
    lead = "To upraszcza sprawę" if born_today else "Sprawa jest prostsza"
    return CaseNote(
        id="situation",
        kind="situation",
        title=title,
        text=(
            f"{lead}: nie trzeba już planować urlopu przed porodem ani zdobywać zaświadczenia "
            f"o przewidywanej dacie porodu. {start[0].upper()}{start[1:]}."
        ),
        sources=[*rules.medical_certificate.sources, *rules.first_day_is_birth.sources],
    )


def _insurance(scenario: Scenario, timeline: Timeline, params: Params, cover: Coverage) -> CaseNote:
    """Phase 2: the right to the maternity benefit belongs to the insured mother."""
    after = insurance_note(scenario, timeline, params)  # ustawa art. 30: after losing the job
    if after is not None:
        return after
    b = params.benefit
    born = timeline.child_born
    on_the_day = (
        "Liczy się, że mama podlegała ubezpieczeniu chorobowemu w dniu porodu."
        if born
        else "Ważne, żeby ubezpieczenie chorobowe trwało w dniu porodu."
    )
    # Before the birth the right is still to come (it arises after the birth).
    entitled = (
        "Mama ma prawo do zasiłku macierzyńskiego"
        if born
        else "Po porodzie: prawo do zasiłku macierzyńskiego"
    )
    # The guide: the benefit is paid "in defined situations also after the insurance has ended"
    # (ustawa art. 30 ust. 1: after an employment that ended in pregnancy).
    exceptions = (
        "Po ustaniu ubezpieczenia zasiłek macierzyński przysługuje tylko w określonych "
        "sytuacjach: gdy ubezpieczenie ustało w ciąży wskutek śmierci, upadłości lub likwidacji "
        "pracodawcy albo z naruszeniem przepisów prawa stwierdzonym prawomocnym orzeczeniem sądu."
    )
    needed = "Zasiłek macierzyński: potrzebne ubezpieczenie chorobowe"
    denied = "Zasiłek macierzyński wymaga ubezpieczenia chorobowego"
    work = WORK_LOCATIVE.get(scenario.mothers_work or "", "")
    match cover:
        case "obligatory":
            return CaseNote(
                id="insurance",
                kind="right",
                title=entitled,
                text=(
                    "Umowa o pracę daje obowiązkowe ubezpieczenie chorobowe, a po porodzie "
                    "ubezpieczona mama nabywa prawo do zasiłku macierzyńskiego za okres urlopu "
                    f"macierzyńskiego. {on_the_day}"
                ),
                sources=_merge(
                    b.insured_mother.sources,
                    b.obligatory_insurance.sources,
                    b.insured_on_birth_day.sources,
                ),
            )
        case "voluntary":
            return CaseNote(
                id="insurance",
                kind="right",
                title=entitled,
                text=(
                    f"Przy {work} ubezpieczenie chorobowe jest dobrowolne. Mama jest do niego "
                    "zgłoszona, więc po porodzie nabywa prawo do zasiłku macierzyńskiego. Nie "
                    "jest pracownicą, dlatego nie dostaje urlopu: ma prawo do zasiłku za okres "
                    "odpowiadający urlopowi, na tych samych zasadach co do wymiaru i wysokości. "
                    f"{on_the_day}"
                ),
                sources=_merge(
                    b.insured_mother.sources,
                    b.voluntary_insurance.sources,
                    b.non_employees.sources,
                    b.same_rules_for_non_employees.sources,
                    b.insured_on_birth_day.sources,
                ),
            )
        case "unknown-voluntary":
            return CaseNote(
                id="insurance",
                kind="right",
                title=needed,
                text=(
                    "Prawo do zasiłku macierzyńskiego nabywa po porodzie mama ubezpieczona. Przy "
                    f"{work} ubezpieczenie chorobowe jest dobrowolne, więc trzeba ustalić, czy "
                    "mama jest do niego zgłoszona. Na razie oś zakłada, że tak."
                ),
                sources=_merge(b.insured_mother.sources, b.voluntary_insurance.sources),
            )
        case "unknown-work":
            return CaseNote(
                id="insurance",
                kind="right",
                title=needed,
                text=(
                    "Prawo do zasiłku macierzyńskiego nabywa po porodzie mama ubezpieczona, czyli "
                    "podlegająca ubezpieczeniu chorobowemu. Zależy to od tego, jak mama pracuje. "
                    "Na razie oś zakłada, że jest ubezpieczona."
                ),
                sources=_merge(
                    b.insured_mother.sources,
                    b.paid_to_the_insured.sources,
                    b.obligatory_insurance.sources,
                    b.voluntary_insurance.sources,
                ),
            )
        case "not-registered":
            state = (
                "a mama nie była do niego zgłoszona. Liczy się dzień porodu: bez ubezpieczenia "
                "chorobowego w tym dniu zasiłek macierzyński mamie nie przysługuje."
                if born
                else "a mama nie jest do niego zgłoszona. Liczy się dzień porodu: jeśli mama "
                "nie będzie wtedy podlegać ubezpieczeniu chorobowemu, zasiłek macierzyński nie "
                "będzie jej przysługiwał."
            )
            return CaseNote(
                id="insurance",
                kind="risk",
                title=denied,
                text=(
                    "Prawo do zasiłku macierzyńskiego nabywa po porodzie mama ubezpieczona. Przy "
                    f"{work} ubezpieczenie chorobowe jest dobrowolne, {state}"
                ),
                sources=_merge(
                    b.insured_mother.sources,
                    b.voluntary_insurance.sources,
                    b.insured_on_birth_day.sources,
                    b.voluntary_not_registered.sources,
                    b.without_insurance.sources,
                    b.paid_to_the_insured.sources,
                ),
            )
        case "not-working":
            return CaseNote(
                id="insurance",
                kind="risk",
                title=denied,
                text=(
                    "Prawo do zasiłku macierzyńskiego nabywa po porodzie mama ubezpieczona, czyli "
                    "podlegająca ubezpieczeniu chorobowemu: obowiązkowemu (np. z umowy o pracę) "
                    "albo dobrowolnemu (np. przy umowie zlecenia lub działalności gospodarczej). "
                    "Z odpowiedzi wynika, że mama nie pracuje, więc nie ma umowy ani działalności, "
                    "z której wynikałoby to ubezpieczenie, a bez niego zasiłek macierzyński nie "
                    f"przysługuje. {exceptions}"
                ),
                sources=_merge(
                    b.insured_mother.sources,
                    b.paid_to_the_insured.sources,
                    b.obligatory_insurance.sources,
                    b.voluntary_insurance.sources,
                    b.without_insurance.sources,
                    params.pregnancy.maternity_after_job_loss.sources,
                ),
            )


def _before_birth(scenario: Scenario, timeline: Timeline, params: Params) -> CaseNote:
    """While the child is on the way: the choice between leave before the birth and work."""
    limit = params.maternity.max_weeks_before_birth
    rules = params.rules
    weeks = scenario.leave_before_birth_weeks

    if weeks is None:
        window = _segment(timeline, "prenatal-window")
        earliest = f"Najwcześniej {long_date(window.start)}. " if window else ""
        return CaseNote(
            id="before-birth",
            kind="choice",
            title=f"Urlop można zacząć nawet {limit.value} tygodni przed przewidywaną datą porodu",
            text=(
                f"{earliest}Potrzebne jest wtedy zaświadczenie lekarskie o przewidywanej dacie "
                "porodu. Można też pracować do dnia porodu — zasiłek zacznie się wtedy po "
                "urodzeniu dziecka."
            ),
            sources=[
                *limit.sources,
                *rules.medical_certificate.sources,
                *rules.work_until_birth.sources,
            ],
        )

    if weeks == 0:
        return CaseNote(
            id="before-birth",
            kind="choice",
            title="Praca do dnia porodu",
            text=(
                "Urlop macierzyński zacznie się w dniu porodu, a zasiłek po urodzeniu dziecka. "
                "Zaświadczenie o przewidywanej dacie porodu nie jest do tego potrzebne."
            ),
            sources=[
                *rules.work_until_birth.sources,
                *rules.medical_certificate.sources,
                *rules.first_day_is_birth.sources,
            ],
        )

    prenatal = _segment(timeline, "maternity-prenatal")
    assert prenatal is not None
    count = scenario.children_count
    if count is not None:
        total = _total_weeks(count, params)
        counted = (
            f"Te tygodnie wliczają się do {total} tyg. urlopu macierzyńskiego, więc po porodzie "
            f"zostaje {total - weeks} tyg."
        )
    else:
        counted = "Te tygodnie wliczają się do całego urlopu macierzyńskiego."
    certificate = (
        "Zaświadczenie lekarskie o przewidywanej dacie porodu już jest."
        if scenario.has_medical_certificate
        else f"Żeby zacząć urlop {long_date(prenatal.start)}, potrzebne jest zaświadczenie "
        "lekarskie o przewidywanej dacie porodu."
    )
    return CaseNote(
        id="before-birth",
        kind="choice",
        title=f"Urlop od {long_date(prenatal.start)}, {weeks} tyg. przed przewidywaną datą porodu",
        text=f"{counted} {certificate}",
        sources=[
            *limit.sources,
            *rules.medical_certificate.sources,
            *rules.rest_after_birth.sources,
        ],
    )


def _parental(scenario: Scenario, timeline: Timeline, params: Params) -> CaseNote | None:
    """Phase 2: after maternity leave comes parental leave; how much of it the mother can use."""
    deadline = _marker(timeline, "parental-deadline")
    if not _mothers_parental(timeline) or deadline is None:
        return None
    p = params.parental
    total, mothers = parental_weeks(scenario, params)
    sources = [
        p.after_maternity.sources,
        parental_table(scenario, params).sources,
        p.exclusive_weeks.sources,
        p.max_parts.sources,
    ]
    longer = ""
    if not scenario.za_zyciem:
        table = p.weeks_by_children_za_zyciem
        longer = (
            " Z zaświadczeniem „Za życiem” urlop jest dłuższy: do "
            f"{for_children(table, scenario.children_count)} tyg."
        )
        sources.append(table.sources)
    return CaseNote(
        id="parental",
        kind="choice",
        title="Po urlopie macierzyńskim: urlop rodzicielski",
        text=(
            f"Rodzice mają razem do {total} tyg. urlopu rodzicielskiego. Każde z nich ma "
            f"{p.exclusive_weeks.value} tyg. wyłącznie dla siebie, których nie można przenieść "
            f"na drugie, więc mama może wykorzystać najwięcej {mothers} tyg. Urlop można wziąć "
            f"jednorazowo albo w nie więcej niż {p.max_parts.value} częściach, najpóźniej do "
            f"{long_date(deadline.date)} — końca roku, w którym dziecko kończy "
            f"{p.deadline_age.value} lat.{longer}"
        ),
        sources=_merge(*sources),
    )


def _more_children(scenario: Scenario, timeline: Timeline, params: Params) -> CaseNote | None:
    """More children at once: longer maternity leave and longer parental leave."""
    count = scenario.children_count
    if count is None or count < 2:
        return None
    weeks = params.maternity.weeks_by_children
    text = (
        f"Przy urodzeniu {children_phrase(count)} urlop macierzyński trwa "
        f"{_total_weeks(count, params)} tyg. zamiast {weeks.value[0]}"
    )
    sources = [_law(weeks.sources)]
    if _mothers_parental(timeline):
        table = parental_table(scenario, params)
        text += (
            f", a urlop rodzicielski obojga rodziców — do {table.value[1]} tyg. zamiast "
            f"{table.value[0]}"
        )
        sources.append(_law(table.sources))
    return CaseNote(
        id="more-children",
        kind="relief",
        title=f"{multiples(count)}: dłuższy urlop",
        text=f"{text}.",
        sources=_merge(*sources),
    )


def _za_zyciem(scenario: Scenario, timeline: Timeline, params: Params) -> CaseNote | None:
    """The "Za życiem" certificate: longer parental leave."""
    if not scenario.za_zyciem or not _mothers_parental(timeline):
        return None
    p = params.parental
    count = scenario.children_count
    total, mothers = parental_weeks(scenario, params)
    return CaseNote(
        id="za-zyciem",
        kind="relief",
        title="Zaświadczenie „Za życiem”: dłuższy urlop rodzicielski",
        text=(
            f"Dziecko ma zaświadczenie „Za życiem”, więc rodzice mają razem do {total} tyg. "
            f"urlopu rodzicielskiego zamiast {for_children(p.weeks_by_children, count)}. Mama "
            f"może z nich wykorzystać najwięcej {mothers} tyg."
        ),
        sources=_merge(p.weeks_by_children_za_zyciem.sources, p.exclusive_weeks.sources),
    )


def _supplementary(scenario: Scenario, timeline: Timeline, params: Params) -> CaseNote | None:
    """A premature child or one that needed hospital: supplementary maternity leave."""
    if not timeline.child_born or not scenario.hospital_care:
        return None
    s = params.supplementary
    leave = supplementary_leave(scenario, params, timeline.birth_date, timeline.today)
    if leave is None:
        return CaseNote(
            id="supplementary",
            kind="relief",
            title="Uzupełniający urlop macierzyński: potrzebne szczegóły",
            text=(
                "Może przysługiwać bezpośrednio po urlopie macierzyńskim, gdy dziecko urodziło "
                "się przedwcześnie albo o czasie, ale wymagało hospitalizacji: tydzień za każdy "
                "tydzień pobytu dziecka w szpitalu. Żeby go policzyć, potrzebne są: tydzień "
                "ciąży, w którym urodziło się dziecko, jego masa urodzeniowa i daty pobytu "
                "w szpitalu."
            ),
            sources=_merge(
                s.situations.sources,
                s.limit_weeks_early.sources,
                s.limit_weeks_preterm.sources,
                s.term.sources,
                s.once_after_maternity.sources,
            ),
        )
    case_sources = {
        "early": s.limit_weeks_early.sources,
        "preterm": s.limit_weeks_preterm.sources,
        "term": s.term.sources,
    }[leave.case]
    if leave.weeks == 0:
        reason = (
            "Podany pobyt w szpitalu nie spełnia tego warunku."
            if not leave.condition_met
            else "W podanych datach nie ma pobytu w szpitalu, który by się liczył."
        )
        return CaseNote(
            id="supplementary",
            kind="risk",
            title="Uzupełniający urlop macierzyński: warunki niespełnione",
            text=f"{describe_case(leave, params)} {reason}",
            sources=_merge(_guide(s.situations.sources), case_sources),
        )
    days = "dzień" if leave.days == 1 else "dni"
    ongoing = (
        f" Dziecko jest jeszcze w szpitalu, więc liczba tygodni może wzrosnąć, najwyżej do "
        f"{leave.max_weeks}."
        if leave.ongoing and leave.max_weeks > leave.weeks
        else ""
    )
    amount = f"{leave.days} {days} to {leave.weeks} tyg."
    if leave.days % 7:
        amount = (
            f"{leave.days} {days} to {leave.weeks} tyg., bo niepełny tydzień zaokrągla się w górę."
        )
    return CaseNote(
        id="supplementary",
        kind="relief",
        title=f"Uzupełniający urlop macierzyński: {leave.weeks} tyg.",
        text=(
            f"{describe_case(leave, params)} Za każdy tydzień pobytu dziecka w szpitalu "
            f"przysługuje tydzień urlopu: {amount} Urlop może wziąć mama albo tata, tylko jedno "
            f"z nich, bezpośrednio po urlopie macierzyńskim.{ongoing}"
        ),
        sources=_merge(
            _guide(s.situations.sources),
            case_sources,
            s.sum_and_round.sources,
            s.once_after_maternity.sources,
        ),
    )


def _computed(scenario: Scenario, timeline: Timeline, params: Params) -> CaseNote:
    """What exactly the timeline shows, and the rule each number comes from."""
    m = params.maternity
    maternity = _segment(timeline, "maternity")
    personal = _marker(timeline, "personal-weeks")
    count = scenario.children_count
    if count is None or maternity is None:
        return CaseNote(
            id="computed",
            kind="computed",
            title="Co jeszcze policzymy",
            text=(
                "Długość urlopu macierzyńskiego i rodzicielskiego zależy od liczby dzieci "
                "urodzonych przy jednym porodzie. Gdy będzie wiadomo, ile ich jest, oś pokaże "
                "oba urlopy."
            ),
            sources=_merge(
                _guide(m.weeks_by_children.sources),
                _guide(params.parental.weeks_by_children.sources),
            ),
        )

    weeks = scenario.leave_before_birth_weeks or 0
    prenatal_segment = _segment(timeline, "maternity-prenatal")
    in_total = (
        f", w tym {weeks_or_days(prenatal_segment.days)} przed porodem"
        if prenatal_segment is not None
        else ""
    )
    whole = _maternity_end(timeline) or maternity.end
    ended = timeline.child_born and whole < timeline.today
    rules = params.rules
    split, split_sources = _split(scenario, timeline, params)
    event = scenario.mother_event
    if _segment(timeline, "maternity-father") is None and (
        (event is not None and event.kind == "death" and maternity.end == event.start)
        or _abandoned(maternity)
    ):
        # The mother died or abandoned the child and nobody takes the rest of her leave: just
        # its last day.
        text = split.strip()
        sources = [*split_sources, rules.week_is_7_days.sources]
    else:
        text = (
            f"Urlop macierzyński trwa {_total_weeks(count, params)} tyg.{in_total}; po porodzie "
            f"do {long_date(whole)}{' (już się skończył)' if ended else ''}.{split}"
        )
        sources = [
            m.weeks_by_children.sources,
            rules.rest_after_birth.sources if weeks else rules.first_day_is_birth.sources,
            rules.week_is_7_days.sources,
            *split_sources,
        ]
    if personal is not None:
        text += (
            f" Pierwsze {m.mother_personal_weeks.value} tygodni po porodzie, do "
            f"{long_date(personal.date)}, mama wykorzystuje osobiście."
        )
        sources.append(m.mother_personal_weeks.sources)
    supplementary = _segment(timeline, "supplementary")
    if supplementary is not None:
        s = params.supplementary
        text += (
            f" Uzupełniający urlop macierzyński: {supplementary.days // 7} tyg., od "
            f"{long_date(supplementary.start)} do {long_date(supplementary.end)}."
        )
        sources += [s.sum_and_round.sources, s.once_after_maternity.sources]
        sources.append(s.week_is_7_days.sources)
    parental = _segment(timeline, "parental")
    if parental is not None:
        p = params.parental
        _, mothers = parental_weeks(scenario, params)
        text += (
            f" Urlop rodzicielski mamy, wzięty w całości od razu potem: {parental.days // 7} "
            f"tyg., od {long_date(parental.start)} do {long_date(parental.end)}."
            if parental.days == mothers * 7
            # Cut short (the mother's death): just the dates.
            else f" Urlop rodzicielski mamy: od {long_date(parental.start)} do "
            f"{long_date(parental.end)}."
        )
        sources += [parental_table(scenario, params).sources, p.exclusive_weeks.sources]
        sources.append(p.week_is_7_days.sources)
    father_text, father_sources = _father_dates(scenario, timeline, params)
    return CaseNote(
        id="computed",
        kind="computed",
        title="Co policzyliśmy",
        text=f"{text}{father_text} Tydzień urlopu to 7 dni kalendarzowych.",
        sources=_merge(*sources, *father_sources),
    )


# Section B: the father (guide pages 7-8).


def _father_notes(
    scenario: Scenario, timeline: Timeline, params: Params, cover: Coverage, loss: Loss | None
) -> list[CaseNote]:
    """The mother's special situation, taking over maternity leave, and what the father has.
    Nothing when no child lives, and nothing until the number of children is known."""
    if (loss is not None and loss.none_survived) or scenario.children_count is None:
        return []
    notes = [
        _mother_event(scenario, timeline, params, cover),
        _takeover(scenario, timeline, params, cover),
        _father(scenario, timeline, params, cover),
    ]
    return [note for note in notes if note is not None]


def _maternity_end(timeline: Timeline) -> dt.date | None:
    """The last day of maternity leave after the birth, whichever parent uses it."""
    ends = [s.end for s in timeline.segments if s.id in MATERNITY_PARTS]
    return max(ends) if ends else None


def _event_rule(scenario: Scenario, params: Params) -> Rule:
    """The Labour Code rule for the mother's special situation (taking over without one)."""
    f = params.father
    event = scenario.mother_event
    if event is None:
        return f.takeover_starts_after
    return {
        "incapacity": f.special_incapacity,
        "hospital": f.special_hospital,
        "death": f.special_death,
        "abandonment": f.special_abandonment,
    }[event.kind]


ARTICLE = {
    "incapacity": "art. 180 § 6",
    "hospital": "art. 180 § 10 i 11",
    "death": "art. 180 § 12",
    "abandonment": "art. 180 § 13",
}
"""The Labour Code provisions behind each special situation, as the text names them."""


def _quoting(sources: list[SourceRef], fragment: str) -> list[SourceRef]:
    return [s for s in sources if fragment in s.quote]


def _split(
    scenario: Scenario, timeline: Timeline, params: Params
) -> tuple[str, list[list[SourceRef]]]:
    """Who uses which part of maternity leave when the father takes part of it (or the leave
    ended with the mother's death)."""
    maternity = _segment(timeline, "maternity")
    father = _segment(timeline, "maternity-father")
    resumed = _segment(timeline, "maternity-resumed")
    event = scenario.mother_event
    rule = _event_rule(scenario, params).sources
    if maternity is None:
        return "", []
    if event is not None and event.kind == "death" and maternity.end == event.start:
        text = f" Urlop macierzyński mamy trwał do {long_date(maternity.end)}"
        if father is not None:
            text += f"; tata ma urlop od {long_date(father.start)} do {long_date(father.end)}"
        return f"{text}.", [rule]
    if father is None and _abandoned(maternity):
        verb = "trwał" if maternity.end < timeline.today else "trwa"
        weeks = params.father.special_after_weeks.value
        return (
            f" Urlop macierzyński mamy {verb} po porodzie do {long_date(maternity.end)}: część "
            "przypadająca po dniu porzucenia dziecka jej nie przysługuje, ale urlop po porodzie "
            f"nie może wynosić mniej niż {weeks} tygodni.",
            [params.father.abandonment_mother_loses.sources],
        )
    if father is None:
        return "", []
    text = (
        f" Mama korzysta z urlopu macierzyńskiego do {long_date(maternity.end)}, tata od "
        f"{long_date(father.start)} do {long_date(father.end)}"
    )
    if resumed is not None:
        text += f", a mama znów od {long_date(resumed.start)} do {long_date(resumed.end)}"
    return f"{text}.", [rule, params.father.total_cap.sources]


def _father_dates(
    scenario: Scenario, timeline: Timeline, params: Params
) -> tuple[str, list[list[SourceRef]]]:
    """The father's paternity and parental leave, as the timeline shows them."""
    f = params.father
    p = params.parental
    text = ""
    sources: list[list[SourceRef]] = []
    paternity = _segment(timeline, "paternity")
    deadline = _marker(timeline, "paternity-deadline")
    if paternity is not None and deadline is not None:
        text += (
            f" Urlop ojcowski: {paternity.days} dni, od {long_date(paternity.start)} do "
            f"{long_date(paternity.end)}; tata może go wziąć do {long_date(deadline.date)}."
        )
        sources += [f.paternity_days.sources, f.paternity_months.sources]
    parental = _segment(timeline, "parental-father")
    if parental is not None:
        length = f"{parental.days // 7} tyg." if parental.days % 7 == 0 else f"{parental.days} dni"
        text += (
            f" Urlop rodzicielski taty: {length}, od {long_date(parental.start)} do "
            f"{long_date(parental.end)}."
        )
        sources += [parental_table(scenario, params).sources, p.exclusive_weeks.sources]
        if coverage(scenario) in NOT_INSURED:
            sources.append(f.parental_uninsured_mother.sources)
    return text, sources


def _father_computed(scenario: Scenario, timeline: Timeline, params: Params) -> list[CaseNote]:
    """The mother has no benefit periods: what we computed is the father's alone."""
    text, sources = _father_dates(scenario, timeline, params)
    his = _segment(timeline, "maternity-father")
    if his is not None:  # after the death, abandonment or incapacity of an uninsured mother
        text = (
            f" Urlop macierzyński taty: od {long_date(his.start)} do {long_date(his.end)}." + text
        )
        sources = [params.father.special_uninsured.sources, *sources]
    if not text:
        return []
    return [
        CaseNote(
            id="computed",
            kind="computed",
            title="Co policzyliśmy",
            text=f"{text.strip()} Tydzień urlopu to 7 dni kalendarzowych.",
            sources=_merge(
                *sources,
                params.parental.week_is_7_days.sources,
                params.rules.week_is_7_days.sources,
            ),
        )
    ]


def _abandoned(maternity: Segment) -> bool:
    """The mother's maternity leave was cut after she abandoned the child (father.py cites
    art. 182 on it)."""
    return any(s.article == "art. 182" for s in maternity.sources)


def _mother_left(scenario: Scenario) -> bool:
    """The mother died or abandoned the child: her lane ended (father.py)."""
    event = scenario.mother_event
    return event is not None and event.kind in ("death", "abandonment")


def _not_employee(scenario: Scenario) -> bool:
    return scenario.fathers_work in ("contract", "business")


def _interrupted_work(
    scenario: Scenario, params: Params, cover: Coverage
) -> tuple[str, list[list[SourceRef]]]:
    """A father who is not an employee: his benefit for the mother's maternity leave needs him
    to interrupt his work (ustawa art. 29 ust. 3, 5-7, 9)."""
    if not _not_employee(scenario):
        return "", []
    return f" {INTERRUPTED_WORK}", [interrupted_work_rule(scenario, params, cover).sources]


def _mother_event(
    scenario: Scenario, timeline: Timeline, params: Params, cover: Coverage
) -> CaseNote | None:
    """Guide B.2: the mother's special situation and what the father takes over."""
    event = scenario.mother_event
    if event is None or not timeline.child_born:
        return None
    if cover in NOT_INSURED:
        return _uninsured_mother_event(scenario, timeline, params, cover)
    maternity = _segment(timeline, "maternity")
    if maternity is None:
        return None
    f = params.father
    after = f.special_after_weeks.value
    rule = _event_rule(scenario, params).sources
    article = ARTICLE[event.kind]
    father = _segment(timeline, "maternity-father")
    interrupted, interrupted_sources = _interrupted_work(scenario, params, cover)
    if father is not None:
        span = f"od {long_date(father.start)} do {long_date(father.end)}"
        title = f"Tata przejmuje urlop macierzyński od {long_date(father.start)}"
        sources = [_guide(f.special.sources), rule, f.total_cap.sources]
        match event.kind:
            case "incapacity":
                text = (
                    "Mama ma orzeczenie o niezdolności do samodzielnej egzystencji. Po "
                    f"wykorzystaniu po porodzie co najmniej {after} tygodni urlopu macierzyńskiego "
                    f"może zrezygnować z jego pozostałej części, a wykorzystuje ją tata: {span} "
                    f"(Kodeks pracy, {article})."
                )
            case "hospital":
                text = (
                    "Gdy mama przebywa w szpitalu, a stan zdrowia uniemożliwia jej opiekę nad "
                    f"dzieckiem, po wykorzystaniu po porodzie co najmniej {after} tygodni urlopu "
                    "macierzyńskiego może przerwać urlop na okres pobytu w szpitalu. Tę część "
                    f"wykorzystuje tata: {span} (Kodeks pracy, {article})."
                )
                resumed = _segment(timeline, "maternity-resumed")
                if resumed is not None:
                    text += (
                        f" Potem mama wraca na urlop: od {long_date(resumed.start)} do "
                        f"{long_date(resumed.end)}."
                    )
                elif event.end is None:
                    text += (
                        " Mama jest jeszcze w szpitalu, więc urlop taty pokazujemy do końca "
                        "urlopu macierzyńskiego."
                    )
            case "death":
                title = f"Urlop macierzyński taty od {long_date(father.start)}"
                text = (
                    "Bardzo nam przykro. Tacie przysługuje część urlopu macierzyńskiego "
                    f"przypadająca po dniu śmierci mamy: {span} (Kodeks pracy, {article})."
                )
                sources = [rule]
            case "abandonment":
                text = (
                    "Gdy mama porzuci dziecko w czasie urlopu macierzyńskiego, tacie przysługuje "
                    "część urlopu przypadająca po dniu porzucenia, nie wcześniej jednak niż po "
                    f"wykorzystaniu przez mamę po porodzie co najmniej {after} tygodni urlopu. "
                    f"Tata ma urlop {span} (Kodeks pracy, {article})."
                )
        if event.kind != "death":
            text += " Łączny wymiar urlopu macierzyńskiego się nie zmienia."
        return CaseNote(
            id="mother-event",
            kind="right",
            title=title,
            text=text + interrupted,
            sources=_merge(*sources, *interrupted_sources),
        )

    sorry = "Bardzo nam przykro. " if event.kind == "death" else ""
    earliest = timeline.birth_date + after * 7 * DAY
    if event.kind == "hospital" and event.end is not None and event.end < earliest:
        return CaseNote(
            id="mother-event",
            kind="right",
            title="Pobyt w szpitalu przed upływem 8 tygodni",
            text=(
                "Mama może przerwać urlop macierzyński na okres pobytu w szpitalu, a tata "
                "wykorzystać tę część urlopu, gdy mama wykorzysta po porodzie co najmniej "
                f"{after} tygodni urlopu macierzyńskiego, czyli od {long_date(earliest)}. Pobyt "
                f"skończył się wcześniej, {long_date(event.end)}, dlatego urlop mamy się nie "
                "zmienia."
            ),
            sources=_merge(_guide(f.special.sources), rule),
        )
    # Nothing passed to the father: the leave had ended, or he is not insured.
    covered = father_coverage(scenario) not in NOT_INSURED
    if event.kind == "death":
        ended = maternity.end < event.start or covered
    elif event.kind == "abandonment":
        ended = not _abandoned(maternity)
    else:
        ended = event.start > maternity.end
    if ended:
        verb = "kończy się" if maternity.end >= timeline.today else "skończył się"
        return CaseNote(
            id="mother-event",
            kind="right",
            title="Urlop macierzyński już się skończył"
            if maternity.end < timeline.today
            else "Urlop macierzyński kończy się wcześniej",
            text=(
                f"{sorry}Urlop macierzyński {verb} {long_date(maternity.end)}, więc nie zostaje "
                "jego część, którą mógłby przejąć tata."
            ),
            sources=_merge(_guide(f.special.sources), rule),
        )
    b = params.benefit
    family = (
        "tata albo inny członek najbliższej rodziny, który jest pracownikiem. Zasiłek "
        "macierzyński za ten okres przysługuje też ubezpieczonemu ojcu albo innemu ubezpieczonemu "
        "członkowi rodziny, który przerwał działalność zarobkową w celu sprawowania osobistej "
        "opieki nad dzieckiem."
    )
    no_insurance = (
        "Tata nie podlega jednak ubezpieczeniu chorobowemu, a bez niego zasiłek nie przysługuje"
    )
    if event.kind == "death":
        return CaseNote(
            id="mother-event",
            kind="right",
            title="Urlop macierzyński mamy",
            text=(
                f"Bardzo nam przykro. Urlop macierzyński mamy trwał do "
                f"{long_date(maternity.end)}. Pozostałą część urlopu może wykorzystać {family} "
                f"{no_insurance}."
            ),
            sources=_merge(rule, f.interrupted_work_death.sources, b.without_insurance.sources),
        )
    if event.kind == "abandonment":
        return CaseNote(
            id="mother-event",
            kind="right",
            title="Mamie nie przysługuje dalsza część urlopu",
            text=(
                f"Mama porzuciła dziecko {long_date(event.start)}. Część urlopu macierzyńskiego "
                "przypadająca po dniu porzucenia dziecka jej nie przysługuje, ale urlop po "
                f"porodzie nie może wynosić mniej niż {after} tygodni, więc trwa do "
                f"{long_date(maternity.end)}. Dalszą część mógłby wykorzystać tata, ale nie "
                "podlega ubezpieczeniu chorobowemu, a bez niego zasiłek nie przysługuje."
            ),
            sources=_merge(
                f.abandonment_mother_loses.sources,
                _guide(f.special.sources),
                rule,
                b.without_insurance.sources,
            ),
        )
    situation, part, benefit = {
        "incapacity": (
            "Mama ma orzeczenie o niezdolności do samodzielnej egzystencji.",
            "Pozostałą część urlopu macierzyńskiego",
            f.interrupted_work_incapacity,
        ),
        "hospital": (
            "Mama przebywa w szpitalu.",
            "Część urlopu macierzyńskiego odpowiadającą okresowi pobytu mamy w szpitalu",
            f.interrupted_work_hospital,
        ),
    }[event.kind]
    return CaseNote(
        id="mother-event",
        kind="right",
        title="Przejęcie urlopu wymaga ubezpieczenia chorobowego taty",
        text=(
            f"{situation} {part} mógłby wtedy wykorzystać tata albo inny członek najbliższej "
            "rodziny. Tata nie podlega jednak ubezpieczeniu chorobowemu, a bez niego zasiłek nie "
            "przysługuje, dlatego urlop mamy się nie zmienia."
        ),
        sources=_merge(_guide(f.special.sources), rule, b.without_insurance.sources),
    )


UNINSURED_SITUATION = {
    "death": "Mama nie podlegała ubezpieczeniu chorobowemu, ale",
    "abandonment": "Mama porzuciła dziecko. Nie podlegała ubezpieczeniu chorobowemu, ale",
    "incapacity": (
        "Mama ma orzeczenie o niezdolności do samodzielnej egzystencji i nie może sprawować "
        "osobistej opieki nad dzieckiem. Nie podlega ubezpieczeniu chorobowemu, ale"
    ),
}


def _uninsured_mother_event(
    scenario: Scenario, timeline: Timeline, params: Params, cover: Coverage
) -> CaseNote | None:
    """Art. 180 § 15, ustawa art. 29 ust. 9: the mother had no sickness insurance and died,
    abandoned the child, or cannot look after it with a ruling of incapacity."""
    event = scenario.mother_event
    assert event is not None
    if event.kind == "hospital":
        return None  # not among the cases of art. 180 § 15 (see the assumptions)
    f = params.father
    b = params.benefit
    sorry = "Bardzo nam przykro. " if event.kind == "death" else ""
    situation = UNINSURED_SITUATION[event.kind]
    after = UNINSURED_AFTER[event.kind]
    rule = f.special_uninsured.sources
    father = _segment(timeline, "maternity-father")
    if father is not None:
        interrupted, interrupted_sources = _interrupted_work(scenario, params, cover)
        return CaseNote(
            id="mother-event",
            kind="right",
            title=f"Urlop macierzyński taty od {long_date(father.start)}",
            text=(
                f"{sorry}{situation} tacie przysługuje część urlopu macierzyńskiego przypadająca "
                f"{after}: od {long_date(father.start)} do {long_date(father.end)} (Kodeks pracy, "
                f"art. 180 § 15).{interrupted}"
            ),
            sources=_merge(_guide(f.benefit.sources), rule, *interrupted_sources),
        )
    if father_coverage(scenario) in NOT_INSURED:
        return CaseNote(
            id="mother-event",
            kind="right",
            title="Urlop macierzyński taty wymaga ubezpieczenia chorobowego",
            text=(
                f"{sorry}{situation} część urlopu macierzyńskiego przypadająca {after} "
                "przysługuje tacie albo innemu członkowi najbliższej rodziny, który jest "
                "pracownikiem; zasiłek za ten okres — także ubezpieczonemu, który przerwał "
                "działalność zarobkową w celu sprawowania osobistej opieki nad dzieckiem. Tata nie "
                "podlega jednak ubezpieczeniu chorobowemu, a bez niego zasiłek nie przysługuje."
            ),
            sources=_merge(rule, f.special_uninsured_benefit.sources, b.without_insurance.sources),
        )
    loss = child_loss(scenario, params, timeline.birth_date, timeline.today)
    end = uninsured_maternity_end(scenario, params, timeline.birth_date, loss)
    if end is None:
        return None
    verb = "kończy się" if end >= timeline.today else "skończył się"
    return CaseNote(
        id="mother-event",
        kind="right",
        title="Urlop macierzyński już się skończył"
        if end < timeline.today
        else "Urlop macierzyński kończy się wcześniej",
        text=(
            f"{sorry}Urlop macierzyński, liczony od dnia porodu, {verb} {long_date(end)}, więc "
            f"nie zostaje jego część przypadająca {after}, którą mógłby wykorzystać tata."
        ),
        sources=_merge(rule, params.maternity.weeks_by_children.sources),
    )


def _takeover(
    scenario: Scenario, timeline: Timeline, params: Params, cover: Coverage
) -> CaseNote | None:
    """Guide B.1: after 14 weeks the father can take over the rest of maternity leave."""
    maternity = _segment(timeline, "maternity")
    if scenario.mother_event is not None or cover in NOT_INSURED or maternity is None:
        return None
    f = params.father
    b = params.benefit
    weeks = f.takeover_after_weeks.value
    sources = [f.takeover_after_weeks.sources, f.takeover_starts_after.sources]
    father = _segment(timeline, "maternity-father")
    interrupted, interrupted_sources = _interrupted_work(scenario, params, cover)
    if father is not None:
        return CaseNote(
            id="takeover",
            kind="choice",
            title=f"Tata przejmuje urlop macierzyński od {long_date(father.start)}",
            text=(
                "Mama wykorzystuje urlop macierzyński po porodzie do "
                f"{long_date(maternity.end)}. Dalszą część, od {long_date(father.start)} do "
                f"{long_date(father.end)}, przejmuje tata: jego urlop zaczyna się bezpośrednio "
                "po zakończeniu urlopu mamy. Łączny wymiar urlopu macierzyńskiego się nie zmienia."
                + interrupted
            ),
            sources=_merge(*sources, f.total_cap.sources, *interrupted_sources),
        )
    personal = _marker(timeline, "personal-weeks")
    if personal is None or maternity.end <= personal.date:
        return None  # nothing is left after the 14 weeks
    if father_coverage(scenario) in NOT_INSURED:
        if not scenario.father_takes_over:
            return None
        return CaseNote(
            id="takeover",
            kind="choice",
            title="Tata nie przejmie urlopu macierzyńskiego",
            text=(
                f"Po {weeks} tygodniach urlopu po porodzie mama może zostawić jego dalszą część "
                "tacie. Zasiłek macierzyński jest jednak wypłacany osobom podlegającym "
                "ubezpieczeniu chorobowemu, a tata mu nie podlega, dlatego oś pokazuje cały urlop "
                "u mamy."
            ),
            sources=_merge(*sources, b.paid_to_the_insured.sources, b.without_insurance.sources),
        )
    return CaseNote(
        id="takeover",
        kind="choice",
        title="Tata może przejąć część urlopu macierzyńskiego",
        text=(
            f"Po wykorzystaniu przez mamę co najmniej {weeks} tygodni urlopu macierzyńskiego po "
            "porodzie tata może przejąć jego dalszą część, czyli najwcześniej od "
            f"{long_date(personal.date + DAY)}. Urlop taty zaczyna się bezpośrednio po "
            "zakończeniu urlopu mamy, a łączny wymiar urlopu się nie zmienia." + interrupted
        ),
        sources=_merge(*sources, f.total_cap.sources, *interrupted_sources),
    )


def _father(scenario: Scenario, timeline: Timeline, params: Params, cover: Coverage) -> CaseNote:
    """Guide B.3-B.4: what the father has — paternity leave and his part of parental leave."""
    f = params.father
    p = params.parental
    b = params.benefit
    father = father_coverage(scenario)
    if father in NOT_INSURED:
        return _father_uninsured(scenario, params, father)
    paternity = _segment(timeline, "paternity")
    deadline = _marker(timeline, "paternity-deadline")
    parental = _segment(timeline, "parental-father")
    months = f.paternity_months.value
    shortest = f.paternity_min_part_days.value
    parts: list[str] = []
    sources: list[list[SourceRef]] = []
    if paternity is not None and deadline is not None:
        parts.append(
            f"Urlop ojcowski taty to najwyżej {f.paternity_days.value} dni. Można go "
            f"wykorzystać jednorazowo albo w {f.paternity_parts.value} częściach po co najmniej "
            f"{shortest} dni, do ukończenia przez dziecko {months} miesięcy życia, czyli do "
            f"{long_date(deadline.date)}."
        )
        sources += [f.paternity_days.sources, f.paternity_parts.sources, f.paternity_months.sources]
        if cover in NOT_INSURED:
            parts.append(
                "Urlop ojcowski przysługuje także wtedy, gdy mama nie podlega ubezpieczeniu "
                "chorobowemu."
            )
            sources.append(_quoting(f.paternity_who.sources, "matka nie podlega"))
    elif deadline is not None:
        parts.append(
            f"Do końca czasu na urlop ojcowski, {long_date(deadline.date)}, zostało mniej niż "
            f"{shortest} dni, a żadna część tego urlopu nie może być krótsza niż tydzień."
        )
        sources += [_law(f.paternity_parts.sources), f.paternity_months.sources]
    else:
        parts.append(
            "Czas na urlop ojcowski minął: można go wykorzystać do ukończenia przez dziecko "
            f"{months} miesięcy życia, a potem prawo do niego wygasa."
        )
        sources += [f.paternity_months.sources, f.paternity_expires.sources]
    if parental is not None:
        exclusive = p.exclusive_weeks.value
        if cover in NOT_INSURED:
            parts.append(
                "Mama nie była ubezpieczona w dniu porodu, a zasiłek macierzyński za okres urlopu "
                "rodzicielskiego przysługuje wtedy tacie."
                if timeline.child_born
                else "Jeśli mama nie będzie ubezpieczona w dniu porodu, zasiłek macierzyński za "
                "okres urlopu rodzicielskiego przysługuje tacie."
            )
            sources.append(f.parental_uninsured_mother.sources)
        elif _mother_left(scenario):
            # Her lane ended (father.py): what is left of the pool is his to use, not shared.
            parts.append("Urlop rodzicielski może wykorzystać tata.")
            sources.append(f.parental_together.sources)
        elif _mothers_parental(timeline):
            parts.append(
                f"Z urlopu rodzicielskiego {exclusive} tyg. należy wyłącznie do taty: nie można "
                "ich przenieść na mamę. Rodzice mogą korzystać z urlopu jednocześnie albo "
                "naprzemiennie, a tata może też wziąć go po mamie."
            )
            sources += [p.exclusive_weeks.sources, f.parental_together.sources]
        else:
            parts.append("Po urlopie macierzyńskim tata może wziąć urlop rodzicielski.")
            sources.append(f.parental_together.sources)
    work = scenario.fathers_work
    if work in ("contract", "business"):
        parts.append(
            "Tata nie jest pracownikiem, więc nie dostaje urlopu: za te okresy ma prawo do "
            "zasiłku macierzyńskiego, na tych samych zasadach co do wymiaru."
        )
        sources += [b.non_employees.sources, b.same_rules_for_non_employees.sources]
    if father == "unknown-work":
        parts.append(
            "Zasiłek macierzyński jest wypłacany osobom podlegającym ubezpieczeniu chorobowemu, "
            "a to zależy od tego, jak tata pracuje. Na razie oś zakłada, że tata mu podlega."
        )
        sources += [
            b.paid_to_the_insured.sources,
            b.obligatory_insurance.sources,
            b.voluntary_insurance.sources,
        ]
    elif father == "unknown-voluntary":
        parts.append(
            f"Przy {WORK_LOCATIVE[work or '']} ubezpieczenie chorobowe jest dobrowolne, więc "
            "trzeba ustalić, czy tata jest do niego zgłoszony. Na razie oś zakłada, że tak."
        )
        sources += [b.voluntary_insurance.sources, b.paid_to_the_insured.sources]
    if paternity is not None and parental is not None:
        title = "Tata: urlop ojcowski i urlop rodzicielski"
    elif paternity is not None:
        title = "Tata: urlop ojcowski"
    elif parental is not None:
        title = "Tata: urlop rodzicielski"
    else:
        title = "Uprawnienia taty"
    return CaseNote(
        id="father", kind="right", title=title, text=" ".join(parts), sources=_merge(*sources)
    )


def _father_uninsured(scenario: Scenario, params: Params, father: Coverage) -> CaseNote:
    """The father has no sickness insurance: no benefit periods on his lane."""
    b = params.benefit
    f = params.father
    if father == "not-working":
        text = (
            "Zasiłek macierzyński jest wypłacany osobom podlegającym ubezpieczeniu chorobowemu: "
            "obowiązkowemu (np. z umowy o pracę) albo dobrowolnemu (np. przy umowie zlecenia lub "
            "działalności gospodarczej). Z odpowiedzi wynika, że tata nie pracuje, więc nie ma "
            "umowy ani działalności, z której wynikałoby to ubezpieczenie, a bez niego zasiłek "
            "nie przysługuje. Urlop ojcowski przysługuje jednak także tacie, który zaczął pracę "
            "po narodzinach dziecka, o ile dziecko nie ukończyło "
            f"{f.paternity_months.value} miesięcy."
        )
        sources = [
            b.paid_to_the_insured.sources,
            b.obligatory_insurance.sources,
            b.voluntary_insurance.sources,
            b.without_insurance.sources,
            _quoting(f.paternity_who.sources, "rozpoczął pracę"),
        ]
    else:
        text = (
            f"Przy {WORK_LOCATIVE[scenario.fathers_work or '']} ubezpieczenie chorobowe jest "
            "dobrowolne, a tata nie jest do niego zgłoszony. Osoba, która nie podlega "
            "ubezpieczeniu chorobowemu, nie ma uprawnień do zasiłków, dlatego oś nie pokazuje "
            "okresów zasiłku taty."
        )
        sources = [
            b.voluntary_insurance.sources,
            b.voluntary_not_registered.sources,
            b.without_insurance.sources,
        ]
    return CaseNote(
        id="father",
        kind="risk",
        title="Tata: zasiłek wymaga ubezpieczenia chorobowego",
        text=text,
        sources=_merge(*sources),
    )
