"""From what the model read to what the parent sees, without AI: personal data removed, every
date checked against the letter's own words (a date not written in its quote is dropped, so a
computed date never reaches the parent), the forms named with the guide's description and the
timeline elements the letter is about."""

import datetime as dt
from collections.abc import Iterable

from app.documents.dates import dates_in, mentions
from app.documents.forms import abolished_text, find_forms
from app.engine import Params, Timeline
from app.engine.applications import COURT_JUDGMENT, JOB_LOSS_REQUEST, SICK_AFTER_REQUEST
from app.engine.pregnancy import JOB_LOSS_SEGMENT, REHAB_SEGMENT, SEGMENT_IDS
from app.engine.wording import fmt

from .models import (
    KIND_LABELS,
    OUTCOME_LABELS,
    Benefit,
    LetterAction,
    LetterExplanation,
    LetterItem,
    LetterPeriod,
    LetterQuote,
    LetterReading,
)
from .privacy import Scrubber

BENEFIT_ELEMENTS: dict[Benefit, tuple[str, ...]] = {
    "maternity": (
        "maternity-prenatal",
        "maternity",
        "maternity-resumed",
        "maternity-father",
        "maternity-request",
        "adoption-leave",
    ),
    "parental": (
        "parental",
        "parental-father",
        "parental-request",
        "parental-father-request",
        "parental-deadline",
    ),
    "paternity": ("paternity", "paternity-request", "paternity-deadline"),
    "supplementary": ("supplementary", "supplementary-request"),
    "sickness": (
        *SEGMENT_IDS.values(),
        "sick-leave-notice",
        "sick-benefit-request",
        SICK_AFTER_REQUEST,
    ),
    "rehabilitation": (REHAB_SEGMENT,),
    "job_loss": (JOB_LOSS_SEGMENT, COURT_JUDGMENT, JOB_LOSS_REQUEST),
    "rate_815": ("rate-815-deadline",),
    "other": (),
}
"""Which timeline elements a letter about this benefit concerns (ids of `engine/`; a numbered
piece "parental-2" counts as "parental")."""


def timeline_elements(benefits: Iterable[Benefit], timeline: Timeline | None) -> list[str]:
    """The element ids for the benefits; with a timeline, only those on it."""
    candidates = list(dict.fromkeys(i for b in benefits for i in BENEFIT_ELEMENTS[b]))
    if timeline is None:
        return candidates
    on_timeline = [e.id for e in timeline.elements()]
    found = [
        element
        for candidate in candidates
        for element in on_timeline
        if element == candidate or element.startswith(f"{candidate}-")
    ]
    return list(dict.fromkeys(found))


def explain(
    reading: LetterReading,
    *,
    model: str,
    pages: int,
    pages_read: int,
    params: Params,
    timeline: Timeline | None = None,
) -> LetterExplanation:
    scrub = Scrubber(reading.personal_data)
    warnings: list[str] = []
    if not reading.is_zus_letter:
        warnings.append("To nie wygląda na pismo z ZUS: wyjaśnienie może być niepełne.")

    def quote(q: LetterQuote) -> LetterQuote:
        if not 1 <= q.page <= pages:
            warnings.append(
                f"Fragment „{scrub(q.text)}” ma numer strony {q.page}, a pismo ma {pages} str.: "
                "sprawdź go w piśmie."
            )
        return LetterQuote(text=scrub(q.text), page=q.page)

    def item(i: LetterItem) -> LetterItem:
        return LetterItem(text=scrub(i.text), quote=quote(i.quote))

    def checked(day: dt.date | None, *written: str | None) -> dt.date | None:
        """The date only if the letter's words given with it contain it."""
        if day is None or any(mentions(text, day) for text in written):
            return day
        warnings.append(
            f"Data {fmt(day)} nie jest zapisana w cytowanym fragmencie pisma, więc jej nie "
            "podajemy. Sprawdź ją w piśmie."
        )
        return None

    def action(a: LetterAction) -> LetterAction:
        return LetterAction(
            what=scrub(a.what),
            deadline_text=scrub.optional(a.deadline_text),
            deadline_date=checked(a.deadline_date, a.quote.text, a.deadline_text),
            quote=quote(a.quote),
        )

    def period(p: LetterPeriod) -> LetterPeriod:
        return LetterPeriod(
            benefit=p.benefit,
            start=checked(p.start, p.quote.text),
            end=checked(p.end, p.quote.text),
            quote=quote(p.quote),
        )

    actions = [action(a) for a in reading.actions]
    appeal = action(reading.appeal) if reading.appeal else None
    periods = [period(p) for p in reading.periods]
    reason = item(reading.reason) if reading.reason else None
    prepare = [item(i) for i in reading.prepare]

    # Dates in the free text must also come from the letter's quoted words.
    asked = [*reading.actions, *([reading.appeal] if reading.appeal else [])]
    written = [q.text for q in _quotes(reading)] + [a.deadline_text or "" for a in asked]
    free = [reading.subject, reading.summary, *(a.what for a in asked)]
    free += [i.text for i in reading.prepare] + ([reading.reason.text] if reading.reason else [])
    for day in dict.fromkeys(d for text in free for d in dates_in(text)):
        if not any(mentions(text, day) for text in written):
            warnings.append(
                f"W wyjaśnieniu jest data {fmt(day)}, której nie ma w cytowanych fragmentach "
                "pisma. Sprawdź ją w piśmie."
            )
    if any(
        a.deadline_date is None and a.deadline_text and "doręcz" in a.deadline_text.lower()
        for a in [*actions, *([appeal] if appeal else [])]
    ):
        warnings.append(
            "Termin liczy się od dnia doręczenia pisma. Aplikacja go nie liczy: sprawdź, kiedy "
            "pismo zostało Ci doręczone."
        )

    # The forms: what the guide says about them; abolished ones get a warning.
    texts = " ".join([*reading.forms, reading.summary, *(q.text for q in _quotes(reading))])
    known = find_forms(texts, params)
    other = [scrub(code) for code in reading.forms if not find_forms(code, params)]
    for form in known:
        if form.abolished:
            then = (
                f" Jeśli masz go złożyć teraz, złóż {form.merged_into}." if form.merged_into else ""
            )
            warnings.append(
                f"Pismo wymienia formularz {form.code}. {abolished_text(form, params)}{then}"
            )

    quotes = [*(a.quote for a in actions), *(i.quote for i in prepare)]
    quotes += [p.quote for p in periods] + ([appeal.quote] if appeal else [])
    quotes += [reason.quote] if reason else []
    unique = {(q.page, q.text): q for q in quotes}
    benefits = [*reading.benefits, *(p.benefit for p in reading.periods)]
    heading, subject, summary = (
        scrub(t) for t in (reading.heading, reading.subject, reading.summary)
    )
    unreadable = [scrub(u) for u in reading.unreadable]
    return LetterExplanation(
        model=model,
        is_zus_letter=reading.is_zus_letter,
        kind=reading.kind,
        kind_label=KIND_LABELS[reading.kind],
        heading=heading,
        subject=subject,
        outcome=reading.outcome,
        outcome_label=OUTCOME_LABELS[reading.outcome],
        summary=summary,
        reason=reason,
        action_needed=bool(actions),
        actions=actions,
        prepare=prepare,
        periods=periods,
        appeal=appeal,
        forms=known,
        other_forms=other,
        timeline_elements=timeline_elements(benefits, timeline),
        quotes=sorted(unique.values(), key=lambda q: q.page),
        pages=pages,
        pages_read=pages_read,
        personal_data_removed=scrub.removed,
        warnings=list(dict.fromkeys(warnings)),
        unreadable=unreadable,
    )


def _quotes(reading: LetterReading) -> list[LetterQuote]:
    """Every quote of the reading, before personal data is removed."""
    quotes = [a.quote for a in reading.actions] + [i.quote for i in reading.prepare]
    quotes += [p.quote for p in reading.periods]
    quotes += [reading.appeal.quote] if reading.appeal else []
    quotes += [reading.reason.quote] if reading.reason else []
    return quotes
