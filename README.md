# disk-search

Buscador local de **discos duros internos HDD de 2,5" y 3,5"** en tiendas
españolas. Compara precios, ordena y filtra los resultados, y guarda un
histórico en SQLite con favoritos y avisos de productos que dejan de aparecer.

La aplicación se ejecuta en tu equipo: no hay cuentas, servicios externos ni
telemetría. Solo se consultan las páginas públicas de catálogo de las tiendas.

## Características

- Búsqueda de HDD internos **sin límite artificial de capacidad**: desde
  modelos pequeños de 500 GB hasta discos de 32 TB.
- Agrupación por producto canónico: un modelo puede reunir ofertas de varias
  tiendas y se muestra el mejor precio.
- Tabla ordenable por marca, modelo, capacidad, caché, formato, precio,
  €/TB, tienda, etc.
- Filtros por texto, marca, formato, capacidad, interfaz, gama NAS, tienda y
  favoritos.
- Paginación de 25, 50 o 100 resultados.
- Histórico SQLite con todos los modelos vistos, precios, ofertas por tienda y
  última fecha de aparición.
- Favoritos manuales y avisos no intrusivos para productos favoritos que
  desaparecen o vuelven a aparecer.
- Un producto se marca como no disponible tras **dos ausencias fiables**. Las
  tiendas bloqueadas o con errores no cuentan como ausencia.
- Interfaz web local y también modo estático (`nas_discos.html`) para abrirlo
  sin servidor.
- Código preparado para añadir SSD, NVMe y discos externos en el futuro, y un
  adaptador documentado para PocketBase.

## Fuentes

Fuentes activas:

| Tienda | Método |
|---|---|
| PcComponentes | Chromium real con Playwright |
| PcBox | Petición HTTP |
| Amazon.es | Chromium real con Playwright |
| LDLC | Petición HTTP |
| Coolmod | Petición HTTP |
| Alternate.es | Petición HTTP |

Las pausas entre peticiones son deliberadas. No se intenta evadir captchas ni
se usan páginas distintas de los catálogos públicos. Si una tienda bloquea la
petición, su estado se muestra en la interfaz y **no** se usa para detectar
productos descatalogados.

## Requisitos

- Python 3.10 o superior (probado con Python 3.14).
- `requests`, `beautifulsoup4` y `playwright`.
- Chromium de Playwright para PcComponentes y Amazon.es.
- SQLite, incluido en la biblioteca estándar de Python.

## Instalación

Se recomienda usar un entorno virtual. Si el repositorio está en un
filesystem que no admite enlaces simbólicos (por ejemplo, algunos montajes de
red o CIFS), crea el entorno fuera del repositorio:

```bash
python3 -m venv ~/.venvs/disk-search
source ~/.venvs/disk-search/bin/activate

pip install -r requirements.txt
python -m playwright install chromium
```

En Ubuntu pueden faltar librerías del sistema para Chromium. Consulta
[`Install_dependences.md`](Install_dependences.md) para los paquetes concretos
y la solución de problemas habitual.

## Uso

### Servidor local

```bash
source ~/.venvs/disk-search/bin/activate
python nas_discos.py
```

Abre `http://localhost:8765`. La primera búsqueda se lanza automáticamente y
puedes repetirla desde la interfaz cuando pase el tiempo de espera.

### Datos de ejemplo, sin internet

```bash
python nas_discos.py --demo
```

Útil para probar la interfaz, los filtros, la ordenación y el histórico sin
hacer peticiones a las tiendas.

### HTML estático

```bash
python nas_discos.py --demo --once   # con datos de ejemplo
python nas_discos.py --once          # búsqueda real y HTML estático
```

Genera `nas_discos.html` en el directorio actual. En modo estático los
favoritos no se guardan; para eso hace falta el servidor.

### Opciones

```text
--once        busca una vez, genera nas_discos.html y sale
--demo        usa datos de ejemplo sin tocar internet
--debug       muestra por stderr qué se extrae de cada página
--headed      abre Chromium visible (útil si hay que resolver un captcha)
--no-open     no abre el navegador al arrancar el servidor
--db RUTA     ruta alternativa para la base SQLite del histórico
--port N      puerto del servidor (por defecto 8765)
```

## Ejecución diaria en GitHub Actions

El repositorio incluye un workflow que ejecuta la búsqueda una vez al día,
publica `nas_discos.html` en GitHub Pages y deja el HTML como artifact
descargable. El histórico SQLite se conserva entre ejecuciones mediante la
caché de Actions, sin commitear datos al repositorio.

Consulta [`docs/github-actions.md`](docs/github-actions.md) para activar Pages,
lanzar la primera ejecución y revisar las limitaciones. En local puedes
reproducir el mismo flujo con:

```bash
scripts/daily.sh
```

## Histórico

El histórico se guarda en SQLite:

- Por defecto: `data/history.sqlite3`.
- Se puede cambiar con `--db RUTA` o con la variable `DISKSEARCH_DB`.
- Si el filesystem no admite bloqueos, como puede ocurrir en CIFS, se usa
  automáticamente `~/.local/share/disk-search/history.sqlite3`.
- La carpeta de datos se puede cambiar con `DISKSEARCH_DATA_DIR`.

### Histórico diario en GitHub Actions

Además del histórico local, el workflow
`.github/workflows/history-daily.yml` ejecuta la búsqueda una vez al día y
guarda el SQLite en la rama `state` del repositorio (`state/history.sqlite3`),
de forma que el histórico de precios sobrevive entre ejecuciones y no depende
de la caché de Actions. Consulta
[`docs/github-actions.md`](docs/github-actions.md) para saber cómo
restaurarlo en local.

### Ver el histórico acumulado

**Opción 1 — En tu equipo con la interfaz completa (recomendada):**

```bash
git fetch origin state
git show origin/state:state/history.sqlite3 > /tmp/opencode/historico.sqlite3
source ~/.venvs/disk-search/bin/activate
DISKSEARCH_DB=/tmp/opencode/historico.sqlite3 python nas_discos.py
```

Abre `http://localhost:8765`: la vista de Histórico muestra fechas, precios
por tienda y ofertas de los días acumulados. Usa siempre una copia del SQLite
(no lo apuntes a `data/history.sqlite3`) para no mezclarlo con tu histórico
local.

**Opción 2 — Descargar el SQLite desde GitHub:**

En **Actions → Histórico diario de precios → ejecución → Artifacts** está
`nas-discos-<n>`, que incluye `history.sqlite3` de esa corrida.

**Opción 3 — Consulta rápida por terminal:**

```bash
git show origin/state:state/history.sqlite3 > /tmp/h.sqlite3
sqlite3 /tmp/h.sqlite3 ".schema"
sqlite3 /tmp/h.sqlite3 "SELECT * FROM prices ORDER BY date DESC LIMIT 20;"
```

Cada día, el commit `history: <fecha> (N discos)` en la rama `state` añade el
registro diario; con varias fechas acumuladas, la interfaz muestra la
evolución de precios y los avisos de productos desaparecidos.

Se guardan todos los modelos vistos, no solo los favoritos. Los favoritos se
marcan desde la tabla y sirven para:

- Filtrar el histórico.
- Recibir avisos cuando un producto desaparece de las tiendas o vuelve a
  aparecer.
- Conservar un seguimiento más claro de los modelos que interesan.

Los avisos aparecen en la propia interfaz y se pueden descartar sin modales.

## Estructura del proyecto

```text
nas_discos.py              entrada CLI compatible
.github/workflows/         búsqueda diaria y publicación en Pages
docs/                      documentación de despliegue
scripts/                   utilidades de ejecución local
disksearch/
  config.py                fuentes, límites de red y rutas
  parsing.py               precios, capacidades, formatos y claves canónicas
  extractors.py            extractores genéricos y por tienda
  search.py                búsqueda, agregación y dataset de demo
  history.py               interfaz de histórico + implementación SQLite
  server.py                servidor HTTP y API local
  ui.py                    composición del HTML
  pocketbase.py            punto de extensión futuro para PocketBase
  web/                     HTML, CSS y JavaScript de la interfaz
tests/                     pruebas de regresión sin red
```

## API local

El servidor expone una API sencilla en `127.0.0.1`:

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/api/status` | Estado de la búsqueda y tiempo de espera |
| `GET` | `/api/data` | Resultados actuales y favoritos |
| `GET` | `/api/history` | Histórico paginado y filtrable |
| `GET` | `/api/history/<key>` | Detalle de un producto |
| `GET` | `/api/notifications` | Avisos activos |
| `GET` | `/api/stats` | Totales del histórico |
| `GET` | `/api/searches` | Búsquedas recientes |
| `POST` | `/api/refresh` | Inicia una nueva búsqueda |
| `POST` | `/api/favorites` | Marca o desmarca un favorito |
| `POST` | `/api/notifications/dismiss` | Descarta un aviso |

## Pruebas

Las pruebas no necesitan internet:

```bash
python -m unittest discover -s tests -v
```

Antes de dar por buena una versión también conviene comprobar la interfaz:

```bash
python nas_discos.py --demo --once
python nas_discos.py --demo --no-open
```

## Limitaciones

- Solo se buscan **HDD internos de 2,5" y 3,5"**. SSD, NVMe y discos externos
  están fuera del alcance actual, aunque la arquitectura ya los contempla.
- Los precios y la disponibilidad cambian; la aplicación muestra la última
  observación, no una garantía en tiempo real.
- Algunas tiendas aplican límites anti-bot. Si una fuente falla, el resto sigue
  funcionando y esa fuente no se usa para marcar ausencias.
- La agrupación entre tiendas se apoya en marca, línea, capacidad, formato y
  número de parte. Cambios de nombre comercial pueden requerir ajustes en el
  parser.

## Documentación adicional

- [`Install_dependences.md`](Install_dependences.md): instalación detallada y
  resolución de problemas.
- [`docs/github-actions.md`](docs/github-actions.md): búsqueda diaria y
  publicación en GitHub Pages.
- [`AGENTS.md`](AGENTS.md): flujo de trabajo, estructura y reglas del proyecto.
- [`POCKETBASE.md`](POCKETBASE.md): esquema e interfaz del adaptador futuro.
