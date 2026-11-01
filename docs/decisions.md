# Decisions

Every product and architecture decision of Finanzfuchs (first called Bauplan), with its reason.
Settled in design sessions from 2026-10-31; newest additions at the end of each section.

## Product

- **What it is**: plan vs. actual of the Fuxbau family budget (Max and Merle). The plan used to
  live in `Fuxbau Finanzen.xlsx`, which stays as an archive.
- **Granularity**: every bank transaction is assigned to exactly one plan line; the category
  follows from the line. Views show categories per month with plan lines as the detail.
- **Accounts in scope**: the joint DKB account and the shared sub-accounts *Fixkosten*,
  *Funpark* and *Notgroschen*. Transfers to the personal accounts and to private loans count as spent
  the moment they leave the joint account; what happens on those accounts is private.
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

- **A web app replaces the Google Sheet** (2026-10-31, same day): in the sheet, assigning meant
  finding a row among 1.282 and picking one of 64 ids in a dropdown, and its formulas broke on
  locale and `LET`. The app shows the open and doubtful transactions one by one with plan lines
  as buttons, and turns a choice into a rule on request. Rules, plan and assignments now live in
  one place instead of a sheet plus a rule file on a laptop.
- **SQLite on the Pi is the single source of truth**: plan, rules, transactions, imports and
  login sessions in one file, amounts as cents. One connection per request; the schema version
  sits in `PRAGMA user_version`, so later migrations know where they start.
- **Runs on the pi5 as `http://finanzfuchs.home`** behind Traefik (AdGuard resolves `*.home` to
  the Pi), deployed by the homelab Ansible like the other pi5 apps. The image is built for arm64
  by GitHub Actions on a native ARM runner (free for the public repository).
- **Login through Pocket ID**, group `fuxbau` only, with the OIDC code from the Fuxbau app. The
  session is an HttpOnly, SameSite=Lax cookie (30 days) whose token is stored only as a hash.
  Lax cookies are not sent on cross-site POSTs, which covers CSRF for the forms; the JSON API
  additionally needs a JSON content type. There is no login bypass; tests use a fake provider.
- **Pages**: *Übersicht* (the dashboard), *Zuordnen* (open first, then doubtful; confirm the
  rule's guess, pick a plan line, optionally remember it as a rule), *Import* (upload a DKB CSV;
  known rows are skipped, rules run at once), *Plan* (edit lines; a changed amount ends the old
  line with *gültig bis* and starts a new one), and an Excel export as backup.
- **Rules from the app go to the top** and apply to open and doubtful transactions only; a choice
  made by hand (`manual`) is never changed by a rule again.
- **Doubtful** means assigned by a rule whose note starts with `ZWEIFEL`; confirming it makes it
  a choice made by hand.
- **Takeover**: `finanzfuchs seed data` reads `plan.csv`, `rules.csv` and the DKB exports from
  before the app into an empty database, which is then copied to the Pi.
- **Public repository**: code, tests and docs contain no IBANs, real counterparties, amounts or
  keys; `data/`, `.env`, `*.pem`, `*.csv` and `*.xlsx` are ignored.
- **Dashboard**: a BI-style page with KPIs, monthly trend, plan vs. actual per category, the
  largest effects on the balance, where the money goes and the Fixkosten pot, filterable by year,
  month and category. ECharts and the data are inlined, so nothing loads from the internet.
- **Unplanned means a plan line without an amount** (or no line yet), in every category. This
  includes drugstore and Amazon under *Täglicher Bedarf*, not only the *Ungeplant* category.
- **CSV import before Enable Banking**: the DKB web export covers any period (not just 90 days),
  so a monthly manual export is enough. The export has no transaction ids, so an id is derived
  from the row plus its position among identical rows of the same day.
- **Bank access through Enable Banking later** (code prepared): restricted production mode, one
  approval in the DKB app about every 180 days; FinTS would need an approval on every run,
  GoCardless takes no new customers. Banks often return the full history only shortly after the
  approval, so `connect` backs up everything since 2026-01-01 at once, and raw responses are
  archived before parsing because older transactions cannot be fetched again.
- **Assignment by AI later (v2)**: through the Claude API, sending counterparty name, purpose,
  amount and date but no own IBANs or balances.

- **The month is the start page** (2026-11-01): Max wants to know how the current month is going
  more than the year. It shows spent vs. planned with the remaining amount, the variable budgets
  with a pace mark, a checklist of the fixed income and debits, what the Fixkosten pot paid, the
  unplanned spending and the latest bookings. Without bookings yet it says so and offers the
  import and the previous month. The former overview moves to *Jahr*.
- **Plan lines are fixed or variable** (schema version 2): fixed lines arrive once at a known
  amount and go on the checklist; variable lines are budgets used up over the month. Existing
  lines got a guess (income, standing orders to a pot, housing, insurance, fixed costs and savings
  are fixed); the plan page changes it.
- **Pace**: a budget is *too fast* once its share spent is more than 10 percentage points ahead of
  the share of the month passed, and *over* once it exceeds the plan.
- **Fixed items**: received within 1 € or 1 %; income counts as received from the planned amount
  upwards, because more income is no problem. Everything else deviates and is shown in red.
- **Yearly costs and what the Fixkosten account reimburses** stay out of the monthly budget and
  appear in their own section; they were saved up over the year.
- **Year view in plain words**: per category "8.659 € von 8.000 €" and "659 € drüber" or
  "350 € übrig" instead of arrows and percentages; an active category filter shows as a chip.
- **Phones**: one column, bigger charts, a bottom tab bar (Monat, Jahr, Zuordnen, Import, Plan),
  and a web manifest with icon so the app can live on the home screen. ECharts is served as a
  cached file to the month page instead of being inlined into it.
- **Weekly CSV import for now**, without reminders; Enable Banking remains the next big step for
  fresh numbers without manual work.

## Superseded

- **Google Sheet as frontend and source of truth** (replaced by the web app, see above). Learned
  on the way: the Sheets API parses formulas in the spreadsheet's locale, and `LET` needs
  `ARRAYFORMULA` to evaluate `SEQUENCE`.
- **Service on the NUC with a daily sync and ntfy notifications**: postponed until Enable Banking
  is connected; with CSV uploads there is nothing to schedule.
- **Rules in `data/rules.csv`, kept by Claude Code**: rules now live in the database and grow
  from the assigning page.
