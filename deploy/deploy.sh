#!/usr/bin/env bash
#
# Pull, rebuild and restart the production stack.
#
#   ./deploy/deploy.sh
#
# Safe to re-run: the api service applies `alembic upgrade head` on start
# (RUN_MIGRATIONS=1), and every service declares `restart: unless-stopped`.
set -euo pipefail

cd "$(dirname "$0")/.."

COMPOSE_FILE=docker-compose.prod.yml
compose() { docker compose -f "$COMPOSE_FILE" "$@"; }

if [ ! -f .env ]; then
  echo "deploy: .env is missing." >&2
  echo "        cp deploy/env.prod.example .env  &&  edit it" >&2
  exit 1
fi

# data/historical is gitignored, so a fresh clone has no datasets. Without it
# seeding and backtests report DATA_UNAVAILABLE rather than crashing, which is
# easy to mistake for a broken deployment.
if [ ! -d data/historical ]; then
  echo "deploy: WARNING: data/historical is missing from this checkout." >&2
  echo "        Copy it from your development machine, e.g." >&2
  echo "          rsync -av --delete data/ user@host:$(pwd)/data/" >&2
fi

echo "==> git pull"
git pull --ff-only

echo "==> build"
compose build

echo "==> up"
compose up -d

echo "==> status"
compose ps

echo "==> alembic revision"
compose exec -T api alembic current

echo
echo "API health:  curl -fsS https://\${DOMAIN:-<DOMAIN>}/health"
echo "Logs:        docker compose -f $COMPOSE_FILE logs -f api"
