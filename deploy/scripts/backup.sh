#!/bin/sh
set -eu

destination="${1:-./deploy/backups}"
mkdir -p "$destination"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
output="$destination/expertise_insight_$stamp.dump"

docker compose --env-file deploy/.env -f deploy/compose.yaml exec -T postgres \
  sh -c 'pg_dump --format=custom --no-owner --username "$POSTGRES_USER" --dbname "$POSTGRES_DB"' \
  > "$output"

test -s "$output"
echo "Backup created: $output"
