"""A booked transaction together with the plan line it belongs to."""

from dataclasses import dataclass
from enum import StrEnum

from finanzfuchs.banking.transactions import BankTransaction

DOUBT_PREFIX = "ZWEIFEL"


class AssignmentSource(StrEnum):
    OPEN = ""
    RULE = "rule"
    MANUAL = "manual"
    """Chosen by Max or Merle; rules never change it again."""


@dataclass(frozen=True)
class LedgerEntry:
    transaction: BankTransaction
    plan_line_id: str | None
    source: AssignmentSource
    note: str

    @property
    def is_open(self) -> bool:
        return self.plan_line_id is None

    @property
    def is_doubtful(self) -> bool:
        return self.source == AssignmentSource.RULE and self.note.startswith(DOUBT_PREFIX)

    @property
    def needs_attention(self) -> bool:
        return self.is_open or self.is_doubtful

    @property
    def may_be_reassigned_by_rule(self) -> bool:
        return self.source != AssignmentSource.MANUAL and self.needs_attention
