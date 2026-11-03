# PLAN_WORKSPACE — Publicación diaria de nas-discos

Documento de traspaso para que otro modelo ejecute la opción elegida sin
repetir el análisis. Está fuera del repositorio para no ensuciar git ni
disparar el workflow.

- Fecha: 2026-11-03
- Repo local: `/home/ubuntu/red/repos/disk-search`
- Rama actual: `feat/github-actions-diario` (ya subida a `origin`)
- `main` no se ha tocado.
- Últimos commits de la rama:
  - `145c32b ci: evita publicar búsquedas sin resultados`
  - `f8572c7 chore: hace ejecutable scripts/daily.sh`
  - `0c9a8bd docs: documenta la búsqueda diaria y Pages`
  - `39be2ce ci: añade búsqueda diaria con GitHub Actions`

## Estado actual

Ya está implementado en la rama:

- Workflow `.github/workflows/disk-search-daily.yml`:
  - Cron diario `0 6 * * *` + `workflow_dispatch`.
  - Trigger temporal `push` para `feat/github-actions-diario` (prueba previa al merge).
  - Python 3.13, tests, Playwright + Chromium.
  - Histórico SQLite persistido con `actions/cache` en `.cache/disk-search`.
  - Búsqueda con `python nas_discos.py --once --debug`.
  - Guard que falla si la búsqueda devuelve 0 discos.
  - Artifact `nas-discos-<run_number>` con `public/index.html`.
  - Despliegue en GitHub Pages solo cuando `github.ref == refs/heads/main`.
- `scripts/daily.sh`: reproducir el flujo en local.
- `docs/github-actions.md`: activación, histórico, diagnóstico y límites.
- `.gitignore`: `.cache/` y `public/`.
- `README.md` y `AGENTS.md` actualizados.

Verificado en local:

- 22 tests OK.
- `nas_discos.py --demo --once` genera 107 discos.
- `scripts/daily.sh --demo` funciona en una copia temporal.
- YAML válido, 12 pasos, guards de Pages correctos.
- Guard de 0 resultados probado (`unique=0` falla, `unique=1` pasa).
- `scripts/daily.sh` con modo `100755` en git.

Pendiente:

- Revisar el resultado real de la ejecución en GitHub Actions.
- Decidir cómo publicar (el repo resultó ser privado).
- Quitar el trigger temporal `push` antes del merge.
- Hacer merge solo después de validar.

## Hallazgo importante: el repo es privado

`https://github.com/Elicupra/nas-discos` devuelve `404` sin autenticación,
mientras que el perfil del usuario devuelve `200`. Por tanto, el repositorio
es privado (o no visible públicamente), no público como se asumió al principio.

Consecuencias:

- **GitHub Pages** en repos privados requiere plan de pago (Pro/Team/Enterprise).
  En el plan gratuito, el despliegue fallará tras el merge.
- Los **minutos de Actions** de repos privados consumen cuota. Una ejecución
  diaria de 10–30 min puede quedar dentro de los 2.000 min gratuitos, pero hay
  que vigilarlo.
- Los **artifacts** siguen siendo privados y descargables por quien tenga acceso
  al repo.

No cambiar la visibilidad del repositorio sin permiso explícito del usuario.

## Decisión pendiente

| Opción | Repo | Pages | Coste | Código privado | URL pública | Complejidad |
|---|---|---|---|---|---|---|
| 1. Hacer público + Pages | Público | Sí | Gratis | No | Sí | Baja |
| 2. Privado + solo artifact | Privado | No | Gratis | Sí | No | Baja |
| 3. Privado + repo público aparte | Privado | Sí, en otro repo | Gratis | Sí | Sí | Media |
| 4. Privado + plan de pago + Pages | Privado | Sí | Plan de pago | Sí | Sí | Baja |

Recomendación:

- Si el código puede ser público: **opción 1**.
- Si debe seguir privado y no hay plan de pago: **opción 2**.
- Si debe seguir privado pero hace falta URL pública: **opción 3**.
- Si ya hay plan de pago: **opción 4**.

## Opción 1 — Hacer público el repositorio y usar Pages

**Cuándo:** el código y el HTML pueden ser públicos; se quiere la solución más
simple y gratuita.

**Pasos para el modelo:**

1. Confirmar con el usuario que acepta hacer público el repo.
2. El usuario cambia la visibilidad en GitHub:
   **Settings → General → Danger Zone → Change repository visibility → Make public**.
   El modelo no debe cambiarla por su cuenta.
3. Verificar que la ejecución de la rama terminó bien en Actions.
4. Quitar el trigger temporal `push` del workflow antes del merge:
   ```yaml
   push:
     branches:
       - feat/github-actions-diario
   ```
5. Commit: `ci: elimina trigger temporal de prueba`.
6. Push y merge a `main` cuando el usuario lo autorice.
7. Activar Pages: **Settings → Pages → Build and deployment → Source: GitHub Actions**.
8. Lanzar `workflow_dispatch` desde `main`.
9. Comprobar:
   - URL `https://eliqupra.github.io/nas-discos/`.
   - Artifact `nas-discos-<n>`.
   - Histórico restaurado en una segunda ejecución (el log debe indicar que
     restauró una clave `disksearch-history-...` anterior).

**Criterios de aceptación:** workflow verde, página con discos, artifact
descargable, histórico persistente.

**Riesgos:** el código y los precios/histórico embebido pasan a ser públicos;
posibles bloqueos anti-bot desde IPs de GitHub.

## Opción 2 — Mantener privado y publicar solo artifact

**Cuándo:** el repo debe seguir privado y no se quiere pagar Pages. La más
segura y sencilla sin coste.

**Cambios en `.github/workflows/disk-search-daily.yml`:**

1. Dejar solo:
   ```yaml
   permissions:
     contents: read
   ```
2. Eliminar el bloque `environment:` del job.
3. Eliminar los tres pasos de Pages:
   - `Configurar Pages`
   - `Empaquetar sitio`
   - `Desplegar en Pages`
4. Mantener tests, caché, búsqueda, guard de 0 resultados y
   `actions/upload-artifact@v4`.
5. Opcional: renombrar el workflow a `Búsqueda diaria de discos (artifact)`.

**Documentación:**

- En `docs/github-actions.md` y `README.md`, quitar la URL de Pages y las
  instrucciones de **Settings → Pages**.
- Explicar que el resultado se descarga desde **Actions → ejecución →
  Artifacts**.
- Mantener las limitaciones de caché, anti-bot y caducidad del artifact
  (30 días).

**Pasos:**

1. Editar workflow y docs.
2. Validar YAML y ejecutar tests + demo.
3. Commit: `ci: publica solo el artifact sin Pages`.
4. Push (confirmar antes; el trigger temporal lanza una búsqueda).
5. Verificar en Actions que el job termina verde y que el artifact existe.
6. Quitar el trigger temporal `push` antes del merge.
7. Merge solo tras validar.

**Criterios de aceptación:** el workflow no referencia Pages ni `pages: write`;
el artifact contiene `index.html` con discos; no se publica nada en una URL
pública.

**Riesgos:** no hay web consultable, solo artifact; caduca a los 30 días.

## Opción 3 — Privado + publicación en un repo público aparte

**Cuándo:** el código debe seguir privado pero se quiere una URL pública.

**Diseño:**

- `Elicupra/nas-discos` (privado): código, workflow, histórico en caché.
- `Elicupra/nas-discos-pages` (público): solo el HTML generado y Pages.

**Pasos:**

1. Crear el repo público `Elicupra/nas-discos-pages`.
2. Activar Pages en ese repo:
   **Settings → Pages → Source: Deploy from a branch → `gh-pages` / root**.
3. Crear un token fine-grained con acceso solo a ese repo y permiso
   **Contents: Read and write**.
4. Guardar el token como secret en el repo privado:
   `PAGES_REPO_TOKEN` en **Settings → Secrets and variables → Actions**.
5. Añadir al workflow, después del guard de resultados:
   ```yaml
   - name: Publicar en el repo público
     if: success() && github.ref == 'refs/heads/main'
     uses: peaceiris/actions-gh-pages@v3
     with:
       personal_token: ${{ secrets.PAGES_REPO_TOKEN }}
       external_repository: Elicupra/nas-discos-pages
       publish_branch: gh-pages
       publish_dir: ./public
       commit_message: "deploy: ${{ github.run_number }}"
   ```
6. Eliminar del workflow los pasos de Pages del repo privado y los permisos
   `pages: write` / `id-token: write`; el token del secret es suficiente.
7. Mantener el artifact en el repo privado para diagnóstico.
8. Documentar en `docs/github-actions.md`: repo de publicación, secret,
   rotación del token y que el HTML es público pero el histórico no.
9. Validar con una ejecución manual en `main` y comprobar la URL del repo
   público.

**Criterios de aceptación:** workflow privado verde; commit en `gh-pages` del
repo público; Pages del repo público muestra los discos; el token no aparece
en logs ni en el repo.

**Riesgos:** dos repos y un token que mantener; si caduca, falla la
publicación; el HTML es público.

## Opción 4 — Privado + plan de pago + Pages

**Cuándo:** ya existe plan Pro/Team/Enterprise y se quiere Pages en el repo
privado.

**Pasos:**

1. Confirmar que el plan incluye Pages para repos privados.
2. Activar Pages: **Settings → Pages → Source: GitHub Actions**.
3. Quitar el trigger temporal `push` antes del merge.
4. Merge y ejecutar `workflow_dispatch` desde `main`.
5. Comprobar URL, artifact e histórico.

**Criterios de aceptación:** Pages funciona desde el repo privado; workflow
verde; artifact e histórico operativos.

**Riesgos:** coste recurrente del plan y consumo de minutos de Actions.

## Plan de ejecución común (cualquier opción)

1. **Revisar el estado actual**
   ```bash
   cd /home/ubuntu/red/repos/disk-search
   git status
   git log --oneline -5
   ```
2. **Revisar la ejecución en GitHub**
   - Abrir `https://github.com/Elicupra/nas-discos/actions`.
   - Ver el run de `feat/github-actions-diario`.
   - Si falló, leer el paso `Buscar discos` y el guard `Comprobar resultados`.
3. **Confirmar la opción con el usuario** antes de tocar nada.
4. **Implementar solo lo necesario** de la opción elegida.
5. **Verificar en local**
   ```bash
   /home/ubuntu/.venvs/disk-search/bin/python -m unittest discover -s tests -v
   scripts/daily.sh --demo
   ```
   Y validar el YAML:
   ```bash
   python3 - <<'PY'
   import pathlib, yaml
   wf = yaml.safe_load(pathlib.Path(".github/workflows/disk-search-daily.yml").read_text())
   print(wf["name"], len(wf["jobs"]["search"]["steps"]))
   PY
   ```
6. **Commit pequeño** en imperativo (`ci:`, `docs:`, `fix:`).
7. **Push con confirmación** (el trigger temporal lanza una búsqueda real).
8. **Verificar el run** y el artifact; si aplica, la URL de Pages.
9. **Quitar el trigger temporal `push`** antes del merge.
10. **Merge solo tras validación** y comprobar el cron y `workflow_dispatch`
    en `main`.
11. **Segunda ejecución** para confirmar que la caché del histórico se
    restaura.

## Reglas para el modelo ejecutor

- No trabajar directamente en `main`; usar una rama `feat/`, `fix/` o `ci/`.
- No hacer merge ni push sin confirmación explícita.
- No cambiar la visibilidad del repositorio ni crear tokens sin permiso.
- No editar `data/`, `*.sqlite3` ni `nas_discos.html` del repo local.
- No commitear `.cache/` ni `public/`.
- No añadir secretos al repo; usar GitHub Secrets.
- No prometer que Pages funciona en repo privado gratuito: verificar el plan.
- Si el guard de 0 resultados falla, es intencional: no desactivarlo sin
  discutirlo; revisar bloqueos anti-bot.
- Mantener el estilo de commits y documentación del repo (`AGENTS.md`).

## Comandos útiles

```bash
# entorno ya existente
source ~/.venvs/disk-search/bin/activate

# tests
python -m unittest discover -s tests -v

# demo local
python nas_discos.py --demo --once

# flujo completo local
scripts/daily.sh --demo
scripts/daily.sh --debug

# estado de git
git status
git log --oneline -5
git diff --stat main...HEAD
```

## Archivos relevantes

```text
.github/workflows/disk-search-daily.yml   workflow diario
scripts/daily.sh                          ejecución local
docs/github-actions.md                    documentación de despliegue
README.md                                 resumen y enlaces
AGENTS.md                                 convenciones del proyecto
nas_discos.py                             CLI (--once, --demo, --debug)
disksearch/config.py                      fuentes y configuración
```

## Resultado esperado

Una de estas dos situaciones, validada antes del merge:

- **Con Pages:** una URL diaria con el HTML de discos y un artifact por
  ejecución.
- **Sin Pages:** un artifact diario descargable con el HTML de discos.

En ambos casos el histórico SQLite debe conservarse entre ejecuciones mediante
la caché de Actions y el workflow debe terminar en verde salvo que la búsqueda
devuelva 0 discos, en cuyo caso debe fallar sin publicar.
