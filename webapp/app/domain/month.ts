/** A month as `YYYY-MM`: sorts as text and matches the start of an ISO booking date. */
export type Month = string;

const MONTH_PATTERN = /^(\d{4})-(0[1-9]|1[0-2])$/;
const MONTH_NAMES = [
  "Januar", "Februar", "März", "April", "Mai", "Juni",
  "Juli", "August", "September", "Oktober", "November", "Dezember",
];

/** A local `Date` or an ISO date like `2026-10-30`. */
export function monthOf(day: Date | string): Month {
  if (typeof day === "string") {
    return day.slice(0, 7);
  }
  return toMonth(day.getFullYear(), day.getMonth() + 1);
}

export function shiftMonth(month: Month, by: number): Month {
  const [year, monthNumber] = split(month);
  const index = year * 12 + (monthNumber - 1) + by;
  return toMonth(Math.floor(index / 12), (index % 12) + 1);
}

export function monthLabel(month: Month): string {
  const [year, monthNumber] = split(month);
  return `${MONTH_NAMES[monthNumber - 1]} ${year}`;
}

export function parseMonth(text: string | null): Month | null {
  return text && MONTH_PATTERN.test(text) ? text : null;
}

function split(month: Month): [number, number] {
  const [year, monthNumber] = month.split("-").map(Number);
  return [year, monthNumber];
}

function toMonth(year: number, monthNumber: number): Month {
  return `${year}-${String(monthNumber).padStart(2, "0")}`;
}
