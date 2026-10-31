# Decisions

Every product and architecture decision of Bauplan, with its reason. Settled in a design session on
2026-10-31; newest additions at the end of each section.

## Product

- **What it is**: plan vs. actual of the Fuxbau family budget (Max and Merle). The plan used to
  live in `Fuxbau Finanzen.xlsx`, which stays as an archive.
- **Granularity**: every bank transaction is assigned to exactly one plan line; the category
  follows from the line. Views show categories per month with plan lines as the detail.
- **Accounts in scope**: the joint DKB account and the shared sub-accounts *Fixkosten*,
  *Funpark* and *Notgroschen*. Transfers to the personal accounts and to private loans count as spent the
  moment they leave the joint account; what happens on those accounts is private.
- **Internal transfers**: transfers between the four Fuxbau accounts are recognized by IBAN as
  *Umbuchung* and never count as spending. They only serve the monthly check whether a standing
  order arrived as planned.
- **Yearly costs**: they are saved monthly on *Fixkosten* and paid once a year, so a plain
  monthly comparison would be misleading. Three views instead: the monthly transfer to
  *Fixkosten* vs. plan, per yearly line the payments so far this year vs. the yearly plan, and
  the *Fixkosten* balance vs. the yearly costs still open.
- **Plan history**: plan lines carry *gültig ab* / *gültig bis*, so past months are compared with
  the plan that applied then. The current plan starts on 2026-01-01.
- **Analysis start**: 2026-01-01.
- **The Fixkosten account reimburses** (found in the 2026 export): yearly costs are paid from the
  joint account and then refunded from *Fixkosten*. So the joint account alone holds almost every
  real expense; transfers to and from *Fixkosten* are *Umbuchung*.
- **Funpark and Notgroschen count on their plan lines in both directions**: the transfer to the
  pot is the planned spending, a refund from the pot reduces it. That keeps vacation costs paid
  from the joint account and refunded from *Funpark* at zero net.
- **Unplanned spending gets its own lines** (`Ungeplant` category plus unplanned lines in
  *Täglicher Bedarf* and *Arbeitskosten*) with a plan of 0, so it shows up instead of hiding in a
  planned line. Refunds (TK, tax, travel costs) are booked on the line they reduce.

## Architecture

- **Frontend v1 is a Google Sheet**: both of us know spreadsheets, it works on the phone and
  needs no hosting or login of our own. Owned by Max, Merle and the service account edit it.
  A web app (or a section of the Fuxbau app) may follow later and build on the same service.
- **The sheet is the source of truth** for transactions and assignments. The service appends new
  transactions (deduplicated by transaction id) and only ever fills empty cells, so manual
  assignments are never overwritten. A two-way sync with a database of our own would cost far
  more for no gain in v1.
- **Raw bank responses are archived on the NUC**: transactions older than 90 days can usually not
  be fetched again, so nothing may get lost when a row in the sheet is deleted.
- **Bank access through Enable Banking** in restricted production mode (only our own linked
  accounts): one approval in the DKB app about every 180 days, then unattended API access.
  FinTS would need an approval on every run; GoCardless takes no new customers; a manual CSV
  import stays the fallback.
- **Full backfill right after the approval**: banks often return the full history only shortly
  after the approval, so `connect` fetches everything since 2026-01-01 immediately.
- **Runs on the homelab NUC**: Python 3.13 with uv, a Docker image like the Fuxbau app, deployed
  by the homelab Ansible as `nuc/bauplan`. Daily sync at 06:00 (PSD2 allows four unattended
  fetches a day).
- **Notifications through ntfy** (pi5): failed sync, consent expiring within 14 days, and a
  Sunday summary of unassigned transactions.
- **Assignment v1**: deterministic rules in code for the unambiguous cases (internal transfers,
  standing orders); everything else is assigned by hand or with Claude Code in this repository.
  **v2** moves that into the service through the Claude API, sending counterparty name,
  purpose, amount and date but no own IBANs or balances.
- **CSV import before Enable Banking**: the DKB web export covers any period (not just 90 days),
  so a monthly manual export is enough to start. `bauplan import` adds it to the local ledger
  `data/transactions.csv`; Enable Banking follows later. The export has no transaction ids, so an
  id is derived from the row plus its position among identical rows of the same day.
- **Sheet layout**: tabs *Auswertung* (category × month: actual, plan, difference), *Planzeilen*
  (per line year to date, which also covers yearly costs), *Fixkosten-Topf* (planned rate, paid
  in, refunded, running balance), *Buchungen* and *Plan*. Every analysis is a formula, so a plan
  line chosen by hand updates all views at once; the service never computes totals itself.
- **Formulas are written under en_US, the sheet is shown under de_DE**: the Sheets API parses
  formulas in the spreadsheet's locale (the first live run under de_DE failed with parse errors
  in every cell). Switching the locale around the writes keeps one formula syntax in the code;
  Google stores formulas independent of locale and shows them in German afterwards.
- **Bank text is written raw**: transactions go in with `valueInputOption=RAW` and dates as serial
  numbers, so a purpose starting with `=` can never become a formula. Only Bauplan's own formulas
  are written as entered.
- **Own service account `bauplan`** in the existing Google Cloud project instead of reusing the
  calendar account: a leaked key of another service must not open the finances. The Sheets API is
  called directly with httpx and pyjwt; the Google client libraries are not worth it for five calls.
- **Dashboard as a local, self-contained HTML file** (`bauplan dashboard` → `data/dashboard.html`):
  the sheet's tables are hard to read at a glance, so a BI-style page shows KPIs, monthly trend,
  plan vs. actual per category, the largest effects on the balance, where the money goes and the
  Fixkosten pot, all filterable by year, month and category. It reads the sheet, not the local
  ledger, so assignments made by hand show up. ECharts and the data are inlined: nothing loads
  from the internet and the family's numbers never reach a CDN or a hosting service. Serving it
  on the NUC behind Pocket ID is the natural next step for Merle.
- **Unplanned means a plan line without an amount** (or no line yet), in every category. This
  includes drugstore and Amazon under *Täglicher Bedarf*, not only the *Ungeplant* category.
- **Assignment rules live in `data/rules.csv`** (first match wins, kept by Claude Code). They are
  private data like the transactions, so they stay out of git; only the rule engine is code.
