"""Histórico local en SQLite.

La interfaz ``HistoryStore`` permite sustituir SQLite por PocketBase en el
futuro sin tocar la búsqueda ni la UI. La implementación SQLite usa conexiones
cortas, WAL e índices para que el crecimiento sea razonable.
"""
from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS products (
    key TEXT PRIMARY KEY,
    brand TEXT NOT NULL DEFAULT '',
    model TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL DEFAULT '',
    part TEXT,
    capacity_gb INTEGER NOT NULL DEFAULT 0,
    form_factor TEXT,
    interface TEXT,
    rpm INTEGER,
    cache_mb INTEGER,
    nas INTEGER NOT NULL DEFAULT 0,
    kind TEXT NOT NULL DEFAULT 'HDD',
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    last_price REAL,
    best_price REAL,
    best_price_at TEXT,
    available INTEGER NOT NULL DEFAULT 1,
    missing_count INTEGER NOT NULL DEFAULT 0,
    missing_since TEXT,
    favorite INTEGER NOT NULL DEFAULT 0,
    favorite_at TEXT,
    last_store TEXT,
    last_url TEXT,
    last_search_id INTEGER
);
CREATE TABLE IF NOT EXISTS offers (
    product_key TEXT NOT NULL,
    store TEXT NOT NULL,
    url TEXT NOT NULL,
    title TEXT,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    last_price REAL,
    best_price REAL,
    available INTEGER NOT NULL DEFAULT 1,
    missing_count INTEGER NOT NULL DEFAULT 0,
    missing_since TEXT,
    last_search_id INTEGER,
    PRIMARY KEY (product_key, store, url)
);
CREATE TABLE IF NOT EXISTS price_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_key TEXT NOT NULL,
    store TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    price REAL NOT NULL,
    available INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS searches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT NOT NULL,
    status TEXT NOT NULL,
    pages_ok INTEGER NOT NULL DEFAULT 0,
    raw_count INTEGER NOT NULL DEFAULT 0,
    unique_count INTEGER NOT NULL DEFAULT 0,
    shown_count INTEGER NOT NULL DEFAULT 0,
    sources_json TEXT NOT NULL DEFAULT '[]',
    scope_json TEXT
);
CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_key TEXT NOT NULL,
    kind TEXT NOT NULL,
    created_at TEXT NOT NULL,
    dismissed_at TEXT,
    message TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_products_favorite ON products(favorite);
CREATE INDEX IF NOT EXISTS idx_products_last_seen ON products(last_seen);
CREATE INDEX IF NOT EXISTS idx_products_available ON products(available);
CREATE INDEX IF NOT EXISTS idx_offers_store ON offers(store);
CREATE INDEX IF NOT EXISTS idx_offers_available ON offers(available);
CREATE INDEX IF NOT EXISTS idx_price_product_date ON price_history(product_key, observed_at);
CREATE INDEX IF NOT EXISTS idx_notifications_open ON notifications(dismissed_at, created_at);
"""


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


class HistoryStore:
    """Persistencia local. Los métodos son seguros entre hilos."""

    def __init__(self, path=None):
        self.path = Path(path or config.default_db_path()).expanduser()
        self._memory = str(self.path) == ":memory:"
        self._lock = threading.RLock()
        self._memory_conn = None
        if not self._memory:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(SCHEMA)
            conn.execute(
                "INSERT OR REPLACE INTO meta(key, value) VALUES('schema_version', '1')"
            )

    @contextmanager
    def _connect(self):
        if self._memory:
            with self._lock:
                if self._memory_conn is None:
                    self._memory_conn = sqlite3.connect(
                        ":memory:", check_same_thread=False, timeout=10
                    )
                    self._memory_conn.row_factory = sqlite3.Row
                yield self._memory_conn
                self._memory_conn.commit()
            return
        conn = sqlite3.connect(str(self.path), timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA busy_timeout=5000")
            try:
                conn.execute("PRAGMA journal_mode=WAL")
            except sqlite3.DatabaseError:
                pass
            conn.execute("PRAGMA synchronous=NORMAL")
            yield conn
            conn.commit()
        finally:
            conn.close()

    # ── registro de búsquedas ────────────────────────────────────────────
    def record_search(self, data: dict) -> dict:
        """Guarda la búsqueda, sus ofertas y detecta ausencias fiables.

        Una búsqueda acotada (``meta.partial``) nunca marca ausencias ni
        cambia disponibilidades; solo actualiza o inserta productos del ámbito.
        """
        meta = data.get("meta") or {}
        sources = meta.get("sources") or []
        reliable = [s["name"] for s in sources if s.get("ok")]
        partial = bool(meta.get("partial"))
        now = now_iso()
        items = data.get("items") or []
        before = {}

        with self._connect() as conn:
            # Migración segura: scope_json puede no existir en bases antiguas.
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(searches)")}
            scope_json = __import__("json").dumps(
                {"scope": meta.get("scope"), "partial": partial}, ensure_ascii=False
            )
            if "scope_json" in columns:
                cursor = conn.execute(
                    """INSERT INTO searches
                       (started_at, finished_at, status, pages_ok, raw_count,
                        unique_count, shown_count, sources_json, scope_json)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        now, now, "ok" if items else "empty",
                        int(meta.get("pages") or 0), int(meta.get("raw") or 0),
                        int(meta.get("unique") or 0), int(meta.get("shown") or 0),
                        __import__("json").dumps(sources, ensure_ascii=False),
                        scope_json,
                    ),
                )
            else:
                cursor = conn.execute(
                    """INSERT INTO searches
                       (started_at, finished_at, status, pages_ok, raw_count,
                        unique_count, shown_count, sources_json)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        now, now, "ok" if items else "empty",
                        int(meta.get("pages") or 0), int(meta.get("raw") or 0),
                        int(meta.get("unique") or 0), int(meta.get("shown") or 0),
                        __import__("json").dumps(sources, ensure_ascii=False),
                    ),
                )
            search_id = cursor.lastrowid

            # Estado previo de todos los productos: los upserts de esta misma
            # búsqueda no deben ocultar una transición disponible→ausente.
            for row in conn.execute(
                "SELECT key, available, missing_since, favorite FROM products"
            ):
                before[row["key"]] = dict(row)

            for item in items:
                key = item["key"]
                offer_rows = item.get("offers_detail") or [{
                    "store": item.get("store", ""),
                    "url": item.get("url", ""),
                    "price": item.get("price"),
                    "title": item.get("title", ""),
                }]
                lowest = min(
                    (o["price"] for o in offer_rows if o.get("price") is not None),
                    default=item.get("price"),
                )
                existing = conn.execute(
                    "SELECT first_seen, best_price, best_price_at, favorite, favorite_at FROM products WHERE key=?",
                    (key,),
                ).fetchone()
                first_seen = existing["first_seen"] if existing else now
                best_price = existing["best_price"] if existing else None
                best_price_at = existing["best_price_at"] if existing else None
                if lowest is not None and (best_price is None or lowest < best_price):
                    best_price, best_price_at = lowest, now
                conn.execute(
                    """INSERT INTO products
                       (key, brand, model, title, part, capacity_gb, form_factor,
                        interface, rpm, cache_mb, nas, kind, first_seen, last_seen,
                        last_price, best_price, best_price_at, available,
                        missing_count, missing_since, favorite, favorite_at,
                        last_store, last_url, last_search_id)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1,
                               0, NULL, ?, ?, ?, ?, ?)
                       ON CONFLICT(key) DO UPDATE SET
                         brand=excluded.brand, model=excluded.model,
                         title=excluded.title, part=excluded.part,
                         capacity_gb=excluded.capacity_gb,
                         form_factor=excluded.form_factor,
                         interface=excluded.interface, rpm=excluded.rpm,
                         cache_mb=excluded.cache_mb, nas=excluded.nas,
                         kind=excluded.kind, last_seen=excluded.last_seen,
                         last_price=excluded.last_price,
                         best_price=excluded.best_price,
                         best_price_at=excluded.best_price_at,
                         available=1, missing_count=0, missing_since=NULL,
                         last_store=excluded.last_store, last_url=excluded.last_url,
                         last_search_id=excluded.last_search_id""",
                    (
                        key, item.get("brand", ""), item.get("model", ""),
                        item.get("title", ""), item.get("part"),
                        int(item.get("capacity_gb") or 0), item.get("form_factor"),
                        item.get("interface"), item.get("rpm"), item.get("cache"),
                        1 if item.get("nas") else 0, item.get("kind", "HDD"),
                        first_seen, now, lowest, best_price, best_price_at,
                        1 if existing and existing["favorite"] else 0,
                        existing["favorite_at"] if existing else None,
                        item.get("store", ""), item.get("url", ""), search_id,
                    ),
                )

                for offer in offer_rows:
                    if not offer.get("url") or offer.get("price") is None:
                        continue
                    old = conn.execute(
                        """SELECT last_price, available, best_price
                           FROM offers WHERE product_key=? AND store=? AND url=?""",
                        (key, offer["store"], offer["url"]),
                    ).fetchone()
                    old_price = old["last_price"] if old else None
                    old_available = bool(old["available"]) if old else True
                    old_best = old["best_price"] if old else None
                    new_best = offer["price"] if old_best is None else min(old_best, offer["price"])
                    conn.execute(
                        """INSERT INTO offers
                           (product_key, store, url, title, first_seen, last_seen,
                            last_price, best_price, available, missing_count,
                            missing_since, last_search_id)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, 0, NULL, ?)
                           ON CONFLICT(product_key, store, url) DO UPDATE SET
                             title=excluded.title, last_seen=excluded.last_seen,
                             last_price=excluded.last_price,
                             best_price=excluded.best_price, available=1,
                             missing_count=0, missing_since=NULL,
                             last_search_id=excluded.last_search_id""",
                        (
                            key, offer["store"], offer["url"], offer.get("title", ""),
                            now, now, offer["price"], new_best, search_id,
                        ),
                    )
                    if old_price is None or old_price != offer["price"] or not old_available:
                        conn.execute(
                            """INSERT INTO price_history
                               (product_key, store, observed_at, price, available)
                               VALUES (?, ?, ?, ?, 1)""",
                            (key, offer["store"], now, offer["price"]),
                        )

            # Ausencias por tienda fiable. Una tienda bloqueada no cuenta.
            # Las búsquedas acotadas no marcan ausencias para no corromper el
            # histórico con un subconjunto de productos.
            if not partial:
                for store in reliable:
                    rows = conn.execute(
                        """SELECT product_key, url, last_price, missing_count
                           FROM offers
                           WHERE store=? AND available=1
                             AND (last_search_id IS NULL OR last_search_id<>?)""",
                        (store, search_id),
                    ).fetchall()
                    for row in rows:
                        missing_count = int(row["missing_count"] or 0) + 1
                        if missing_count >= 2:
                            conn.execute(
                                """UPDATE offers SET available=0, missing_count=?,
                                   missing_since=COALESCE(missing_since, ?)
                                   WHERE product_key=? AND store=? AND url=?""",
                                (missing_count, now, row["product_key"], store, row["url"]),
                            )
                            conn.execute(
                                """INSERT INTO price_history
                                   (product_key, store, observed_at, price, available)
                                   VALUES (?, ?, ?, ?, 0)""",
                                (row["product_key"], store, now, row["last_price"] or 0),
                            )
                        else:
                            conn.execute(
                                """UPDATE offers SET missing_count=?
                                   WHERE product_key=? AND store=? AND url=?""",
                                (missing_count, row["product_key"], store, row["url"]),
                            )

            # Disponibilidad a nivel de producto y avisos solo para favoritos.
            # En búsquedas acotadas no recalculamos disponibilidad: no se sabe
            # si un producto ausente lo es realmente o simplemente no estaba en
            # el ámbito.
            if not partial:
                products = conn.execute(
                    "SELECT key, available, missing_since, favorite FROM products"
                ).fetchall()
                for product in products:
                    available = conn.execute(
                        "SELECT 1 FROM offers WHERE product_key=? AND available=1 LIMIT 1",
                        (product["key"],),
                    ).fetchone() is not None
                    previous = before.get(product["key"], {})
                    old_available = bool(previous.get("available", product["available"]))
                    old_missing_since = previous.get("missing_since", product["missing_since"])
                    if available and not old_available:
                        conn.execute(
                            """UPDATE products SET available=1, missing_count=0,
                               missing_since=NULL WHERE key=?""",
                            (product["key"],),
                        )
                        if product["favorite"]:
                            title_row = conn.execute(
                                "SELECT brand, model FROM products WHERE key=?",
                                (product["key"],),
                            ).fetchone()
                            label = f'{title_row["brand"]} {title_row["model"]}'.strip()
                            conn.execute(
                                """INSERT INTO notifications
                                   (product_key, kind, created_at, message)
                                   SELECT ?, 'back', ?, ?
                                   WHERE NOT EXISTS (
                                     SELECT 1 FROM notifications
                                     WHERE product_key=? AND kind='back'
                                       AND created_at >= COALESCE(?, '1970-01-01')
                                   )""",
                                (
                                    product["key"], now,
                                    f"{label} vuelve a estar disponible.",
                                    product["key"], old_missing_since,
                                ),
                            )
                    elif not available and old_available:
                        conn.execute(
                            """UPDATE products SET available=0,
                               missing_count=missing_count+1,
                               missing_since=COALESCE(missing_since, ?) WHERE key=?""",
                            (now, product["key"]),
                        )
                        if product["favorite"]:
                            title_row = conn.execute(
                                "SELECT brand, model FROM products WHERE key=?",
                                (product["key"],),
                            ).fetchone()
                            label = f'{title_row["brand"]} {title_row["model"]}'.strip()
                            conn.execute(
                                """INSERT INTO notifications
                                   (product_key, kind, created_at, message)
                                   SELECT ?, 'missing', ?, ?
                                   WHERE NOT EXISTS (
                                     SELECT 1 FROM notifications
                                     WHERE product_key=? AND kind='missing'
                                       AND created_at >= COALESCE(?, '1970-01-01')
                                   )""",
                                (
                                    product["key"], now,
                                    f"{label} ya no aparece en las tiendas.",
                                    product["key"], now,
                                ),
                            )

        return {"search_id": search_id, "reliable_sources": reliable}

    # ── favoritos e histórico ─────────────────────────────────────────────
    def set_favorite(self, key: str, favorite: bool) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE products SET favorite=?, favorite_at=? WHERE key=?",
                (1 if favorite else 0, now_iso() if favorite else None, key),
            )
            return cur.rowcount > 0

    def favorites(self) -> list[str]:
        with self._connect() as conn:
            return [r["key"] for r in conn.execute(
                "SELECT key FROM products WHERE favorite=1 ORDER BY favorite_at DESC"
            )]

    def list_products(self, favorites=False, q="", status="", limit=50,
                      offset=0, sort="last_seen", direction="desc", kind=""):
        limit = max(1, min(int(limit or 50), 200))
        offset = max(0, int(offset or 0))
        where, params = [], []
        if favorites:
            where.append("p.favorite=1")
        if q:
            where.append("(p.brand LIKE ? OR p.model LIKE ? OR p.title LIKE ?)")
            params += [f"%{q}%"] * 3
        if kind in ("HDD", "SSD"):
            where.append("p.kind=?")
            params.append(kind)
        if status == "available":
            where.append("p.available=1")
        elif status == "missing":
            where.append("p.available=0")
        clause = (" WHERE " + " AND ".join(where)) if where else ""
        column = config.HISTORY_SORT_FIELDS.get(sort, "last_seen")
        order = "ASC" if str(direction).lower() == "asc" else "DESC"
        with self._connect() as conn:
            total = conn.execute(
                f"SELECT COUNT(*) AS n FROM products p{clause}", params
            ).fetchone()["n"]
            rows = conn.execute(
                f"""SELECT p.*,
                       (SELECT COUNT(*) FROM offers o
                        WHERE o.product_key=p.key AND o.available=1) AS offer_count
                    FROM products p{clause}
                    ORDER BY {column} {order}, p.key ASC
                    LIMIT ? OFFSET ?""",
                params + [limit, offset],
            ).fetchall()
        return {"items": [dict(r) for r in rows], "total": total,
                "limit": limit, "offset": offset}

    def get_product(self, key: str):
        with self._connect() as conn:
            product = conn.execute("SELECT * FROM products WHERE key=?", (key,)).fetchone()
            if not product:
                return None
            offers = conn.execute(
                "SELECT * FROM offers WHERE product_key=? ORDER BY available DESC, last_price ASC",
                (key,),
            ).fetchall()
            prices = conn.execute(
                """SELECT observed_at, store, price, available
                   FROM price_history WHERE product_key=?
                   ORDER BY observed_at DESC LIMIT 200""",
                (key,),
            ).fetchall()
        return {"product": dict(product), "offers": [dict(r) for r in offers],
                "price_history": [dict(r) for r in prices]}

    def notifications(self, include_dismissed=False):
        clause = "" if include_dismissed else " WHERE n.dismissed_at IS NULL"
        with self._connect() as conn:
            rows = conn.execute(
                f"""SELECT n.*, p.brand, p.model, p.capacity_gb,
                           p.available, p.last_seen, p.missing_since
                    FROM notifications n
                    JOIN products p ON p.key=n.product_key{clause}
                    ORDER BY n.created_at DESC LIMIT 50"""
            ).fetchall()
        return [dict(r) for r in rows]

    def dismiss_notification(self, notification_id: int) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE notifications SET dismissed_at=? WHERE id=?",
                (now_iso(), int(notification_id)),
            )
            return cur.rowcount > 0

    def price_series(self, days=90):
        """Serie diaria de precio mínimo por producto, para gráficas y barras.

        Devuelve una lista de productos con sus puntos por día (precio mínimo
        del día entre tiendas disponibles) y el último precio por tienda.
        Limitada a los últimos `days` días para que el dataset sea liviano.
        """
        cutoff = (datetime.now() - timedelta(days=days)).isoformat(timespec="seconds")
        with self._connect() as conn:
            points = conn.execute(
                """SELECT product_key, substr(observed_at, 1, 10) AS day,
                          MIN(price) AS price
                   FROM price_history
                   WHERE observed_at >= ? AND available = 1
                   GROUP BY product_key, day
                   ORDER BY day""",
                (cutoff,),
            ).fetchall()
            records = conn.execute(
                """SELECT product_key, substr(observed_at, 1, 10) AS day,
                          store, price
                   FROM price_history
                   WHERE observed_at >= ? AND available = 1
                   ORDER BY observed_at ASC""",
                (cutoff,),
            ).fetchall()
            stores = conn.execute(
                """SELECT product_key, store, last_price AS price, last_seen
                   FROM offers
                   WHERE available = 1 AND last_price IS NOT NULL
                   ORDER BY last_price ASC""",
            ).fetchall()
        by_product = {}
        for row in points:
            by_product.setdefault(row["product_key"], []).append(
                {"day": row["day"], "price": row["price"]}
            )
        records_by_product = {}
        for row in records:
            records_by_product.setdefault(row["product_key"], []).append(
                {"day": row["day"], "store": row["store"], "price": row["price"]}
            )
        stores_by_product = {}
        for row in stores:
            entry = stores_by_product.setdefault(row["product_key"], {})
            if row["store"] not in entry:
                entry[row["store"]] = {"price": row["price"], "date": row["last_seen"]}
        series = []
        for row in self._product_rows():
            key = row["key"]
            if key not in by_product and key not in stores_by_product:
                continue
            series.append(
                {
                    "key": key,
                    "brand": row["brand"],
                    "model": row["model"],
                    "capacity_gb": row["capacity_gb"],
                    "form_factor": row["form_factor"],
                    "kind": row["kind"],
                    "favorite": bool(row["favorite"]),
                    "available": bool(row["available"]),
                    "last_price": row["last_price"],
                    "best_price": row["best_price"],
                    "points": by_product.get(key, []),
                    "records": records_by_product.get(key, [])[-200:],
                    "stores": stores_by_product.get(key, {}),
                }
            )
        return series

    def _product_rows(self):
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT key, brand, model, capacity_gb, form_factor, kind,
                          favorite, available, last_price, best_price
                   FROM products"""
            ).fetchall()
        return [dict(r) for r in rows]

    def stats(self) -> dict:
        with self._connect() as conn:
            row = conn.execute(
                """SELECT COUNT(*) AS total,
                          SUM(CASE WHEN favorite=1 THEN 1 ELSE 0 END) AS favorites,
                          SUM(CASE WHEN available=0 THEN 1 ELSE 0 END) AS missing
                   FROM products"""
            ).fetchone()
            notifications = conn.execute(
                "SELECT COUNT(*) AS n FROM notifications WHERE dismissed_at IS NULL"
            ).fetchone()["n"]
        return {
            "total": row["total"] or 0,
            "favorites": row["favorites"] or 0,
            "missing": row["missing"] or 0,
            "notifications": notifications,
        }

    def recent_searches(self, limit=10):
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM searches ORDER BY id DESC LIMIT ?",
                (max(1, min(int(limit), 50)),),
            ).fetchall()
        return [dict(r) for r in rows]

    def close(self):
        if self._memory and self._memory_conn is not None:
            self._memory_conn.close()
            self._memory_conn = None


class NullHistoryStore:
    """Modo degradado: la búsqueda funciona aunque SQLite no esté disponible."""

    path = None

    def record_search(self, data):
        return {"search_id": None, "reliable_sources": []}

    def set_favorite(self, key, favorite):
        return False

    def favorites(self):
        return []

    def list_products(self, **kwargs):
        return {"items": [], "total": 0, "limit": 50, "offset": 0}

    def get_product(self, key):
        return None

    def price_series(self, days=90):
        return []

    def notifications(self, include_dismissed=False):
        return []

    def dismiss_notification(self, notification_id):
        return False

    def stats(self):
        return {"total": 0, "favorites": 0, "missing": 0, "notifications": 0}

    def recent_searches(self, limit=10):
        return []

    def close(self):
        pass


def create_store(path=None):
    """Crea SQLite; si el filesystem falla, prueba XDG y luego degrada."""
    explicit = path or __import__("os").environ.get("DISKSEARCH_DB")
    candidates = [Path(path).expanduser() if path else config.default_db_path()]
    if not explicit:
        candidates.append(config.fallback_db_path())
    last_error = None
    for candidate in candidates:
        try:
            return HistoryStore(candidate)
        except (sqlite3.Error, OSError) as exc:
            last_error = exc
    print(f"AVISO: histórico desactivado ({last_error})", flush=True)
    return NullHistoryStore()
