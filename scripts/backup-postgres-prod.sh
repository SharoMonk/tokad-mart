#!/usr/bin/env bash
set -euo pipefail
umask 077
cd "$(dirname "$0")/.."
BACKUP_DIR="${BACKUP_DIR:-./backups}"
mkdir -p "$BACKUP_DIR"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
file="$BACKUP_DIR/tokad-$timestamp.dump"
tmp="$file.partial"
trap 'rm -f "$tmp"' EXIT
docker compose -f docker-compose.prod.yml exec -T db sh -ec \
  'export PGPASSWORD="$POSTGRES_PASSWORD"; exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom --no-owner --no-acl' > "$tmp"
test -s "$tmp"
mv "$tmp" "$file"
trap - EXIT
echo "Backup written to: $file"
echo "Backups must be encrypted, stored off-host, and periodically restore-tested."
