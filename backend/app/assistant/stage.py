"""What the model needs at this stage of the family's case (ZADANIA B.17).

Every chat request used to carry the literal text of every source (about 95 000 characters) and
every tool. The family's stage decides what can come up: a child on the way needs the pregnancy
chapter but not adoption; a child taken in needs section D but not the birth; the benefit base
matters once there is an amount. `stage_topics` names the parts of the sources and instructions
that apply, `SOURCE_TOPICS` puts every source into its parts (a source missing there fails
`tests/test_sources.py`), and `hidden_tools` leaves out the tools that would only fail here.

The topics are coarse on purpose: the instructions built from them are the cached prefix of the
prompt (prompts.stage_instructions), so they stay the same for many turns of one conversation.
"""

from typing import Literal

from app.assistant.guide import guide_sections
from app.assistant.law import kp_articles, ustawa_articles, zalacznik_sections
from app.engine.insurance import NOT_INSURED
from app.engine.models import Scenario, Timeline
from app.engine.money import pay_matters, requester_cover

Topic = Literal[
    "core",  # every family: insurance, the benefit, parental and paternity leave, requests
    "birth",  # a child born to the family or on the way
    "pregnancy",  # the child is on the way (or the mother's sick leave in pregnancy is recorded)
    "sick",  # the mother's sick leave in pregnancy is recorded: sick pay, sick benefit, rehab
    "born",  # the child is born: supplementary leave in law
    "mother-event",  # the mother's special situation is recorded (KP art. 180 § 6, 10-13)
    "takeover",  # the other parent takes over the rest of the leave
    "taken-in",  # section D: a child taken in for upbringing
    "loss",  # a stillbirth or the death of a child
    "job-loss",  # the mother's work ended in pregnancy: benefits after the insurance ended
    "money",  # an amount is known: the rates in law and the benefit base
    "pay-history",  # months of pay are recorded: the detailed rules of the benefit base
    "work",  # parental leave combined with work
    "za-zyciem",  # the child has the "Za życiem" certificate
    "debt",  # someone runs a business: contribution debt
    "plans",  # plans for a goal and the stress test make sense
]
SourceKind = Literal["guide", "kp", "ustawa", "zalacznik"]
SourceKey = tuple[SourceKind, str]

# Guide sections (guide.py) -> the topics they serve.
GUIDE_TOPICS: dict[str, tuple[Topic, ...]] = {
    "ZC.o": ("core",),
    "ZC.d": ("core",),
    "ZM": ("core",),
    "A.1": ("birth",),
    "A.2": ("core",),  # parental leave rules: section D.2 refers back to them
    "A.2-przypis": ("za-zyciem",),  # who issues the certificate; point A.2 says what it gives
    "A.3": ("loss",),
    "B": ("core",),
    "B.1": ("birth",),
    "B.2": ("birth",),
    "B.3": ("core",),
    "B.4": ("core",),
    "C": ("birth", "taken-in"),  # supplementary leave also after taking a child in
    "E": ("core",),
    "D": ("taken-in",),
    "D.1": ("taken-in",),
    "D.2": ("taken-in",),
    "H.1": ("birth",),  # risks in pregnancy and on the day of the birth
    "H.2": ("birth",),
    "H.3": ("birth",),
    "W": ("core",),
    "A.4": ("core",),
    "I": ("core",),
    "F": ("core",),
    "ZC": ("pregnancy",),
    "U": ("pregnancy",),
    "ZC.s": ("job-loss",),
    "G.1": ("core",),
    "G.2": ("core",),
    "G.3": ("core",),
}

# Labour Code articles (the part before " §") -> topics.
KP_TOPICS: dict[str, tuple[Topic, ...]] = {
    "art. 177": ("core",),
    "art. 92": ("sick",),
    "art. 180": ("birth",),  # § 1-3, the length of the leave; the rest: KP_EXCEPTIONS
    "art. 180¹": ("loss",),
    "art. 180²": ("born", "taken-in"),  # before the birth the guide's section C says enough
    "art. 182¹ᵃ": ("core",),
    "art. 182¹ᶜ": ("core",),
    "art. 182¹ᵈ": ("core",),
    "art. 182¹ᵉ": ("work",),  # before any work is planned the guide's section E says enough
    "art. 182¹ᶠ": ("work",),
    "art. 182¹ᵍ": ("core",),
    "art. 182³": ("core",),
    "art. 183": ("taken-in",),
    "art. 183¹": ("core",),  # a week is 7 days, for every leave
}
KP_EXCEPTIONS: dict[str, tuple[Topic, ...]] = {
    # Art. 180 § 4-5 and 14: the father takes over after 14 weeks, the total length; art. 183
    # § 2 applies them to the leave after taking a child in.
    **{f"art. 180 § {p}": ("birth", "taken-in") for p in (4, 5, 14)},
    # Art. 180 § 8-9: the requests to hand over the rest of the leave, once that is planned.
    **{f"art. 180 § {p}": ("takeover", "mother-event") for p in (8, 9)},
    # Art. 180 § 6, 10-13 and 16: the mother's special situations (guide B.2 sums them up).
    **{f"art. 180 § {p}": ("mother-event",) for p in (6, 10, 11, 12, 13, 16)},
    # Sick pay is computed like the benefit base: the base points cite it.
    "art. 92 § 2": ("sick", "money"),
}
"""Provisions placed apart from the rest of their article."""

# Ustawa zasiłkowa articles (the number after "art.") -> topics.
USTAWA_TOPICS: dict[str, tuple[Topic, ...]] = {
    "2": ("debt",),
    "2a": ("debt",),
    "64": ("debt",),
    "3": ("money",),
    "7": ("sick",),
    "8": ("sick",),
    "11": ("sick",),
    "13": ("sick",),
    "18": ("sick",),
    "19": ("sick",),
    "22": ("sick",),
    "29a": ("core",),
    "30": ("job-loss",),  # ust. 1 and 4: USTAWA_EXCEPTIONS below
    "30a": ("money",),
    "31": ("money",),
    "36": ("money",),  # ust. 2 and 4: PAY_HISTORY below
    "37": ("pay-history",),
    "38": ("pay-history",),
    "42": ("pay-history",),
    "43": ("money",),  # the base stays after a short break (e.g. sick leave, then maternity)
    "45": ("money",),
    "47": ("money",),
    "48": ("money",),  # ust. 2: PAY_HISTORY below
    "48a": ("pay-history",),
    "49": ("pay-history",),
    "50": ("pay-history",),
    "52": ("money",),
    # ZUS pays for a period after the insurance ended; page 1 of the guide says who pays otherwise.
    "61": ("job-loss", "sick"),
}
USTAWA_EXCEPTIONS: dict[str, tuple[Topic, ...]] = {
    # The maternity benefit after the insurance ended: the insurance point says when it applies
    # (ust. 1), the protection point cites a fixed-term contract extended to the birth (ust. 4).
    "art. 30 ust. 1": ("birth",),
    "art. 30 ust. 4": ("birth",),
    # Paid for every day: art. 31 ust. 5 applies it to the maternity benefit.
    "art. 11 ust. 4": ("sick", "money"),
    # Only the base computed month by month needs these provisions of the money articles.
    **dict.fromkeys(("art. 36 ust. 2", "art. 36 ust. 4", "art. 48 ust. 2"), ("pay-history",)),
}


def source_topics(kind: SourceKind, key: str) -> tuple[Topic, ...]:
    """The topics a source serves. KeyError for a source nobody placed: add it above."""
    match kind:
        case "guide":
            return GUIDE_TOPICS[key]
        case "kp":
            return KP_EXCEPTIONS.get(key) or KP_TOPICS[key.partition(" §")[0]]
        case "ustawa":
            return USTAWA_EXCEPTIONS.get(key) or USTAWA_TOPICS[key.split()[1]]
        case "zalacznik":
            return ("money",)


def all_sources() -> list[SourceKey]:
    """Every source the model may get, in the order the instructions list them."""
    return [
        *(("guide", key) for key in guide_sections()),
        *(("kp", key) for key in kp_articles()),
        *(("ustawa", key) for key in ustawa_articles()),
        *(("zalacznik", key) for key in zalacznik_sections()),
    ]


def sources_for(topics: frozenset[Topic]) -> list[SourceKey]:
    return [s for s in all_sources() if set(source_topics(*s)) & topics]


def money_known(scenario: Scenario) -> bool:
    """The amount question was answered (an amount, months of pay, or "I don't know", after
    which the interview asks about 81,5%) or the rate was chosen (in the chat or in the app)."""
    pays = (scenario.mother_pay, scenario.father_pay)
    histories = (scenario.mother_pay_history, scenario.father_pay_history)
    return (
        any(p is not None for p in pays)
        or any(h is not None for h in histories)
        or scenario.rate_815 is not None
    )


def all_children_lost(scenario: Scenario) -> bool:
    return bool(scenario.losses) and len(scenario.losses) >= (scenario.children_count or 1)


def mother_left(scenario: Scenario) -> bool:
    event = scenario.mother_event
    return event is not None and event.kind in ("death", "abandonment")


def stage_topics(scenario: Scenario) -> frozenset[Topic]:
    topics: set[Topic] = {"core"}
    if scenario.taken_in is not None:
        topics.add("taken-in")
    else:
        topics.add("birth")
        topics.add("born" if scenario.child_born is True else "pregnancy")
        if scenario.sick_leave:
            topics |= {"pregnancy", "sick"}
        if scenario.losses:
            topics.add("loss")
        if scenario.job_loss is not None:
            topics.add("job-loss")
        if scenario.mother_event is not None:
            topics.add("mother-event")
    if scenario.father_takes_over or scenario.taken_in_handover:
        topics.add("takeover")
    if money_known(scenario):
        topics.add("money")
    if scenario.mother_pay_history is not None or scenario.father_pay_history is not None:
        topics.add("pay-history")
    if any(part.work_fraction for part in scenario.parental_parts):
        topics.add("work")
    if scenario.za_zyciem:
        topics.add("za-zyciem")
    debt = (scenario.mother_contribution_debt, scenario.father_contribution_debt)
    if "business" in (scenario.mothers_work, scenario.fathers_work) or any(debt):
        topics.add("debt")
    if scenario.taken_in is None and not all_children_lost(scenario) and not mother_left(scenario):
        topics.add("plans")
    return frozenset(topics)


# Tools that can only fail or do nothing in some stages (each mirrors the tool's own check).
TAKEN_IN_ONLY = frozenset(
    {"set_school_postponed", "set_adoption_ruling", "set_leave_handover", "set_foster_before"}
)
BIRTH_ONLY = frozenset(
    {
        # Pregnancy and the birth (section A, B.1-B.2): the own birth date of a child taken in
        # goes through `set_taken_in`. `set_hospital_care` serves both paths (art. 183 § 3¹).
        "set_birth_date",
        "set_leave_before_birth",
        "set_medical_certificate",
        "set_child_loss",
        "set_father_takeover",
        "set_mother_situation",
        # Losing the job, a raised contribution base and sick leave: in this pregnancy.
        "set_job_loss",
        "set_contribution_base_raised",
        "set_sick_leave",
        "set_mother_over_50",
        "set_rehab_benefit",
    }
)
AFTER_BIRTH_ONLY = frozenset({"set_child_loss", "set_mother_situation", "set_hospital_care"})
"""They need the date of birth (each asks for `set_birth_date` first)."""
PLANS = frozenset({"propose_plans", "stress_test"})
AFTER_TOTAL_LOSS = frozenset(
    {"set_hospital_care", "set_za_zyciem", "set_parental_plan", "set_parental_work"}
)
"""No child to look after: no parental leave, no supplementary leave to count."""


def hidden_tools(scenario: Scenario, timeline: Timeline | None) -> set[str]:
    """The tools that cannot apply now. Checked again before every request, so a fact recorded
    earlier in the same turn (e.g. the birth, a contract of mandate) brings its tools back."""
    hidden: set[str] = set()
    if scenario.taken_in is not None:
        hidden |= BIRTH_ONLY
    else:
        hidden |= TAKEN_IN_ONLY
        if scenario.child_born is True:
            hidden.add("set_medical_certificate")  # only to start leave before an expected birth
            if scenario.sick_leave is None:
                hidden.add("set_sick_leave")  # sick leave in pregnancy is asked before the birth
        else:
            hidden |= AFTER_BIRTH_ONLY
        if all_children_lost(scenario):
            hidden |= AFTER_TOTAL_LOSS
    if "plans" not in stage_topics(scenario):
        hidden |= PLANS
    if not scenario.sick_leave:
        hidden.add("set_mother_over_50")
    no_limit = timeline is None or timeline.element("sick-benefit-limit") is None
    if no_limit and scenario.rehab_benefit is None:
        hidden.add("set_rehab_benefit")
    if scenario.mothers_work not in ("contract", "business"):
        hidden.add("set_voluntary_insurance")
    if scenario.fathers_work not in ("contract", "business"):
        hidden.add("set_father_insurance")
    if not {scenario.mothers_work, scenario.fathers_work} & {"employment", "contract"}:
        hidden.add("set_payer_size")
    if not (pay_matters(scenario, "mother") or pay_matters(scenario, "father")):
        hidden |= {"set_monthly_pay", "set_pay_history"}
    if requester_cover(scenario) in NOT_INSURED:
        hidden.add("set_rate_choice")
    return hidden
