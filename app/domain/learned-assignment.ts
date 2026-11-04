import type { Assignment } from "./categories";
import type { AssignedTransaction } from "./overview";

export interface LearnedAssignment {
  transactionId: string;
  category: Assignment;
  budgetItemId: number | null;
}

/** Below this share of one category a counterparty is too mixed to guess, e.g. a payment service. */
const MINIMUM_SHARE_OF_USUAL_CATEGORY = 0.8;
/** A single earlier payment with another amount says too little about the next one. */
const MINIMUM_EARLIER_PAYMENTS = 2;

type AssignedPayment = AssignedTransaction & { category: Assignment };

/**
 * Assigns open payments the way the family assigned earlier ones, so nobody has to keep rules:
 * the same counterparty and amount get the category chosen last time (yearly item included);
 * a new amount gets the counterparty's usual category. Everything else stays open.
 */
export function learnAssignments(open: AssignedTransaction[], history: AssignedTransaction[]): LearnedAssignment[] {
  const earlierByCounterparty = groupByCounterparty(newestFirst(history.filter(hasCategory)));
  return open.flatMap((transaction) => {
    const earlier = earlierByCounterparty.get(counterpartyKey(transaction));
    const learned = earlier && (fromSameAmount(transaction, earlier) ?? fromUsualCategory(transaction, earlier));
    return learned ? [learned] : [];
  });
}

function fromSameAmount(transaction: AssignedTransaction, earlier: AssignedPayment[]): LearnedAssignment | undefined {
  const latest = earlier.find((payment) => payment.amountCents === transaction.amountCents);
  return latest && { transactionId: transaction.id, category: latest.category, budgetItemId: latest.budgetItemId };
}

/** A yearly item is tied to its amount, so a new amount is monthly spending. */
function fromUsualCategory(transaction: AssignedTransaction, earlier: AssignedPayment[]): LearnedAssignment | undefined {
  if (earlier.length < MINIMUM_EARLIER_PAYMENTS) {
    return undefined;
  }
  const [category, count] = mostFrequentCategory(earlier);
  if (count / earlier.length < MINIMUM_SHARE_OF_USUAL_CATEGORY) {
    return undefined;
  }
  return { transactionId: transaction.id, category, budgetItemId: null };
}

function mostFrequentCategory(payments: AssignedPayment[]): [Assignment, number] {
  const counts = new Map<Assignment, number>();
  for (const payment of payments) {
    counts.set(payment.category, (counts.get(payment.category) ?? 0) + 1);
  }
  return [...counts].reduce((best, entry) => (entry[1] > best[1] ? entry : best));
}

/** Payments without a counterparty (an empty key) have nothing to learn from. */
function groupByCounterparty(payments: AssignedPayment[]): Map<string, AssignedPayment[]> {
  const groups = new Map<string, AssignedPayment[]>();
  for (const payment of payments) {
    const key = counterpartyKey(payment);
    if (key) {
      groups.set(key, [...(groups.get(key) ?? []), payment]);
    }
  }
  return groups;
}

function counterpartyKey(transaction: AssignedTransaction): string {
  return transaction.counterparty.trim().toLowerCase();
}

function newestFirst(payments: AssignedPayment[]): AssignedPayment[] {
  return [...payments].sort((first, second) => second.bookingDate.localeCompare(first.bookingDate));
}

function hasCategory(transaction: AssignedTransaction): transaction is AssignedPayment {
  return transaction.category !== null;
}
