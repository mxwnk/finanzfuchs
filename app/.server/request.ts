import { type Month, monthOf, parseMonth } from "~/domain/month";

/** The month in `?monat=YYYY-MM`, the current one otherwise. */
export function requestedMonth(request: Request): Month {
  const text = new URL(request.url).searchParams.get("monat");
  return parseMonth(text) ?? monthOf(new Date());
}
