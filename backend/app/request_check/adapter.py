"""The one place that reads a filled request form (`read_request`): which request it is, who files
it, and what its labelled fields say (dates, weeks, attachments). The form model of the app
(`{title, addressee, fields: [{label, value, source}]}`) gives labels, not keys, so the keys are
inferred from the Polish labels here; a field with an explicit `key` wins. Align the label rules
with the forms when they change."""

import datetime as dt
import re
import unicodedata
from dataclasses import dataclass, field
from typing import get_args

from app.documents.dates import dates_in
from app.documents.forms import find_forms
from app.engine import Params
from app.engine.models import Role

from .models import FieldKey, FilledRequest, RequestKind

EMPTY = {"", "-", "—", "–", "…", "..."}
"""What an empty field looks like. "brak" is an answer (e.g. no leave used so far)."""
YES = {"tak", "x", "true", "1", "wybieram"}
FATHER_WORDS = {"tata", "taty", "tacie", "ojca", "ojciec", "ojcu"}
FATHER_KINDS: tuple[RequestKind, ...] = (
    "maternity-father-request",
    "parental-father-request",
    "paternity-request",
)
KINDS = set(get_args(RequestKind))
DOCUMENT_KINDS: dict[str, RequestKind] = {"father-benefit-request": "zam"}
"""Timeline document ids that are another request kind's name (the rest are the same)."""

KIND_LABELS: dict[RequestKind, str] = {
    "maternity-request": "Wniosek o urlop macierzyński",
    "maternity-father-request": "Wniosek taty o część urlopu macierzyńskiego",
    "maternity-resignation": "Wniosek o rezygnację z części urlopu macierzyńskiego",
    "supplementary-request": "Wniosek o uzupełniający urlop macierzyński",
    "parental-request": "Wniosek o urlop rodzicielski",
    "parental-father-request": "Wniosek taty o urlop rodzicielski",
    "paternity-request": "Wniosek o urlop ojcowski",
    "zam": "Wniosek o zasiłek macierzyński (ZAM)",
    "rate-815": "Wniosek o zasiłek macierzyński w wysokości 81,5%",
    "zas-53": "Wniosek o zasiłek chorobowy (ZAS-53)",
    "unknown": "Wniosek",
}


def plain(text: str) -> str:
    """Lower case, without Polish diacritics and punctuation: "Data złożenia:" → "data zlozenia"."""
    decomposed = unicodedata.normalize("NFKD", text.lower().replace("ł", "l"))
    letters = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(re.findall(r"[a-z0-9]+(?:[,.][0-9]+)?", letters))


@dataclass
class ReadRequest:
    """What the checks read from a filled request."""

    kind: RequestKind
    title: str
    parent: Role
    filed_on: dt.date
    addressee: str | None
    start: dt.date | None = None
    end: dt.date | None = None
    weeks: int | None = None
    return_to_work: dt.date | None = None
    maternity_end: dt.date | None = None
    birth_date: dt.date | None = None
    rate_815: bool = False
    empty: list[str] = field(default_factory=list)
    """Labels of the required fields left empty."""
    attachments: list[str] = field(default_factory=list)
    labels: dict[FieldKey, str] = field(default_factory=dict)
    """The label of the field each value came from (to point at it)."""
    text: str = ""
    """The title, values and attachments together: where a form code may be named."""


def field_key(label: str) -> FieldKey | None:
    """What a field means, from its label. The order matters: "Termin zakończenia urlopu
    macierzyńskiego" is the end of maternity leave, not the end of this leave."""
    words = plain(label)
    tokens = set(words.split())
    if "81,5" in words or "81.5" in words:
        return "rate_815"
    if "zlozenia" in words or "data wniosku" in words or words in ("data", "miejscowosc i data"):
        return "filed_on"
    if "powrot" in words:
        return "return_to_work"
    if "macierzynsk" in words and any(w in words for w in ("zakonczen", "koniec", "konca")):
        return "maternity_end"
    if "urodzenia" in words:
        return "birth_date"
    if "tygodni" in words or "wymiar" in words:
        return "weeks"
    if "od" in tokens or any(w in words for w in ("poczat", "rozpocz", "pierwszy dzien")):
        return "start"
    if "do" in tokens or any(w in words for w in ("koniec", "zakoncz", "ostatni dzien")):
        return "end"
    if "okres" in words and not any(w in words for w in ("wykorzyst", "dotychczas")):
        return "period"
    return None


def request_kind(request: FilledRequest, params: Params) -> RequestKind:
    if request.form_id in DOCUMENT_KINDS:
        return DOCUMENT_KINDS[request.form_id]
    if request.form_id in KINDS:
        return request.form_id  # type: ignore[return-value]
    codes = {form.code for form in find_forms(request.title, params)}
    if codes & {"ZAM", "ZUR", "ZAO"}:
        return "zam"
    if "ZAS-53" in codes:
        return "zas-53"
    title = plain(request.title)
    father = request.parent == "father" or bool(FATHER_WORDS & set(title.split()))
    if "81,5" in title or "81.5" in title:
        return "rate-815"
    if "rezygnac" in title:
        return "maternity-resignation"
    if "uzupelniaj" in title:
        return "supplementary-request"
    if "ojcowsk" in title:
        return "paternity-request"
    if "rodzicielsk" in title:
        return "parental-father-request" if father else "parental-request"
    if "zasil" in title and "macierzynsk" in title:
        return "zam"
    if "macierzynsk" in title:
        return "maternity-father-request" if father else "maternity-request"
    return "unknown"


def read_request(request: FilledRequest, params: Params, today: dt.date) -> ReadRequest:
    kind = request_kind(request, params)
    title_words = set(plain(request.title).split())
    father = request.parent == "father" or kind in FATHER_KINDS or bool(FATHER_WORDS & title_words)
    read = ReadRequest(
        kind=kind,
        title=request.title,
        parent=request.parent or ("father" if father else "mother"),
        filed_on=request.filed_on or today,
        addressee=request.addressee,
        attachments=list(request.attachments),
    )
    texts = [request.title, *request.attachments]
    filed_on: dt.date | None = None
    for f in request.fields:
        value = (f.value or "").strip()
        if value.lower() in EMPTY:
            if f.required:
                read.empty.append(f.label)
            continue
        texts.append(value)
        if "zalacz" in plain(f.label):
            if value.lower() in YES:
                read.attachments.append(f.label)
            elif value.lower() != "nie":
                read.attachments.append(value)
            continue
        key = f.key or field_key(f.label)
        if key is None:
            continue
        dates = dates_in(value)
        match key:
            case "start" if dates:
                read.start = dates[0]
                if len(dates) > 1 and read.end is None:
                    read.end = dates[-1]
            case "end" if dates:
                read.end = dates[-1]
            case "period" if dates:
                read.start = dates[0]
                read.end = dates[-1] if len(dates) > 1 else read.end
            case "weeks":
                number = re.search(r"\d+", value)
                read.weeks = int(number[0]) if number else None
            case "return_to_work" if dates:
                read.return_to_work = dates[0]
            case "maternity_end" if dates:
                read.maternity_end = dates[0]
            case "birth_date" if dates:
                read.birth_date = dates[0]
            case "filed_on" if dates:
                filed_on = dates[0]
            case "rate_815":
                read.rate_815 = value.lower() in YES
            case _:
                continue
        read.labels.setdefault(key, f.label)
    if request.filed_on is None and filed_on is not None:
        read.filed_on = filed_on
    read.rate_815 = read.rate_815 or "81,5" in plain(request.title)
    read.text = " ".join(texts)
    return read
