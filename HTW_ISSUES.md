# HTW_ISSUES.md — Cómo gestionar las tareas con GitHub Issues

Guía para el humano: aquí está el método ágil acordado para controlar el
proyecto desde la pestaña **Issues** de `Elicupra/nas-discos`.

## Principios

1. **Todo trabajo tiene un issue antes de empezar** y se cierra cuando sus
   criterios de aceptación pasan los tests de regresión.
2. **Los issues [Decisión] no se implementan**: se responden con un
   comentario y solo entonces se desbloquea el trabajo dependiente.
3. Un issue bloqueado lo indica en su cuerpo ("bloqueado por #n"); GitHub
   no lo oculta, así que se revisa el tablero de arriba abajo.
4. Cada SPEC del repo (`docs/plans/SPEC_x.md`) corresponde a un issue; el
   issue es el estado vivo, el SPEC es el detalle técnico estable.

## Sprints (iteraciones)

| Sprint | Tema | Issues |
|---|---|---|
| Sprint 0 | Histórico operativo en rama `state` | #2–#6 (resueltos) |
| Sprint 1 | Publicar el histórico en GitHub | #7 (decisión), #8 (SPEC_8) |
| Sprint 2 | UI del histórico | #9 (SPEC_9), #10 (SPEC_10), #13 (SPEC_11), #14 (SPEC_12) |
| Sprint 3 | SSD, agregador y búsqueda acotada | #20 (SPEC_13), #21 (SPEC_14), #22 (SPEC_15) |
| Backlog | Mejoras sin fecha | #11, #15, #23 y futuros |

**Regla de avance:** no se empieza el sprint siguiente hasta que el actual
no tenga issues abiertos (o se re-planifique).

## Convención de títulos

`[Sprint n][Tipo] título corto`. Tipos:

- `[Resuelta]` — hecho y cerrado (queda como histórico/incidencia resuelta).
- `[Spec]` — trabajo funcional definido en un SPEC_x.md.
- `[Decisión]` — bloquea a otros; se cierra comentando la decisión tomada.
- `[Backlog]` — sin sprint asignado.

*(Cuando existan labels/milestones, estas etiquetas de título se traducen a
labels `spec`/`incidencia`/`decision-pendiente` y milestones por sprint.)*

## Rutina de gestión (5 minutos al día)

1. Abrir **Issues** ordenado por *Recently updated*.
2. Cerrar lo resuelto en el último run/PR (verificar contra los criterios
   de aceptación del issue).
3. Revisar los `[Decisión]`: si hay alguno abierto, es lo primero que
   toca decidir (comentar la decisión cierra el bloqueo).
4. Del sprint activo, elegir un `[Spec]` abierto y trabajarlo en una rama
   `feat/…` (las reglas de rama están en `AGENTS.md`).
5. Al cerrar, referenciar el issue en el mensaje de commit
   (`feat: ... (#9)`) para que quede enlazado.

## Estado actual (2026-11-13)

Mergeado en `main` (PRs #17, #18, #19): SPEC_9, SPEC_10, SPEC_11, SPEC_12.
Pendiente de mergear (ramas ya en `origin`, sin PR): SPEC_13 (#20, `feat/ssd-m2`),
SPEC_14 (#21, `feat/geeknetic`) y SPEC_15 (#22, `feat/busqueda-acotada`).

- **Cerrar a mano** (resuelto o decidido, el token de API no cierra issues):
  - **#9 (SPEC_9)**: implementado y mergeado en PR #17.
  - **#13 (SPEC_11)**: implementado y mergeado en PR #18.
  - **#14 (SPEC_12)**: implementado y mergeado en PR #19.
  - **#2 `test-permiso`**: prueba antigua, sin trabajo pendiente.
- **Implementado, cerrar tras merge**: **#20, #21, #22** (SPEC_13/14/15).
- **Abierto con decisión pendiente**: **#11** (recortar páginas).
- **Abierto sin fecha**: **#15** (paralelismo real entre tiendas).
- **Nuevo**: **#23** (`[Bug] --once rompe el callback de progreso`) →
  `fix/once-progress`. Al mergear, el workflow diario vuelve a completar y
  puede publicar en `nas-discos-pages`.
- Milestones/labels: crearlos a mano en *Issues → Milestones/Labels*
  siguiendo la tabla de sprints (el token de API no tiene ese permiso).
