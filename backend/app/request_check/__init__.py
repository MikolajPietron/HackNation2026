"""F23 "Sprawdzanie wniosku przed złożeniem": a filled request against the forms of the guide and
the parent's timeline. Deterministic checks find the problems (`checks.py`); an optional AI pass
(`phrasing.py`, Claude or Gemini) may only reword them. The form's labelled fields are read in one
place (`adapter.py`)."""
