"""Amounts in PLN: rounding to the grosz and the Polish way of writing them (money.py, base.py)."""

from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")


def cents(amount: Decimal) -> Decimal:
    """To the grosz, half a grosz up."""
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)


def pln(amount: Decimal) -> str:
    """6 903,20 zł"""
    return f"{cents(amount):,.2f}".replace(",", " ").replace(".", ",") + " zł"


def percent(rate: Decimal) -> str:
    """100%, 81,5%"""
    return f"{rate.normalize():f}".replace(".", ",") + "%"


def dec(value: float) -> Decimal:
    """A float from the parameters or the scenario, exactly as written (8000.5 -> 8000.5)."""
    return Decimal(str(value))
