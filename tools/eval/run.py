"""Run the eval scenarios against a running backend and print a pass/fail table.

Costs real LLM calls (one per chat step). Not part of CI. See README.md.

    cd backend && uv run python ../tools/eval/run.py --base http://127.0.0.1:8010 --out run.json
    cd backend && uv run python ../tools/eval/run.py --only twins-and-back --runs 3
    cd backend && uv run python ../tools/eval/run.py --rescore run.json   # no LLM calls
    cd backend && uv run python ../tools/eval/run.py --compare a.json b.json   # no LLM calls

After the checks it prints time to the first text, turn time, tokens (cached too) and cost per
scenario, from the `done` event of every turn (ZADANIA B.17).
"""

import argparse
import asyncio
import datetime as dt
import hashlib
import json
import re
import statistics
import sys
import time
import uuid
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))

from checks import (  # noqa: E402
    OUT_OF_SCOPE,
    SYMPATHY,
    Check,
    Turn,
    check_brief,
    check_mentions,
    check_notes_covered,
    check_question,
    check_quotes,
    check_reply_dates,
    check_timeline,
    extract_dates,
    facts,
    load_sources,
    opening_note_ids,
    source_dates,
    timeline_dates,
)
from scenarios import SCENARIOS  # noqa: E402

EXPECTED_TODAY = "2026-11-21"
SCENARIO_BY_ID = {s["id"]: s for s in SCENARIOS}


async def chat(client: httpx.AsyncClient, base: str, sid: str, step: dict) -> Turn:
    body = {"session_id": sid}
    body.update({"event": step["event"]} if "event" in step else {"message": step["say"]})
    turn = Turn()
    start = time.monotonic()
    async with client.stream("POST", f"{base}/api/chat", json=body, timeout=300) as response:
        if response.status_code != 200:
            turn.error = f"HTTP {response.status_code}: {(await response.aread())[:200]!r}"
            return turn
        async for line in response.aiter_lines():
            if not line.strip():
                continue
            event = json.loads(line)
            match event["type"]:
                case "text":
                    if turn.first_text_seconds is None:
                        turn.first_text_seconds = time.monotonic() - start
                    turn.text += event["delta"]
                case "tool-call":
                    turn.tool_calls.append({"name": event["name"], "args": event.get("args", {})})
                case "tool-result":
                    turn.tool_results.append({"name": event["name"], "ok": event["ok"]})
                case "timeline":
                    turn.timelines.append(event)
                case "focus":
                    turn.focus.append(event["element_id"])
                case "error":
                    turn.error = event["message"]
                case "done":
                    turn.done = True
                    turn.usage = event.get("usage") or {}
    turn.seconds = time.monotonic() - start
    return turn


def _subset(want: dict, got: dict) -> bool:
    return all(got.get(k) == v for k, v in want.items())


def tool_checks(step: dict, calls: list[dict], results: list[dict]) -> list[Check]:
    out = []
    for want in step.get("tools", []):
        named = [c for c in calls if c["name"] == want["name"]]
        ok = any(_subset(want.get("args", {}), c["args"]) for c in named)
        oks = [r["ok"] for r in results if r["name"] == want["name"]]
        detail = f"calls {[c['args'] for c in named]}, results {oks}"
        out.append(Check(f"tool {want['name']}", ok and any(oks), detail))
    for name in step.get("no_tools", []):
        called = [c for c in calls if c["name"] == name]
        out.append(Check(f"no tool {name}", not called, str([c["args"] for c in called])))
    setters = [c["name"] for c in calls if c["name"].startswith("set_")]
    if step.get("out_of_scope") or step.get("event") or step.get("no_setters"):
        # Nobody answered anything: the assistant must not record answers itself.
        out.append(Check("no unrequested scenario change", not setters, ", ".join(setters)))
    return out


def app_texts(*timelines: dict | None) -> list[str]:
    """The app's own wording (explanation and element texts): not a source to quote."""
    out = []
    for t in timelines:
        if not t:
            continue
        out += [n["text"] for n in t["notes"]] + [n["title"] for n in t["notes"]]
        for s in t["segments"]:
            out += [s["summary"], *s["details"]]
        for m in t["markers"]:
            out += [m["summary"], *m["details"]]
        out += t.get("assumptions", [])
    return out


def step_checks(step: dict, rec: dict, sources: dict, src_dates: set) -> list[Check]:
    """All checks of one finished step; `rec` holds what the turn produced (see run_scenario)."""
    text, before, after, question = rec["reply"], rec["before"], rec["after"], rec["question"]
    checks: list[Check] = []
    if rec.get("error") or not rec.get("done", True):
        checks.append(Check("turn finished", False, rec.get("error") or "no done event"))
    checks += tool_checks(step, rec["tools"], rec["tool_results"])
    if "timeline" in step:
        checks += check_timeline(after, step["timeline"])
    for eid in step.get("changed", []):
        checks.append(Check(f"changed {eid}", eid in rec["changed"], str(rec["changed"])))
    for nid in step.get("changed_notes", []):
        checks.append(
            Check(f"changed note {nid}", nid in rec["changed_notes"], str(rec["changed_notes"]))
        )
    if rec.get("live_differs"):
        checks.append(Check("restore = live", False, "GET /api/session differs from the stream"))

    user_dates = {
        dt.date(y, m, d) for y, m, d in extract_dates(step.get("say", ""), default_year=2026)
    }
    extra = user_dates | src_dates | (timeline_dates(before) if before else set())
    extra |= {dt.date.fromisoformat(iso) for iso in step.get("extra_dates", [])}
    checks.append(check_reply_dates(text, after, extra))
    mention = step.get("mention", {})
    checks += check_mentions(text, mention.get("dates", []), mention.get("numbers", []))
    for pattern in step.get("require", []):
        checks.append(Check(f"says /{pattern[:30]}/", re.search(pattern, text, re.I) is not None))
    for pattern in step.get("forbid", []):
        m = re.search(pattern, text, re.I)
        checks.append(Check(f"never /{pattern[:30]}/", m is None, m.group(0) if m else ""))
    for iso in step.get("not_repeat", []):
        x = dt.date.fromisoformat(iso)
        hit = any(
            mo == x.month and d == x.day and y in (None, x.year) for y, mo, d in extract_dates(text)
        )
        checks.append(Check(f"does not repeat {iso}", not hit, soft=True))
    if step.get("sensitive"):
        checks.append(Check("no exclamation mark", "!" not in text))
        checks.append(
            Check("sympathy", SYMPATHY.search(text) is not None, soft=step.get("say") is None)
        )
        checks.append(Check("no congratulations", re.search(r"gratul", text, re.I) is None))
    if step.get("out_of_scope"):
        checks.append(Check("says out of scope", OUT_OF_SCOPE.search(text) is not None))
    if step.get("event") == "timeline_ready":
        checks.append(check_notes_covered(text, opening_note_ids(after["notes"])))
    elif rec["changed_notes"]:
        # The chat says what a change means, not every changed point: reported, not failed.
        covered = [n["id"] for n in after["notes"] if n["id"] in rec["changed_notes"]]
        note_check = check_notes_covered(text, covered)
        note_check.soft = True
        checks.append(note_check)
    # A loss or a question for details may take more words.
    checks.append(check_brief(text, question, soft=bool(step.get("sensitive"))))
    leak = re.search(
        r"bez źródła: to opis|nie dopisuj do niego źródła|⟦|Następne pytanie wywiadu", text
    )
    checks.append(
        Check("no internal instructions in reply", leak is None, leak.group(0) if leak else "")
    )
    q = check_question(text, question)
    # Asking the next question is required after an answer, optional after a question.
    if "tools" not in step and "event" not in step:
        q.soft = True
    checks.append(q)
    if "question" in step:
        got = question["key"] if question else None
        checks.append(
            Check(
                "next question key", got == step["question"], f"want {step['question']}, got {got}"
            )
        )
    ignore = [question["text"]] if question else []
    checks += check_quotes(text, sources, ignore, app_texts(before, after))
    return checks


async def run_scenario(client, base: str, scenario: dict, run: int) -> dict:
    sid = str(uuid.uuid4())
    record = {"scenario": scenario["id"], "run": run, "session": sid, "steps": []}
    r = await client.put(f"{base}/api/session/{sid}/onboarding", json=scenario["onboarding"])
    r.raise_for_status()
    timeline = r.json()["timeline"]
    record["onboarding_today"] = timeline["today"]
    for index, step in enumerate(scenario["steps"]):
        if "patch" in step:
            # B.16: the parent changes the plan in the app (week tiles, the 81,5% switch, a plan
            # for a goal) before writing; the server leaves a hidden note in the history.
            patched = await client.patch(f"{base}/api/session/{sid}/scenario", json=step["patch"])
            patched.raise_for_status()
            timeline = patched.json()["timeline"]
        before = timeline
        turn = await chat(client, base, sid, step)
        view = (await client.get(f"{base}/api/session/{sid}")).json()
        timeline = view["timeline"] or timeline
        live_differs = bool(turn.timelines) and turn.timelines[-1]["timeline"] != view["timeline"]
        record["steps"].append(
            {
                "index": index,
                "input": step.get("say") or f"<{step.get('event')}>",
                "reply": turn.text,
                "error": turn.error,
                "done": turn.done,
                "tools": turn.tool_calls,
                "tool_results": turn.tool_results,
                "changed": sorted(turn.changed),
                "changed_notes": sorted(turn.changed_notes),
                "focus": turn.focus,
                "question": view.get("question"),
                "live_differs": live_differs,
                "seconds": round(turn.seconds, 1),
                "first_text_seconds": (
                    None if turn.first_text_seconds is None else round(turn.first_text_seconds, 2)
                ),
                "usage": turn.usage,
                "before": before,
                "after": timeline,
                "timeline_sha": hashlib.sha256(
                    json.dumps(timeline, sort_keys=True).encode()
                ).hexdigest()[:12],
                "facts": facts(turn.text),
            }
        )
    return record


def score(records: list[dict]) -> None:
    sources = load_sources()
    src_dates = source_dates(sources)
    for r in records:
        steps = SCENARIO_BY_ID[r["scenario"]]["steps"]
        for rec in r["steps"]:
            checks = step_checks(steps[rec["index"]], rec, sources, src_dates)
            rec["checks"] = [c.__dict__ for c in checks]


def determinism(records: list[dict]) -> list[dict]:
    """Compare runs of the same scenario step by step: timeline, tools, dates and numbers."""
    by_scenario: dict[str, list[dict]] = {}
    for r in records:
        by_scenario.setdefault(r["scenario"], []).append(r)
    out = []
    for sid, runs in by_scenario.items():
        if len(runs) < 2:
            continue
        for i in range(len(runs[0]["steps"])):
            steps = [r["steps"][i] for r in runs if i < len(r["steps"])]
            tools = {
                json.dumps(
                    sorted(
                        (c["name"], json.dumps(c["args"], sort_keys=True))
                        for c in s["tools"]
                        if c["name"] != "explain_timeline_element"
                    )
                )
                for s in steps
            }
            dates = [set(s["facts"]["dates"]) for s in steps]
            weeks = [set(s["facts"]["weeks"]) for s in steps]
            out.append(
                {
                    "scenario": sid,
                    "step": i,
                    "runs": len(steps),
                    "timeline_identical": len({s["timeline_sha"] for s in steps}) == 1,
                    "tools_identical": len(tools) == 1,
                    "dates_not_in_every_run": sorted(set.union(*dates) - set.intersection(*dates)),
                    "weeks_not_in_every_run": sorted(set.union(*weeks) - set.intersection(*weeks)),
                    "wrong_dates": sorted(
                        {
                            c["detail"]
                            for s in steps
                            for c in s["checks"]
                            if c["name"] == "reply dates on timeline" and not c["ok"]
                        }
                    ),
                }
            )
    return out


def print_report(records: list[dict], det: list[dict]) -> int:
    hard_fail = 0
    print(f"\n{'scenario':24} {'run':>3} {'step':>4}  result  failed checks")
    print("-" * 110)
    for r in records:
        for s in r["steps"]:
            failed = [c for c in s["checks"] if not c["ok"] and not c["soft"]]
            soft = [c for c in s["checks"] if not c["ok"] and c["soft"]]
            hard_fail += bool(failed)
            status = "FAIL" if failed else ("warn" if soft else "ok")
            names = "; ".join(
                f"{c['name']} ({c['detail'][:90]})" if c["detail"] else c["name"] for c in failed
            )
            print(f"{r['scenario']:24} {r['run']:>3} {s['index']:>4}  {status:6}  {names}")
            if soft:
                print(f"{'':37}warn: {'; '.join(c['name'] for c in soft)}")
    if det:
        print("\nDeterminism (same answers, fresh sessions)")
        header = "timeline  tools  wrong dates  facts not stated in every run"
        print(f"{'scenario':24} {'step':>4}  {header}")
        print("-" * 110)
        for d in det:
            diff = ", ".join(
                d["dates_not_in_every_run"] + [f"{w} tyg." for w in d["weeks_not_in_every_run"]]
            )
            timeline = "same" if d["timeline_identical"] else "DIFF"
            tools = "same" if d["tools_identical"] else "DIFF"
            wrong = "; ".join(d["wrong_dates"]) or "-"
            print(
                f"{d['scenario']:24} {d['step']:>4}  {timeline:8}  {tools:5}  {wrong:11}  "
                f"{diff or '-'}"
            )
    total = sum(len(r["steps"]) for r in records)
    print(f"\n{total - hard_fail}/{total} steps without hard failures; {total} chat turns.")
    return hard_fail


def _median(values: list[float]) -> float | None:
    return round(statistics.median(values), 2) if values else None


def summarize(steps: list[dict]) -> dict:
    """Time, tokens and cost of these turns (ZADANIA B.17). `input` counts cached tokens too,
    `cached` only those read from the provider's prompt cache."""
    usages = [s.get("usage") or {} for s in steps]
    costs = [u["cost_usd"] for u in usages if u.get("cost_usd") is not None]
    first = [s["first_text_seconds"] for s in steps if s.get("first_text_seconds") is not None]
    return {
        "turns": len(steps),
        "first_text_median_s": _median(first),
        "turn_median_s": _median([s["seconds"] for s in steps if s.get("seconds") is not None]),
        "input_tokens": sum(u.get("input_tokens", 0) for u in usages),
        "cached_tokens": sum(u.get("cache_read_tokens", 0) for u in usages),
        "output_tokens": sum(u.get("output_tokens", 0) for u in usages),
        "requests": sum(u.get("requests", 0) for u in usages),
        "cost_usd": round(sum(costs), 4) if costs else None,
        # From the second turn on the static prefix should come from the cache.
        "later_turns_with_cache": sum(1 for u in usages[1:] if u.get("cache_read_tokens")),
    }


def print_usage(records: list[dict]) -> dict:
    """Per scenario: time to the first text and of the whole turn (medians), tokens, cost."""
    by_scenario: dict[str, list[dict]] = {}
    for r in records:
        by_scenario.setdefault(r["scenario"], []).extend(r["steps"])
    print("\nTime and tokens per scenario (medians over turns; tokens and cost summed)")
    head = f"{'scenario':24} {'turns':>5} {'1st text':>8} {'turn':>6} {'input':>9} {'cached':>9}"
    print(f"{head} {'output':>7} {'per turn':>9} {'cost $':>8}  cache from 2nd turn")
    print("-" * 110)
    out = {}
    for name, steps in [*by_scenario.items(), ("ALL", [s for r in records for s in r["steps"]])]:
        s = out[name] = summarize(steps)
        per_turn = s["input_tokens"] // s["turns"] if s["turns"] else 0
        cost = "-" if s["cost_usd"] is None else f"{s['cost_usd']:.4f}"
        later = max(s["turns"] - 1, 0) if name != "ALL" else "-"
        print(
            f"{name:24} {s['turns']:>5} {s['first_text_median_s'] or '-':>8} "
            f"{s['turn_median_s'] or '-':>6} {s['input_tokens']:>9} {s['cached_tokens']:>9} "
            f"{s['output_tokens']:>7} {per_turn:>9} {cost:>8}  "
            f"{s['later_turns_with_cache']}/{later}"
        )
    return out


def compare(paths: list[Path]) -> None:
    """Model comparison from saved `--out` files: accuracy, time, cost (no LLM calls)."""
    print(f"\n{'run':28} {'model':28} {'ok steps':>9} {'1st text':>8} {'turn':>6} {'in/turn':>8}")
    print("-" * 110)
    for path in paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        records = data["records"]
        score(records)
        steps = [s for r in records for s in r["steps"]]
        ok = sum(1 for s in steps if not any(not c["ok"] and not c["soft"] for c in s["checks"]))
        s = summarize(steps)
        per_turn = s["input_tokens"] // s["turns"] if s["turns"] else 0
        cost = "-" if s["cost_usd"] is None else f"${s['cost_usd']:.4f}"
        print(
            f"{path.name:28} {data.get('label', '?'):28} {ok:>4}/{len(steps):<4} "
            f"{s['first_text_median_s'] or '-':>8} {s['turn_median_s'] or '-':>6} "
            f"{per_turn:>8}  cost {cost}, cached {s['cached_tokens']} of {s['input_tokens']}"
        )


async def run_all(args) -> list[dict]:
    chosen = [s for s in SCENARIOS if not args.only or s["id"] in args.only.split(",")]
    async with httpx.AsyncClient() as client:
        health = (await client.get(f"{args.base}/api/health")).json()
        print(f"backend: {health}")
        if health.get("sessions") != "memory":
            print("warning: sessions are not in memory: test sessions will be stored remotely")
        limit = asyncio.Semaphore(args.parallel)

        async def one(scenario: dict, run: int) -> dict:
            async with limit:
                return await run_scenario(client, args.base, scenario, run)

        jobs = [one(s, n + 1) for s in chosen for n in range(args.runs or s.get("runs", 1))]
        records = list(await asyncio.gather(*jobs))
    today = records[0]["onboarding_today"] if records else EXPECTED_TODAY
    if today != EXPECTED_TODAY:
        print(f"warning: server today is {today}, the scenarios assume {EXPECTED_TODAY}")
    return records


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--base", default="http://127.0.0.1:8010")
    parser.add_argument("--only", help="comma-separated scenario ids")
    parser.add_argument("--runs", type=int, help="override the number of runs per scenario")
    parser.add_argument("--parallel", type=int, default=4)
    parser.add_argument("--out", type=Path, help="write all turns and checks as JSON here")
    parser.add_argument("--rescore", type=Path, help="re-check a saved --out file; no LLM calls")
    parser.add_argument(
        "--label", default="?", help="the chat model the backend runs, saved with --out"
    )
    parser.add_argument(
        "--compare", type=Path, nargs="+", help="compare saved --out files; no LLM calls"
    )
    args = parser.parse_args()

    if args.compare:
        compare(args.compare)
        return 0
    label = args.label
    if args.rescore:
        saved = json.loads(args.rescore.read_text(encoding="utf-8"))
        records, label = saved["records"], saved.get("label", label)
        if args.only:
            records = [r for r in records if r["scenario"] in args.only.split(",")]
    else:
        records = asyncio.run(run_all(args))
    score(records)
    det = determinism(records)
    failures = print_report(records, det)
    usage = print_usage(records)
    if args.out:
        args.out.write_text(
            json.dumps(
                {"label": label, "records": records, "determinism": det, "usage": usage},
                ensure_ascii=False,
                indent=1,
            ),
            encoding="utf-8",
        )
        print(f"details: {args.out}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
