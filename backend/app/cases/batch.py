"""Read the example cases ahead of the demo, outside the web server, into the same cache the API
uses: then every case opens at once for the jury. Cases already read are skipped. At the end it
prints how often the calculator agrees with the decisions of ZUS (the goal in CLAUDE.md:
"zgodność z decyzjami ZUS: X/86").

    cd backend && uv run python -m app.cases.batch            # every case not read yet
    uv run python -m app.cases.batch S01 S25 --jobs 2         # some cases, two at a time
    uv run python -m app.cases.batch --summary out.json       # also save the per-case results
"""

import argparse
import asyncio
import time
from collections import Counter
from pathlib import Path

from pydantic_ai.exceptions import ModelRateLimitError

from app.api.cases import get_case_cache, get_cases_folder, get_reader_factory
from app.cases.cache import CachedRead, file_digest
from app.cases.catalog import CaseFile, list_case_files
from app.cases.pages import render_pages
from app.cases.report import build_report
from app.clock import today_in_warsaw
from app.config import get_settings
from app.services.params import load_params

# A provider's 429 means "slow down": wait this long and try the same case again.
RATE_LIMIT_WAIT = 90
RATE_LIMIT_TRIES = 4


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("ids", nargs="*", help="np. S01 S25; puste = wszystkie")
    parser.add_argument("--jobs", type=int, default=1, help="ile spraw naraz (domyślnie 1)")
    parser.add_argument("--summary", type=Path, help="zapisz wyniki spraw do pliku JSON")
    parser.add_argument(
        "--only-cached", action="store_true", help="niczego nie czytaj, tylko podsumuj odczytane"
    )
    args = parser.parse_args()

    settings = get_settings()
    cache = get_case_cache(settings)
    make_reader = get_reader_factory(settings)
    cases = list_case_files(get_cases_folder(settings))
    if args.ids:
        cases = [case for case in cases if case.id in set(args.ids)]
    print(f"Spraw: {len(cases)} · model: {settings.cases_model_name}", flush=True)

    limit = asyncio.Semaphore(max(1, args.jobs))

    async def read(case: CaseFile) -> None:
        key = file_digest(case.path)
        if cache.has(key):
            return
        async with limit:
            started = time.monotonic()
            pages = await asyncio.to_thread(render_pages, case.path.read_bytes())
            to_read = [page for page in pages if not page.blank]
            for attempt in range(1, RATE_LIMIT_TRIES + 1):
                try:
                    facts = await make_reader().read(to_read)
                    break
                except ModelRateLimitError as error:
                    # The provider asks to slow down (429): wait and try the same case again.
                    if attempt == RATE_LIMIT_TRIES:
                        print(f"{case.id} BŁĄD limit: {str(error)[:400]}", flush=True)
                        return
                    print(f"{case.id} limit (429), czekam {RATE_LIMIT_WAIT} s…", flush=True)
                    await asyncio.sleep(RATE_LIMIT_WAIT)
                except Exception as error:  # noqa: BLE001 — report and go on with the next case
                    print(f"{case.id} BŁĄD {type(error).__name__}: {str(error)[:400]}", flush=True)
                    return
            cache.put(key, CachedRead(facts=facts, pages=len(pages), pages_read=len(to_read)))
            print(
                f"{case.id} ok · {len(to_read)} str. · {time.monotonic() - started:.0f} s",
                flush=True,
            )

    if not args.only_cached:
        await asyncio.gather(*(read(case) for case in cases))

    report = build_report(get_cases_folder(settings), cache, load_params(), today_in_warsaw())
    read = [row for row in report.rows if row.read]
    print()
    print(f"Przeczytane: {report.read}/{len(report.rows)}")
    print(f"Decyzja ZUS w aktach: {Counter(row.zus for row in read)}")
    print(f"Zgodność z decyzjami ZUS: {report.agree}/{report.decided} (gdzie obie strony są znane)")
    with_amounts = sum(1 for row in read if row.payments)
    print(f"Z osią: {sum(row.timeline for row in read)} · z kwotami: {with_amounts}")
    for row in read:
        if row.match is False:
            print(
                f"  różnica {row.id} ({row.category}): ZUS {row.zus}, my {row.ours} — {row.title}"
            )
    if args.summary:
        args.summary.write_text(report.model_dump_json(indent=1), encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main())
