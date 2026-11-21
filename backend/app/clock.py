"""'Today' for the whole app: the calendar day in Poland, not in the server's time zone."""

import datetime as dt
from zoneinfo import ZoneInfo

WARSAW = ZoneInfo("Europe/Warsaw")


def today_in_warsaw() -> dt.date:
    return dt.datetime.now(WARSAW).date()
