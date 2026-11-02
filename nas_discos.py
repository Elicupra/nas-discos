#!/usr/bin/env python3
"""nas_discos.py - Buscador de discos duros internos en tiendas españolas.

Uso:
  pip install -r requirements.txt && playwright install chromium
  python nas_discos.py              # servidor en http://localhost:8765
  python nas_discos.py --once       # busca una vez y escribe nas_discos.html
  python nas_discos.py --demo       # datos de ejemplo, sin tocar internet
  python nas_discos.py --debug      # muestra qué extrae de cada página
  python nas_discos.py --headed     # navegador visible si hay captcha
  python nas_discos.py --db ruta.sqlite3

El histórico se guarda en SQLite (por defecto data/history.sqlite3).
"""
from __future__ import annotations

import argparse
import sys

from disksearch import config
from disksearch.extractors import (  # noqa: F401 - compatibilidad con imports antiguos
    extract_alternate, extract_amazon, extract_coolmod, extract_products,
    extract_vtex,
)
from disksearch.parsing import parse_price, parse_spec, product_key  # noqa: F401
from disksearch.search import (  # noqa: F401
    build_dataset, demo_dataset, highlights, run_search,
)
from disksearch.server import build_store, serve
from disksearch.ui import history_snapshot, render_html


def main():
    parser = argparse.ArgumentParser(
        description="Buscador local de discos duros internos en tiendas españolas."
    )
    parser.add_argument("--once", action="store_true", help="genera nas_discos.html y sale")
    parser.add_argument("--demo", action="store_true", help="datos de ejemplo")
    parser.add_argument("--debug", action="store_true", help="log de extracción por página")
    parser.add_argument("--headed", action="store_true", help="navegador visible (anti-bot)")
    parser.add_argument("--no-open", action="store_true", help="no abrir el navegador")
    parser.add_argument("--db", help="ruta de la base SQLite del histórico")
    parser.add_argument("--port", type=int, default=None, help=f"puerto (por defecto {config.PORT})")
    args = parser.parse_args()

    config.HEADED = args.headed
    store = build_store(demo=args.demo, path=args.db)

    if args.once:
        try:
            data = demo_dataset() if args.demo else run_search(
                lambda p, label: print(f"{p:4.0%} {label}", file=sys.stderr),
                args.debug,
            )
            try:
                store.record_search(data)
            except Exception as exc:
                print(f"AVISO: no se pudo guardar el histórico: {exc}", file=sys.stderr)
            html = render_html(data, False, history_snapshot(store, limit=200))
            with open("nas_discos.html", "w", encoding="utf-8") as output:
                output.write(html)
            print(f"OK: nas_discos.html ({data['meta']['unique']} discos distintos)")
        finally:
            store.close()
        return

    try:
        serve(args.demo, args.debug, store, port=args.port, open_browser=not args.no_open)
    finally:
        store.close()


if __name__ == "__main__":
    main()
