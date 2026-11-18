#!/usr/bin/env bash
# Trigger admin ingestion. Reads ADMIN_API_KEY from .env without sourcing it
# (the scraper user-agent value contains spaces and parentheses).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT_DIR/.env}"
BASE_URL="${API_BASE_URL:-http://localhost:8000}"
SOURCE="${1:-both}"

command -v curl >/dev/null 2>&1 || { echo "curl is required" >&2; exit 1; }
[[ -f "$ENV_FILE" ]] || { echo "Missing $ENV_FILE (run scripts/bootstrap_local.sh)" >&2; exit 1; }

ADMIN_KEY="$(grep -E '^ADMIN_API_KEY=' "$ENV_FILE" | head -n1 | cut -d= -f2- | tr -d '\r')"
ADMIN_KEY="${ADMIN_KEY%\"}"; ADMIN_KEY="${ADMIN_KEY#\"}"
ADMIN_KEY="${ADMIN_KEY%\'}"; ADMIN_KEY="${ADMIN_KEY#\'}"

if [[ -z "$ADMIN_KEY" || "$ADMIN_KEY" == replace-with-* ]]; then
  echo "ADMIN_API_KEY is empty or still a placeholder in $ENV_FILE" >&2
  exit 1
fi

case "$SOURCE" in
  both|darglobal|wasalt) ;;
  *) echo "source must be one of: both, darglobal, wasalt" >&2; exit 1 ;;
esac

echo "POST $BASE_URL/api/v1/admin/ingest  (source=$SOURCE)"
RESPONSE="$(curl -sS --max-time 600 \
  -X POST "$BASE_URL/api/v1/admin/ingest" \
  -H "X-Admin-Key: $ADMIN_KEY" \
  -H 'Content-Type: application/json' \
  -d "{\"source\":\"$SOURCE\"}" \
  -w $'\n%{http_code}')"

CODE="${RESPONSE##*$'\n'}"
BODY="${RESPONSE%$'\n'*}"

if command -v python3 >/dev/null 2>&1; then
  echo "$BODY" | python3 -m json.tool 2>/dev/null || echo "$BODY"
else
  echo "$BODY"
fi

echo "HTTP $CODE"
if [[ ! "$CODE" =~ ^2 ]]; then
  echo "Ingestion failed. Check ADMIN_API_KEY, database connectivity and backend logs." >&2
  exit 1
fi
