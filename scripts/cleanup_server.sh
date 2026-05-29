#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-/opt/xml_conciliador}"
PYTHON_BIN="${PYTHON_BIN:-$PROJECT_DIR/.venv/bin/python}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "ERROR: no se encontro el interprete Python en $PYTHON_BIN"
  exit 1
fi

cd "$PROJECT_DIR"

# Para este job en Debian dejamos ambas retenciones en 15 dias salvo override.
export PROCESSED_ZIP_RETENTION_DAYS="${PROCESSED_ZIP_RETENTION_DAYS:-15}"
export RECONCILIATION_CACHE_RETENTION_DAYS="${RECONCILIATION_CACHE_RETENTION_DAYS:-15}"

"$PYTHON_BIN" -m backend.app.cleanup_processed_archives
