#!/usr/bin/env bash
set -euo pipefail

# Defaults
: "${UVICORN_HOST:=0.0.0.0}"
: "${UVICORN_PORT_HTTP:=8080}"
: "${UVICORN_PORT_HTTPS:=8443}"
: "${UVICORN_WORKERS:=2}"
: "${ENABLE_TLS:=}"
: "${SSL_CERTFILE:=}"
: "${SSL_KEYFILE:=}"

exec_uvicorn() {
  echo "> Starting Uvicorn: $*"
  # If running as root, drop to appuser for Uvicorn
  if [ "$(id -u)" = "0" ]; then
    # shellcheck disable=SC2016
    CMD_STR="uvicorn app.main:app $*"
    exec su -s /bin/sh -c "$CMD_STR" appuser
  else
    exec uvicorn app.main:app "$@"
  fi
}

if [[ -n "${ENABLE_TLS}" ]] && [[ -n "${SSL_CERTFILE}" ]] && [[ -n "${SSL_KEYFILE}" ]] \
   && [[ -f "${SSL_CERTFILE}" ]] && [[ -f "${SSL_KEYFILE}" ]]; then
  # HTTPS mode
  exec_uvicorn \
    --host "${UVICORN_HOST}" \
    --port "${UVICORN_PORT_HTTPS}" \
    --workers "${UVICORN_WORKERS}" \
    --log-level info \
    --ssl-certfile "${SSL_CERTFILE}" \
    --ssl-keyfile "${SSL_KEYFILE}"
else
  echo "> TLS disabled or cert files not found; starting HTTP only."
  exec_uvicorn \
    --host "${UVICORN_HOST}" \
    --port "${UVICORN_PORT_HTTP}" \
    --workers "${UVICORN_WORKERS}" \
    --log-level info
fi
