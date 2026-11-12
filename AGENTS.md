# AGENTS.md — disk-search

## Resumen

Aplicación local en Python que busca discos duros internos HDD (2,5" y 3,5")
en tiendas españolas, muestra una tabla comparable y guarda un histórico en
SQLite con favoritos y avisos de productos desaparecidos.

## Convenciones de OpenCode

Este repositorio usa **OpenCode V2**. `AGENTS.md` es el archivo de
instrucciones persistentes que OpenCode carga automáticamente; no se usa
`CLAUDE.md` como respaldo. La documentación oficial está en
<https://opencode.ai/v2/docs/>.

### Alcance y carga

- Las instrucciones globales van en `~/.config/opencode/AGENTS.md`.
- Las instrucciones del repositorio van en este `AGENTS.md`.
- Los `AGENTS.md` anidados se cargan al leer esa zona del proyecto. Usa uno
  cerca del código solo si sus reglas no aplican a todo el repositorio.
- OpenCode combina los archivos en lugar de resolver conflictos: evita repetir
  reglas y deja claro cuál manda cuando haya excepciones.
- Los cambios en este archivo se aplican sin reiniciar la sesión. Si cambia un
  `AGENTS.md` anidado ya cargado, inicia una sesión nueva.
- Este archivo se versiona en git para que todo el mundo reciba las mismas
  instrucciones.

### Cómo redactar instrucciones

- Usa frases imperativas, concretas y verificables.
- Incluye comandos exactos de instalación, pruebas y verificación.
- Documenta la arquitectura y las convenciones que no se deducen leyendo el
  código.
- No incluyas secretos, tokens, rutas personales ni datos locales.
- Mantén las reglas cerca del código al que afectan y actualiza este archivo
  cuando cambie el flujo de trabajo.
- No dupliques la documentación extensa: enlaza `README.md`,
  `Install_dependences.md` o `POCKETBASE.md` cuando corresponda.

### Configuración y extensiones

- La configuración de OpenCode vive en `opencode.json(c)` o
  `.opencode/opencode.json(c)`. Incluye siempre
  `"$schema": "https://opencode.ai/config.json"`.
- Las preferencias de terminal van aparte, en `cli.json`; no las mezcles con
  la configuración del proyecto.
- Los agentes personalizados van en `.opencode/agents/*.md`, los comandos en
  `.opencode/commands/*.md` y las skills en
  `.opencode/skills/<id>/SKILL.md`.
- No inventes campos de configuración: consulta la documentación V2 antes de
  añadir o modificar opciones.
- Los permisos se declaran como reglas ordenadas; la última regla que coincide
  gana. Usa `allow`, `ask` o `deny` de forma explícita para operaciones
  destructivas o fuera del repositorio.

### Uso en este proyecto

- Antes de tocar código, revisa este archivo y el `README.md`.
- Sigue el flujo de ramas y la verificación de la sección siguiente.
- No ejecutes `git push`, despliegues ni borres datos sin confirmación.
- No edites `data/`, `*.sqlite3` ni `nas_discos.html`: son datos locales
  ignorados por git.
- Si una tarea requiere cambiar las convenciones del repositorio, actualiza
  este `AGENTS.md` en la misma rama.

## Comandos

```bash
# entorno (el venv vive fuera del repo por limitaciones de CIFS)
source ~/.venvs/disk-search/bin/activate

# UI con datos de ejemplo, sin internet
python nas_discos.py --demo

# HTML estático
python nas_discos.py --demo --once

# servidor real (la portada es el Histórico; la búsqueda se lanza a mano)
python nas_discos.py

# búsqueda diaria en local (igual que el workflow de GitHub Actions)
scripts/daily.sh

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

- `nas_discos.py`: entrada CLI compatible (`--once`, `--demo`, `--historico-html`).
- `disksearch/config.py`: fuentes, límites de red y rutas.
- `disksearch/parsing.py`: precios, capacidades y clave canónica.
- `disksearch/extractors.py`: extractores por tienda.
- `disksearch/search.py`: búsqueda, agregación y demo (progreso por tienda).
- `disksearch/history.py`: interfaz de histórico + SQLite (`price_series`).
- `disksearch/server.py`: servidor HTTP/API (estado por tienda en `/api/status`).
- `disksearch/web/`: UI (HTML, CSS y JS).
- `.github/workflows/history-daily.yml`: histórico diario, guard en la rama
  `state`, `historico.html` en el artifact y publicación en
  `Elicupra/nas-discos-pages` (Pages, secret `PAGES_TOKEN`).
- `docs/github-actions.md`: activación, histórico en caché y limitaciones.
- `docs/plans/SPEC_x.md`: specs por issue (gitignored).
- `HTW_ISSUES.md`: metodología de gestión de issues para el humano.
- `scripts/daily.sh`: reproducción local del flujo diario.
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
- Histórico diario en GitHub Actions: el workflow
  `.github/workflows/history-daily.yml` acumula el SQLite en la rama
  `state` (commit diario). Ver `docs/github-actions.md`.
- PocketBase es un adaptador futuro documentado en `POCKETBASE.md`; no se
  activa por defecto.
