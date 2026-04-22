#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-/opt/xml_conciliador}"
BACKEND_SERVICE="${BACKEND_SERVICE:-xml-conciliador-backend}"
WATCHER_SERVICE="${WATCHER_SERVICE:-xml-conciliador-watcher}"
NGINX_SERVICE="${NGINX_SERVICE:-nginx}"
WORKSPACE="${GITHUB_WORKSPACE:-$(pwd)}"

run_systemctl() {
  if command -v sudo >/dev/null 2>&1; then
    sudo systemctl "$@"
  else
    systemctl "$@"
  fi
}

echo "Deploying from workspace: $WORKSPACE"
echo "Target directory: $PROJECT_DIR"

if ! command -v rsync >/dev/null 2>&1; then
  echo "ERROR: rsync is required on the server."
  exit 1
fi

if [[ ! -x "$PROJECT_DIR/.venv/bin/python" ]]; then
  echo "ERROR: Python virtualenv not found in $PROJECT_DIR/.venv"
  exit 1
fi

mkdir -p "$PROJECT_DIR"

rsync -av --delete \
  --exclude '.git/' \
  --exclude '.github/' \
  --exclude '.venv/' \
  --exclude '.env' \
  --exclude 'frontend/.env' \
  --exclude 'frontend/.env.production' \
  --exclude 'frontend/node_modules/' \
  --exclude 'frontend/dist/' \
  --exclude 'cache/' \
  --exclude 'facturas_entrada/' \
  --exclude 'facturas_procesadas/' \
  --exclude 'logs/' \
  --exclude 'reportes_excel/' \
  --exclude 'backend_start_stdout.log' \
  --exclude 'backend_start_stderr.log' \
  "$WORKSPACE"/ "$PROJECT_DIR"/

"$PROJECT_DIR/.venv/bin/python" -m pip install --upgrade pip
"$PROJECT_DIR/.venv/bin/python" -m pip install -r "$PROJECT_DIR/backend/requirements.txt"

pushd "$PROJECT_DIR/frontend" >/dev/null
npm ci
npm run build
popd >/dev/null

run_systemctl restart "$BACKEND_SERVICE"

if run_systemctl list-unit-files | grep -q "^${WATCHER_SERVICE}\.service"; then
  run_systemctl restart "$WATCHER_SERVICE"
fi

run_systemctl reload "$NGINX_SERVICE"

echo "Deployment completed successfully."
