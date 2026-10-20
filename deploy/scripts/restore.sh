#!/bin/sh
set -eu

if [ "$#" -ne 1 ] || [ ! -s "$1" ]; then
  echo "Usage: $0 <non-empty-backup.dump>" >&2
  exit 2
fi

backup="$1"
database_name="$(docker compose --env-file deploy/.env -f deploy/compose.yaml exec -T postgres sh -c 'printf %s "$POSTGRES_DB"')"
echo "This replaces all data in database '$database_name'."
printf "Type RESTORE %s: " "$database_name"
read -r confirmation
test "$confirmation" = "RESTORE $database_name"

docker compose --env-file deploy/.env -f deploy/compose.yaml stop api worker beat
docker compose --env-file deploy/.env -f deploy/compose.yaml exec -T postgres \
  sh -c 'dropdb --if-exists --force --username "$POSTGRES_USER" "$POSTGRES_DB"'
docker compose --env-file deploy/.env -f deploy/compose.yaml exec -T postgres \
  sh -c 'createdb --username "$POSTGRES_USER" "$POSTGRES_DB"'
docker compose --env-file deploy/.env -f deploy/compose.yaml exec -T postgres \
  sh -c 'pg_restore --exit-on-error --no-owner --username "$POSTGRES_USER" --dbname "$POSTGRES_DB"' \
  < "$backup"
docker compose --env-file deploy/.env -f deploy/compose.yaml up -d api worker beat frontend caddy
