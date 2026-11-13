"""Servidor HTTP local y API del histórico."""
from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlsplit

from . import config
from .history import create_store
from .search import demo_dataset, run_search
from .ui import history_snapshot, render_html

STATE = {
    "running": False,
    "progress": 0.0,
    "label": "",
    "data": None,
    "error": "",
    "history_error": "",
    "last": 0.0,
    "stores": {},
}
LOCK = threading.Lock()


def empty_data():
    return {
        "meta": {"time": "—", "pages": 0, "raw": 0, "unique": 0, "shown": 0, "sources": []},
        "items": [],
        "highlights": {},
    }


def worker(demo, debug, store):
    try:
        def progress(value, label, store_name=None, info=None):
            STATE.update(progress=value, label=label)
            if store_name:
                entry = STATE["stores"].setdefault(
                    store_name, {"state": "buscando", "results": None}
                )
                if info:
                    entry.update(info)
                else:
                    entry["state"] = "buscando"

        if demo:
            # simulación de progreso por tienda para la demo
            for name in ("PCComponentes", "Coolmod", "Alternate", "Amazon"):
                STATE["stores"][name] = {"state": "buscando", "results": None}
                time.sleep(0.6)
                STATE["stores"][name] = {"state": "ok", "results": 30}
            time.sleep(1)
            data = demo_dataset()
        else:
            data = run_search(progress, debug)
        try:
            store.record_search(data)
            STATE["history_error"] = ""
        except Exception as exc:
            STATE["history_error"] = f"histórico: {str(exc)[:120]}"
        STATE.update(
            data=data,
            error="" if data["items"] else (
                "No se extrajo ningún disco. Ejecuta con --debug y revisa SOURCES."
            ),
        )
    except Exception as exc:
        STATE["error"] = str(exc)
    finally:
        STATE.update(running=False, progress=1.0, last=time.time())


def start(demo, debug, store):
    with LOCK:
        wait = config.COOLDOWN - (time.time() - STATE["last"])
        if STATE["running"] or wait > 0:
            return False, max(0, int(wait))
        STATE.update(running=True, progress=0.0, label="", error="", history_error="", stores={})
    threading.Thread(target=worker, args=(demo, debug, store), daemon=True).start()
    return True, 0


def make_handler(demo, debug, store):
    class Handler(BaseHTTPRequestHandler):
        server_version = "DiskSearch/2.0"

        def _send(self, code, body, ctype="application/json; charset=utf-8"):
            raw = body.encode() if isinstance(body, str) else body
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(raw)

        def _json(self, code, payload):
            self._send(code, json.dumps(payload, ensure_ascii=False))

        def _status(self):
            cooldown = (
                max(0, int(config.COOLDOWN - (time.time() - STATE["last"])))
                if STATE["last"] else 0
            )
            return {
                key: STATE[key]
                for key in ("running", "progress", "label", "error", "history_error", "stores")
            } | {"cooldown": cooldown}

        def _read_json(self):
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                return {}
            if length <= 0 or length > 1_048_576:
                return {}
            try:
                return json.loads(self.rfile.read(length).decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                return {}

        def do_GET(self):
            path = urlsplit(self.path).path
            query = parse_qs(urlsplit(self.path).query)
            try:
                if path == "/api/status":
                    self._json(200, self._status())
                elif path == "/api/data":
                    data = dict(STATE["data"] or empty_data())
                    data["favorites"] = store.favorites()
                    self._json(200, data)
                elif path == "/api/history":
                    listing = store.list_products(
                        favorites=query.get("favorites", ["0"])[0] in ("1", "true", "yes"),
                        q=query.get("q", [""])[0],
                        status=query.get("status", [""])[0],
                        limit=query.get("limit", ["25"])[0],
                        offset=query.get("offset", ["0"])[0],
                        sort=query.get("sort", ["last_seen"])[0],
                        direction=query.get("direction", ["desc"])[0],
                        kind=query.get("kind", [""])[0],
                    )
                    listing["favorites"] = store.favorites()
                    self._json(200, listing)
                elif path.startswith("/api/history/"):
                    key = unquote(path[len("/api/history/"):])
                    detail = store.get_product(key)
                    self._json(200 if detail else 404, detail or {"error": "no encontrado"})
                elif path == "/api/notifications":
                    self._json(200, {"items": store.notifications()})
                elif path == "/api/stats":
                    self._json(200, store.stats())
                elif path == "/api/searches":
                    self._json(200, {"items": store.recent_searches()})
                elif path == "/api/series":
                    self._json(200, {"series": store.price_series()})
                elif path in ("/", "/index.html"):
                    html = render_html(
                        STATE["data"], True, history_snapshot(store)
                    )
                    self._send(200, html, "text/html; charset=utf-8")
                else:
                    self._json(404, {"error": "no encontrado"})
            except Exception as exc:
                self._json(500, {"error": str(exc)[:200]})

        def do_POST(self):
            path = urlsplit(self.path).path
            try:
                if path == "/api/refresh":
                    ok, wait = start(demo, debug, store)
                    self._json(200 if ok else 429, {"started": ok, "cooldown": wait})
                elif path == "/api/favorites":
                    payload = self._read_json()
                    key = payload.get("key")
                    if not isinstance(key, str) or not key:
                        self._json(400, {"error": "key requerida"})
                    else:
                        ok = store.set_favorite(key, bool(payload.get("favorite")))
                        self._json(200 if ok else 404, {"ok": ok})
                elif path == "/api/notifications/dismiss":
                    payload = self._read_json()
                    try:
                        notification_id = int(payload.get("id"))
                    except (TypeError, ValueError):
                        self._json(400, {"error": "id requerido"})
                    else:
                        ok = store.dismiss_notification(notification_id)
                        self._json(200 if ok else 404, {"ok": ok})
                else:
                    self._json(404, {"error": "no encontrado"})
            except Exception as exc:
                self._json(500, {"error": str(exc)[:200]})

        def log_message(self, *args):
            pass

    return Handler


def serve(demo, debug, store, port=None, open_browser=True):
    server = ThreadingHTTPServer(
        ("127.0.0.1", port or config.PORT), make_handler(demo, debug, store)
    )
    print(f"Abre http://localhost:{server.server_port}  (Ctrl+C para salir)")
    if open_browser:
        import webbrowser
        webbrowser.open(f"http://localhost:{server.server_port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def build_store(demo=False, path=None):
    if demo and not path:
        import os
        if not os.environ.get("DISKSEARCH_DB"):
            return create_store(":memory:")
    return create_store(path)
