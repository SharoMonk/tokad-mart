#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ $# -ne 1 || ! -f "$1" ]]; then
  echo "Usage: bash scripts/verify-postgres-restore.sh path/to/backup.dump" >&2
  exit 2
fi
backup="$(realpath "$1")"
# Never restore into the live application DB.
db="tokad_restore_check_$(date +%s)_$$"
cleanup() {
  docker compose -f docker-compose.prod.yml exec -T db sh -ec \
    'export PGPASSWORD="$POSTGRES_PASSWORD"; dropdb --if-exists --force -U "$POSTGRES_USER" "$1"' -- "$db" >/dev/null 2>&1 || true
}
trap cleanup EXIT
docker compose -f docker-compose.prod.yml exec -T db sh -ec \
  'export PGPASSWORD="$POSTGRES_PASSWORD"; createdb -U "$POSTGRES_USER" "$1"' -- "$db"
docker compose -f docker-compose.prod.yml exec -T db sh -ec \
  'export PGPASSWORD="$POSTGRES_PASSWORD"; exec pg_restore -U "$POSTGRES_USER" -d "$1" --exit-on-error --no-owner --no-acl' -- "$db" < "$backup"
docker compose -f docker-compose.prod.yml exec -T db sh -ec \
  'export PGPASSWORD="$POSTGRES_PASSWORD"; psql -U "$POSTGRES_USER" -d "$1" -Atc "SELECT COUNT(*) FROM django_migrations"' -- "$db"
echo "Restore check succeeded in isolated temporary database $db"
