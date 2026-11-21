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
