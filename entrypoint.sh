#!/usr/bin/env bash
set -euo pipefail

# Defaults
: "${UVICORN_HOST:=0.0.0.0}"
: "${UVICORN_PORT_HTTP:=8080}"
: "${UVICORN_WORKERS:=2}"

exec_uvicorn() {
  echo "> Starting Uvicorn: $*"
  # If running as root, drop to appuser for Uvicorn
  if [ "$(id -u)" = "0" ]; then
    # shellcheck disable=SC2016
    CMD_STR="uvicorn app.main:app $*"
    exec su -m -s /bin/sh -c "$CMD_STR" appuser
  else
    exec uvicorn app.main:app "$@"
  fi
}

echo "> Starting HTTP on ${UVICORN_HOST}:${UVICORN_PORT_HTTP} via Uvicorn (TLS terminated by Nginx)."
exec_uvicorn \
  --host "${UVICORN_HOST}" \
  --port "${UVICORN_PORT_HTTP}" \
  --workers "${UVICORN_WORKERS}" \
  --log-level info
