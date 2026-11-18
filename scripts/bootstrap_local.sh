#!/usr/bin/env bash
# Create a local .env from .env.example with freshly generated secrets.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/.env"
EXAMPLE_FILE="$ROOT_DIR/.env.example"

command -v python3 >/dev/null 2>&1 || {
  echo "python3 is required to generate secrets and update .env" >&2
  exit 1
}

if [[ ! -f "$EXAMPLE_FILE" ]]; then
  echo "Missing $EXAMPLE_FILE" >&2
  exit 1
fi

if [[ -f "$ENV_FILE" ]]; then
  echo "Refusing to overwrite existing $ENV_FILE — edit it manually instead." >&2
  exit 1
fi

generate_secret() {
  python3 -c 'import secrets; print(secrets.token_urlsafe(32))'
}

ADMIN_KEY="$(generate_secret)"
DB_PASSWORD="$(generate_secret)"

cp "$EXAMPLE_FILE" "$ENV_FILE"

python3 - "$ENV_FILE" "$ADMIN_KEY" "$DB_PASSWORD" <<'PY'
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
admin_key, db_password = sys.argv[2], sys.argv[3]
text = path.read_text()
text = text.replace(
    "ADMIN_API_KEY=replace-with-a-long-random-value",
    f"ADMIN_API_KEY={admin_key}",
)
text = text.replace("POSTGRES_PASSWORD=change-me", f"POSTGRES_PASSWORD={db_password}")
text = text.replace("darglobal:change-me@", f"darglobal:{db_password}@")
if "VITE_API_BASE_URL=" not in text:
    text += (
        "\n# Build-time API base URL baked into the frontend bundle.\n"
        "VITE_API_BASE_URL=http://localhost:8000\n"
    )
path.write_text(text)
PY

chmod 600 "$ENV_FILE"

cat <<'EOF'

Created .env with a generated ADMIN_API_KEY and POSTGRES_PASSWORD (mode 600).

Next steps:
  1. Edit .env and set LLM_API_KEY to your OpenRouter key
     (retrieval/search/stats work without it; chat does not).
  2. Start the stack:
       docker compose up --build -d
  3. Wait for health, then run initial ingestion:
       ./scripts/ingest.sh
  4. Smoke-test the API:
       ./scripts/smoke_test.sh
  5. Open the frontend at http://localhost:8080

Never commit .env. Rotate ADMIN_API_KEY before exposing the backend publicly.
EOF
