# AGENTS.md — disk-search

## Resumen

Aplicación local en Python que busca discos duros internos HDD (2,5" y 3,5")
en tiendas españolas, muestra una tabla comparable y guarda un histórico en
SQLite con favoritos y avisos de productos desaparecidos.

## Comandos

```bash
# entorno (el venv vive fuera del repo por limitaciones de CIFS)
source ~/.venvs/disk-search/bin/activate

# UI con datos de ejemplo, sin internet
python nas_discos.py --demo

# HTML estático
python nas_discos.py --demo --once

# servidor real
python nas_discos.py

# tests
python -m unittest discover -s tests -v
```

## Flujo de trabajo git

- La versión funcional actual está en `main`.
- **A partir de ahora no se trabaja directamente en `main`.** Cada cambio debe
  hacerse en una rama:
  - `feat/nombre-corto` para funcionalidad.
  - `fix/nombre-corto` para correcciones.
  - `test/nombre-corto` para pruebas o refactors.
- Antes de abrir/mergear una rama:
  1. `python -m unittest discover -s tests -v`
  2. `python nas_discos.py --demo --once`
  3. Comprobar el arranque del servidor con `--demo`.
- Commits pequeños y con mensaje en imperativo: `feat: ...`, `fix: ...`,
  `test: ...`, `docs: ...`.
- No se suben datos locales: `data/`, `*.sqlite3`, `nas_discos.html` están en
  `.gitignore`.

## Estructura

- `nas_discos.py`: entrada CLI compatible.
- `disksearch/config.py`: fuentes, límites de red y rutas.
- `disksearch/parsing.py`: precios, capacidades y clave canónica.
- `disksearch/extractors.py`: extractores por tienda.
- `disksearch/search.py`: búsqueda, agregación y demo.
- `disksearch/history.py`: interfaz de histórico + SQLite.
- `disksearch/server.py`: servidor HTTP/API.
- `disksearch/web/`: UI (HTML, CSS y JS).
- `tests/`: pruebas de regresión sin red.

## Reglas de scraping

- Respetar `robots.txt` y usar solo páginas de catálogo permitidas.
- Mantener pausas entre peticiones.
- Un bloqueo anti-bot no debe marcar productos como ausentes.
- No añadir tiendas frágiles sin un extractor probado con fixture.
- Si se amplía a SSD/NVMe/externos, hacerlo en una rama y añadir filtros de
  tipo antes de activar las fuentes.

## Histórico

- SQLite por defecto (`data/history.sqlite3`, configurable con `--db` o
  `DISKSEARCH_DB`). En filesystems sin bloqueos (el repo puede estar en CIFS)
  se usa automáticamente `~/.local/share/disk-search/history.sqlite3`.
- Favoritos manuales; todo modelo visto se guarda.
- Un producto se marca no disponible tras **2 ausencias fiables**.
- Los avisos no intrusivos se muestran solo para favoritos.
- PocketBase es un adaptador futuro documentado en `POCKETBASE.md`; no se
  activa por defecto.
