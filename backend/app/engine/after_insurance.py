"""The maternity benefit after the insurance ended in pregnancy: ustawa zasiłkowa art. 30 ust. 1,
behind the guide's "w określonych sytuacjach również po ustaniu tego ubezpieczenia" (page 4).

A mother whose employment ended in pregnancy through the employer's death, bankruptcy or
liquidation, or in breach of the law confirmed by a final court judgment (`Scenario.job_loss`):
- until the birth: the benefit equal to the maternity benefit (pregnancy.py, guide page 4);
- after the birth: the maternity benefit (art. 30 ust. 1), for the periods the ustawa pays it
  for: maternity, supplementary and parental leave (art. 29a ust. 1). She is no longer an
  employee, so she gets no leave: the benefit is for the period corresponding to the leave
  (guide page 4). No request to an employer and no special protection: she files ZAM with ZUS
  (guide A.4, a woman who is not an employee), and ZUS pays every benefit for a period after
  the insurance ended (art. 61 ust. 1 pkt 2 lit. d; applications.py);
- maternity leave before the birth cannot start once the employment has ended: from the next
  day she has the benefit equal to the maternity benefit instead.
While a breach of the law has not been confirmed by a final judgment, the benefit after the
birth is drawn as an option: it depends on the judgment.

Any other end of work before the birth: no insurance on the day of the birth, no maternity
benefit (insurance.py, guide section H, risk 3).

Our readings, not settled by the materials (CLAUDE.md, open questions):
- art. 30 ust. 1 does not limit the periods, so we draw all of art. 29a ust. 1: maternity,
  supplementary and parental leave (the 81,5% request stays open to her as to any mother);
- leave before the birth that had already started when the employment ended goes on as
  maternity leave (no benefit equal to the maternity benefit for those days);
- the benefit base is the one given for the 12 months before (simple case), as for the benefit
  until the birth: art. 43 keeps the base when one benefit follows another without a break.
"""

import datetime as dt

from app.engine.draft import DAY, Draft, merge_sources
from app.engine.models import CaseNote, JobLoss, Scenario, Timeline
from app.engine.params import Params
from app.engine.wording import fmt, long_date

REASON = {
    "bankruptcy": "upadłości pracodawcy",
    "liquidation": "likwidacji pracodawcy",
    "employer-death": "śmierci pracodawcy",
    "unlawful": "rozwiązania umowy o pracę z naruszeniem przepisów prawa",
}
"""After "z powodu"."""
PERIODS = ("maternity", "maternity-resumed", "supplementary", "parental")
"""The mother's periods after the birth the benefit after the insurance ended is paid for (with
the parts of the parents' plan, `parental-mother-<k>`)."""


def after_job_loss(scenario: Scenario) -> JobLoss | None:
    """The job loss in pregnancy that gives the maternity benefit after the birth, or None."""
    loss, birth = scenario.job_loss, scenario.anchor_date
    if loss is None or loss.reason == "other" or scenario.taken_in is not None:
        return None
    if birth is None or loss.ended_on >= birth:
        return None
    if scenario.mothers_work not in ("employment", None):
        return None  # pregnancy.py refuses it: the guide's case is a contract of employment
    return loss


def confirmed(loss: JobLoss) -> bool:
    """The employer's death, bankruptcy or liquidation, or a breach of the law confirmed by a
    final court judgment."""
    return loss.reason != "unlawful" or loss.court_confirmed is True


def prenatal_start(scenario: Scenario, birth: dt.date) -> dt.date | None:
    """The first day of maternity leave before the birth, if the mother takes (took) it."""
    if scenario.child_born:
        days = scenario.prenatal_days(birth)
        return birth - days * DAY if days else None
    weeks = scenario.leave_before_birth_weeks
    return birth - weeks * 7 * DAY if weeks else None


def leave_before_cut(scenario: Scenario) -> bool:
    """The employment ended (giving the benefit after it) before maternity leave before the birth
    started, or with no such leave: none can start any more."""
    loss, birth = after_job_loss(scenario), scenario.anchor_date
    if loss is None or birth is None:
        return False
    start = prenatal_start(scenario, birth)
    return start is None or start > loss.ended_on


def without_leave_before(scenario: Scenario) -> Scenario:
    """The scenario the rules draw: no maternity leave before the birth after the job loss (the
    weeks planned or said before it are kept in the answers)."""
    if not leave_before_cut(scenario):
        return scenario
    return scenario.model_copy(update={"leave_before_birth_weeks": 0, "leave_start": None})


def after_insurance_lines(draft: Draft, scenario: Scenario, params: Params) -> None:
    """Every period of the mother after the birth says she has the benefit after the insurance
    ended, not leave; while the court has not confirmed the breach of the law, it is an option."""
    loss = after_job_loss(scenario)
    if loss is None:
        return
    p, b = params.pregnancy, params.benefit
    ok = confirmed(loss)
    line = (
        f"Zatrudnienie mamy ustało {fmt(loss.ended_on)}, w ciąży, z powodu {REASON[loss.reason]}. "
        "Zasiłek macierzyński przysługuje jej również po ustaniu ubezpieczenia"
        + ("" if ok else ", jeśli naruszenie przepisów prawa stwierdzi prawomocne orzeczenie sądu")
        + ". Nie jest już pracownicą, więc nie dostaje urlopu: zasiłek przysługuje za okres "
        "odpowiadający urlopowi."
    )
    sources = merge_sources(
        p.maternity_after_job_loss.sources,
        p.benefit_periods.sources,
        b.paid_to_the_insured.sources,
        b.non_employees.sources,
    )
    draft.segments = [
        segment.model_copy(
            update={
                "tone": segment.tone if ok else "option",
                "details": [*segment.details, line],
                "sources": merge_sources(segment.sources, sources),
            }
        )
        if segment.lane == "mother" and _after_birth_period(segment.id)
        else segment
        for segment in draft.segments
    ]


def _after_birth_period(segment_id: str) -> bool:
    return segment_id in PERIODS or segment_id.startswith("parental-mother-")


def after_insurance_assumptions(scenario: Scenario) -> list[str]:
    """`scenario`: the answers as given (before `without_leave_before`)."""
    loss, birth = after_job_loss(scenario), scenario.anchor_date
    if loss is None or birth is None:
        return []
    assumptions = [
        "Zasiłek macierzyński po ustaniu ubezpieczenia pokazujemy za wszystkie okresy, za które "
        "ustawa zasiłkowa go przyznaje (art. 29a ust. 1): urlopu macierzyńskiego, "
        "uzupełniającego i rodzicielskiego. Art. 30 ust. 1 tych okresów nie ogranicza.",
        "Wniosek o 81,5% (art. 30a ust. 1) zostawiamy mamie jako możliwość także po ustaniu "
        "ubezpieczenia: materiały nie mówią, czy go wtedy wyklucza.",
    ]
    if not leave_before_cut(scenario) and prenatal_start(scenario, birth) is not None:
        assumptions.append(
            "Urlop macierzyński przed porodem zaczął się, zanim ustało zatrudnienie: pokazujemy go "
            "dalej jako urlop macierzyński, bez zasiłku w wysokości zasiłku macierzyńskiego za te "
            "dni. Materiały nie mówią, jak te świadczenia się łączą."
        )
    return assumptions


# The case explanation (explain.py: the mother's insurance).


def insurance_note(scenario: Scenario, timeline: Timeline, params: Params) -> CaseNote | None:
    """The right to the maternity benefit after the insurance ended in pregnancy."""
    loss = after_job_loss(scenario)
    if loss is None:
        return None
    p, b = params.pregnancy, params.benefit
    born = timeline.child_born
    ok = confirmed(loss)
    after = "Po porodzie mama ma prawo" if born else "Po porodzie mama będzie mieć prawo"
    if ok:
        right = f"{after} do zasiłku macierzyńskiego, choć nie podlega już ubezpieczeniu."
    else:
        right = (
            f"{after} do zasiłku macierzyńskiego, jeśli naruszenie przepisów prawa stwierdzi "
            "prawomocne orzeczenie sądu."
        )
    text = (
        f"Zatrudnienie mamy ustało {long_date(loss.ended_on)}, w ciąży, z powodu "
        f"{REASON[loss.reason]}. Zasiłek macierzyński przysługuje również w razie urodzenia "
        "dziecka po ustaniu ubezpieczenia chorobowego, jeśli ustało ono w ciąży wskutek śmierci, "
        "upadłości lub likwidacji pracodawcy albo z naruszeniem przepisów prawa stwierdzonym "
        f"prawomocnym orzeczeniem sądu. {right} Przysługuje za okres urlopu macierzyńskiego, "
        "a potem uzupełniającego i rodzicielskiego. Mama nie jest już pracownicą, więc nie "
        "dostaje urlopu, tylko zasiłek za okres odpowiadający urlopowi; wypłaca go ZUS."
    )
    return CaseNote(
        id="insurance",
        kind="right" if ok else "risk",
        title="Zasiłek macierzyński po ustaniu ubezpieczenia" + ("" if ok else " — po wyroku sądu"),
        text=text,
        sources=merge_sources(
            p.maternity_after_job_loss.sources,
            p.benefit_periods.sources,
            b.non_employees.sources,
            p.zus_after_insurance.sources,
        ),
    )
