# Tokad Mart outbox worker deployment

This directory packages the transactional outbox worker for production. The worker is the continuous Django management command:

```bash
uv run python manage.py run_outbox_worker
```

The repository also keeps the one-shot recovery command:

```bash
uv run python manage.py dispatch_outbox_events
```

## Docker

Build from `services/api` so the Dockerfile and lockfile are in the build context:

```bash
docker build -f Dockerfile.outbox-worker -t tokad-mart-outbox-worker .
```

Run with runtime configuration supplied from the host. Do not copy `.env` into the image:

```bash
docker run --rm \
  --name tokad-mart-outbox-worker \
  --restart unless-stopped \
  --env-file /etc/tokad-mart/api.env \
  tokad-mart-outbox-worker
```

The image uses `SIGTERM` for shutdown. The worker handles `SIGTERM` and `SIGINT` and exits cleanly. The image also exposes a Docker `HEALTHCHECK` that runs `check_outbox_health --strict` against the configured database.

## systemd

The supplied unit assumes this deployment layout:

```text
/opt/tokad-mart/services/api/
/etc/tokad-mart/api.env
```

Create the service account and environment file with appropriate permissions. The environment file should contain the normal Django/database settings and the Paystack configuration required by the worker, for example:

```dotenv
DJANGO_SECRET_KEY=<django-secret>
DJANGO_DEBUG=0
DJANGO_ALLOWED_HOSTS=...
POSTGRES_DB=tokad_mart
POSTGRES_USER=postgres
POSTGRES_PASSWORD=<database-password>
POSTGRES_HOST=...
POSTGRES_PORT=5432
PAYSTACK_SECRET_KEY=<paystack-secret>
```

Install and enable the unit:

```bash
sudo install -m 0644 deploy/systemd/tokad-mart-outbox-worker.service /etc/systemd/system/tokad-mart-outbox-worker.service
sudo systemctl daemon-reload
sudo systemctl enable --now tokad-mart-outbox-worker
```

Check status and logs:

```bash
sudo systemctl status tokad-mart-outbox-worker --no-pager
sudo journalctl -u tokad-mart-outbox-worker -f
```

The unit uses `Restart=on-failure`, so a normal `SIGTERM` shutdown is not immediately restarted, while unexpected worker failures are restarted after a short delay. The service also uses basic systemd hardening such as `NoNewPrivileges`, `PrivateTmp`, `ProtectSystem=strict`, and `ProtectHome`.

## Operational contract

The continuous worker is intended to run as one long-lived process per deployment instance. Multiple worker instances are safe because the outbox dispatcher claims rows with transactional row locks and `skip_locked` semantics.

The worker defaults are:

```text
poll interval: 2 seconds
batch size:    20
lease:         60 seconds
```

Override them when needed:

```bash
uv run python manage.py run_outbox_worker \
  --poll-interval 5 \
  --limit 50 \
  --lease-seconds 120
```

For manual recovery or debugging, run one cycle instead of starting a long-lived worker:

```bash
uv run python manage.py run_outbox_worker --once
```

## Health and observability

The worker exposes an operational health snapshot through:

```bash
uv run python manage.py check_outbox_health
```

The command reports:

```text
queue_depth
pending_ready
retryable_ready
processing
stale_processing
oldest_ready_at
oldest_ready_age_seconds
database_reachable
ready
healthy
```

Use strict mode for container or service supervision:

```bash
uv run python manage.py check_outbox_health --strict
```

Strict mode exits non-zero when the database is unreachable or stale processing work is detected. A non-empty retryable queue is observable through the snapshot without making the worker itself unready.

The continuous worker emits a structured heartbeat after every dispatch cycle containing cycle counters, cumulative completion/failure counts, queue depth, retryable work, stale leases, oldest ready age, database reachability, and overall health. Logs must not include payment secrets or full event payloads.

## Release checklist

Before deploying a new worker image or service version:

```bash
uv run python manage.py migrate
uv run python manage.py makemigrations --check --dry-run
uv run pytest -q transactional/
git diff --check
```

The worker does not replace webhook processing. Paystack webhooks remain the authoritative asynchronous confirmation path for successful payments; the outbox worker is responsible for durable provider-side initiation and refund operations.
