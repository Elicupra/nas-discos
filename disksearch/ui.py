"""Composición del HTML (UI embebida y reutilizable)."""
from __future__ import annotations

import json
from pathlib import Path

WEB_DIR = Path(__file__).resolve().parent / "web"


def _json_for_script(value) -> str:
    return json.dumps(value, ensure_ascii=False).replace("</", "<\\/")


def history_snapshot(store, limit=25) -> dict:
    """Instantánea para el arranque y para el modo --once."""
    if store is None:
        return {"items": [], "total": 0, "stats": {}, "notifications": [], "favorites": [], "series": []}
    try:
        listing = store.list_products(limit=limit, offset=0, sort="last_seen", direction="desc")
        return {
            "items": listing.get("items", []),
            "total": listing.get("total", 0),
            "stats": store.stats(),
            "notifications": store.notifications(),
            "favorites": store.favorites(),
            "series": store.price_series(),
        }
    except Exception:
        return {"items": [], "total": 0, "stats": {}, "notifications": [], "favorites": [], "series": []}


def render_html(data, live, history=None) -> str:
    template = (WEB_DIR / "index.html").read_text(encoding="utf-8")
    css = (WEB_DIR / "styles.css").read_text(encoding="utf-8")
    js = (WEB_DIR / "app.js").read_text(encoding="utf-8")
    html = template.replace("/*CSS*/", css).replace("/*JS*/", js)
    html = html.replace("/*LIVE*/false", "true" if live else "false")
    html = html.replace("/*DATA*/null", _json_for_script(data) if data is not None else "null")
    html = html.replace("/*HISTORY*/null", _json_for_script(history) if history is not None else "null")
    return html
