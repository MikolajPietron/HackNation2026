"""Legal parameters. Every number carries its sources; the engine never hardcodes them."""

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
    foster: TakenInKindParams
    adoption: TakenInKindParams


class Rules(BaseModel):
    medical_certificate: Rule
    work_until_birth: Rule
    week_is_7_days: Rule
    first_day_is_birth: Rule
    rest_after_birth: Rule


class Params(BaseModel):
    version: str
    description: str
    maternity: MaternityParams
    benefit: BenefitRules
    supplementary: SupplementaryParams
    parental: ParentalParams
    loss: LossParams
    father: FatherParams
    taken_in: TakenInParams
    rules: Rules

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
