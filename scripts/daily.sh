#!/usr/bin/env bash
# Ejecuta la búsqueda diaria en local, igual que el workflow de GitHub Actions.
#
# Uso:
#   scripts/daily.sh              # búsqueda real y HTML en public/index.html
#   scripts/daily.sh --demo       # datos de ejemplo, sin internet
#   scripts/daily.sh --debug      # log de extracción por página
#
# Variables opcionales:
#   DISKSEARCH_VENV  ruta del entorno virtual (por defecto ~/.venvs/disk-search)
#   DISKSEARCH_DB    ruta del SQLite (por defecto .cache/disk-search/history.sqlite3)
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="${DISKSEARCH_VENV:-$HOME/.venvs/disk-search}"
PYTHON="$VENV/bin/python"

cd "$ROOT"

if [[ ! -x "$PYTHON" ]]; then
  echo "Creando entorno virtual en $VENV"
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install --upgrade pip
  "$VENV/bin/pip" install -r requirements.txt
  "$PYTHON" -m playwright install chromium
fi

if ! "$PYTHON" -c "import requests, bs4, playwright" >/dev/null 2>&1; then
  echo "Instalando dependencias de Python"
  "$VENV/bin/pip" install -r requirements.txt
fi

# Es idempotente: no descarga Chromium si ya está instalado.
"$PYTHON" -m playwright install chromium >/dev/null

mkdir -p .cache/disk-search public
DISKSEARCH_DB="${DISKSEARCH_DB:-$ROOT/.cache/disk-search/history.sqlite3}" \
  "$PYTHON" nas_discos.py --once "$@"

cp nas_discos.html public/index.html
echo "OK: resultado en $ROOT/public/index.html"
