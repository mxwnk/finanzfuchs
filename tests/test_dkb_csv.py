from datetime import date
from decimal import Decimal

import pytest

from bauplan.imports.dkb_csv import DkbExportError, parse_dkb_export

HEADER = (
    '"Girokonto";"DE00111111110000000001"\n'
    '"Zeitraum:";"01.01.2026 - 31.10.2026"\n'
    '"Kontostand vom 31.10.2026:";"5.276,06 €"\n'
    '""\n'
    '"Buchungsdatum";"Wertstellung";"Status";"Zahlungspflichtige*r";"Zahlungsempfänger*in";'
    '"Verwendungszweck";"Umsatztyp";"IBAN";"Betrag (€)";"Gläubiger-ID";"Mandatsreferenz";'
    '"Kundenreferenz"\n'
)
CARD_PAYMENT = (
    '"30.10.26";"30.10.26";"Gebucht";"ISSUER";"REWE";"VISA Debitkartenumsatz vom 29.10.2026";'
    '"Ausgang";"DE96120300009005290904";"-20,3";"";"";"486302531506729"\n'
)
SALARY = (
    '"28.10.26";"28.10.26";"Gebucht";"Arbeitgeber GmbH";"Familie";"Lohn/Gehalt 10/2026";'
    '"Eingang";"DE55555555555555555555";"2.345,67";"";"";""\n'
)


def export_with(*rows: str) -> str:
    return "﻿" + HEADER + "".join(rows)


def test_reads_the_account_iban_from_the_first_line() -> None:
    export = parse_dkb_export(export_with(CARD_PAYMENT))

    assert export.account_iban == "DE00111111110000000001"


def test_payment_is_negative_with_the_payee_as_counterparty() -> None:
    [transaction] = parse_dkb_export(export_with(CARD_PAYMENT)).transactions

    assert transaction.amount == Decimal("-20.30")
    assert transaction.counterparty_name == "REWE"
    assert transaction.counterparty_iban == "DE96120300009005290904"
    assert transaction.purpose == "VISA Debitkartenumsatz vom 29.10.2026"


def test_income_is_positive_with_the_payer_as_counterparty() -> None:
    [transaction] = parse_dkb_export(export_with(SALARY)).transactions

    assert transaction.amount == Decimal("2345.67")
    assert transaction.counterparty_name == "Arbeitgeber GmbH"


def test_reads_two_digit_years_as_this_century() -> None:
    [transaction] = parse_dkb_export(export_with(CARD_PAYMENT)).transactions

    assert transaction.booking_date == date(2026, 10, 30)


def test_marks_only_booked_rows_as_booked() -> None:
    pending = CARD_PAYMENT.replace('"Gebucht"', '"Vorgemerkt"')

    [transaction] = parse_dkb_export(export_with(pending)).transactions

    assert not transaction.is_booked


def test_belongs_to_the_exported_account() -> None:
    [transaction] = parse_dkb_export(export_with(CARD_PAYMENT)).transactions

    assert transaction.account_uid == "DE00111111110000000001"


def test_the_same_row_gets_the_same_id_in_every_export() -> None:
    [first] = parse_dkb_export(export_with(CARD_PAYMENT, SALARY)).transactions[:1]
    [second] = parse_dkb_export(export_with(CARD_PAYMENT)).transactions

    assert first.transaction_id == second.transaction_id
    assert first.transaction_id.startswith("dkb-")


def test_identical_rows_on_one_day_get_different_ids() -> None:
    first, second = parse_dkb_export(export_with(CARD_PAYMENT, CARD_PAYMENT)).transactions

    assert first.transaction_id != second.transaction_id


def test_rejects_a_file_without_the_column_header() -> None:
    with pytest.raises(DkbExportError, match="Buchungsdatum"):
        parse_dkb_export('"Girokonto";"DE00111111110000000001"\n"nothing else"\n')


def test_names_the_line_of_an_unreadable_amount() -> None:
    broken = CARD_PAYMENT.replace('"-20,3"', '"zwanzig"')

    with pytest.raises(DkbExportError, match="line 6"):
        parse_dkb_export(export_with(broken))
