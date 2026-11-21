"""Legal parameters. Every number carries its sources; the engine never hardcodes them."""

from pydantic import BaseModel, Field

from app.engine.models import SourceRef


class Param[T](BaseModel):
    value: T
    note: str | None = None
    sources: list[SourceRef] = Field(min_length=1)


class Rule(BaseModel):
    """A rule without a number (e.g. where to file an application), kept for its sources."""

    sources: list[SourceRef] = Field(min_length=1)


class MaternityParams(BaseModel):
    weeks_by_children: Param[list[int]]
    max_weeks_before_birth: Param[int]
    mother_personal_weeks: Param[int]
    rate_percent: Param[float]


class ParentalParams(BaseModel):
    weeks_single: Param[int]
    weeks_multiple: Param[int]
    reserved_weeks_per_parent: Param[int]
    max_parts: Param[int]
    last_year_of_child_age: Param[int]
    rate_percent: Param[float]
    application_days_before: Param[int]


class PaternityParams(BaseModel):
    days: Param[int]
    min_part_days: Param[int]
    window_months: Param[int]
    rate_percent: Param[float]
    application_days_before: Param[int]


class FlatRateParams(BaseModel):
    rate_percent: Param[float]
    application_days_after_birth: Param[int]
    other_parent_rate_percent: Param[float]


class PayerParams(BaseModel):
    employer_pays_above_insured: Param[int]


class Rules(BaseModel):
    maternity_application: Rule
    forms_merged_into_zam: Rule
    first_day_is_birth: Rule
    week_is_7_days: Rule
    parents_share_parental: Rule


class Params(BaseModel):
    version: str
    description: str
    maternity: MaternityParams
    parental: ParentalParams
    paternity: PaternityParams
    flat_rate: FlatRateParams
    payer: PayerParams
    rules: Rules
