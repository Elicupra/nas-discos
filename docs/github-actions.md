# Ejecución diaria en GitHub Actions

## Histórico diario en la rama `state` (workflow `history-daily.yml`)

`.github/workflows/history-daily.yml` ejecuta la búsqueda una vez al día
(06:00 UTC) y su único cometido es **acumular el histórico de precios en un
SQLite persistente**:

1. Instala Python, las dependencias y Chromium de Playwright.
2. Lanza las pruebas sin red del repositorio.
3. Restaura `state/history.sqlite3` desde la rama `state` (si existe; si no,
   empieza un histórico nuevo).
4. Ejecuta `python nas_discos.py --once --debug`.
5. Comprueba que la búsqueda haya devuelto discos; si no, **falla y no
   commitea**, para que un bloqueo anti-bot nunca corrompa el histórico.
6. Hace commit del SQLite actualizado en la rama `state` con un mensaje como
   `history: 2026-11-10 (107 discos)` y lo publica con push. Si el SQLite no
   ha cambiado, no commitea.
7. Sube un artifact de diagnóstico con el HTML y el SQLite de esa corrida
   (30 días).

No usa secretos: solo necesita el `GITHUB_TOKEN` con `contents: write`.

### Restaurar el histórico en local

Para trabajar con el histórico acumulado en tu equipo:

```bash
git fetch origin state
git show origin/state:state/history.sqlite3 > historico.sqlite3
DISKSEARCH_DB="$PWD/historico.sqlite3" python nas_discos.py
```

Para eliminar el histórico y empezar de cero, borra la rama `state`
(`git push origin --delete state`); la siguiente ejecución creará una nueva.

### Limitaciones

- El historial de `main` no se toca: el SQLite vive solo en la rama `state`.
- Si dos ejecuciones se solapan, la concurrencia del workflow (`group:
  disksearch-history`, sin cancelación) hace que esperen; el commit usa la
  rama remota como base.
- El anti-bot y el cron impreciso aplican igual que al resto de workflows.

## Publicación en GitHub Pages (workflow `disk-search-daily.yml`)

El repositorio también incluye un workflow que ejecuta la búsqueda una vez al
día, publica `nas_discos.html` en GitHub Pages y deja el HTML como artifact
descargable. El histórico SQLite se conserva entre ejecuciones mediante la
caché de Actions, sin commitear datos al repositorio.

## Qué hace

`.github/workflows/disk-search-daily.yml`:

1. Se ejecuta todos los días a las `06:00 UTC` (≈07:00 en invierno y 08:00 en
   verano, hora de Madrid) y también a mano desde la pestaña **Actions**.
2. Instala Python, las dependencias y Chromium de Playwright.
3. Lanza las pruebas sin red del repositorio.
4. Restaura el histórico SQLite desde la caché de Actions.
5. Ejecuta `python nas_discos.py --once --debug`.
6. Comprueba que la búsqueda haya devuelto discos; si no, falla y no publica.
7. Guarda el histórico actualizado en la caché.
8. Sube `nas_discos.html` como artifact descargable (30 días).
9. Publica el HTML en **GitHub Pages**.

No usa secretos ni tokens propios: el workflow solo necesita el
`GITHUB_TOKEN` que GitHub proporciona automáticamente.

## Activación

Solo hace falta una vez:

1. **Actions**: abre la pestaña Actions del repositorio y acepta habilitar los
   workflows si GitHub los muestra desactivados.
2. **Pages**: ve a **Settings → Pages → Build and deployment** y elige
   **Source: GitHub Actions**. No selecciones "Deploy from a branch".
3. **Primera ejecución**: en **Actions → Búsqueda diaria de discos → Run
   workflow**. Así compruebas el flujo sin esperar al cron.

Cuando termine correctamente, la página estará en:

```text
https://eliqupra.github.io/nas-discos/
```

La URL exacta depende del usuario y del nombre del repositorio. También
aparece en el resumen del job y en **Settings → Pages**.

### Probar antes del merge

El cron y el botón **Run workflow** solo están disponibles cuando el workflow
está en la rama por defecto (`main`). Para poder validarlo antes, el workflow
incluye un disparador temporal `push` para la rama
`feat/github-actions-diario`: al subir la rama se ejecuta la búsqueda completa,
se guarda la caché y se sube el artifact, pero **no** se despliega en Pages
(los pasos de publicación están limitados a `main`).

Cuando la rama esté validada, elimina el bloque `push` antes del merge para que
no se lance una búsqueda en cada push a esa rama. Si se queda, tampoco rompe
nada: la rama desaparece tras el merge.

## Dónde ver los resultados

- **Página publicada**: `https://eliqupra.github.io/nas-discos/`.
- **Artifact**: en la ejecución del workflow, sección **Artifacts**,
  `nas-discos-<número>`. Contiene el `index.html` de esa ejecución concreta.
- **Logs**: el paso "Buscar discos" muestra el progreso por tienda y termina
  con una línea `OK: nas_discos.html (N discos distintos)`. Con `--debug`
  también registra cada URL y cuántos productos se extraen.

## Histórico entre ejecuciones

El workflow define:

```yaml
DISKSEARCH_DB: ${{ github.workspace }}/.cache/disk-search/history.sqlite3
```

y guarda la carpeta `.cache/disk-search` con `actions/cache`. La clave de
caché es única por ejecución (`disksearch-history-<run_id>-<run_attempt>`) y
se restaura la más reciente con el prefijo `disksearch-history-`.

Consecuencias:

- El histórico no se commitea al repositorio ni se publica.
- La caché no es una copia de seguridad. GitHub puede eliminarla por
  inactividad o por límite de almacenamiento.
- Para empezar de cero, borra las entradas del prefijo `disksearch-history-`
  en **Actions → Caches** o cambia el prefijo en el workflow.
- Las entradas antiguas dejan de usarse y GitHub las elimina tras un tiempo,
  así que no crecen indefinidamente.

Si prefieres un histórico más duradero, la alternativa es commitear el SQLite
a una rama `state`. No se hace por defecto porque ensucia el historial de git
y, en un repositorio público, expondría los favoritos.

## Ejecución local

El script `scripts/daily.sh` reproduce el mismo flujo en tu equipo:

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

**Actions → Búsqueda diaria de discos → Run workflow**. No hace falta esperar
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
  falla y no despliega para no sustituir la última página válida por una vacía.
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

### El job falla en "Desplegar en Pages"

Suele significar que Pages no está configurado con **Source: GitHub Actions**.
Revisa **Settings → Pages**. Si el repositorio es privado, Pages puede requerir
un plan de pago.

### La búsqueda termina pero hay pocos discos

Mira el paso "Buscar discos" y las notas por tienda. Si aparecen bloqueos
anti-bot, es el comportamiento esperado desde una IP de datacenter. Puedes
probar la misma búsqueda en local con `scripts/daily.sh --debug`.

### No se restaura el histórico

La primera ejecución no tiene caché y muestra un aviso; es normal. A partir de
la segunda debería restaurarse. Comprueba que el prefijo de `restore-keys`
coincide con el de la clave.

### Chromium no arranca

El workflow ya instala las librerías del sistema con
`python -m playwright install --with-deps chromium`. En local, si faltan
dependencias, consulta [`Install_dependences.md`](../Install_dependences.md).

### El workflow supera el tiempo límite

Aumenta `timeout-minutes` o reduce páginas en `disksearch/config.py`. También
puedes desactivar temporalmente una fuente lenta añadiendo `"enabled": False`
a su entrada.
