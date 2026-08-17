# Local PostgreSQL in Docker

This setup moves the local Tokad Mart PostgreSQL service from a host systemd installation to Docker while keeping the Django API on the host machine.

## Runtime model

```text
Django API (host)
       |
       | localhost:5432
       v
PostgreSQL 18.4 (Docker)
       |
       v
Named volume: tokad_postgres_data
```

The API keeps using:

```dotenv
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
```

When the API and worker are later placed in the same Compose project, switch their database host to the Compose service name:

```dotenv
POSTGRES_HOST=postgres
```

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

Then verify:

```bash
uv run python manage.py check
uv run pytest -q transactional/
```

## Moving existing host data

Do not delete the existing host PostgreSQL database before taking a backup.

Create a logical dump from the old host database first:

```bash
pg_dump \
  --host=localhost \
  --port=5432 \
  --username=postgres \
  --format=custom \
  --file=tokad_mart_before_docker.dump \
  tokad_mart
```

Start the Docker database:

```bash
docker compose up -d postgres
```

After the container is healthy, restore the dump into the Docker database. Example:

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

For a fresh development database, it is simpler to let Django migrations create the schema instead of restoring old data.

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

From another container on the Compose network later, use `postgres:5432` rather than `localhost:5432`.
