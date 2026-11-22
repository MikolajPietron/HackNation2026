"""F14 "Nie przysługuje" z dalszą drogą (FUNKCJE 4.2; ZADANIA B.8): where the case explanation
says there is no right, the point right after it says what the family has instead and what would
give the right, only as far as the materials say it (explain.py adds it).

- The mother is not insured on the day of the birth (insurance.py: not registered for the
  voluntary insurance, not working, or her work ended before the birth). Instead: the father's
  benefit for parental leave and his paternity leave (guide B.3, B.4), when he is insured or
  assumed so; after an employment that ended, the extension of a fixed-term contract until the
  birth (not a contract to replace an absent employee), with the maternity benefit after a
  fixed-term contract (guide I, KP art. 177 § 3 and § 3¹; ustawa art. 30 ust. 4).
  To have the right, while the child is on the way: sickness insurance on the day of the birth
  (guide pages 3-5 and 10), with the guide's warning about a contract or a business concluded
  only for that (section H, risk 1).
- The father is not insured. On a contract or with a business: registering for the voluntary
  insurance; not working: paternity leave is due also to a father who started work after the
  birth, until the child completes 12 months (guide B.4).
- A child taken in by a foster family past the age limit of 7, while nobody has said whether
  compulsory schooling was postponed: then the limit is 10 (guide D.1; KP art. 183 § 1).

- For a parent without sickness insurance (the mother, the father) also, as "Co zamiast": the
  ZUS Poradnik says that people who cannot get the maternity benefit because of their work
  situation (e.g. unemployed, students, a contract for a specific task) have the parental
  allowance (świadczenie rodzicielskie) or the maternity pay (uposażenie macierzyńskie). Only
  that sentence, without an amount or conditions: the materials give neither (the ustawa names
  the allowance's amount only in art. 31 ust. 3a, without stating it).
Nothing after a loss when no child lives: there is nothing to offer in its place.
"""

from app.engine.adoption import birthday, cover_of, taken_in_leave, taker
from app.engine.after_insurance import FIXED_TERM, fixed_term_sources
from app.engine.draft import merge_sources
from app.engine.father import paternity_deadline
from app.engine.insurance import NOT_INSURED, coverage, father_coverage, work_ended_before_birth
from app.engine.loss import child_loss
from app.engine.models import CaseNote, Scenario, Segment, SourceRef, Timeline
from app.engine.params import Params
from app.engine.wording import long_date, weeks_or_days

WORK_LOCATIVE = {"contract": "umowie zlecenia", "business": "własnej działalności gospodarczej"}
"""After "przy" (as in explain.py)."""


def add_way_notes(
    notes: list[CaseNote], scenario: Scenario, timeline: Timeline, params: Params
) -> list[CaseNote]:
    """Each "co dalej" point right after the point that says there is no right."""
    for anchors, note in (
        (("job-loss", "insurance"), _mother_way(scenario, timeline, params)),
        (("father",), _father_way(scenario, timeline, params)),
        (("taken-in-leave",), _taken_in_way(scenario, params)),
    ):
        if note is not None:
            at = _after(notes, anchors)
            notes = [*notes[:at], note, *notes[at:]]
    return notes


def _after(notes: list[CaseNote], anchors: tuple[str, ...]) -> int:
    for anchor in anchors:
        found = next((i for i, n in enumerate(notes) if n.id == anchor), None)
        if found is not None:
            return found + 1
    return len(notes)


def _way_note(
    note_id: str,
    subject: str,
    instead: list[str],
    todo: list[str],
    sources: list[list[SourceRef]],
) -> CaseNote | None:
    if not instead and not todo:
        return None
    parts = []
    if instead:
        parts.append("Co zamiast: " + " ".join(instead))
    if todo:
        parts.append("Co zrobić, żeby przysługiwał: " + " ".join(todo))
    if instead and todo:
        title = f"{subject}: co zamiast i co zrobić"
    elif instead:
        title = f"{subject}: co zamiast"
    else:
        title = f"{subject}: co zrobić, żeby przysługiwał"
    return CaseNote(
        id=note_id, kind="risk", title=title, text=" ".join(parts), sources=merge_sources(*sources)
    )


def _quoting(sources: list[SourceRef], fragment: str) -> list[SourceRef]:
    return [s for s in sources if fragment in s.quote]


def _allowance(params: Params) -> tuple[str, list[SourceRef]]:
    """The parental allowance or the maternity pay instead of the benefit (ZUS Poradnik)."""
    return (
        "Kto z powodu swojej sytuacji zawodowej nie może skorzystać z zasiłku macierzyńskiego, "
        "a sprawuje opiekę nad dzieckiem, ma świadczenie rodzicielskie albo uposażenie "
        "macierzyńskie (np. osoba bezrobotna, studentka lub student, osoba pracująca na umowę "
        "o dzieło). Kwot i warunków tych świadczeń nie ma w naszych materiałach; więcej na "
        "stronie „Świadczenie rodzicielskie” w portalu Gov.pl.",
        params.benefit.instead_of_benefit.sources,
    )


def _no_child_lives(scenario: Scenario, timeline: Timeline, params: Params) -> bool:
    loss = child_loss(scenario, params, timeline.birth_date, timeline.today)
    return loss is not None and loss.none_survived


def _segment(timeline: Timeline, segment_id: str) -> Segment | None:
    return next((s for s in timeline.segments if s.id == segment_id), None)


# The mother.


def _mother_way(scenario: Scenario, timeline: Timeline, params: Params) -> CaseNote | None:
    if scenario.taken_in is not None or coverage(scenario) not in NOT_INSURED:
        return None
    if _no_child_lives(scenario, timeline, params):
        return None
    instead, instead_sources = _mother_instead(scenario, timeline, params)
    todo, todo_sources = _mother_todo(scenario, timeline, params)
    return _way_note(
        "insurance-way", "Zasiłek mamy", instead, todo, [*instead_sources, *todo_sources]
    )


def _mother_instead(
    scenario: Scenario, timeline: Timeline, params: Params
) -> tuple[list[str], list[list[SourceRef]]]:
    """The father's rights when the mother is not insured; a fixed-term contract extended by
    law until the birth."""
    b, f = params.benefit, params.father
    lines: list[str] = []
    sources: list[list[SourceRef]] = []
    father = father_coverage(scenario)
    parental = [s for s in timeline.segments if s.lane == "father" and s.id.startswith("parental")]
    paternity = _segment(timeline, "paternity")
    deadline = next((m for m in timeline.markers if m.id == "paternity-deadline"), None)
    if father not in NOT_INSURED:
        if parental:
            start, end = min(s.start for s in parental), max(s.end for s in parental)
            rule = (
                "Mama nie była ubezpieczona w dniu porodu, więc zasiłek macierzyński za okres "
                "urlopu rodzicielskiego przysługuje tacie"
                if timeline.child_born
                else "Jeśli mama nie będzie ubezpieczona w dniu porodu, zasiłek macierzyński za "
                "okres urlopu rodzicielskiego przysługuje tacie"
            )
            lines.append(
                f"{rule}: na osi {weeks_or_days(sum(s.days for s in parental))}, od "
                f"{long_date(start)} do {long_date(end)}."
            )
            sources.append(f.parental_uninsured_mother.sources)
        if paternity is not None and deadline is not None:
            lines.append(
                "Urlop ojcowski przysługuje tacie także wtedy, gdy mama nie podlega "
                f"ubezpieczeniu chorobowemu: można go wykorzystać do {long_date(deadline.date)}."
            )
            sources += [_quoting(f.paternity_who.sources, "matka nie podlega"), deadline.sources]
        if lines and father in ("unknown-work", "unknown-voluntary"):
            lines.append(
                "Tata musi przy tym podlegać ubezpieczeniu chorobowemu; na razie zakładamy, że "
                "podlega."
            )
            sources.append(b.paid_to_the_insured.sources)
    # Her employment ended before the birth for a reason that gives no benefit (insurance.py).
    if work_ended_before_birth(scenario) and scenario.mothers_work in ("employment", None):
        lines.append(FIXED_TERM)
        sources.append(fixed_term_sources(params))
    allowance, allowance_sources = _allowance(params)
    lines.append(allowance)
    sources.append(allowance_sources)
    return lines, sources


def _mother_todo(
    scenario: Scenario, timeline: Timeline, params: Params
) -> tuple[list[str], list[list[SourceRef]]]:
    """While the child is on the way: what the day of the birth needs."""
    if timeline.child_born:
        return [], []
    b, p = params.benefit, params.pregnancy
    if coverage(scenario) == "not-registered":
        work = WORK_LOCATIVE[scenario.mothers_work or "contract"]
        return [
            f"Przy {work} ubezpieczenie chorobowe jest dobrowolne, więc trzeba się do niego "
            "zgłosić. Liczy się dzień porodu: jeśli mama będzie wtedy podlegać ubezpieczeniu "
            "chorobowemu, po porodzie nabędzie prawo do zasiłku macierzyńskiego. Gdy się zgłosi, "
            "napisz o tym asystentowi, a oś się przeliczy."
        ], [
            b.voluntary_insurance.sources,
            b.voluntary_not_registered.sources,
            b.insured_on_birth_day.sources,
            b.insured_mother.sources,
        ]
    return [
        "Zasiłek macierzyński jest wypłacany osobom podlegającym ubezpieczeniu chorobowemu: "
        "obowiązkowemu (np. z umowy o pracę) albo dobrowolnemu (np. przy umowie zlecenia lub "
        "działalności gospodarczej). Liczy się dzień porodu: po porodzie prawo do zasiłku "
        "macierzyńskiego nabywa mama, która jest wtedy ubezpieczona.",
        "Uwaga: jeśli umowę zawarto albo działalność podjęto tylko po to, żeby zgłosić się do "
        "ubezpieczenia chorobowego i dostać zasiłki, ZUS po postępowaniu może uznać, że zawarto "
        "ją dla pozoru, i wydać decyzję o niepodleganiu ubezpieczeniom społecznym.",
    ], [
        b.paid_to_the_insured.sources,
        b.obligatory_insurance.sources,
        b.voluntary_insurance.sources,
        b.insured_on_birth_day.sources,
        b.insured_mother.sources,
        p.risk_sham.sources,
    ]


# The father.


def _father_way(scenario: Scenario, timeline: Timeline, params: Params) -> CaseNote | None:
    """Only where the explanation has the father's point (explain.py, `_father_notes`)."""
    if scenario.taken_in is not None or scenario.children_count is None:
        return None
    father = father_coverage(scenario)
    if father not in NOT_INSURED or _no_child_lives(scenario, timeline, params):
        return None
    b, f = params.benefit, params.father
    if father == "not-registered":
        work = WORK_LOCATIVE[scenario.fathers_work or "contract"]
        todo = [
            f"Przy {work} ubezpieczenie chorobowe jest dobrowolne, więc trzeba się do niego "
            "zgłosić: osoba, która nie podlega ubezpieczeniu chorobowemu, nie ma uprawnień do "
            "zasiłków. Gdy tata się zgłosi, napisz o tym asystentowi, a oś się przeliczy."
        ]
        sources = [
            b.voluntary_insurance.sources,
            b.voluntary_not_registered.sources,
            b.without_insurance.sources,
        ]
    else:
        deadline = paternity_deadline(timeline.birth_date, params)
        estimate = "" if timeline.child_born else " Liczymy od przewidywanej daty porodu."
        todo = (
            []
            if deadline < timeline.today
            else [
                "Urlop ojcowski przysługuje także tacie, który rozpoczął pracę po narodzinach "
                f"dziecka, o ile dziecko nie ukończyło {f.paternity_months.value} miesięcy: "
                f"najpóźniej do {long_date(deadline)}.{estimate}"
            ]
        )
        sources = (
            [_quoting(f.paternity_who.sources, "rozpoczął pracę"), f.paternity_months.sources]
            if todo
            else []
        )
    allowance, allowance_sources = _allowance(params)
    return _way_note("father-way", "Zasiłek taty", [allowance], todo, [*sources, allowance_sources])


# A child taken in.


def _taken_in_way(scenario: Scenario, params: Params) -> CaseNote | None:
    """A foster child past the age limit of 7: with postponed schooling it would be 10."""
    later = params.taken_in.foster.age_school_postponed
    if scenario.taken_in != "foster" or scenario.school_postponed is not None or later is None:
        return None
    leave = taken_in_leave(scenario, params)
    birth = scenario.birth_date
    if leave is None or not leave.too_old or birth is None:
        return None
    if leave.start >= birthday(birth, later.value) or cover_of(scenario, taker(scenario)) in (
        NOT_INSURED
    ):
        return None
    todo = [
        "Jeśli wobec dziecka podjęto decyzję o odroczeniu obowiązku szkolnego, urlop przysługuje "
        f"nie dłużej niż do ukończenia przez nie {later.value} lat. Napisz wtedy o tym "
        "asystentowi, a oś się przeliczy."
    ]
    return _way_note(
        "taken-in-way",
        "Urlop na warunkach urlopu macierzyńskiego",
        [],
        todo,
        [later.sources, params.taken_in.foster.age.sources],
    )
