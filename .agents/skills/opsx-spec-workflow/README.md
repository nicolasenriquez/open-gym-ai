# OpenSpec workflow — guía de uso

Dos skills coordinan el trabajo sin sustituir OpenSpec ni sus especialistas:

```text
opsx-spec-workflow
  Investigar → resolver decisiones → especificar → validar
  Implementation Ready — STOP
         │ aprobación de alcance y seams + solicitud de implementación
         ▼
opsx-delivery-workflow
  OpenSpec Apply → slices con prueba/checkpoint → verificación → review
  Ready for closeout — STOP
         │ autorización de sincronización y archivado
         ▼
OpenSpec Sync → OpenSpec Archive
```

Un seam es la interfaz pública desde la que una prueba observa el comportamiento.
Aprobar los seams evita repetir esa pregunta en cada test; no autoriza implementar.

## Prompts para copiar

Son instrucciones en lenguaje natural, no comandos slash universales. El harness
necesita poder descubrir las skills; si aún no aparecen, pide que lea su SKILL.md
por ruta. Esta guía no instala adaptadores ni garantiza registro entre harnesses.

### 1. Planificar

> Lee `.agents/skills/opsx-spec-workflow/SKILL.md` y úsala para preparar un cambio
> que permita <objetivo>. Investiga primero, define alcance, seams y slices con
> checkpoints. No implementes. Detente en Implementation Ready o explica el bloqueo.

Para un bug, describe síntoma, pasos y resultado esperado. El workflow usa
`diagnosing-bugs` para reproducción; cualquier escritura de pruebas diagnósticas
requiere acordar su alcance y seams. La planificación no aplica el fix de producción.

### 2. Aprobar e implementar

> Apruebo el alcance y los seams documentados de `<change-name>`. Lee
> `.agents/skills/opsx-delivery-workflow/SKILL.md` e implementa y verifica por slices.
> Corrige problemas dentro de ese alcance. Detente antes de sincronizar, archivar,
> hacer commits o publicar cambios.

### 3. Reanudar

> Continúa `<change-name>` con opsx-delivery-workflow. Revisa el diff y las notas,
> revalida la evidencia afectada y retoma la siguiente slice. Conserva el trabajo ajeno.

### 4. Cerrar

> Si `<change-name>` no tiene tareas obligatorias ni checks pendientes, autorizo
> sincronizar sus delta specs y archivarlo. Comprueba las condiciones antes de actuar.
> No hagas commit, push ni despliegue.

## Cómo se eligen los especialistas

- Falta orientación: un Prime por superficie; no los tres por rutina.
- Bug: `diagnosing-bugs`; interacción de stores: `click-path-audit`.
- Interfaz de módulo o seam incierto: `codebase-design`.
- UI/UX: `impeccable`; interacción accesible: `frontend-a11y`.
- Runtime: `tdd`; componentes y hooks: `react-testing`.
- Flujos guest existentes: `verify-opengym` y su mapa.
- Navegador interactivo: `playwright-cli`; regresión E2E: `e2e-testing`.
- Revisión habitual: `ponytail-review`; reglas posiblemente obsoletas: `rules-check-drift`.

No todas participan en cada cambio. Se consulta cada SKILL.md antes de usarla.
Si faltan herramientas o dependencias, se informa la adaptación o el bloqueo;
no se afirma haber ejecutado el método completo.

## Límites y evidencia

OpenSpec conserva las tareas y el progreso; no se crea otro tracker. Apply es el
único ejecutor que actualiza checkboxes. Los especialistas entregan evidencia o
hallazgos. Un RED de contrato completa esa prueba inicial, no la implementación.

`openspec validate` comprueba artefactos, no el funcionamiento de la app.
`verify-opengym` acredita los recorridos guest ejecutados, no autenticación, sync,
Coach, MCP o móvil por extensión. Una captura no demuestra persistencia.
Los checks requeridos no ejecutados bloquean la declaración de readiness.

El mantenimiento global del harness, la creación de PRs y las auditorías de todo
el repo se solicitan aparte; no son pasos automáticos de una feature.

## Prueba piloto pendiente

Antes de considerar estable el workflow, ejercitar:

| Caso | Resultado esperado |
| --- | --- |
| Docs-only | Comprobación de coherencia; sin TDD ni navegador forzados. |
| Bug de dominio | Reproducción, seam aprobado, RED conductual y GREEN. |
| UI con persistencia | Interacción real y estado después de recarga u otra vista. |
| Herramienta ausente | Adaptación explícita o bloqueo; nunca ejecución ficticia. |
| Reanudación parcial | Preservar cambios y revalidar evidencia afectada. |
| Cierre incompleto | Bloquear sync/archive aunque exista autorización condicional. |

Estos son criterios de aceptación, no resultados de pruebas ya ejecutadas.
