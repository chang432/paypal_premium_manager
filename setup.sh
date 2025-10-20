#!/usr/bin/env bash
set -euo pipefail

# setup.sh - entrypoint to run the application with a specific env file
# Usage:
#   ./setup.sh /path/to/.env
# Notes:
#   - First arg: path to the env file to use (passed via SRC_ENV_PATH to compose and app)
#   - This script will call start-docker.sh under the hood.

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <env-file-path>" >&2
  exit 1
fi

ENV_PATH="$1"

if [[ ! -f "$ENV_PATH" ]]; then
  echo "ERROR: Env file not found at: $ENV_PATH" >&2
  exit 1
fi

export SRC_ENV_PATH="$ENV_PATH"

# Helpful message
echo "> Using env file: $SRC_ENV_PATH"

# Start services (build if needed and tail logs)
"$(dirname "$0")/start-docker.sh" --rebuild --logs
