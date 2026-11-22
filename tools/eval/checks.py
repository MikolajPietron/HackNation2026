"""Checks on one chat turn: the timeline against hand-computed values, the reply against the
timeline and the sources. Pure functions, no network."""

import datetime as dt
import difflib
import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GUIDE_JSON = ROOT / "backend/app/assistant/przewodnik_pages.json"
KP_JSON = ROOT / "backend/app/assistant/kodeks_pracy.json"
USTAWA_JSON = ROOT / "backend/app/assistant/ustawa_zasilkowa.json"
ZALACZNIK_JSON = ROOT / "backend/app/assistant/zalacznik.json"

MONTHS = {
    "stycznia": 1,
    "lutego": 2,
    "marca": 3,
    "kwietnia": 4,
    "maja": 5,
    "czerwca": 6,
    "lipca": 7,
    "sierpnia": 8,
    "września": 9,
    "października": 10,
    "listopada": 11,
    "grudnia": 12,
}
_MONTH_RE = "|".join(MONTHS)
WORD_DATE = re.compile(rf"\b(\d{{1,2}})\s+({_MONTH_RE})(?:\s+(\d{{4}}))?", re.IGNORECASE)
NUM_DATE = re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b")
ISO_DATE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
WEEKS = re.compile(r"\b(\d{1,3})\s*(?:tyg\.?|tygodni(?:e|a)?|tydzień)", re.IGNORECASE)
QUOTE = re.compile(r"„([^”]{12,}?)”")
# A human first sentence after a loss: "Bardzo mi przykro", "Rozumiem, że to trudne", …
SYMPATHY = re.compile(
    r"przykro|współczu|wyrazy|bardzo nam|trudn|ciężk|bolesn|rozumiem, że", re.IGNORECASE
)
OUT_OF_SCOPE = re.compile(
    r"nie obejmuje|jeszcze nie obejmuj|nie obejmuj|poza zakresem|nie mogę (?:jeszcze )?"
    r"(?:tego )?(?:policzyć|odpowiedzieć|podać|wyliczyć)|kolejn\w+ (?:etap|częś)|dojd\w+ wkrótce|"
    r"na tym etapie",
    re.IGNORECASE,
)


@dataclass
class Check:
    name: str
    ok: bool
    detail: str = ""
    soft: bool = False
    """Soft checks are reported but do not fail the step (e.g. the reply repeats old points)."""


@dataclass
class Turn:
    """What one POST /api/chat produced."""

    text: str = ""
    tool_calls: list[dict] = field(default_factory=list)
    tool_results: list[dict] = field(default_factory=list)
    timelines: list[dict] = field(default_factory=list)
    focus: list[str] = field(default_factory=list)
    error: str | None = None
    done: bool = False
    seconds: float = 0.0

    @property
    def changed(self) -> set[str]:
        return {i for t in self.timelines for i in t.get("changed", [])}

    @property
    def changed_notes(self) -> set[str]:
        return {i for t in self.timelines for i in t.get("changed_notes", [])}


# --- sources -----------------------------------------------------------------------------


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("­", "")
    text = re.sub(r"[‘’‚'`]", "'", text)
    text = re.sub(r"[“”„\"«»]", '"', text)
    text = re.sub(r"[‐-―−]", "-", text)
    return re.sub(r"\s+", " ", text).strip().lower()


def load_sources() -> dict[str, str]:
    """Normalized source texts: 'p<N>' for guide pages, 'kp:<article>' for the Labour Code,
    'ustawa:<article>' for the ustawa zasiłkowa, 'zal:<section>' for the ZUS Załącznik."""
    guide = json.loads(GUIDE_JSON.read_text(encoding="utf-8"))["pages"]
    kp = json.loads(KP_JSON.read_text(encoding="utf-8"))["articles"]
    ustawa = json.loads(USTAWA_JSON.read_text(encoding="utf-8"))["articles"]
    # Not in git (a ZUS document): built locally by tools/przewodnik/extract_zalacznik.py.
    zalacznik = (
        json.loads(ZALACZNIK_JSON.read_text(encoding="utf-8"))["sections"]
        if ZALACZNIK_JSON.exists()
        else {}
    )
    out = {f"p{n}": _norm(text) for n, text in guide.items()}
    out.update({f"kp:{art}": _norm(text) for art, text in kp.items()})
    out.update({f"ustawa:{art}": _norm(text) for art, text in ustawa.items()})
    out.update({f"zal:{name}": _norm(text) for name, text in zalacznik.items()})
    return out


def _article_key(raw: str) -> str:
    """'art. 180 § 1' / 'art. 1831 § 2' / 'art. 183¹ § 2' -> comparable key '180§1'."""
    raw = unicodedata.normalize("NFKC", raw).lower()
    raw = raw.replace("art.", "").replace(" ", "")
    return raw


def find_quote(quote: str, sources: dict[str, str]) -> list[str]:
    """Keys of the sources that contain the quote literally (after whitespace/quote-mark
    normalization). Guide quotes may run over a page break: pages are also tried in pairs."""
    q = _norm(quote).strip(" .,;:")
    hits = [k for k, text in sources.items() if q in text]
    if hits:
        return hits
    pages = sorted(int(k[1:]) for k in sources if k.startswith("p"))
    for a, b in zip(pages, pages[1:], strict=False):
        if q in sources[f"p{a}"] + " " + sources[f"p{b}"]:
            return [f"p{a}", f"p{b}"]
    return []


def best_match(quote: str, sources: dict[str, str]) -> tuple[float, str]:
    """For a quote that is not literal: the closest sentence and its similarity."""
    q = _norm(quote)
    best = (0.0, "")
    for key, text in sources.items():
        for sentence in re.split(r"(?<=[.;:])\s+", text):
            ratio = difflib.SequenceMatcher(None, q, sentence).ratio()
            if ratio > best[0]:
                best = (ratio, f"{key}: {sentence[:120]}")
    return best


ATTRIBUTION = re.compile(
    r"(?:s\.|str\.|stron[aiey])\s*(\d{1,2})|art\.\s*([0-9¹²³ᵃᵇᶜᵈᵉᶠᵍ]+(?:\s*§\s*\d+[¹]?)?)",
    re.IGNORECASE,
)


def _cited(text: str, end: int) -> tuple[set[str], set[str]]:
    """Pages and articles named in the first parenthesis after a quote (or the next 80
    characters when there is none): ({'p5', ...}, {'180§1', ...})."""
    tail = text[end : end + 400]
    m = re.match(r"[^(\n]{0,60}\(([^)]*)\)", tail)
    span = m.group(1) if m else tail[:80]
    pages, arts = set(), set()
    for page, art in ATTRIBUTION.findall(span):
        if page:
            pages.add(f"p{page}")
        else:
            arts.add(_article_key(art))
    # "s. 5–6" names both pages
    for a, b in re.findall(r"s\.\s*(\d{1,2})\s*[–-]\s*(\d{1,2})", span):
        pages |= {f"p{n}" for n in range(int(a), int(b) + 1)}
    # "art. 182¹ᵃ § 1 i § 4" / "§ 1, § 4": the bare paragraphs belong to the last article
    for art_m in re.finditer(r"art\.\s*([0-9¹²³ᵃᵇᶜᵈᵉᶠᵍ]+)((?:\s*(?:§\s*\d+[¹]?|i|,|oraz))+)", span):
        base = _article_key(art_m.group(1))
        for par in re.findall(r"§\s*(\d+[¹]?)", art_m.group(2)):
            arts.add(f"{base}§{par}")
    return pages, arts


def _article_matches(cited: set[str], hits: list[str]) -> bool:
    found = {_article_key(h.split(":", 1)[1]) for h in hits if h.startswith(("kp:", "ustawa:"))}
    flat = {k.replace("¹", "1").replace("ᵃ", "a").replace("ᶜ", "c") for k in found}
    for c in cited:
        c_flat = c.replace("¹", "1").replace("ᵃ", "a").replace("ᶜ", "c")
        if c in found or c_flat in flat or any(f.startswith(c_flat) for f in flat):
            return True
    return False


ELISION = re.compile(r"\s*(?:\[…\]|\[\.\.\.\]|\(…\)|\(\.\.\.\)|…|\.\.\.)\s*")


def find_elided(quote: str, sources: dict[str, str]) -> list[str]:
    """A quote shortened with […]: every part must be literal, all in one source."""
    parts = [p for p in ELISION.split(quote) if len(p.split()) >= 2]
    if not parts:
        return []
    common = None
    for part in parts:
        hits = set(find_quote(part, sources))
        common = hits if common is None else common & hits
    return sorted(common or [])


def check_quotes(
    text: str, sources: dict[str, str], ignore: list[str], app_texts: list[str] | None = None
) -> list[Check]:
    """Every „…” fragment of 4+ words must be a literal fragment of the guide or the Labour Code
    excerpt, and the parenthesis after it must name a page or article that contains it.
    A quote shortened with […] counts when each part is literal in the same source.
    A non-literal quote is classified: the app's own explanation text presented as a quote,
    or an altered quote (dropped words without […], changed grammar)."""
    checks = []
    ignored = [_norm(i) for i in ignore if i]
    app = [_norm(t) for t in app_texts or []]
    for m in QUOTE.finditer(text):
        quote = m.group(1).strip("*_ ")
        nq = _norm(quote)
        if any(nq in i or i in nq for i in ignored) or len(nq.split()) < 4:
            continue  # the interview question or a name like „Za życiem”
        hits = find_quote(quote, sources) or (
            find_elided(quote, sources) if ELISION.search(quote) else []
        )
        pages, arts = _cited(text, m.end())
        if not hits:
            if any(nq.strip(" .") in a for a in app):
                kind = "app text quoted as a source"
            else:
                ratio, where = best_match(quote, sources)
                kind = f"altered quote (closest {ratio:.2f} {where[:90]})"
            cited = ", ".join(sorted(pages | arts)) or "no source named"
            checks.append(Check("quote literal", False, f"„{quote[:80]}” {kind}; cited: {cited}"))
            continue
        if not pages and not arts:
            checks.append(Check("quote literal", True, f"„{quote[:50]}” in {hits[0]}"))
            continue
        ok = bool(pages & set(hits)) or _article_matches(arts, hits)
        checks.append(
            Check(
                "quote attribution",
                ok,
                f"„{quote[:50]}” cited as {sorted(pages | arts)}, found in {hits}",
            )
        )
    return checks


# --- dates and numbers -------------------------------------------------------------------


def extract_dates(text: str, default_year: int | None = None) -> set[tuple[int | None, int, int]]:
    """(year or None, month, day) for every date written in words or digits."""
    found: set[tuple[int | None, int, int]] = set()
    for d, mon, y in WORD_DATE.findall(text):
        found.add((int(y) if y else default_year, MONTHS[mon.lower()], int(d)))
    for d, mon, y in NUM_DATE.findall(text):
        found.add((int(y), int(mon), int(d)))
    for y, mon, d in ISO_DATE.findall(text):
        found.add((int(y), int(mon), int(d)))
    return found


def extract_weeks(text: str) -> set[int]:
    return {int(n) for n in WEEKS.findall(text)}


def timeline_dates(timeline: dict) -> set[dt.date]:
    """Every date the timeline shows: periods, days, documents and the dates in its texts."""
    out: set[dt.date] = {dt.date.fromisoformat(timeline["today"])}
    out.add(dt.date.fromisoformat(timeline["birth_date"]))
    for s in timeline["segments"]:
        out |= {dt.date.fromisoformat(s["start"]), dt.date.fromisoformat(s["end"])}
    for m in timeline["markers"]:
        out.add(dt.date.fromisoformat(m["date"]))
    for d in timeline["documents"]:
        out.add(dt.date.fromisoformat(d["needed_by"]))
    texts = [n["text"] + " " + n["title"] for n in timeline["notes"]]
    texts += [s["summary"] + " " + " ".join(s["details"]) for s in timeline["segments"]]
    texts += [m["summary"] + " " + " ".join(m["details"]) for m in timeline["markers"]]
    for t in texts:
        for y, mo, d in extract_dates(t):
            if y:
                out.add(dt.date(y, mo, d))
    return out


def _matches(found: tuple[int | None, int, int], dates: set[dt.date]) -> bool:
    y, mo, d = found
    return any(x.month == mo and x.day == d and (y is None or x.year == y) for x in dates)


def source_dates(sources: dict[str, str]) -> set[dt.date]:
    """Dates written in the sources themselves, e.g. the date of the "Za życiem" act."""
    out = set()
    for text in sources.values():
        for y, mo, d in extract_dates(text):
            if y:
                out.add(dt.date(y, mo, d))
    return out


def check_reply_dates(text: str, timeline: dict, extra: set[dt.date]) -> Check:
    """Every date the assistant writes must be on the timeline (or in the user's message, the
    previous timeline or the sources)."""
    allowed = timeline_dates(timeline) | extra
    wrong = []
    for y, mo, d in sorted(extract_dates(text), key=lambda x: (x[0] or 0, x[1], x[2])):
        try:
            if y and not _matches((y, mo, d), allowed):
                wrong.append(dt.date(y, mo, d).isoformat())
            elif not y and not _matches((None, mo, d), allowed):
                wrong.append(f"{d:02d}.{mo:02d}")
        except ValueError:
            wrong.append(f"{d}.{mo}.{y}")
    return Check("reply dates on timeline", not wrong, ", ".join(wrong) or "all dates match")


def check_mentions(text: str, dates: list[str], numbers: list[int]) -> list[Check]:
    found = extract_dates(text)
    out = []
    for iso in dates:
        x = dt.date.fromisoformat(iso)
        ok = any(m == x.month and d == x.day and y in (None, x.year) for y, m, d in found)
        out.append(Check(f"mentions {iso}", ok))
    weeks = extract_weeks(text)
    for n in numbers:
        ok = n in weeks or re.search(rf"\b{n}\b", text) is not None
        out.append(Check(f"mentions {n}", ok))
    return out


def facts(text: str) -> dict[str, list]:
    """The checkable facts of a reply, for comparing runs: dates and week counts."""
    dates = sorted(f"{y or '????'}-{m:02d}-{d:02d}" for y, m, d in extract_dates(text))
    return {"dates": dates, "weeks": sorted(extract_weeks(text))}


NOTE_KEYWORDS = {
    "situation": r"w drodze|urodził|urodzi|zmarł|martwe|liczymy od",
    "insurance": r"ubezpiecz",
    "before-birth": r"przed (przewidywaną datą )?porod|do dnia porodu|zaświadczeni|zacząć urlop",
    "parental": r"rodzicielsk",
    "more-children": r"bliźni|trojacz|dwojga|trojga|czworga",
    "za-zyciem": r"za życiem",
    "supplementary": r"uzupełniając",
    "takeover": r"przej(ąć|mie|muje|mować|ęci)|oddać|przekaza",
    "father": r"ojcowsk",
    "loss": r"8 tygodni|7 dni|tygodni po porodzie",
    "mother-event": r"szpital|zmarł|śmier|przejm|przerw",
    "computed": r"\d{1,2} (stycznia|lutego|marca|kwietnia|maja|czerwca|lipca|sierpnia|"
    r"września|października|listopada|grudnia)|\d{1,2}\.\d{1,2}\.\d{4}",
}
"""A word each explanation point cannot be told without: a heuristic for "did the reply cover
this point"."""


def check_notes_covered(text: str, note_ids: list[str]) -> Check:
    missing = [
        nid
        for nid in note_ids
        if nid in NOTE_KEYWORDS and not re.search(NOTE_KEYWORDS[nid], text, re.I)
    ]
    return Check("covers explanation points", not missing, "missing: " + ", ".join(missing))


def norm_question(text: str) -> str:
    return re.sub(r"[^\w ]", "", _norm(text))


def check_question(text: str, question: dict | None) -> Check:
    """The reply should end with the next interview question, word for word."""
    if not question:
        return Check("asks next question", True, "interview finished", soft=True)
    q, r = norm_question(question["text"]), norm_question(text)
    if q in r:
        return Check("asks next question", True, question["key"])
    words = r.split()
    n = len(q.split())
    best = 0.0
    for i in range(max(1, len(words) - n + 1)):
        window = " ".join(words[i : i + n + 3])
        best = max(best, difflib.SequenceMatcher(None, q, window).ratio())
    return Check(
        "asks next question",
        False,
        f"{question['key']}: not word for word (best {best:.2f}): {question['text'][:70]}",
        soft=best >= 0.8,
    )


def check_timeline(timeline: dict, expect: dict) -> list[Check]:
    """expect: {"segments": {id: [start, end]}, "markers": {id: date},
    "documents": {id: needed_by or [needed_by, done]}, "absent": [ids], "notes": [ids],
    "no_notes": [ids], "bases": {parent: monthly benefit base}}."""
    out = []
    segs = {s["id"]: s for s in timeline["segments"]}
    for sid, (start, end) in expect.get("segments", {}).items():
        s = segs.get(sid)
        got = f"{s['start']}..{s['end']}" if s else "missing"
        out.append(
            Check(f"segment {sid}", got == f"{start}..{end}", f"want {start}..{end}, got {got}")
        )
    marks = {m["id"]: m for m in timeline["markers"]}
    for mid, date in expect.get("markers", {}).items():
        got = marks[mid]["date"] if mid in marks else "missing"
        out.append(Check(f"marker {mid}", got == date, f"want {date}, got {got}"))
    docs = {d["id"]: d for d in timeline["documents"]}
    for did, want in expect.get("documents", {}).items():
        needed, done = (want, None) if isinstance(want, str) else want
        d = docs.get(did)
        ok = d is not None and d["needed_by"] == needed and (done is None or d["done"] == done)
        got = f"{d['needed_by']} done={d['done']}" if d else "missing"
        out.append(Check(f"document {did}", ok, f"want {needed} done={done}, got {got}"))
    ids = {*segs, *marks, *docs}
    for gone in expect.get("absent", []):
        out.append(Check(f"absent {gone}", gone not in ids))
    note_ids = {n["id"] for n in timeline["notes"]}
    for nid in expect.get("notes", []):
        out.append(Check(f"note {nid}", nid in note_ids))
    for nid in expect.get("no_notes", []):
        out.append(Check(f"no note {nid}", nid not in note_ids))
    bases = {b["parent"]: b["base"] for b in timeline.get("bases", [])}
    for parent, want in expect.get("bases", {}).items():
        got = bases.get(parent, "missing")
        out.append(Check(f"base {parent}", got == want, f"want {want}, got {got}"))
    return out
