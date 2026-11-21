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
