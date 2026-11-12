"""Configuración de fuentes, red y almacenamiento.

Para ampliar la búsqueda en el futuro solo hay que añadir fuentes aquí y, si su
HTML lo requiere, un extractor en ``extractors.py``. Ahora mismo se buscan HDD
internos de 2,5" y 3,5" y SSD internos SATA 2,5" y M.2/mSATA, sin límites
artificiales de capacidad.
"""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# {page} se sustituye por 1, 2, 3...
# mode: "browser" = Chromium real con Playwright (webs con JS o anti-bot)
#       "http"    = petición simple con requests
#       "vtex"    = API JSON pública de tiendas VTEX (reservado)
SOURCES = [
    {
        "name": "PcComponentes",
        "mode": "browser",
        "extract": "generic",
        "urls": [
            {"url": "https://www.pccomponentes.com/categorias/discos-duros/3-5-pulgadas?page={page}", "pages": 6},
            {"url": "https://www.pccomponentes.com/categorias/discos-duros/2-5-pulgadas?page={page}", "pages": 3},
            # La página 2 de SSD cae en el reto anti-bot; con 1 página basta.
            {"url": "https://www.pccomponentes.com/categorias/discos-duros/disco-ssd?page={page}", "pages": 1},
        ],
    },
    {
        "name": "PcBox",
        "mode": "http",
        "extract": "generic",
        "urls": [
            {"url": "https://www.pcbox.com/componentes-de-ordenador/discos-duros/discos-hdd?page={page}", "pages": 3},
            {"url": "https://www.pcbox.com/componentes-de-ordenador/discos-duros/discos-ssd?page={page}", "pages": 7},
        ],
    },
    {
        "name": "Amazon.es",
        "mode": "browser",
        "extract": "amazon",
        "query": "disco duro interno hdd",
        "url": "https://www.amazon.es/s?k={q}&page={page}",
        "pages": 3,
    },
    {
        "name": "LDLC",
        "mode": "http",
        "extract": "generic",
        "urls": [
            {"url": "https://www.ldlc.com/es-es/informatica/piezas-de-informatica/disco-duro-interno/c4697/+fv63-1346.html", "pages": 1},
            {"url": "https://www.ldlc.com/es-es/informatica/piezas-de-informatica/disco-duro-interno/c4697/+fv63-1345.html", "pages": 1},
        ],
    },
    {
        "name": "Coolmod",
        "mode": "http",
        "extract": "coolmod",
        "urls": [
            {"url": "https://www.coolmod.com/componentes-pc-discos-hdd/", "pages": 1},
            {"url": "https://www.coolmod.com/componentes-pc-discos-ssd/", "pages": 1},
        ],
    },
    {
        "name": "Geeknetic · agregado",
        "mode": "http",
        "extract": "geeknetic",
        # Es un comparador, no una tienda: sus precios son «desde» y solo se
        # usan como respaldo/descubrimiento. robots.txt permite /comparador-precios/
        # salvo */ver-tienda, que no se sigue.
        "aggregator": True,
        "full_page_items": 42,
        "urls": [
            {"url": "https://www.geeknetic.es/comparador-precios/discos-duros/", "pages": 1},
            {"url": "https://www.geeknetic.es/comparador-precios/discos-duros/{page}/", "pages": 11},
            {"url": "https://www.geeknetic.es/comparador-precios/ssds/", "pages": 1},
            {"url": "https://www.geeknetic.es/comparador-precios/ssds/{page}/", "pages": 24},
        ],
    },
    {
        "name": "Alternate.es",
        "mode": "http",
        "extract": "alternate",
        "urls": [
            {"url": "https://www.alternate.es/Discos-duros", "pages": 1},
        ],
    },
]

HEADED = False
DELAY = (1.2, 2.5)          # pausa aleatoria entre peticiones (segundos)
COOLDOWN = 60               # espera mínima entre rebúsquedas (segundos)
PORT = 8765
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "es-ES,es;q=0.9",
}

# Formatos y tipos aceptados. La UI y el modelo de datos usan estos valores.
DISK_KINDS = ("HDD", "SSD")
FORM_FACTORS = ("2.5", "3.5", "M.2", "mSATA")

DEFAULT_PAGE_SIZE = 25
PAGE_SIZES = (25, 50, 100)
HISTORY_SORT_FIELDS = {
    "last_seen": "last_seen",
    "first_seen": "first_seen",
    "brand": "brand",
    "model": "model",
    "capacity_gb": "capacity_gb",
    "price": "last_price",
    "best_price": "best_price",
    "missing_since": "missing_since",
}


def data_dir() -> Path:
    """Directorio de datos local, separado del código y de git."""
    env = os.environ.get("DISKSEARCH_DATA_DIR")
    if env:
        return Path(env).expanduser().resolve()
    return BASE_DIR / "data"


def default_db_path() -> Path:
    """Ruta de la base SQLite.

    Se puede sobrescribir con ``DISKSEARCH_DB``. Si el directorio del repo no
    admite bloqueos (p. ej. algunos montajes de red), ``HistoryStore`` probará
    una ubicación XDG antes de degradar a modo sin histórico.
    """
    env = os.environ.get("DISKSEARCH_DB")
    if env:
        return Path(env).expanduser().resolve()
    return data_dir() / "history.sqlite3"


def fallback_db_path() -> Path:
    xdg = os.environ.get("XDG_DATA_HOME")
    root = Path(xdg).expanduser() if xdg else Path.home() / ".local" / "share"
    return (root / "disk-search" / "history.sqlite3").resolve()
