# Local PostgreSQL in Docker

This setup runs the local Tokad Mart PostgreSQL service in Docker and supports running the Django API and transactional outbox worker in the same Compose network.

## Runtime model

```text
                         Compose network
              ┌───────────────────────────────┐
              │                               │
              │  API ───────────────┐         │
              │                     │         │
              │  Outbox worker ─────┼──> postgres:5432
              │                     │         │
              │  PostgreSQL 18.4 <──┘         │
              │       │                       │
              │       v                       │
              │  tokad_postgres_data          │
              └───────────────────────────────┘
                         │
                         │ published port
                         v
                    host :5432
```

The host-side Django process can continue using:

```dotenv
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
```

Containers in the Compose project use the service hostname automatically:

```dotenv
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
```

The Compose configuration overrides those two variables for the `api` and `outbox-worker` services, so the same `.env` file can be used by both host-side development and containerized services.

## Start the database

From `services/api`:

```bash
docker compose up -d postgres
```

Check readiness:

```bash
docker compose ps
```

Or:

```bash
docker inspect --format='{{.State.Health.Status}}' tokad-postgres
```

The PostgreSQL container uses the named volume `tokad_postgres_data` mounted at `/var/lib/postgresql`. PostgreSQL 18 and newer official images use that mount point and a version-specific `PGDATA` under it. See the official image documentation before changing the PostgreSQL major version. (https://hub.docker.com/_/postgres)

## Start API, worker, and database together

From `services/api`:

```bash
docker compose up -d postgres api outbox-worker
```

The API is exposed on host port `8000` by default:

```text
http://127.0.0.1:8000
```

The outbox worker connects to PostgreSQL through the Compose network rather than using host networking.

Inspect all services:

```bash
docker compose ps
```

Follow worker logs:

```bash
docker compose logs -f outbox-worker
```

Follow API logs:

```bash
docker compose logs -f api
```

## First-time initialization

The official image initializes the database using:

```dotenv
POSTGRES_DB
POSTGRES_USER
POSTGRES_PASSWORD
```

These values are read only when the volume is initialized. Changing them later does not recreate an existing database.

## Migrate the Django schema

With PostgreSQL healthy:

```bash
uv run python manage.py migrate
```

Or, against the containerized API, run migrations from the API image:

```bash
docker compose run --rm api python manage.py migrate
```

Then verify locally:

```bash
uv run python manage.py check
uv run pytest -q transactional/
```

## Moving existing data

Do not delete an existing PostgreSQL database before taking a backup.

For a pre-Docker host database, create a logical dump first:

```bash
pg_dump \
  --host=localhost \
  --port=5432 \
  --username=postgres \
  --format=custom \
  --file=tokad_mart_before_docker.dump \
  tokad_mart
```

For an existing Docker PostgreSQL container/volume, inspect and preserve the volume before removing the old container. Do not use `docker rm -v` unless the database data has been backed up and the volume is intentionally disposable.

After the Docker database is healthy, a logical dump can be restored through the published host port:

```bash
pg_restore \
  --host=localhost \
  --port=5432 \
  --username=postgres \
  --dbname=tokad_mart \
  --clean \
  --if-exists \
  tokad_mart_before_docker.dump
```

## Persistence

The PostgreSQL container can be removed and recreated without deleting the database as long as the named volume is retained:

```bash
docker compose down
docker compose up -d postgres
```

Do **not** use:

```bash
docker compose down -v
```

unless you intentionally want to delete the Docker database volume.

A Docker named volume is not a backup. Keep separate backups for any data that matters.

## Connection checks

From the host:

```bash
PGPASSWORD="$POSTGRES_PASSWORD" psql \
  --host=localhost \
  --port=5432 \
  --username="$POSTGRES_USER" \
  --dbname="$POSTGRES_DB" \
  -c 'select version();'
```

From the API or outbox worker container, use:

```text
postgres:5432
```

not `localhost:5432`.
