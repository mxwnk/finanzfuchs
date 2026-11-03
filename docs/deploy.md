# Deploying to the Raspberry Pi

Every push to `main` runs typecheck and tests and, when they pass, builds an arm64 image
`ghcr.io/mxwnk/finanzfuchs:latest` on GitHub's ARM runner. The homelab repo deploys it to the
pi5 behind Traefik as `http://finanzfuchs.home` (AdGuard resolves `*.home` to the Pi).

## Once

1. **Pocket ID client** (<https://id.fuxbau.org>, admin → OIDC clients):
   - name `Finanzfuchs`, callback URL `http://finanzfuchs.home/auth/callback` (and
     `http://localhost:8000/auth/callback` for local development);
   - allowed group `fuxbau` (Max and Merle).
2. **Secrets** in the homelab repo: `cp pi5/finanzfuchs/.env.example pi5/finanzfuchs/.env`, fill
   in client id and secret and a session secret (`openssl rand -base64 48`). The file is ignored
   by git.
3. **Deploy**: in the homelab repo `./run -h pi5 -t finanzfuchs`.

## Every update

Push to `main`, wait for CI, then `./run -h pi5 -t finanzfuchs` in the homelab repo.

## Data

The whole state is `~/Projects/homelab/finanzfuchs/data/finanzfuchs.db` on the Pi; the app
migrates it on start. To replace it with a local database:

```bash
ssh max@pi5.fuxbau 'docker stop finanzfuchs'
scp data/finanzfuchs.db max@pi5.fuxbau:Projects/homelab/finanzfuchs/data/
ssh max@pi5.fuxbau 'docker start finanzfuchs'
```

For a backup copy the file while the container is stopped, or use
`sqlite3 finanzfuchs.db ".backup backup.db"`.
