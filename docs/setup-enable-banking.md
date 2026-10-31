# Setting up Enable Banking

One-time setup of the bank access. Only the account holder can do steps 1–3: they create an
account, accept terms and approve access at the bank.

## 1. Register the application

1. Sign in at <https://enablebanking.com/sign-in/> with your email; the account is created on
   the first sign-in.
2. Open *API applications* (<https://enablebanking.com/cp/applications>) and add a new
   application:
   - Environment: **Production** (not Sandbox).
   - Name: `Finanzfuchs` — shown on the bank approval page.
   - Redirect URL: `https://fuxbau.org/finanzfuchs/callback`. Nothing needs to answer there; after
     the approval you copy the address from the browser.
3. Click *Register*. The browser downloads the private key as `<application id>.pem`.
4. Move the key out of the downloads, e.g. to `~/.config/finanzfuchs/<application id>.pem`, and
   restrict it: `chmod 600 ~/.config/finanzfuchs/*.pem`. Never commit it (`*.pem` is ignored).

## 2. Activate restricted mode by linking the accounts

The new application is *Inactive*. Click **Activate by linking accounts**, choose DKB and approve
in the DKB app. Link the joint account and the sub-accounts *Fixkosten*, *Funpark* and
*Notgroschen*. The application then runs in restricted mode: it can only read the linked
accounts.

While doing this, check two things that are not verified yet:

- whether restricted mode is free of charge for private use (control panel, pricing/terms);
- whether all four accounts are offered for linking.

## 3. Configure Finanzfuchs

```bash
cp .env.example .env
```

Fill in `ENABLE_BANKING_APPLICATION_ID` and `ENABLE_BANKING_PRIVATE_KEY_PATH`.

## 4. Approve the API access and back up the history

Linking in the control panel does not authorize the API; that is a separate approval:

```bash
set -a && source .env && set +a && uv run finanzfuchs connect
```

1. Open the printed address and approve in the DKB app.
2. The browser lands on the redirect address (an error page is fine).
3. Paste the full address into the terminal.

`connect` saves the session in `data/session.json` and immediately fetches every transaction since
`FINANZFUCHS_HISTORY_START` into `data/raw/`. Banks often return the full history only shortly
after the approval, so do this in one go. Afterwards:

```bash
uv run finanzfuchs accounts   # session status and the accounts it covers
uv run finanzfuchs fetch      # fetch and archive again
```

Back up `data/` — the raw files are the only lasting copy of transactions older than 90 days.
