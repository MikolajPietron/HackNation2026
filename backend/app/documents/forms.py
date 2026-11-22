"""The ZUS forms the guide names (pages 3, 6 and 12), found in free text: the title of a request,
its attachments, a letter from ZUS. Names, the abolished forms (ZUR, ZAO, Z-3b since 24 October
2026) and their sources are parameters (`params.applications.forms`): a change in the forms is a
change in the parameters file, not in the code."""

import datetime as dt
import re
from functools import cache

from app.engine.params import KnownForm, Params
from app.engine.wording import long_date


def _spellings(code: str) -> set[str]:
    """ "Z-3b" also as "Z-3B"; "e-ZLA" also as "E-ZLA". The hyphen is optional (see `_pattern`)."""
    found = {code}
    if len(code) > 1 and code[-1].isalpha() and code[-2].isdigit():
        found.add(code[:-1] + code[-1].swapcase())
    if code[0].islower():
        found.add(code[0].upper() + code[1:])
    return found


@cache
def _pattern(code: str) -> re.Pattern[str]:
    """The code as a whole word: "Z-3b" also as "Z3b" or "Z 3b", never inside a longer code
    ("Z-3" does not match "Z-3a"). Letters keep their case, so "zam." (zamieszkały) is no ZAM."""
    bodies = [r"[-\s]?".join(re.escape(part) for part in s.split("-")) for s in _spellings(code)]
    return re.compile(rf"(?<![\w-])(?:{'|'.join(sorted(bodies))})(?![\w-])")


def find_forms(text: str, params: Params) -> list[KnownForm]:
    """The known forms the text names, in the order it names them, each once."""
    hits: list[tuple[int, KnownForm]] = []
    for form in params.applications.forms:
        match = _pattern(form.code).search(text)
        if match is not None:
            hits.append((match.start(), form))
    return [form for _, form in sorted(hits, key=lambda hit: hit[0])]


def abolished_on(params: Params) -> dt.date:
    return params.applications.forms_abolished_on.value


def abolished_text(form: KnownForm, params: Params) -> str:
    """One sentence, in the words of the guide's footnotes (page 12)."""
    day = long_date(abolished_on(params))
    if form.merged_into:
        return (
            f"Formularz {form.code} od {day} r. jest zlikwidowany: połączono go z formularzem "
            f"{form.merged_into}."
        )
    return f"Formularz {form.code} od {day} r. jest zlikwidowany."
