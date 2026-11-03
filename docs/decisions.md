# Decisions

Every product and architecture decision of Finanzfuchs, with its reason. Version 2 (React Router)
replaced the first Python app on 2026-11-03; what was learned from it is at the end.

## Product

- **What it is**: how the Fuxbau family (Max and Merle) is doing against its budget, from the DKB
  accounts. The plan used to live in `Fuxbau Finanzen.xlsx`, which stays as an archive.
- **Four tabs**: *Übersicht* (the current month), *Budgets*, *Zuordnen*, *Import*. On phones they
  sit in a floating bar at the bottom, on wide screens above the content.
- **Budgets per category** instead of 64 plan lines: Wohnen, Fixkosten, Auto, Sparen,
  Versicherungen, Täglicher Bedarf, Freizeit, Arbeitskosten. Assigning means one tap on a
  category; the v1 plan lines made that a search.
- **Budget items** like the rows of the Excel: each has a name, an amount, a rhythm (*Monat* or
  *Jahr*) and a validity (`validFrom`, `validUntil`). A category's monthly budget is the sum of
  its monthly items.
- **Yearly items feed a reserve**: a twelfth is saved every month; a payment assigned to a yearly
  item is paid from the reserve and stays out of the month's spending. The overview shows the
  reserve's balance for the year and which yearly items are paid.
- **Keine Ausgabe** (`ignoriert`) marks transfers between own accounts; they never count.
- **Income is not assigned**; only money that left the account waits on *Zuordnen*.
- **Refunds reduce the spending** of the category they are assigned to.
- **Bargeld counts as Täglicher Bedarf.**
- **Removing a budget item only marks it**; it is gone when the budgets are saved, so a slip of
  the finger costs nothing.

## Architecture

- **React Router 8 in framework mode** (the newest version): loaders and actions on the server,
  forms that work without JavaScript, typed routes. Tailwind 4 for styles, Vitest for tests.
- **SQLite through `node:sqlite`** (no native dependency): one file, amounts as cents, schema
  steps counted in `PRAGMA user_version`.
- **CSV import from the DKB web export**: it covers any period, so a weekly or monthly manual
  export is enough. The export has no transaction ids, so an id is derived from the row plus its
  position among identical rows of the same day; pending rows are skipped.
- **Login through Pocket ID**, group `fuxbau` only, with `openid-client` (code flow with PKCE,
  verified ID token). The session is a signed HttpOnly, SameSite=Lax cookie (30 days) holding
  only who is logged in; Lax cookies are not sent on cross-site POSTs, which covers CSRF for the
  forms. A middleware on the layout route guards every page and form. There is no login bypass;
  tests use a fake provider.
- **Runs on the pi5 as `http://finanzfuchs.home`** behind Traefik, deployed by the homelab
  Ansible like the other pi5 apps. The image is built for arm64 by GitHub Actions on a native ARM
  runner (free for the public repository).
- **Nothing is loaded from the internet**: no web fonts, icons are inline SVG.
- **Public repository**: code, tests and docs contain no IBANs, real counterparties, amounts or
  keys; `data/`, `.env`, `*.csv` and `*.xlsx` are ignored.

## Learned from version 1 (Python, FastAPI)

- **A Google Sheet was the first frontend** and failed on usability (picking one of 64 ids in a
  dropdown among 1.282 rows) and on formulas (the Sheets API parses them in the spreadsheet's
  locale; `LET` needs `ARRAYFORMULA` to evaluate `SEQUENCE`).
- **Plan lines, rules and a year dashboard were too much**: the family wants to know how the
  current month is going, and assigning by category is fast enough without rules.
- **The v1 data was taken over**: transactions and their categories (unplanned lines mapped to the
  closest category), the plan lines as budget items, and the payments of yearly lines linked to
  their items.
- **Enable Banking stays an option** for fetching transactions without manual exports: restricted
  production mode, one approval in the DKB app about every 180 days. Raw bank responses must be
  archived before parsing, because banks return older transactions only shortly after approval.
