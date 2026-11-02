"""Adaptador futuro para PocketBase.

La aplicación usa SQLite por defecto. PocketBase queda preparado como backend
alternativo local, pero no se activa automáticamente para no romper la
experiencia inicial. La interfaz pública que debe implementar es la misma que
``HistoryStore``: ``record_search``, ``set_favorite``, ``favorites``,
``list_products``, ``get_product``, ``notifications``,
``dismiss_notification``, ``stats``, ``recent_searches`` y ``close``.

Colecciones recomendadas en PocketBase (ver ``POCKETBASE.md``):
``disk_products``, ``disk_offers``, ``disk_price_history``, ``disk_searches``
y ``disk_notifications``.
"""
from __future__ import annotations


class PocketBaseHistoryStore:
    """Punto de extensión explícito; se activará cuando se configure PocketBase."""

    def __init__(self, *args, **kwargs):
        raise RuntimeError(
            "PocketBase todavía no está activado. Usa SQLite (por defecto) y "
            "consulta POCKETBASE.md para el esquema y la interfaz del adaptador."
        )
