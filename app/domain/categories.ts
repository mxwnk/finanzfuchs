/** The spending categories the family budgets per month, in the order they are shown. */
export const CATEGORIES = [
  "Wohnen",
  "Fixkosten",
  "Auto",
  "Sparen",
  "Versicherungen",
  "Täglicher Bedarf",
  "Freizeit",
  "Arbeitskosten",
] as const;

export type Category = (typeof CATEGORIES)[number];

/**
 * For money that leaves the account without being spending, e.g. a transfer between own
 * accounts. Marked transactions stop asking to be assigned and never count in the overview.
 */
export const IGNORED = "ignoriert";

export type Assignment = Category | typeof IGNORED;

export function isAssignment(value: unknown): value is Assignment {
  return value === IGNORED || CATEGORIES.includes(value as Category);
}
