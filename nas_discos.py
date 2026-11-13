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
    _scope_summary, build_dataset, demo_dataset, highlights, run_search,
)
from disksearch.server import build_store, serve
from disksearch.ui import history_snapshot, render_history_html, render_html


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
    parser.add_argument("--historico-html", nargs="?", const="historico.html", default=None,
                        help="genera una página estática con el histórico y sale (opcional: ruta de salida)")
    parser.add_argument("--port", type=int, default=None, help=f"puerto (por defecto {config.PORT})")
    parser.add_argument("--kind", choices=("HDD", "SSD"), help="acota la búsqueda a un tipo")
    parser.add_argument("--store", action="append", default=None,
                        help="tienda a consultar (repetible); acota la búsqueda")
    parser.add_argument("--text", default="", help="texto a buscar en marca/modelo")
    args = parser.parse_args()

    config.HEADED = args.headed
    store = build_store(demo=args.demo, path=args.db)

    scope = {}
    if args.kind:
        scope["kind"] = args.kind
    if args.store:
        scope["stores"] = args.store
    if args.text:
        scope["text"] = args.text
    scope = scope or None

    if args.once:
        try:
            if args.demo:
                data = demo_dataset()
                if scope:
                    data["meta"]["partial"] = True
                    data["meta"]["scope"] = _scope_summary(scope)
                    if scope.get("kind"):
                        data["items"] = [
                            item for item in data["items"]
                            if item["kind"] == scope["kind"]
                        ]
                    if scope.get("stores"):
                        stores = set(scope["stores"])
                        data["items"] = [
                            item for item in data["items"]
                            if item.get("store") in stores
                        ]
                    data["meta"]["unique"] = data["meta"]["shown"] = len(data["items"])
            else:
                data = run_search(
                    lambda p, label: print(f"{p:4.0%} {label}", file=sys.stderr),
                    args.debug, scope=scope,
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

    if args.historico_html:
        try:
            html = render_history_html(store)
            with open(args.historico_html, "w", encoding="utf-8") as output:
                output.write(html)
            snapshot = history_snapshot(store, limit=200)
            print(f"OK: {args.historico_html} ({snapshot.get('total', 0)} modelos en el histórico)")
        finally:
            store.close()
        return

    try:
        serve(args.demo, args.debug, store, port=args.port, open_browser=not args.no_open)
    finally:
        store.close()


if __name__ == "__main__":
    main()
