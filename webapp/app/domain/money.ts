/** Amounts are whole cents everywhere: floats round, and SQLite has no decimal type. */
export type Cents = number;

const CENTS_PER_EURO = 100;
const AMOUNT_PATTERN = /^-?\d+(\.\d+)?$/;

export class AmountError extends Error {}

/** Accepts `-1.409,84`, `-20,3`, `3000` and `1.234,50 €`. */
export function parseGermanAmount(text: string): Cents {
  const normalized = text.replace(/[€\s ]/g, "").replace(/\./g, "").replace(",", ".");
  if (!AMOUNT_PATTERN.test(normalized)) {
    throw new AmountError(`"${text}" ist kein Betrag`);
  }
  return Math.round(Number(normalized) * CENTS_PER_EURO);
}

export function formatEuro(cents: Cents, options: { cents?: boolean } = {}): string {
  const digits = options.cents ? 2 : 0;
  const formatter = new Intl.NumberFormat("de-DE", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
  return `${formatter.format(cents / CENTS_PER_EURO)} €`;
}
