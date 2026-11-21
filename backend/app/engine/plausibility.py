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
