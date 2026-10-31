from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from bauplan.assignment.rules import AssignmentRule, RuleFileError, assign, load_rules
from bauplan.banking.transactions import BankTransaction


def transaction(
    counterparty_name: str = "REWE",
    purpose: str = "VISA Debitkartenumsatz",
    counterparty_iban: str = "DE96",
    amount: str = "-20.30",
) -> BankTransaction:
    return BankTransaction(
        transaction_id="t1",
        account_uid="DE01",
        booking_date=date(2026, 3, 2),
        amount=Decimal(amount),
        counterparty_name=counterparty_name,
        counterparty_iban=counterparty_iban,
        purpose=purpose,
        is_booked=True,
    )


def rule(plan_line_id: str, **conditions: str) -> AssignmentRule:
    return AssignmentRule(plan_line_id=plan_line_id, **conditions)


class TestMatching:
    def test_matches_part_of_the_counterparty_ignoring_case(self) -> None:
        assert rule("lebensmittel", counterparty_contains="rewe").matches(transaction())

    def test_matches_part_of_the_purpose(self) -> None:
        payment = transaction(purpose="Lohn/Gehalt 12345/202610")

        assert rule("gehalt", purpose_contains="Lohn/Gehalt").matches(payment)

    def test_matches_the_exact_counterparty_iban(self) -> None:
        assert rule("umbuchung", counterparty_iban="DE96").matches(transaction())
        assert not rule("umbuchung", counterparty_iban="DE9").matches(transaction())

    def test_requires_every_condition(self) -> None:
        both = rule("sprit", counterparty_contains="REWE", purpose_contains="Tankstelle")

        assert not both.matches(transaction())

    def test_can_be_limited_to_money_leaving_or_arriving(self) -> None:
        refund = transaction(amount="5.00")

        assert not rule("lebensmittel", counterparty_contains="REWE", direction="out").matches(
            refund
        )
        assert rule("erstattung", counterparty_contains="REWE", direction="in").matches(refund)

    def test_a_rule_without_conditions_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="condition"):
            rule("lebensmittel")


class TestAssign:
    def test_the_first_matching_rule_wins(self) -> None:
        rules = [
            rule("drogerie", counterparty_contains="ROSSMANN"),
            rule("lebensmittel", counterparty_contains="REWE"),
            rule("ungeplant", counterparty_contains="R"),
        ]

        [assignment] = assign([transaction()], rules)

        assert assignment.plan_line_id == "lebensmittel"
        assert assignment.rule_number == 2

    def test_leaves_unmatched_transactions_open(self) -> None:
        [assignment] = assign([transaction()], [rule("drogerie", counterparty_contains="dm")])

        assert assignment.plan_line_id is None
        assert assignment.rule_number is None


class TestRuleFile:
    def test_reads_rules_in_file_order(self, tmp_path: Path) -> None:
        rule_file = tmp_path / "rules.csv"
        rule_file.write_text(
            "plan_line_id,counterparty_contains,purpose_contains,counterparty_iban,direction,note\n"
            "lebensmittel,REWE,,,out,Supermarkt\n"
            "umbuchung,,,DE14,,Fixkosten\n"
        )

        rules = load_rules(rule_file)

        assert rules == [
            rule("lebensmittel", counterparty_contains="REWE", direction="out", note="Supermarkt"),
            rule("umbuchung", counterparty_iban="DE14", note="Fixkosten"),
        ]

    def test_hands_the_rule_note_on_to_the_assignment(self) -> None:
        doubtful = rule("rueckzahlung", counterparty_contains="REWE", note="ZWEIFEL: wirklich?")

        [assignment] = assign([transaction()], [doubtful])

        assert assignment.note == "ZWEIFEL: wirklich?"

    def test_names_the_line_of_a_broken_rule(self, tmp_path: Path) -> None:
        rule_file = tmp_path / "rules.csv"
        rule_file.write_text(
            "plan_line_id,counterparty_contains,purpose_contains,counterparty_iban,direction,note\n"
            "lebensmittel,,,,,no condition\n"
        )

        with pytest.raises(RuleFileError, match="line 2"):
            load_rules(rule_file)
