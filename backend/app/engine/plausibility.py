"""Sanity checks for what the parent typed. Not legal rules: they catch typos like a wrong year."""

import datetime as dt

from app.engine.wording import fmt

DUE_DATE_GRACE = dt.timedelta(days=14)
DUE_DATE_MAX_AHEAD = dt.timedelta(days=310)
BIRTH_DATE_MAX_AGO = dt.timedelta(days=6 * 366)


def due_date_problem(due_date: dt.date, today: dt.date) -> str | None:
    """Why this cannot be an expected due date, in Polish, or None if it can."""
    if due_date < today - DUE_DATE_GRACE:
        return f"Data {fmt(due_date)} minęła dawno (dziś {fmt(today)}). Sprawdź datę."
    if due_date > today + DUE_DATE_MAX_AHEAD:
        return f"Data {fmt(due_date)} jest zbyt odległa od dziś ({fmt(today)}). Sprawdź rok."
    return None


def birth_date_problem(birth_date: dt.date, today: dt.date) -> str | None:
    """Why this cannot be the date of birth of a child who is already born, or None."""
    if birth_date > today:
        return (
            f"Data urodzenia {fmt(birth_date)} jest w przyszłości (dziś {fmt(today)}). "
            "Jeśli to przewidywana data porodu, dziecko jest jeszcze w drodze."
        )
    if birth_date < today - BIRTH_DATE_MAX_AGO:
        return f"Data {fmt(birth_date)} jest zbyt odległa od dziś ({fmt(today)}). Sprawdź rok."
    return None


# A child taken in for upbringing (guide section D): older children, and a day of taking in that
# may be planned or years back (parental leave runs until the child is 14 at the latest).
TAKEN_IN_MAX_AGO = dt.timedelta(days=14 * 366)
CHILD_BIRTH_MAX_AGO = dt.timedelta(days=18 * 366)


def taken_in_problem(taken_in_on: dt.date, today: dt.date) -> str | None:
    """Why this cannot be the day a child was (or will be) taken in, or None."""
    if taken_in_on > today + DUE_DATE_MAX_AHEAD or taken_in_on < today - TAKEN_IN_MAX_AGO:
        return f"Data {fmt(taken_in_on)} jest zbyt odległa od dziś ({fmt(today)}). Sprawdź rok."
    return None


def child_birth_problem(birth_date: dt.date, today: dt.date) -> str | None:
    """Why this cannot be the date of birth of a child taken in, or None."""
    if birth_date > today:
        return f"Data urodzenia {fmt(birth_date)} jest w przyszłości (dziś {fmt(today)})."
    if birth_date < today - CHILD_BIRTH_MAX_AGO:
        return f"Data {fmt(birth_date)} jest zbyt odległa od dziś ({fmt(today)}). Sprawdź rok."
    return None
