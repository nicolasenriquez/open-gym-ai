# Streamline Platform Architecture and Maintenance

## Why

Los agentes trabajan principalmente sobre ejemplos del propio repositorio. Hoy encuentran dependencias hacia composición HTTP, coordinación Training–Coach implícita, sincronización frontend concentrada y referencias que todavía enseñan el runtime retirado. Necesitamos propietarios claros y reglas comprobables en CI para localizar, realizar y verificar cada intervención.

## What Changes

- Rebasar el plan sobre Python/FastAPI/PostgreSQL, `/api/v1`, biblioteca JavaScript neutral y verificadores actuales. La API Node y el comparador transitorio ya están retirados; no repetir esa entrega.
- Separar metadata pura y coordinar Training–Coach con un iniciador, una transacción compartida y efectos posteriores al commit.
- Comprobar interfaces públicas y dependencias permitidas en CI, con errores que indiquen ruta, regla y reparación; reutilizar runners existentes.
- Mantener una autoridad persistente frontend y organizar Training, Identity, Coach, Media, Administration y Notifications por recorridos, sin carpetas o fachadas vacías.
- Retirar implementaciones sustituidas y referencias activas que las presentan como actuales. No guardar copias ejecutables bajo `legacy/`, `archive/` o nombres alternativos. Separar esto de la retirada de compatibilidades todavía consumidas.
- Adoptar cero comentarios narrativos en fuente propia mantenida: expresar reglas en nombres, interfaces, validaciones y pruebas; trasladar contratos y restricciones externas a su documentación propietaria. Preservar avisos de licencia y sintaxis efectiva de herramientas hasta reemplazarla con una configuración equivalente comprobada.
- Adoptar Oxfmt 0.76.0 con la [configuración ensayada](formatter.config.json), incluida objectWrap=collapse, e integrar formateo/check de comentarios al flujo existente durante entrega. Conservar Ruff en Python y cambios mecánicos separables.
- Verificar onboarding con seis preguntas de navegación/verificación por cliente soportado. La portabilidad se demuestra por cliente; formato compartido no garantiza descubrimiento universal.
- Mantener Dockerfiles de producto junto a su propietario y ordenar recetas transversales bajo `deploy/`, comprobando contexto, aislamiento e identidad operativa.
- Conservar etapa 9 como aceptación documental final, con comandos y consumidores contrastados contra el árbol resultante.

## Capabilities

### New Capabilities

- `post-port-maintainability`: propiedad modular, colaboración transaccional, sincronización con autoridad única, controles CI, formateo y onboarding comprobable.
- `repository-evidence-hygiene`: retirada de implementaciones sustituidas, sustitución ejecutable de comentarios y limpieza de evidencia por consumidores.
- `container-delivery-organization`: recetas por propietario, contextos mínimos y contratos operativos preservados.

### Modified Capabilities

Ninguna: se preservan contratos de producto. Decisión explícita del promotor el 2026-11-04: eliminar implementaciones sustituidas y decidir aparte las compatibilidades activas. La retirada de soporte offline antiguo o importación Node queda fuera de este cambio; requeriría deltas de requisitos y evaluación BREAKING en su fase específica.

## Impact

Composición/backend, Training–Coach, store y seis capacidades frontend, guías de agentes, verificadores, CI y entrega Docker. Una nueva dependencia dev fijada, oxfmt 0.76.0, para instalar al ejecutar 3.5. El ensayo usó herramientas aisladas; package.json/locks/CI del proyecto no se modificaron. Sin dependencia nueva de runtime.

Sin endpoints, DDL, microservicios, gestor de monorepo, conversión general a TypeScript ni runtime de agentes nuevo. Sin operaciones reales, publicación, despliegue, commit/push, sincronización de specs o archivado. Este cambio es independiente de otras OpenSpec.

## Planning readiness

**Implementation Ready**, revisada el 2026-11-04. Alcance de compatibilidades activas resuelto y ensayo del formatter completado: versión, configuración, exclusiones y comandos fijados. La [auditoría y bibliografía](design.md#auditoría-de-la-propuesta-original) conserva la nota 68/100 de la versión anterior; no es una nota de implementación. El [plan de verificación](verification-plan.md#ensayo-del-formatter-completado-el-2026-11-04) registra prueba y límites. Las 60 tareas de entrega siguen pendientes; no se inicia refactor, instalación en el proyecto, CI, commit/push, sync ni archive.
