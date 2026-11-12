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
| Sprint 2 | UI del histórico | #9 (SPEC_9), #10 (SPEC_10) |
| Backlog | Mejoras sin fecha | #11 y futuros |

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

## Estado actual (2026-11-12)

- Pendiente de cerrar a mano: **#2, #3, #4, #5, #6** (todo Sprint 0 está
  resuelto en `main`; el token no tenía permiso para cerrarlos).
- Pendiente de decidir: **#7** (publicación) y **#11** (recorte de páginas).
- Pendiente de implementar: **#9 (SPEC_9)** y **#10 (SPEC_10)**.
- Milestones/labels: crearlos a mano en *Issues → Milestones/Labels*
  siguiendo la tabla de sprints (el token de API no tiene ese permiso).
