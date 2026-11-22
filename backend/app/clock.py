"""'Today' for the whole app: the calendar day in Poland, not in the server's time zone."""

import datetime as dt
import os
from zoneinfo import ZoneInfo

WARSAW = ZoneInfo("Europe/Warsaw")


def today_in_warsaw() -> dt.date:
    """`APP_TODAY` (RRRR-MM-DD) fixes the day for a test backend, e.g. the real-model eval, whose
    scenarios are computed for 2026-11-21 (tools/eval/README.md). Unset in normal use."""
    fixed = os.environ.get("APP_TODAY")
    if fixed:
        return dt.date.fromisoformat(fixed)
    return dt.datetime.now(WARSAW).date()
