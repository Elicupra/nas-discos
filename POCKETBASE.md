# PocketBase futuro

La aplicación funciona con SQLite local y no necesita PocketBase. Este
documento deja preparada la migración sin mezclar la base de datos con la
lógica de scraping.

## Interfaz que debe cumplir el adaptador

`disksearch.history.HistoryStore` es la implementación de referencia. El
adaptador de PocketBase debe exponer:

- `record_search(data)`
- `set_favorite(key, favorite)`
- `favorites()`
- `list_products(favorites, q, status, limit, offset, sort, direction)`
- `get_product(key)`
- `notifications(include_dismissed=False)`
- `dismiss_notification(id)`
- `stats()`
- `recent_searches(limit)`
- `close()`

## Colecciones

| Colección | Campos mínimos |
|---|---|
| `disk_products` | `key`, `brand`, `model`, `title`, `part`, `capacity_gb`, `form_factor`, `interface`, `rpm`, `cache_mb`, `nas`, `kind`, `first_seen`, `last_seen`, `last_price`, `best_price`, `available`, `missing_count`, `missing_since`, `favorite`, `favorite_at`, `last_store`, `last_url` |
| `disk_offers` | `product_key`, `store`, `url`, `title`, `first_seen`, `last_seen`, `last_price`, `best_price`, `available`, `missing_count`, `missing_since` |
| `disk_price_history` | `product_key`, `store`, `observed_at`, `price`, `available` |
| `disk_searches` | `started_at`, `finished_at`, `status`, `pages_ok`, `raw_count`, `unique_count`, `shown_count`, `sources_json` |
| `disk_notifications` | `product_key`, `kind`, `created_at`, `dismissed_at`, `message` |

`key` debe ser único en `disk_products`; en `disk_offers`, la combinación
`(product_key, store, url)`.

## Activación futura

El punto de entrada está en `disksearch/pocketbase.py`. Cuando exista una
instancia local, se puede añadir una opción `--storage pocketbase` y construir
el adaptador con la URL y el token. Mientras tanto, se mantiene SQLite para
garantizar que el proyecto arranque a la primera sin servicios externos.
