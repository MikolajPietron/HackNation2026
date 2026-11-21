"""Legal parameters. Every number carries its sources; the engine never hardcodes them."""

from fractions import Fraction

from pydantic import BaseModel, Field

from app.engine.models import SourceRef


class Param[T](BaseModel):
    value: T
    note: str | None = None
    sources: list[SourceRef] = Field(min_length=1)


class Rule(BaseModel):
    """A rule without a number (e.g. a required document), kept for its sources."""

    sources: list[SourceRef] = Field(min_length=1)


class MaternityParams(BaseModel):
    max_weeks_before_birth: Param[int]
    weeks_by_children: Param[list[int]]
    mother_personal_weeks: Param[int]


class BenefitRules(BaseModel):
    """Who has the right to the maternity benefit (guide point "Urodzenie dziecka", A4)."""

    insured_mother: Rule
    paid_to_the_insured: Rule
    obligatory_insurance: Rule
    voluntary_insurance: Rule
    insured_on_birth_day: Rule
    voluntary_not_registered: Rule
    work_ended_before_birth: Rule
    without_insurance: Rule
    non_employees: Rule
    same_rules_for_non_employees: Rule


class ParentalParams(BaseModel):
    weeks_by_children: Param[list[int]]
    """Both parents together: one child, more children."""
    weeks_by_children_za_zyciem: Param[list[int]]
    exclusive_weeks: Param[int]
    """Weeks that belong to one parent only and cannot be passed to the other."""
    max_parts: Param[int]
    deadline_age: Param[int]
    """The leave ends at the latest with the calendar year in which the child reaches this age."""
    after_maternity: Rule
    joint: Rule
    week_is_7_days: Rule
    za_zyciem_certificate: Rule


class TermHospitalRule(BaseModel):
    """A child born after the 37th week: when a hospital stay gives supplementary leave."""

    limit_weeks: int
    counted_from_day: int
    """Hospital days count from this day after the birth."""
    min_consecutive_days: int
    first_day_from: int
    first_day_to: int
    """The first of those consecutive days falls between these days after the birth."""
    sources: list[SourceRef] = Field(min_length=1)


class SupplementaryParams(BaseModel):
    limit_weeks_early: Param[int]
    """Born before the end of the 28th week or weighing no more than 1000 g."""
    limit_weeks_preterm: Param[int]
    """Born after the 28th and before the end of the 37th week, weighing more than 1000 g."""
    term: TermHospitalRule
    situations: Rule
    once_after_maternity: Rule
    one_parent: Rule
    multiples: Rule
    sum_and_round: Rule
    week_is_7_days: Rule


class LossParams(BaseModel):
    """Stillbirth or death of the child (guide point "Szczególna sytuacja"; KP art. 180¹)."""

    life_weeks: Param[int]
    """A death before the end of this many weeks of life counts as early."""
    weeks_after_birth: Param[int]
    """Early death or stillbirth: maternity leave lasts this many weeks after the birth..."""
    days_after_death: Param[int]
    """...but not less than this many days from the death; a later death keeps the leave
    for this many days."""
    survivors: Rule
    """More children at once: the leave follows the number of children who live."""
    other_leaves: Rule
    """The same 7 days apply to supplementary and parental leave (art. 180² § 7, 182¹ᵍ)."""
    parental_for_care: Rule


class FatherParams(BaseModel):
    """Guide section B (pages 7-8) and the Labour Code behind it."""

    benefit: Rule
    """When the father can have the maternity benefit for maternity leave at all."""
    paternity_days: Param[int]
    paternity_parts: Param[int]
    paternity_min_part_days: Param[int]
    paternity_months: Param[int]
    """Paternity leave is used before the child completes this many months of life."""
    paternity_who: Rule
    paternity_children: Rule
    paternity_expires: Rule
    parental_together: Rule
    parental_uninsured_mother: Rule
    takeover_after_weeks: Param[int]
    takeover_starts_after: Rule
    special_after_weeks: Param[int]
    """Incapacity, hospital, abandonment: not before the mother used this many weeks."""
    special: Rule
    special_incapacity: Rule
    special_hospital: Rule
    special_death: Rule
    special_abandonment: Rule
    total_cap: Rule


class PregnancyParams(BaseModel):
    """The sickness benefit in pregnancy, the benefit after losing a job in pregnancy and the
    risks to the right to benefits (guide pages 2-4 and section H, pages 9-10; KP art. 92)."""

    sick_benefit: Rule
    e_zla: Rule
    insured_needed: Rule
    waiting_days_obligatory: Param[int]
    """The right arises after this many days of uninterrupted obligatory insurance."""
    waiting_days_voluntary: Param[int]
    employer_days: Param[int]
    """Days of incapacity in a calendar year paid by the employer (wynagrodzenie chorobowe)."""
    employer_days_from_50: Param[int]
    """The same, after the calendar year in which the employee turned 50."""
    employer_pay_in_pregnancy: Rule
    benefit_after_employer: Rule
    no_pay_without_right: Rule
    non_employee_from_day_one: Rule
    rate_percent: Param[int]
    period: Rule
    max_days: Param[int]
    """The benefit period (okres zasiłkowy)."""
    until_birth: Rule
    job_loss_benefit: Rule
    job_loss_employer_gone: Rule
    job_loss_unlawful: Rule
    job_loss_rate_percent: Param[int]
    risk_sham: Rule
    risk_base_raised: Rule
    # The rehabilitation benefit after the sickness benefit (ustawa art. 18-19).
    rehab_benefit: Rule
    rehab_max_months: Param[int]
    """At most this many months (art. 18 ust. 2)..."""
    rehab_month_days: Param[int]
    """...of this many days each (art. 22 with art. 11 ust. 5)."""
    rehab_decides: Rule
    """The ZUS medical examiner rules on the conditions; the decision rests on that ruling."""
    rehab_objection: Rule
    rehab_rate_percent: Param[int]
    """Percent of the sickness benefit base when the incapacity falls in pregnancy."""


class ParentalPlanParams(BaseModel):
    """Guide section E (page 9) and B.3 (page 7): parental leave split between the parents, in
    parts, and combined with part-time work (Labour Code art. 182¹ᵃ § 6-7, 182¹ᵈ § 2, 182¹ᵉ,
    182¹ᶠ)."""

    max_work_fraction: Param[Fraction]
    """The most an employee may work during parental leave, as a part of full time."""
    work_request_days: Param[int]
    """The request to start work is filed at least this many days before."""
    max_weeks_with_work: Param[list[int]]
    """The longest parental leave extended by work: one child, more children."""
    max_weeks_with_work_za_zyciem: Param[list[int]]
    rest_of_time: Rule
    extension: Rule
    extension_paid: Rule
    extension_in_days: Rule
    extension_of_that_part: Rule
    parts_of_both_parents: Rule
    both_at_once: Rule


class TakenInKindParams(BaseModel):
    """One way of taking a child in (Labour Code art. 183 § 1 or § 1¹, § 4 or § 4¹-§ 4⁵)."""

    who: Rule
    weeks_by_children: Param[list[int]]
    age: Param[int]
    """The leave lasts at most until the child reaches this age."""
    age_school_postponed: Param[int] | None
    """Foster care: the age limit when compulsory schooling was postponed."""
    parental_weeks_by_children: Param[list[int]]
    """Both parents together: one child, more children taken in at once."""
    parental_weeks_minimum: Param[int]
    """When the leave lasted only the minimum weeks (art. 183 § 3)."""
    parental_weeks_za_zyciem: Param[list[int]]
    parental_weeks_za_zyciem_minimum: Param[int]
    parental_age: Param[int] | None
    """Adoption: parental leave at most until the child reaches this age. None = the rule for a
    born child (the end of the calendar year in which the child turns `parental.deadline_age`)."""


class TakenInParams(BaseModel):
    """Guide section D (pages 8-9): a child taken in for upbringing; Labour Code art. 183."""

    insured: Rule
    benefit: Rule
    leave: Rule
    minimum_weeks: Param[int]
    request_days: Param[int]
    """The leave is requested within this many days of taking the child in."""
    latest_start_days: Param[int]
    """The leave starts at the latest this many days after taking the child in."""
    parental: Rule
    parental_parts: Rule
    paternity_months: Param[int]
    """Adoption: paternity leave within this many months of the final adoption ruling..."""
    paternity_age: Param[int]
    """...and not after the child reaches this age."""
    # Edge cases of art. 183: supplementary leave, passing the leave on, foster care first.
    supplementary: Rule
    """§ 3¹: supplementary leave for a hospital stay after the child was taken in."""
    handover_after_weeks: Param[int]
    """§ 2 with art. 180 § 4: the rest of the leave passes to the other parent after this many
    weeks."""
    after_foster_leave: Rule
    """§ 7: adoption after foster care, the leave less what was used as a foster family."""
    after_foster_parental: Rule
    """§ 8: the same for parental leave."""
    foster: TakenInKindParams
    adoption: TakenInKindParams


class MoneyParams(BaseModel):
    """Guide section G "Wysokość zasiłku macierzyńskiego" (page 9) and the ustawa zasiłkowa
    behind it: the rates, the 81,5% request and the benefit base."""

    rate_full: Param[float]
    """Percent of the base for maternity, supplementary and paternity leave."""
    rate_parental: Param[float]
    """Percent of the base for parental leave."""
    rate_single: Param[float]
    """Percent of the base for maternity and parental leave after the mother's request."""
    request_days: Param[int]
    """The request for `rate_single` is filed not later than this many days after the birth."""
    other_parent_parental: Rule
    """The other parent's own weeks of parental leave stay at `rate_parental`."""
    first_year: Rule
    """With the request: no day of parental benefit in the first year -> 70%, and a top-up."""
    contributions_percent: Param[float]
    """Deducted from the gross pay (employee) or the contribution base (non-employee)."""
    base_employee: Rule
    """The base of an employee: the average monthly pay of 12 calendar months."""
    base_non_employee: Rule
    """The base of a non-employee: the average monthly income of 12 calendar months."""
    days_in_month: Param[int]
    """The base for one day is this fraction of the monthly base."""
    every_day: Rule
    """The benefit is due for every day, days off work included."""


class Rules(BaseModel):
    medical_certificate: Rule
    work_until_birth: Rule
    week_is_7_days: Rule
    first_day_is_birth: Rule
    rest_after_birth: Rule


class ApplicationParams(BaseModel):
    """Applications and protection (guide A.4 page 6, page 1 footnote 1, page 12, section I page
    10; Labour Code art. 177, 180 § 8-9 and § 16, 180² § 4-5, 182¹ᵈ § 1, 182³ § 2)."""

    paid_by_payer_or_zus: Rule
    payer_more_than_insured: Param[int]
    """The payer pays the benefit itself when it reports more insured than this; else ZUS."""
    payer_count_day: Rule
    employee_request: Rule
    one_request: Rule
    employer_pays_or_z3: Rule
    non_employee_zam: Rule
    contract_zam: Rule
    attachments: Rule
    zam_form: Rule
    parental_days_before: Param[int]
    supplementary_days_before_end: Param[int]
    supplementary_hospital_certificate: Rule
    paternity_days_before: Param[int]
    father_maternity_days_before: Param[int]
    """Taking over after 14 weeks, or the mother's incapacity (art. 180 § 9)."""
    father_maternity_on_request: Rule
    """The mother in hospital, dead or gone: a request with no deadline (art. 180 § 16)."""
    resignation_days_before: Param[int]
    protection: Rule
    protection_early_request_days: Param[list[int]]
    """An early request: the ban starts this many days before a part of maternity leave,
    supplementary or parental leave, paternity leave."""
    fixed_term_extended: Rule
    protection_employees_only: Rule


class Params(BaseModel):
    version: str
    description: str
    maternity: MaternityParams
    benefit: BenefitRules
    supplementary: SupplementaryParams
    parental: ParentalParams
    loss: LossParams
    father: FatherParams
    pregnancy: PregnancyParams
    taken_in: TakenInParams
    rules: Rules
    applications: ApplicationParams
    parental_plan: ParentalPlanParams
    money: MoneyParams

    def sources(self) -> list[SourceRef]:
        """Every source in the file, for the test that checks quotes against the documents."""
        found: list[SourceRef] = []

        def walk(value: object) -> None:
            if isinstance(value, SourceRef):
                found.append(value)
            elif isinstance(value, BaseModel):
                for name in type(value).model_fields:
                    walk(getattr(value, name))
            elif isinstance(value, list):
                for item in value:
                    walk(item)

        walk(self)
        return found
