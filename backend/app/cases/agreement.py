"""The agreement report: how often the calculator agrees with the decisions of ZUS (the goal in
CLAUDE.md: "zgodność z decyzjami ZUS: X/86"), from the readings already in the cache. Nothing is
read here (no AI, no cost, nothing sent anywhere): a case not read yet is listed as such. Used by
`GET /api/cases/agreement` and by `python -m app.cases.batch`."""

import datetime as dt
from collections import Counter

from app.engine import Params

from .assess import assess
from .cache import CaseCache, file_digest
from .catalog import CaseFile
from .models import AgreementReport, AgreementRow


def agreement(
    cases: list[CaseFile],
    cache: CaseCache,
    params: Params,
    today: dt.date,
    *,
    configured: bool = True,
) -> AgreementReport:
    rows: list[AgreementRow] = []
    for case in cases:
        stored = cache.get(file_digest(case.path))
        if stored is None:
            rows.append(AgreementRow(id=case.id, category=case.category, read=False))
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
        comparison = result.comparison
        rows.append(
            AgreementRow(
                id=case.id,
                category=case.category,
                read=True,
                title=stored.facts.title,
                zus=comparison.zus,
                ours=comparison.ours,
                match=comparison.match,
                reason=comparison.reason,
                reason_text=comparison.reason_text,
                covered=result.insurance.covered,
                timeline=result.timeline is not None,
                payments=len(result.timeline.payments) if result.timeline else 0,
                problem=result.problem,
            )
        )
    read = [row for row in rows if row.read]
    decided = [row for row in read if row.match is not None]
    return AgreementReport(
        configured=configured,
        total=len(rows),
        read=len(read),
        decided=len(decided),
        agree=sum(1 for row in decided if row.match),
        zus=dict(Counter(row.zus for row in read if row.zus is not None)),
        reasons=dict(Counter(row.reason for row in decided if row.reason is not None)),
        with_timeline=sum(1 for row in read if row.timeline),
        with_amounts=sum(1 for row in read if row.payments),
        rows=rows,
    )
