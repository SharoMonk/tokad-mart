# Tokad Mart — Production Readiness and Deployment Runbook

## Scope and deployment decision

This milestone adds a **separate** `docker-compose.prod.yml`, production Dockerfiles for the Django and Next.js services, a readiness check, security configuration gates, PostgreSQL dump/isolated-restore scripts, and GitHub Actions checks.

**Not deployed.** This is a release candidate only: production migration, TLS ingress, real backups, restore drills, and full regression tests are required before accepting live customer transactions. The original `docker-compose.yml` is legacy development infrastructure (references `./backend` and development passwords); never use it for production.

## Before deploying

1. Use a host with Docker Engine and Compose, restricted SSH/firewall, and an HTTPS reverse proxy. The application is deliberately bound only to `127.0.0.1:3000`. Do **not** expose that port publicly.
2. Run the branch test suite and CI workflow. Treat any failures as blockers; do not force deployment.
3. Create root `.env` from `.env.production.example` with *unique random* PostgreSQL credentials. This file supplies Compose substitution.
4. Configure `services/api/.env` with `DJANGO_DEBUG=0`, unique `DJANGO_SECRET_KEY` (at least 50 characters), `DJANGO_ALLOWED_HOSTS=api,<your-public-hostname>`, and `DJANGO_CSRF_TRUSTED_ORIGINS=https://<your-public-hostname>`. DB credentials are injected by Compose (and must match the root .env).
5. TLS must terminate at a **trusted reverse proxy** that removes untrusted incoming forwarding headers and sets `X-Forwarded-Proto: https` itself. Only then set `DJANGO_TRUST_PROXY_SSL_HEADER=1`. Ensure API traffic remains internal to Compose; Next.js rewrites proxy `/api/transactional/` to Django.
6. Confirm production Paystack provider credentials, reporting recipient allowlist and SMTP secrets are protected. Keep report emails **disabled** until approved and verified separately. Review Redis login-throttle availability and database cache table initialization.
7. **Back up your existing live database before any migration.** PostgreSQL 17 in the isolated Compose stack is not an automatic migration from an existing PostgreSQL 18 or earlier service: do not mount/adopt an existing database volume across incompatible major versions. Plan a proper PostgreSQL logical export/import and compatibility validation.

## Build and start (never before passing tests and backup)

From the repository root after approved configuration:

```bash
docker compose -f docker-compose.prod.yml config
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d db
docker compose -f docker-compose.prod.yml run --rm api /app/.venv/bin/python manage.py migrate --noinput
docker compose -f docker-compose.prod.yml run --rm api /app/.venv/bin/python manage.py createcachetable
docker compose -f docker-compose.prod.yml up -d api web
docker compose -f docker-compose.prod.yml ps
curl -fsS http://127.0.0.1:3000/
```

The API is also accessible inside the Compose network as `http://api:8000/api/transactional/health/ready/`; readiness returns HTTP 503 if the database query fails. A running container does **not** prove payment providers, mail delivery or external transactions work.

**Reminder:** the production API container installs `gunicorn==23.0.0` separately from the application `uv.lock`, and the frontend repo does not currently carry an npm package lockfile. Freeze both and introduce dependency vulnerability scanning before a high-assurance release. The CI workflow validates tests and builds but does **not** deploy or merge anything.

## Backup, restore, rollback

Back up PostgreSQL to a private off-host encrypted destination:

```bash
bash scripts/backup-postgres-prod.sh
```

The script creates `backups/tokad-<UTC timestamp>.dump` using `pg_dump -Fc`. Check file permissions, encrypted off-site copies, retention, and monitoring. Do not commit or upload backups to GitHub.

Verify a backup in a **new temporary database** without modifying the live DB:

```bash
bash scripts/verify-postgres-restore.sh backups/tokad-<UTC timestamp>.dump
```

This restores to an isolated temporary database using `pg_restore --exit-on-error`, checks the Django migrations table and deletes that temporary DB. It **does not** constitute a full transaction-level recovery test; additionally verify sample sales, stock, receipt and ledger records manually in a staging environment.

For rollback: stop application writes, take a fresh logical backup, restore the preceding *application image* only if database schema compatibility is proven, or restore a known-good database backup into a **separate** database and validate it before cutting over. Never assume Django reverse migrations are safe for financial transactions. Keep immutable release tags and image digests after CI passes.

## CI and release gates

GitHub Actions: `.github/workflows/production-readiness.yml` uses PostgreSQL 17, Python 3.13 + uv for Django checks and the full transactional pytest suite, and Node 22 for `npm run build`. No production deploy job is installed.

Local validation:

```bash
git status --short
git pull --ff-only origin feat/transactional-concurrency
cd services/api
uv sync --extra dev
uv run python manage.py check
uv run python manage.py makemigrations --check --dry-run
uv run python -m pytest -q --reuse-db --create-db transactional/tests/test_production_readiness.py
uv run python -m pytest -q --reuse-db transactional/
cd ../..
npm install
npm run build
```

For a configured staging environment also run `python manage.py check --deploy` with `DJANGO_DEBUG=0` and the correct domain and secure-proxy values. Review warnings instead of suppressing them blindly.

### Follow-up security/operations work

- Configure a real HTTPS ingress, rate limits, monitoring/alerts and reverse-proxy log retention.
- Add S3-compatible encrypted/off-site backup upload, backup age alerts, automated restore drills, and documented recovery time/recovery point objectives.
- Pin all dependency and container image digests with vulnerability scans; establish a signed immutable release artifact.
- Test concurrent transactions, refund/webhook idempotency, worker failover, access-control boundaries and cashier closing on staging.
- Set up a secrets manager, audit log export, privacy/retention policy, and incident response contacts.

**Release status:** Code committed to the feature branch. No containers, backups, restore drills, production migrations, deployment, CI runs, or automated tests were executed by this GitHub editing workflow.
