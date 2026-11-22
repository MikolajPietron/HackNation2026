"""The plans for a goal (engine/plans.py, F8) and the stress test (engine/stress.py, F11) as text
for the model: the engine's results, word for word, so the model explains and never computes."""

import json
from decimal import Decimal

from app.assistant.describe import source_label
from app.engine.amounts import dec, pln
from app.engine.models import SourceRef
from app.engine.plans import GOAL_LABEL, ParentFigures, Plan, PlansResult
from app.engine.stress import StressReport
from app.engine.wording import fmt

VERDICT = {
    "loss": "grozi utrata prawa albo plan przestaje pasować",
    "risk": "prawo zostaje, ale pojawia się ryzyko",
    "kept": "prawa zostają",
}


def describe_plans(result: PlansResult) -> str:
    goal = GOAL_LABEL[result.goal]
    if not result.plans:
        return f"Brak planów dla celu „{goal}”: {result.reason}"
    lines = [
        f"Plany dla celu „{goal}”, w kolejności według tego celu (liczył kalkulator). Pokaż "
        "je jako możliwości z ich skutkami; decyzja należy do rodziców. Plan zapisz dopiero, "
        "gdy rodzic go wybierze: narzędziami podanymi przy planie, dokładnie z tymi wartościami.",
    ]
    for plan in result.plans:
        lines += ["", *_plan(plan)]
    if result.notes:
        lines += ["", "Założenia porównania:", *(f"- {n}" for n in result.notes)]
    return "\n".join(lines)


def _plan(plan: Plan) -> list[str]:
    f = plan.figures
    lines = [
        f"{plan.rank}. {plan.title}" + (" (to Wasz obecny plan)" if plan.current else ""),
        f"   {plan.summary}",
        f"   Mama: {_parent(f.mother)}. Tata: {_parent(f.father)}.",
    ]
    if f.home_until is not None:
        lines.append(f"   Dziecko w domu z rodzicem na urlopie bez przerwy do {fmt(f.home_until)}.")
    if f.total is not None:
        lines.append(f"   Zasiłki za urlopy w planie razem: {pln(dec(f.total))}.")
    lines += [f"   Z czego rezygnujecie albo co zostaje na później: {g}" for g in plan.given_up]
    lines.append(f"   Jak zapisać: {_tools(plan)}")
    lines.append(f"   Źródła: {_sources(plan.sources)}")
    return lines


def _parent(f: ParentFigures) -> str:
    if not f.leave_days:
        return "bez urlopu"
    text = f"{_weeks(f.leave_days)} urlopu"
    if f.work_days:
        text += f" (w tym {_weeks(f.work_days)} z pracą na część etatu)"
    if f.back_to_work is not None:
        text += f", powrót do pracy {fmt(f.back_to_work)}"
    if f.total is not None:
        text += f", zasiłki {pln(dec(f.total))}"
    return text


def _weeks(days: int) -> str:
    weeks = Decimal(days) / 7
    shown = f"{weeks:.1f}".replace(".", ",").removesuffix(",0")
    return f"{shown} tyg."


def _tools(plan: Plan) -> str:
    patch = plan.patch
    parts = [
        {k: v for k, v in part.items() if v not in (None, False)}
        for part in patch["parental_parts"]
    ]
    calls = [f"set_parental_plan(parts={json.dumps(parts, ensure_ascii=False)})"]
    if patch.get("rate_815") is not None:
        calls.append(f"set_rate_choice(rate_815={json.dumps(patch['rate_815'])})")
    if patch.get("father_takes_over"):
        weeks = patch.get("mother_weeks_before_takeover")
        calls.append(
            "set_father_takeover(takes_over=true"
            + (f", mother_weeks={weeks}" if weeks else "")
            + ")"
        )
    return "; ".join(calls)


def _sources(sources: list[SourceRef]) -> str:
    named = []
    for s in sources:
        label = source_label(s)
        if label not in named:
            named.append(label)
    return "; ".join(named)


def describe_stress(report: StressReport) -> str:
    if report.sensitive:
        return (
            "W tej sytuacji aplikacja nie pokazuje wariantów „co by było, gdyby”. Nie proponuj "
            "ich i nie optymalizuj planu."
        )
    if not report.events:
        return f"Brak zdarzeń do sprawdzenia: {report.reason}"
    lines = [
        "Test planu: co zmieniłoby każde zdarzenie (liczył kalkulator; daty zdarzeń są "
        "przykładowe, podane przy każdym). Powiedz rodzicowi, gdzie grozi utrata prawa, bez "
        "straszenia i bez oceniania; decyzje zostaw rodzicom. Zdarzeń oznaczonych "
        "„(delikatnie)” — zdrowie i śmierć mamy — nie wymieniaj sam; mów o nich tylko, gdy "
        "rodzic o nie pyta.",
    ]
    for event in report.events:
        lines += [
            "",
            f"- {event.title} ({VERDICT[event.verdict]})"
            + (" (delikatnie)" if event.sensitive else ""),
            *(f"  Założenie: {a}" for a in event.assumed),
            *(f"  {line}" for line in event.lines),
        ]
        if event.risks:
            lines += [f"  Ryzyko „{n.title}”: {n.text}" for n in event.risks]
        if event.sources:
            lines.append(f"  Źródła: {_sources(event.sources)}")
    for skipped in report.skipped:
        lines.append(f"- {skipped.title}: nie da się policzyć ({skipped.reason})")
    return "\n".join(lines)
