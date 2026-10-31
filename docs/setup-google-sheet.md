# Setting up the Google Sheet

One-time setup. Steps 1–3 happen in Google's web interfaces with your account.

## 1. A service account for Bauplan

Use the existing Google Cloud project `<gcp-project>`, but give Bauplan its **own** service
account instead of reusing `ironman-calendar`: a leaked calendar key must not open the finances.

1. <https://console.cloud.google.com/apis/library/sheets.googleapis.com?project=<gcp-project>>
   → **Enable** the Google Sheets API.
2. *IAM & Admin → Service accounts → Create service account*: name `bauplan`, no roles. It needs
   no project permissions; access comes only from sharing the sheet.
3. Open the account → *Keys → Add key → Create new key → JSON*. Move the download out of the
   downloads folder:

   ```bash
   mkdir -p ~/.config/bauplan && mv ~/Downloads/<gcp-project>-*.json ~/.config/bauplan/google-service-account.json && chmod 600 ~/.config/bauplan/google-service-account.json
   ```

## 2. The sheet

1. Create an empty Google Sheet named **Bauplan** in your Drive.
2. *Share* it with `bauplan@<gcp-project>.iam.gserviceaccount.com` as **Editor** (untick
   "notify"), and with Merle as **Editor**.

`sheet-setup` sets the locale to Germany itself, so amounts show as `1.234,56 €`.

## 3. Configure and fill

In `.env` set `GOOGLE_SERVICE_ACCOUNT_FILE=~/.config/bauplan/google-service-account.json` (as an
absolute path) and `BAUPLAN_SPREADSHEET_ID` (the id between `/d/` and `/edit` in the address).

```bash
set -a && source .env && set +a
uv run bauplan sheet-setup
uv run bauplan sheet-sync
```

`sheet-setup` creates the tabs, formulas, formats and the plan-line dropdown. It writes the plan
from `data/plan.csv` only while the *Plan* tab is empty; afterwards the plan lives in the sheet.
It can be run again at any time to repair formulas. The default tab *Sheet1* can be deleted.

If `sheet-setup` stops with `403 The caller does not have permission`, the key in
`GOOGLE_SERVICE_ACCOUNT_FILE` belongs to an account the sheet is not shared with. Check
`client_email` in the key file.

## Every month

1. Export the joint account as CSV in the DKB online banking (*Umsätze → Export*) into
   `data/imports/`.
2. `uv run bauplan import data/imports/<file>.csv`
3. Ask Claude Code to assign the new transactions (it extends `data/rules.csv`).
4. `uv run bauplan sheet-sync` — appends the new rows and fills plan lines that are still empty.
   Plan lines chosen by hand in the sheet are never overwritten.
5. `uv run bauplan dashboard && open data/dashboard.html` — the dashboard from the sheet's
   current state.
