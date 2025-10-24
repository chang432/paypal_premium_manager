#!/usr/bin/env bash
set -euo pipefail

# Start docker compose at the repository root.
# Usage:
#   ./start-docker.sh             # build and start
#   ./start-docker.sh --no-build  # start without building
#   ./start-docker.sh --logs      # tail logs after starting
#   ./start-docker.sh --down      # stop and remove containers
#   ./start-docker.sh --rebuild   # force rebuild
#   ./start-docker.sh --help      # show help

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

COMPOSE_FILE="docker-compose.yml"
if [[ ! -f "$COMPOSE_FILE" ]]; then
  echo "ERROR: $COMPOSE_FILE not found in $SCRIPT_DIR" >&2
  exit 1
fi

# Pick compose command (Docker v20.10+ plugin preferred)
if docker compose version >/dev/null 2>&1; then
  DCMD=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  DCMD=(docker-compose)
else
  echo "ERROR: Neither 'docker compose' nor 'docker-compose' is available. Install Docker Desktop or docker-compose." >&2
  exit 1
fi

# Resolve env file path; allow SRC_ENV_PATH override
ENV_FILE_PATH="${SRC_ENV_PATH:-.env}"
if [[ ! -f "$ENV_FILE_PATH" ]]; then
  # If override provided but file missing, warn and fallback
  if [[ -n "${SRC_ENV_PATH:-}" ]]; then
    echo "WARN: SRC_ENV_PATH set to '$SRC_ENV_PATH' but file not found. Falling back to .env" >&2
  fi
  ENV_FILE_PATH=".env"
fi

show_help() {
  sed -n '2,20p' "$0"
}

BUILD=1
TAIL_LOGS=0
DO_DOWN=0
FORCE_REBUILD=0

for arg in "$@"; do
  case "$arg" in
    --no-build) BUILD=0 ;;
    --logs) TAIL_LOGS=1 ;;
    --down) DO_DOWN=1 ;;
    --rebuild) FORCE_REBUILD=1 ;;
    --help|-h) show_help; exit 0 ;;
    *) echo "Unknown option: $arg" >&2; show_help; exit 1 ;;
  esac
done

if [[ $DO_DOWN -eq 1 ]]; then
  echo "> Stopping and removing containers..."
  "${DCMD[@]}" --env-file "$ENV_FILE_PATH" down
  exit 0
fi

if [[ $FORCE_REBUILD -eq 1 ]]; then
  echo "> Forcing image rebuild..."
  "${DCMD[@]}" --env-file "$ENV_FILE_PATH" build --no-cache
fi

if [[ $BUILD -eq 1 && $FORCE_REBUILD -eq 0 ]]; then
  echo "> Building images (if needed)..."
  "${DCMD[@]}" --env-file "$ENV_FILE_PATH" build
fi

echo "> Starting services..."
"${DCMD[@]}" --env-file "$ENV_FILE_PATH" up -d

if [[ $TAIL_LOGS -eq 1 ]]; then
  echo "> Tailing logs. Press Ctrl+C to exit."
  "${DCMD[@]}" --env-file "$ENV_FILE_PATH" logs -f
else
  echo "> Done. Services should be running. Use 'docker compose ps' to verify."
fi
