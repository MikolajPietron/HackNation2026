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


class Rules(BaseModel):
    medical_certificate: Rule
    work_until_birth: Rule


class Params(BaseModel):
    version: str
    description: str
    maternity: MaternityParams
    rules: Rules

    def sources(self) -> list[SourceRef]:
        """Every source in the file, for the test that checks quotes against the guide."""
        return [
            *self.maternity.max_weeks_before_birth.sources,
            *self.rules.medical_certificate.sources,
            *self.rules.work_until_birth.sources,
        ]
