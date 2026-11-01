"""Reading a plan line from the plan page's form, with German amounts like `1.409,84`."""

import re
import unicodedata
from collections.abc import Mapping
from datetime import date
from decimal import Decimal, InvalidOperation

from finanzfuchs.plan import KINDS, PlanLine

LINE_TYPES = ("Ausgabe", "Einnahme", "Umbuchung")
RHYTHMS = ("Monat", "Jahr")
UMLAUTS = {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}


class PlanFormError(ValueError):
    """The form holds a value a plan line cannot have; the message is shown on the page."""


def plan_line_from_form(plan_line_id: str, form: Mapping[str, object]) -> PlanLine:
    description = _required(form, "description", "Beschreibung")
    return PlanLine(
        plan_line_id=plan_line_id,
        line_type=_choice(form, "line_type", LINE_TYPES, "Typ"),
        category=_required(form, "category", "Kategorie"),
        description=description,
        amount=_amount(_text(form, "amount")),
        rhythm=_choice(form, "rhythm", RHYTHMS, "Rhythmus"),
        pot=_text(form, "pot"),
        valid_from=_date(_text(form, "valid_from"), "Gültig ab") or date.today(),
        valid_until=_date(_text(form, "valid_until"), "Gültig bis"),
        kind=_choice(form, "kind", KINDS, "Art"),
    )


def new_plan_line_id(description: str, existing_ids: set[str]) -> str:
    base = _slug(description) or "planzeile"
    candidate, suffix = base, 2
    while candidate in existing_ids:
        candidate, suffix = f"{base}-{suffix}", suffix + 1
    return candidate


def parse_amount(text: str) -> Decimal:
    """Accepts `1.409,84`, `1409,84` and `1409.84`."""
    cleaned = text.replace("€", "").replace(" ", "").strip()
    if "," in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    return Decimal(cleaned)


def _amount(text: str) -> Decimal:
    try:
        amount = parse_amount(text or "0")
    except InvalidOperation as error:
        raise PlanFormError(f"Betrag „{text}“ ist keine Zahl.") from error
    if amount < 0:
        raise PlanFormError("Der Betrag ist immer positiv; der Typ sagt, ob Geld kommt oder geht.")
    return amount


def _date(text: str, label: str) -> date | None:
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError as error:
        raise PlanFormError(f"{label} „{text}“ ist kein Datum.") from error


def _choice(form: Mapping[str, object], field: str, choices: tuple[str, ...], label: str) -> str:
    value = _text(form, field)
    if value not in choices:
        raise PlanFormError(f"{label} muss eins von {', '.join(choices)} sein.")
    return value


def _required(form: Mapping[str, object], field: str, label: str) -> str:
    value = _text(form, field)
    if not value:
        raise PlanFormError(f"{label} fehlt.")
    return value


def _text(form: Mapping[str, object], field: str) -> str:
    return str(form.get(field) or "").strip()


def _slug(text: str) -> str:
    lowered = "".join(UMLAUTS.get(char, char) for char in text.lower())
    ascii_text = unicodedata.normalize("NFKD", lowered).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_text).strip("-")
