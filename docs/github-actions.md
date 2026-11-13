# Ejecución diaria en GitHub Actions

El repositorio tiene **dos workflows** que hacen cosas distintas:

| Workflow | Qué hace | Dónde publica |
|---|---|---|
| `history-daily.yml` | Acumula el histórico de precios en un SQLite persistente | Rama `state` + repo `nas-discos-pages` (Pages) |
| `disk-search-daily.yml` | Busca y publica la tabla de resultados | Pages del propio repo `nas-discos` |

El flujo recomendado (y el que usa el histórico entre días) es
`history-daily.yml`. El segundo es una alternativa más simple que no conserva
el histórico de forma duradera.

## Histórico diario en la rama `state` (`history-daily.yml`)

`.github/workflows/history-daily.yml` ejecuta la búsqueda una vez al día
(06:00 UTC) y **acumula el histórico de precios en un SQLite persistente**:

1. Instala Python, las dependencias y Chromium de Playwright.
2. Lanza las pruebas sin red del repositorio.
3. Restaura `state/history.sqlite3` desde la rama `state` (si existe; si no,
   empieza un histórico nuevo).
4. Ejecuta `python nas_discos.py --once --debug`.
5. Comprueba que la búsqueda haya devuelto discos; si no, **falla y no
   commitea**, para que un bloqueo anti-bot nunca corrompa el histórico.
6. Hace commit del SQLite actualizado en la rama `state` con un mensaje como
   `history: 2026-11-13 (N discos)` y lo publica con push. Si el SQLite no ha
   cambiado, no commitea.
7. Genera `historico.html` con `python nas_discos.py --historico-html` y lo
   publica en el repo público **`Elicupra/nas-discos-pages`** (opción B del
   issue #7), que es el que tiene Pages activo. Si el contenido no cambia, no
   commitea.
8. Sube un artifact de diagnóstico con el HTML y el SQLite de esa corrida
   (30 días).

Usa `GITHUB_TOKEN` con `contents: write` para la rama `state` y el secreto
`PAGES_TOKEN` para el repo de Pages.

### Estado actual verificado (2026-11-13)

- Repo **`Elicupra/nas-discos-pages`**: existe, es público y su rama por
  defecto es `main`.
- Secreto **`PAGES_TOKEN`**: configurado en `Elicupra/nas-discos`.
- Pages **del repo `nas-discos`**: sin configurar (no hace falta para la opción
  B).
- Página esperada del histórico:
  <https://elicupra.github.io/nas-discos-pages/>.

> **Antes de la primera publicación**: hay que activar Pages en
> `nas-discos-pages` (**Settings → Pages → Build and deployment → Source:
> Deploy from a branch → `main` / `/ (root)`**). Si no está activo, el push
> funciona pero la URL aún no sirve la página.
>
> **Aviso (histórico, ya corregido)**: entre el merge del panel de búsqueda
> (#19) y el `fix/once-progress`, `python nas_discos.py --once` fallaba con
> `TypeError: ... takes 2 positional arguments but 4 were given`, así que el
> paso "Buscar discos" moría y el workflow nunca llegaba a publicar. Tras el
> fix, el flujo vuelve a completarse.

### Restaurar el histórico en local

Para trabajar con el histórico acumulado en tu equipo:

```bash
git fetch origin state
git show origin/state:state/history.sqlite3 > /tmp/opencode/historico.sqlite3
DISKSEARCH_DB=/tmp/opencode/historico.sqlite3 python nas_discos.py
```

Usa siempre una copia (no apuntes `DISKSEARCH_DB` a `data/history.sqlite3`)
para no mezclarla con tu histórico local.

Para eliminar el histórico y empezar de cero, borra la rama `state`
(`git push origin --delete state`); la siguiente ejecución creará una nueva.

### Limitaciones

- El historial de `main` no se toca: el SQLite vive solo en la rama `state`.
- Si dos ejecuciones se solapan, la concurrencia del workflow (`group:
  disksearch-history`, sin cancelación) hace que esperen; el commit usa la
  rama remota como base.
- El anti-bot y el cron impreciso aplican igual que al resto de workflows.

## Publicación en GitHub Pages

### Opción B — repo dedicado `nas-discos-pages` (la que se usa)

El histórico se publica en un repositorio **público** separado para no mezclar
el SQLite ni los datos con el repo de código:

1. Repo de destino: `Elicupra/nas-discos-pages` (creado).
2. Pages: **Settings → Pages → Source: Deploy from a branch → `main` / `/ (root)`**.
3. Token: un PAT con permiso de escritura (`Contents: Read and write`) sobre
   ese repo.
4. Secreto: en `Elicupra/nas-discos`, **Settings → Secrets and variables →
   Actions → New repository secret**, nombre `PAGES_TOKEN`.
5. Ejecutar **Actions → Histórico diario de precios → Run workflow**.

El paso "Publicar en nas-discos-pages" clona el repo de Pages, copia
`historico.html` como `index.html` y hace push a `main`. Si `PAGES_TOKEN` no
está definido, avisa y no publica (no rompe el job).

URL resultante:

```text
https://elicupra.github.io/nas-discos-pages/
```

### Opción alternativa — Pages del propio repo (`disk-search-daily.yml`)

`.github/workflows/disk-search-daily.yml` ejecuta la búsqueda y publica la
tabla de resultados (`nas_discos.html`) en el Pages del repo `nas-discos`:

1. Se ejecuta a las `06:00 UTC` y también a mano (**Run workflow**).
2. Corre las pruebas, busca, comprueba que haya resultados (si no, no publica).
3. Publica `nas_discos.html` como página y lo deja como artifact.

Activación:

1. **Actions**: habilita los workflows si aparecen desactivados.
2. **Pages**: **Settings → Pages → Source: GitHub Actions**.
3. **Run workflow** manual la primera vez.

No usa secretos propios: solo el `GITHUB_TOKEN` y permisos de Pages. El
histórico se guarda en la caché de Actions (no durable), por lo que **no
sustituye a la opción B**; se usa si solo quieres ver la última tabla.

## Ejecución local

El script `scripts/daily.sh` reproduce el flujo del workflow en tu equipo:

```bash
chmod +x scripts/daily.sh
scripts/daily.sh
```

Opciones útiles:

```bash
scripts/daily.sh --demo     # datos de ejemplo, sin internet
scripts/daily.sh --debug    # detalle de extracción por página
```

El resultado queda en `public/index.html` y el histórico en
`.cache/disk-search/history.sqlite3`. Ambas rutas están ignoradas por git.

Variables opcionales:

- `DISKSEARCH_VENV`: ruta del entorno virtual (por defecto
  `~/.venvs/disk-search`).
- `DISKSEARCH_DB`: ruta alternativa del SQLite.

## Dónde ver los resultados

- **Histórico publicado**: <https://elicupra.github.io/nas-discos-pages/>.
- **Artifact**: en la ejecución del workflow, sección **Artifacts**,
  `nas-discos-<número>`. Contiene `index.html`, `historico.html` y el
  `history.sqlite3` de esa corrida.
- **Logs**: el paso "Buscar discos" muestra el progreso por tienda y termina
  con una línea `OK: nas_discos.html (N discos distintos)`. Con `--debug`
  también registra cada URL y cuántos productos se extraen.

## Ajustes habituales

### Cambiar la hora

Edita el cron del workflow. GitHub lo interpreta siempre en UTC:

```yaml
schedule:
  - cron: "0 6 * * *"
```

Por ejemplo, `0 5 * * *` son las 06:00/07:00 en Madrid.

### Cambiar tiendas o páginas

Las fuentes están en `disksearch/config.py`. Si reduces el número de páginas,
la ejecución tarda menos; si lo aumentas, revisa el `timeout-minutes` del
workflow.

### Forzar una ejecución

**Actions → Histórico diario de precios → Run workflow**. No hace falta esperar
al cron.

## Limitaciones

- **Anti-bot**: PcComponentes y Amazon.es pueden bloquear las IPs de los
  runners de GitHub. La aplicación continúa con las demás tiendas y muestra el
  estado de cada fuente; un bloqueo no marca discos como ausentes. Es normal
  ver resultados parciales o notas de "bloqueo anti-bot" en los logs.
- **Cron no exacto**: GitHub puede retrasar la ejecución varios minutos e
  incluso saltarla en momentos de carga. Para una hora exacta haría falta un
  runner propio o un disparador externo.
- **Modo estático**: en `--once` los favoritos no se guardan. El histórico y
  los avisos sí se generan a partir de la base de datos.
- **Resultados vacíos**: si la búsqueda no devuelve ningún disco, el workflow
  falla y no publica para no sustituir la última página válida por una vacía.
  El artifact de esa ejecución sí se sube para poder diagnosticar.
- **Repositorio público**: la página y el artifact son visibles para
  cualquiera. No publiques el repositorio si el histórico contiene datos que
  no quieres exponer.
- **Inactividad**: GitHub desactiva los workflows programados de repositorios
  públicos tras 60 días sin actividad (commits/pushes). Si vuelve a ocurrir,
  reactívalo desde Actions o haz un commit.
- **Coste**: en repositorios públicos los minutos de Actions son gratuitos.
  Cada ejecución puede durar entre 10 y 30 minutos según las tiendas.

## Diagnóstico

### El job falla en "Buscar discos"

Muy probablemente sea un fallo de la propia búsqueda. Revisa el log del paso y
ejecuta en local `python nas_discos.py --once --debug` (o
`scripts/daily.sh --debug`). Si es un `TypeError` sobre los argumentos del
callback de progreso, comprueba que `nas_discos.cli_progress` y el `progress`
de `disksearch/server.py` aceptan `(valor, etiqueta, tienda, estado)`.

### El job falla en "Publicar en nas-discos-pages"

Revisa que `PAGES_TOKEN` tenga permiso de escritura sobre
`nas-discos-pages`. Si el secreto no existe, el paso avisa y termina sin
publicar (exit 0).

### La búsqueda termina pero hay pocos discos

Mira el paso "Buscar discos" y las notas por tienda. Si aparecen bloqueos
anti-bot, es el comportamiento esperado desde una IP de datacenter. Puedes
probar la misma búsqueda en local con `scripts/daily.sh --debug`.

### No se restaura el histórico

La primera ejecución no tiene rama `state` y muestra un aviso; es normal. A
partir de la segunda debería restaurarse.

### Chromium no arranca

El workflow ya instala las librerías del sistema con
`python -m playwright install --with-deps chromium --only-shell`. En local, si
faltan dependencias, consulta [`Install_dependences.md`](../Install_dependences.md).

### El workflow supera el tiempo límite

Aumenta `timeout-minutes` o reduce páginas en `disksearch/config.py`. También
puedes desactivar temporalmente una fuente lenta añadiendo `"enabled": False`
a su entrada.
