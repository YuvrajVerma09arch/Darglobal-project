#!/usr/bin/env bash
# Minimal end-to-end API smoke test: health, sources, stats, properties, chat.
# Usage: API_BASE_URL=https://my-backend.onrender.com ./scripts/smoke_test.sh
set -uo pipefail

BASE_URL="${API_BASE_URL:-http://localhost:8000}"
BASE_URL="${BASE_URL%/}"
FAILED=0
LAST_BODY=""

show_json() {
  if command -v python3 >/dev/null 2>&1; then
    echo "$1" | python3 -m json.tool 2>/dev/null || echo "$1"
  else
    echo "$1"
  fi
}

request() {
  local label="$1" url="$2"
  shift 2
  local response code body
  echo
  echo "=== $label: $url ==="
  if ! response="$(curl -sS --max-time 60 "$@" -w $'\n%{http_code}' "$url")"; then
    echo "REQUEST FAILED (connection error)" >&2
    FAILED=1
    LAST_BODY=""
    return 0
  fi
  code="${response##*$'\n'}"
  body="${response%$'\n'*}"
  LAST_BODY="$body"
  show_json "$body"
  echo "HTTP $code"
  if [[ ! "$code" =~ ^2 ]]; then
    FAILED=1
  fi
}

request "health" "$BASE_URL/health"
request "sources" "$BASE_URL/api/v1/sources"
request "stats" "$BASE_URL/api/v1/stats"
request "properties" "$BASE_URL/api/v1/properties?limit=3"

CHAT_PAYLOAD='{"message":"Show me 3 bedroom apartments in Riyadh under 2 million SAR","conversation_id":"smoke-test-001","source_filter":"both","filters":{"location":null,"city":null,"property_type":null,"listing_type":null,"min_price":null,"max_price":null,"bedrooms":null,"bathrooms":null},"stream":false}'
request "chat" "$BASE_URL/api/v1/chat" \
  -X POST \
  -H 'Content-Type: application/json' \
  -d "$CHAT_PAYLOAD"

if [[ -n "$LAST_BODY" ]] && command -v python3 >/dev/null 2>&1; then
  echo
  echo "=== citation summary ==="
  echo "$LAST_BODY" | python3 -c '
import json, sys
try:
    data = json.load(sys.stdin)
except Exception:
    print("(chat response was not JSON)")
    raise SystemExit(0)
cites = data.get("citations") or []
print("citations:", len(cites))
for c in cites[:5]:
    print(" -", c.get("source"), "|", c.get("title"), "|", c.get("url"))
print("answer (first 200 chars):", (data.get("answer") or "")[:200])
' || true
fi

echo
if [[ "$FAILED" -ne 0 ]]; then
  echo "SMOKE TEST FAILED — see the non-2xx / connection error above." >&2
  echo "Common causes: backend still warming up, LLM_API_KEY missing (chat), or no ingestion yet." >&2
  exit 1
fi
echo "SMOKE TEST PASSED"
