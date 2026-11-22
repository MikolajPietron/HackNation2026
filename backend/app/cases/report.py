"""The agreement report (FUNKCJE F37): the calculator's answer for every example case already
read, set against the decision of ZUS in the case. From the cache only: nothing is read here,
nothing is sent anywhere. Used by `GET /api/cases/report` and by `python -m app.cases.batch`."""

import datetime as dt
from pathlib import Path

from pydantic import BaseModel

from app.engine import Params

from .assess import assess
from .cache import CaseCache, file_digest
from .catalog import list_case_files
from .models import Outcome


class ReportRow(BaseModel):
    id: str
    category: str
    read: bool
    title: str = ""
    zus: Outcome = "unknown"
    ours: Outcome = "unknown"
    match: bool | None = None
    covered: bool | None = None
    timeline: bool = False
    payments: int = 0
    insurance: str = ""
    """Why the calculator says what it says about the insurance."""
    comparison: str = ""
    problem: str | None = None


class Report(BaseModel):
    rows: list[ReportRow]
    read: int
    decided: int
    """Cases where both the decision of ZUS and the calculator's answer are known."""
    agree: int


def build_report(folder: Path, cache: CaseCache, params: Params, today: dt.date) -> Report:
    rows: list[ReportRow] = []
    for case in list_case_files(folder):
        stored = cache.get(file_digest(case.path))
        if stored is None:
            rows.append(ReportRow(id=case.id, category=case.category, read=False))
            continue
        result = assess(
            stored.facts,
            case_id=case.id,
            pages=stored.pages,
            pages_read=stored.pages_read,
            cached=True,
            params=params,
            today=today,
        )
        rows.append(
            ReportRow(
                id=case.id,
                category=case.category,
                read=True,
                title=stored.facts.title,
                zus=result.comparison.zus,
                ours=result.comparison.ours,
                match=result.comparison.match,
                covered=result.insurance.covered,
                timeline=result.timeline is not None,
                payments=len(result.timeline.payments) if result.timeline else 0,
                insurance=result.insurance.text,
                comparison=result.comparison.text,
                problem=result.problem,
            )
        )
    read = [row for row in rows if row.read]
    decided = [row for row in read if row.match is not None]
    return Report(
        rows=rows,
        read=len(read),
        decided=len(decided),
        agree=sum(1 for row in decided if row.match),
    )
