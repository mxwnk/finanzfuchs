# Deploying to the Raspberry Pi

Every push to `main` runs the tests and, when they pass, builds an arm64 image
`ghcr.io/mxwnk/finanzfuchs:latest` on GitHub's ARM runner. The homelab repo deploys it to the
pi5 behind Traefik as `http://finanzfuchs.home` (AdGuard resolves `*.home` to the Pi).

## Once

1. **Pocket ID client** (<https://id.fuxbau.org>, admin → OIDC clients → add):
   - name `Finanzfuchs`, callback URL `http://finanzfuchs.home/auth/callback`;
   - allowed group `fuxbau` (Max and Merle).
2. **Secrets** in the homelab repo: `cp pi5/finanzfuchs/.env.example pi5/finanzfuchs/.env` and
   fill in client id and secret. The file is ignored by git.
3. **Image access**: the pi5 already pulls private images from ghcr.io (eatwise). If the package
   is private and the pull fails, run `docker login ghcr.io` on the Pi once, or make the
   package public in GitHub (it contains no data).
4. **Deploy**: in the homelab repo `./run -h pi5 -t finanzfuchs`.
5. **Take over the existing data** (plan, rules, transactions) from the Mac, while the app runs
   with an empty database:

   ```bash
   uv run finanzfuchs seed data                      # builds data/finanzfuchs.sqlite3 locally
   ssh max@pi5.fuxbau 'docker stop finanzfuchs'
   scp data/finanzfuchs.sqlite3 max@pi5.fuxbau:Projects/homelab/finanzfuchs/data/
   ssh max@pi5.fuxbau 'docker start finanzfuchs'
   ```

   Alternatively upload the DKB exports on the import page; plan and rules then have to be
   entered on the plan page.

## Every update

Push to `main`, wait for CI, then `./run -h pi5 -t finanzfuchs` in the homelab repo.

## Backup

The whole state is `~/Projects/homelab/finanzfuchs/data/finanzfuchs.sqlite3` on the Pi. The
Excel export on the overview is a readable copy; for a full backup copy the database file while
the container is stopped (or use `sqlite3 … ".backup backup.sqlite3"`).
