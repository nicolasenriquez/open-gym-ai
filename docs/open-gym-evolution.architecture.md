---
type: Architecture
title: OpenGym Evolution — arquitectura Python/FastAPI/PostgreSQL
description: Contratos, transición y gates de la plataforma objetivo Python/FastAPI/PostgreSQL.
---
# OpenGym Evolution — arquitectura Python/FastAPI/PostgreSQL

## Estado y alcance del documento

**Estado:** dirección y cleanup documental autorizados el 2026-10-22. Esta arquitectura sustituye la dirección Node inicial por la prioridad estratégica del promotor descrita en el [PRD Evolution](open-gym-evolution.prd.md), no por un fallo demostrado de Node. Las alternativas y el motivo se mantienen en §3. No acredita implementación ni gates satisfechos.

**Alcance:** documentación de dirección, contratos y aceptación; no ejecuta código, OpenSpecs, instalaciones, migraciones o despliegues. Una modificación futura debe identificar la decisión que sustituye y su motivo.

**Ampliación modular:** por solicitud posterior del promotor, se concreta la organización por vertical slices en la [referencia de modularidad](reference/platform-modularity.md). Sustituye la colocación futura no definida por propiedad funcional de contratos, reglas, operaciones y consultas, conservando el frontend y sus comportamientos. Esta revisión modifica únicamente documentación y artefactos del cambio activo; no implementa el destino ni altera evidencia histórica.

**Fuentes de intención:** [PRD Evolution](open-gym-evolution.prd.md) para la entrega de plataforma y [PRD aprobado de Recovery](open-gym-recovery.prd.md) para sus requisitos funcionales posteriores. Complementos: [discovery](dev/personal-recovery-discovery.md) y [glosario](../GLOSSARY.md). La arquitectura define mecanismos y aceptación técnica; no amplía el MVP funcional de Recovery. La evidencia sintética archivada conserva su alcance histórico.

**Lectura:** decisiones aprobadas, recomendaciones y pendientes no equivalen a pruebas ejecutadas. Este plan no es DDL ni tareas de implementación. Leer [seguridad](reference/platform-security.md) al modificar acceso/audit, [observabilidad](reference/platform-observability.md) al instrumentar/operar y [contratos Recovery](reference/recovery-contracts.md) para su entrega posterior. El [índice documental](README.md#documentation-authority) delimita fuentes de verdad.

## 1. Objetivo y límites

Completar la transición de la aplicación servidor a un monolito modular Python/FastAPI, con PostgreSQL como autoridad del estado duradero migrado y operación reproducible en contenedores. Preservar el frontend React/Vite/Zustand, Training, sincronización/offline, catálogo, autenticación, medios, administración, notificaciones, coach y MCP. La ejecución será incremental; el destino no incluye una API Node de negocio permanente.

**Primera entrega: plataforma.** Caracterizar contratos, preparar Python/PostgreSQL con datos sintéticos, demostrar paridad, ensayar importación/recuperación, realizar un corte controlado y retirar el código sustituido. Su aceptación requiere G0–G3, GP y GO de §12; no requiere implementar Recovery ni validar sus tres sesiones reales.

**Entregas posteriores:** Recovery completo según PRD y G4/G5 → Garmin Connect con alcance/acceso verificados → ampliaciones de IA con evaluación y consentimiento. No comenzar su implementación funcional antes de aceptar plataforma. Recovery mantendrá identidad, Training compatible, dominio aislado, guardado confiable, snapshots, recuperación y experiencia web responsive. LangChain/LangGraph, pgvector, colas y Kubernetes no son dependencias anticipadas.

**Monolito y contenedores:** una sola aplicación backend con módulos internos, una unidad de release y tres servicios Compose iniciales: `web` (nginx/estáticos), `api` (FastAPI) y `db` (PostgreSQL privado). Migraciones como proceso puntual separado del runtime. Esto no exige una imagen conjunta ni introducir microservicios; PostgreSQL conserva su contenedor y volumen propios. No implica portar la UI ni todos sus helpers a Python.

La [construcción/caché](reference/platform-modularity.md#construcción-y-caché-verificables), los [targets entregables](reference/platform-modularity.md#targets-e-imagen-entregable) y la [matriz de ambientes](reference/platform-modularity.md#matriz-de-ambientes-y-comandos-objetivo) tienen aceptación por fase: Foundation prueba imágenes de ensayo; el port prepara desarrollo/CI; operación entrega runtime/migrador y combinaciones Compose explícitas. Linux/amd64 es el alcance inicial de evidencia Python; arm64 y cualquier retirada de soporte previo requieren prueba/decisión expresa antes del corte. Esta edición no cambia Dockerfiles, Compose, lockfiles ni workflows.

## 2. Base de evidencia y límites de la auditoría

### 2.1 OpenGym

As-Is de la revisión `2cc7ee1f`: Node/archivos, frontend/API `1.4.1`, Compose `api` + `web`; Foundation Node sintética archivada, sin corte ni backend Python. La [evidencia histórica completa](research/evolution-architecture-evidence.md#21-opengym) conserva checkouts, digests, comparación de archivos y límites de las observaciones. Esta edición documental no aporta pruebas nuevas.

### 2.2 Datos locales de clientes

G0 exige inventario y backups comprobados por origen/perfil, cuenta/invitado, sesión activa, pendientes y medios antes del corte. Los límites del export y la [observación original](research/evolution-architecture-evidence.md#22-datos-locales-de-clientes) siguen aplicando; preservar almacenamiento local hasta resolverlos.

### 2.3 AI Tutor como referencia

La [comparación histórica](research/evolution-architecture-evidence.md#23-ai-tutor-como-referencia) conserva revisión y fuentes. Adoptar lifecycle/pool, transacciones, repositorios, lockfiles y referencias por tarea; adaptar auth, despliegue y pruebas al contrato OpenGym. Los contratos objetivo se definen aquí y en las referencias, no en el código o artículos de otro producto.

## 3. Decisiones y alternativas consideradas

### 3.1 Aprobadas

| Decisión | Alcance |
| --- | --- |
| Python/FastAPI como backend objetivo | Sustituir la aplicación servidor Node con paridad de capacidades. Node queda como referencia durante la transición, no como entrega productiva intermedia obligatoria. |
| PostgreSQL principal | Autoridad del estado duradero servidor migrado. Almacenes residuales inventariados; medios, secretos, catálogo y almacenamiento local cliente pueden permanecer fuera con contrato explícito. |
| Plataforma antes de Recovery | Cerrar G0–G3/GP/GO antes de implementar Recovery; luego Garmin y ampliaciones de IA. Las tres sesiones reales validan Recovery, no la arquitectura. |
| SQL explícito | Sin ORM obligatorio ni normalización completa de Training. |
| Training en JSONB | Documento compatible, revisiones, linaje, stamps, sync y offline existentes. |
| Recovery relacional + JSONB selectivo | Relaciones/invariantes y snapshots históricos sin normalización excesiva. |
| Paridad antes del corte | Inventario de capacidades, Foundation Python, pruebas de contratos y consumidores en entorno sintético; G0 antes de cualquier migración real. |
| RLS para Recovery, condicionada | Debe pasar pruebas reales de propietario, transacciones y pool; no se puede declarar efectiva antes. |
| Frontend y experiencia actuales | React/Vite/Zustand, componentes, catálogo, acceso rápido y PWA. |
| Vertical slices en monolito modular | Cada funcionalidad posee contratos, reglas, operaciones y consultas. Infraestructura común pequeña; frontend actual con componentes/hooks/clientes de propiedad explícita, mejorados por área sin reorganización masiva. Ver §5.1. |
| Una autoridad por dominio | Sin dual-write permanente, espejos autoritativos ni fallback silencioso a archivos. |
| Pool async y migrador único | Dirección técnica: `asyncpg` y Alembic según §8; versiones, locking y recuperación pendientes de prueba en Python. `pg`/`node-pg-migrate` describen la Foundation histórica. |
| G0 obligatorio antes del corte | Foundation puede investigarse y probarse previamente con datos sintéticos; eso no habilita el corte ni acredita el inventario. |
| Garmin Connect y ampliaciones del AI Coach | Iniciativas posteriores a plataforma y Recovery, con producto/acceso/datos por definir. Preservar el coach actual pertenece a plataforma. |

### 3.2 Alternativas históricas

A conservadora sobre archivos, B híbrida y C modernización amplia fueron evaluadas en la decisión anterior. La API Node inicial y `pg`/`node-pg-migrate` fueron seleccionados para llegar a Recovery y produjeron Foundation sintética. Esta revisión sustituye esa dirección por petición del usuario, conserva sus garantías de datos y mantiene su evidencia histórica.

Para el nuevo objetivo se compararon: (1) preparar Python/PostgreSQL aislado y cortar cuando exista paridad, (2) migrar primero Node a PostgreSQL y portar después, y (3) reemplazar también frontend y modelo Training. Se adopta (1) para evitar una transición productiva intermedia; (2) solo se reconsideraría por un riesgo operativo demostrado y (3) amplía el cambio sin necesidad. Un corte controlado único exige ensayos y ventana de mantenimiento; no implica un único PR ni un salto sin pruebas.

## 4. As-Is y To-Be

### As-Is verificado

```text
React/Vite/Zustand
  ├─ Training local + sesión activa + sync
  ├─ catálogo y ejercicios propios
  └─ PWA: shell y medios offline
                │ mismo origen
             nginx /api
                │
          API Node node:http
  ├─ identidad en memoria + db.json
  ├─ Training: state-<uid>.json
  ├─ coach, administración, recordatorios
  └─ medios y secretos en filesystem

MCP y otros consumidores acceden directamente a archivos.
```

Evidencia: `frontend/src/store/useStore.js`, `frontend/public/sw.js`, `api/server.js:117`, `api/server.js:2169`, `api/durable.js`, `docker-compose.yml`. La API excluye `active` de Training al guardar (`api/server.js:2242`). La escritura síncrona permite comparación/escritura atómica solo dentro del proceso actual; cambiar a acceso asíncrono exige transacciones explícitas.

### To-Be aprobado a nivel arquitectónico

```text
Frontend actual: React/Vite/Zustand, Training local/offline/sync
                   │ mismo origen
           web: nginx + catálogo/estáticos
                   │ /api
           api: Python / FastAPI
  identidad / Training / medios / admin / push / coach actual
                   │ repositorios
           db: PostgreSQL privado
       identidad / documento Training / estado migrado

Medios: filesystem protegido, referencias duraderas.
Secretos: gestión externa/protegida, no frontend ni tablas de dominio.
Migraciones: proceso previo con rol separado, un solo historial.
MCP: cliente stdio opcional, contrato Training restringido.
Después de plataforma: Recovery → Garmin → ampliaciones de IA.
```

Mantener inicialmente un solo proceso/réplica API. PostgreSQL no distribuye automáticamente retos WebAuthn, presencia, limitadores ni estado de jobs en memoria. Recovery será un módulo posterior dentro del backend; un conector Python no exige un servicio de negocio adicional.

## 5. Límites y responsabilidades

| Módulo | Responsabilidad y contrato |
| --- | --- |
| Frontend Training | Mantener edición local, merge, perfil, sync y offline. No convertir PostgreSQL en requisito de cada interacción offline. |
| Frontend Recovery | Cambios pendientes, comandos explícitos, validación del recibo y errores; nunca introducir datos en `S.workouts`, `S.active` o `S.customEx`. |
| Transporte compartido | Reutilizar `frontend/src/lib/api.js`: mismo origen/subpath, timeout y rechazo de respuestas no JSON. Recovery valida además su contrato de éxito. |
| API | Autenticación, origen/CSRF, ownership, validación estricta, límites y errores no sensibles. |
| Dominio Recovery | Reglas puras de procesos, indicaciones, sesiones, contexto y correcciones; sin progresión automática. |
| Persistencia | SQL parametrizado, conexiones y transacciones; no presentación ni reglas de Training. |
| Identidad | Mismos identificadores y semántica de passkeys, sesiones, revocación, roles y deshabilitación. |
| Coach/MCP | Lectura exclusivamente autorizada de Training; sin privilegios sobre Recovery. |
| Operación | Migraciones, backups, restauración, secretos y control de versión compatible. |

Las filas Recovery describen contratos de la entrega posterior; no autorizan crear su esquema o interfaz durante plataforma. Node puede mantenerse como herramienta de build, cliente MCP stdio y dependencia auxiliar opcional expresamente justificada del coach; no como API HTTP de negocio necesaria para cerrar plataforma. Antes del cierre se debe demostrar la viabilidad de cada proveedor/SDK/CLI y su sandbox, o resolver explícitamente su tratamiento sin eliminar capacidades silenciosamente.

Para reutilización futura de catálogo/controles y aislamiento de datos Recovery, leer [interfaz y componentes](reference/recovery-contracts.md#reutilización-e-interfaz).

Separación modular no equivale a sandbox frente al administrador del host ni a una API comprometida. Se requieren permisos y contratos, no solo carpetas diferentes.

### 5.1 Organización por funcionalidad y contratos

La [propuesta modular](reference/platform-modularity.md) es la fuente propietaria del mapa de módulos, árboles objetivo, reglas de dependencia, contratos Pydantic, correspondencia frontend, composición Docker y evidencia por slice. Concentra cada caso de uso en su módulo; evita nuevos directorios globales de controllers/services/repositories que dispersen una misma funcionalidad. Los archivos se crean por necesidad, sin capas de paso.

Foundation implementará solo infraestructura y salud cuando se autorice. El port posterior usará como piloto la lectura/guardado Training compatible, con identidad previa, transacción, conflictos y reconciliación del frontend actual. El mapa completo no autoriza crear módulos vacíos, nuevas tablas de negocio o Recovery durante Foundation. La aceptación EV-09 se incorpora a GP/GO/G3, sin nuevo gate ni reemplazo de paridad.

El [contrato transaccional intermodular](reference/platform-modularity.md#transacción-entre-operaciones-de-módulos) fija un iniciador y un handle compartido sin commits internos; Foundation prueba colaboradores sintéticos y el port casos reales. La [biblioteca JS neutral](reference/platform-modularity.md#biblioteca-javascript-compartida-y-retirada-de-api) conserva coach local y generadores antes de retirar `api/`: su destino es `shared/coach-core/`, sin API Node de negocio permanente. No eliminar el árbol legacy hasta verificar imports y builds actualizados.

## 6. Modelo conceptual PostgreSQL

**No es DDL aprobado ni nomenclatura definitiva.** Durante plataforma:

| Concepto | Relacional | JSONB selectivo |
| --- | --- | --- |
| Usuario | ID heredado, estado, roles, versión de sesión | Atributos heredados preservados durante transición |
| Credencial e identidad auxiliar | Propietario, ID credencial, contador, relaciones relevantes | Metadatos WebAuthn/atributos heredados cuando corresponda |
| Training compatible | Propietario, revisión/linaje sincronizados con el documento | Documento existente completo |

- Conservar IDs de usuario; no exigir UUID para identidades heredadas.
- Coherencia de propietario en asociaciones, preferiblemente respaldada por claves/constraints adecuadas, además de RLS.
- JSONB no autoriza contenido sin contrato: validación de estructura, tamaño y versión, con IDs estables para elementos corregibles.

Para Training, evitar dos copias discordantes de revisión/linaje entre columnas y JSONB. Si se proyectan como columnas, su actualización y serialización deben tener una única regla transaccional probada. Importar también campos internos de sincronización, no solo lo que expone `forClient`.

El [modelo Recovery y sus invariantes](reference/recovery-contracts.md#modelo-conceptual) pertenecen a su entrega posterior.

## 7. Contratos, concurrencia e idempotencia

### Training compatible

Conservar `GET /api/data`, `GET /api/data/rev`, `PUT /api/data`, sus envoltorios y errores, `baseRev`, `baseWid`, `_wid`, `_wids`, stamps, resets y respuestas `409`. Preservar explícitamente comportamientos legacy, incluidas escrituras sin revisión cuando el contrato existente las admite; no endurecerlos inadvertidamente durante el cambio de almacenamiento.

Lectura/comparación/estampado/escritura bajo transacción y serialización por perfil, incluido el caso de primer documento inexistente. No depender del event loop. Conservar la sesión activa como local en Training y sus metadatos de propietario/base. Pruebas de paridad con las suites de revisiones y stamps existentes.

### Recovery

El [contrato de guardado/concurrencia](reference/recovery-contracts.md#guardado-concurrencia-e-idempotencia) define comandos, recibos, versiones, snapshots y generación de restauración de la entrega posterior. Probar restauración Training por linaje además de revisión en plataforma.

## 8. Stack Python, migraciones y evidencia histórica

**Dirección técnica de esta revisión:** FastAPI/Pydantic y Uvicorn; `asyncpg` con SQL explícito; Alembic para esquema; uv y lockfile; pytest/httpx, Ruff y mypy para verificación. Son herramientas objetivo, no dependencias instaladas o versiones verificadas. Mantener npm, Vitest y los controles frontend/MCP pertinentes. La implementación deberá comprobar versiones estables, compatibilidad, licencias y ejecución reproducible antes de fijarlas; no adoptar prereleases sin justificación y aprobación expresa.

El pool se inicializa y cierra mediante lifespan; conexiones/transacciones tienen límites y timeouts probados. SQL permanece en repositorios y reglas de dominio fuera de handlers. SQLAlchemy puede limitarse al engine de migraciones de Alembic; no se impone un ORM a la aplicación. No copiar ajustes pgvector o de pool de AI Tutor sin necesidad.

| Herramienta/enfoque | Estado y razón | Prueba pendiente |
| --- | --- | --- |
| `asyncpg` + Alembic | Objetivo Python, alineado con los patrones pertinentes de AI Tutor y SQL explícito | Lifecycle, cancelaciones/timeouts, rollback, contexto de propietario, locking de migración y recuperación. |
| `pg` + `node-pg-migrate` | Selección anterior, ejecutada en Foundation sintética: pg 8.23.1, migrador 9.0.0 y Node 22.23.2/PG 18.6 | No valida el stack Python ni configura el despliegue objetivo. Conservar evidencia y reutilizar escenarios, sin mantenerlo como migrador del mismo esquema productivo. |
| Node/PostgreSQL antes del port | Alternativa intermedia no adoptada | Solo reconsiderar por evidencia de que reduce un riesgo concreto frente a la preparación directa Python. |
| ORM general o migrador propio | No requeridos | Incorporarlos necesitaría una necesidad concreta; no crear una segunda autoridad de esquema. |

La base actual de archivos no tiene un esquema productivo PostgreSQL que deba convertirse de un ledger Node a Alembic. La especificación posterior debe comprobarlo contra el entorno real. Si aparece una base existente, detener esa suposición y definir su compatibilidad/historial; no inventar un baseline ni marcar revisiones como aplicadas sin validación.

Política de migraciones conservada:

- Un historial y un responsable del esquema compartido; futuros servicios no crean otro migrador sobre las mismas tablas.
- Migrador con rol separado; runtime sin DDL.
- Ejecución única controlada antes de habilitar tráfico compatible, no al arrancar cada réplica.
- Migraciones aplicadas inmutables en Git y releases; no atribuir a la herramienta verificación de checksums no comprobada.
- Cambios aditivos/expandir-compatibilizar-retirar. Operaciones fuera de transacción solo con procedimiento explícito.
- Error bloquea el despliegue; no marcar manualmente una migración como aplicada para eludir validación.
- Cada cambio declara compatibilidad, prueba y recuperación. DDL reversible no implica datos reversibles; usar restore o avance correctivo cuando corresponda.

Alembic no acredita por su nombre ejecución única o recuperación: comprobar concurrencia, interrupción, transacciones y conexión apropiada ante pooler. Separar evolución del esquema de la importación de datos, con equivalencia y recuperación propias. No ejecutar Alembic y `node-pg-migrate` sobre las mismas tablas; el paquete sintético archivado no se transforma en una segunda autoridad.

Referencias: [lifespan FastAPI](https://fastapi.tiangolo.com/advanced/events/), [Alembic async y migraciones de datos](https://alembic.sqlalchemy.org/en/latest/cookbook.html#using-asyncio-with-alembic), [uv en Docker](https://docs.astral.sh/uv/guides/integration/docker/) y AI Tutor `app/backend/alembic/env.py`. La evidencia Node y sus fuentes quedan en el [diseño archivado](../openspec/changes/archive/2026-10-22-add-postgres-foundation/design.md).

## 9. Inventario de consumidores y convergencia

| Consumidor verificado | Dependencia actual | Obligación antes del corte |
| --- | --- | --- |
| API identidad (`api/server.js`, `passkeys-store.js`) | `db` en memoria, múltiples `saveDb`, referencias a usuarios y credenciales | Adaptar lecturas/mutaciones y concurrencia sin un snapshot en memoria que sobrescriba cambios nuevos. |
| API Training | `readStateStrict`, `readStateCached`, `stateFile`, revisión por stat | Repositorio PostgreSQL; no cachear usando mtime de archivos retirados. |
| Coach (`api/coach/jobs.js`) | Enumera `state-*.json` y lee documentos; jobs/config propios | Leer Training autoritativo. Inventariar aparte su estado persistente; mantener funciones actuales. |
| MCP (`mcp/src/state.js`, `tools.js`) | `db.json`, archivos estado y watcher | Adaptador de lectura Training restringido; sin archivos espejo autoritativos ni privilegios Recovery. Transporte/credencial concretos pendientes. |
| Medios (`api/media.js`) | Callback de estado para referencias/GC | Adaptar a nueva lectura; no borrar medios por tomar error de BD como ausencia de referencias. |
| Administración y recordatorios | Usuarios/estado leídos en el servidor | Consultar autoridad actual y conservar ownership/permisos. |
| Export/import/reset frontend (`Settings.jsx`, `useStore.js`, `backup-media.js`) | Documento Training local, merge y reemplazos deliberados | Mantener alcance y semántica. Export Training no debe prometer backup completo de Recovery. |
| Coach payload (`api/coach/core/payload.js`) | Workouts, notas y ejercicios Training permitidos | Pruebas negativas: Recovery no se incorpora directa ni indirectamente. |

### 9.1 Paridad del port y alcance de retirada

La matriz de consumidores anterior cubre persistencia; la sustitución Node → Python debe cubrir además capacidades y contratos. Caracterizar el sistema de referencia con datos sintéticos antes del port y ejecutar los mismos casos contra Python/PostgreSQL. Los tests ligados a archivos pueden retirarse con el código sustituido; sus garantías funcionales deben conservarse.

| Área | Obligación de compatibilidad | Evidencia para GP/G3 |
| --- | --- | --- |
| Rutas HTTP/OpenAPI | Rutas/métodos, respuestas, errores, headers/cookies, límites, origen/CSRF y subpaths; contratos actuales de `api/openapi.yaml` y handlers | Casos positivos/negativos contra ambas implementaciones; no aceptar cambios involuntarios por defaults de FastAPI/Pydantic. |
| Identidad/acceso | IDs, WebAuthn/contadores, revocación, roles, passwords opcionales, pairing y device links | Vectores Node/Python, dos propietarios y casos de deshabilitación/eliminación concurrente. Biblioteca WebAuthn Python y compatibilidad de material heredado por verificar. |
| Passwords y sesiones | Formato scrypt/NFKC y límites actuales; firma/encoding, expiración y revocación de sesiones | Credenciales sintéticas heredadas y Unicode; preservar sesiones o resolver reautenticación controlada explícita. No copiar bcrypt/JWT/OAuth de AI Tutor. |
| Training y cliente | Contratos §7, validaciones legacy admitidas, campos internos, números/fechas, ausente/null, sesión activa local, invitado/offline y pendientes | Pruebas de paridad, JSONB, primera escritura concurrente, stamps, conflictos, reset, respuesta perdida y reconciliación tras restore. |
| Administración/push | Invitaciones, audit, suscripciones, recordatorios/rest timers y estado por dispositivo | Casos habilitados/deshabilitados y permisos; inventario del estado en memoria y persistente. |
| Medios/import/export/catálogo | Ownership, referencias/GC, IDs, formatos e interpretación del historial | Error DB conserva medios; import/export y restore mantienen significado. No presentar export Training como backup de plataforma completa. |
| Coach actual | Proveedores, propuestas/aprobación, consentimiento, jobs/config/credenciales, límites y sandbox | Fixtures sin llamadas reales, fuente Training nueva y prueba de cada SDK/CLI necesario o tratamiento expresamente resuelto. |
| MCP | Solo lectura y propietario, resultados y cálculos compartidos con frontend | Contrato Training restringido y pruebas de paridad. Definir provisionamiento/revocación de credencial, errores y disponibilidad sin mirrors JSON. |

Node puede continuar para build frontend y MCP stdio. Los helpers compartidos frontend/MCP no se portan por anticipación; la lógica servidor que pase a Python necesita equivalencia verificable. La excepción de un runtime auxiliar opcional del coach requiere alcance y evidencia: no convierte otra API Node en destino admitido ni autoriza perder proveedores silenciosamente.

No basta cambiar `/api/data`. JSON de entrenamiento congelado no puede seguir siendo leído como verdad por MCP/coach.

Cada almacén residual de configuración/jobs/credenciales del coach debe clasificarse y tener autoridad y salida explícitas. No son duplicados de Training, pero no deben convertirse en excepción perpetua e indocumentada a la convergencia. Secretos y bytes multimedia pueden permanecer fuera de PostgreSQL con contratos de respaldo; moverlos a tablas no es requisito del MVP.

El inventario de migración debe cubrir todos los productores, consumidores y almacenes afectados, con un destino y tratamiento explícitos para cada uno: sustituir, conservar con justificación o retirar. El almacenamiento local de invitado/offline, medios, secretos y otros elementos con contrato vigente no se consideran obsoletos por usar archivos o JSON.

La retirada técnica incluye eliminar lectores, escritores, cachés, watchers, opciones de configuración, dependencias y pruebas exclusivos de la persistencia sustituida. Las pruebas de comportamiento que sigan siendo aplicables se conservan y adaptan a la nueva autoridad. El cierre exige evidencia de ausencia de accesos activos al almacenamiento sustituido y verificación de los consumidores después de eliminar ese código; no basta con dejarlo desactivado.

## 10. Seguridad y operación

### Roles, RLS y autorización

El [contrato de seguridad](reference/platform-security.md) define identidad, permisos por actor/recurso, roles/RLS, secretos y audit. Es obligatorio para GP antes del corte y G3 tras retirada: probar acceso ajeno, revocación durante espera y eventos de seguridad, además del login correcto. Autenticación/autorización existentes pertenecen a plataforma; ampliar OIDC/SSO requiere un alcance posterior independiente.

### Conexión y despliegue

Compose es la base objetivo con `web`/`api`/`db` según §1. Runtime no root, versiones/lockfiles verificados, build por etapas y healthchecks. Desarrollo y verificación deben tener comandos reproducibles en contenedores; no depender de instalaciones manuales de Python/PostgreSQL ni rutas personales para ejecutar la app. Mantener herramientas frontend actuales. Esta revisión no modifica Docker ni añade comandos que se presenten como disponibles.

Inicialización controlada: DB saludable → migración completada satisfactoriamente con rol separado → API con esquema compatible. Readiness no equivale solo a proceso vivo; fallar explícitamente si DB/esquema no son utilizables y tratar caídas posteriores. Véanse [Compose: dependencias](https://docs.docker.com/compose/how-tos/startup-order/) y [FastAPI en contenedores](https://fastapi.tiangolo.com/deployment/docker/).

Pool acotado, timeouts y transacciones cortas. Proveedor, major PostgreSQL, límites de conexiones, proxy/pooler y compatibilidad con advisory locks están pendientes. Migraciones con conexión de sesión apropiada si un pooler transaccional impide el locking esperado.

### HTTPS y acceso web

Preservar el [contrato de origen, passkeys y clientes](reference/platform-security.md#identidad-y-acceso). Publicación requiere HTTPS/origen/RP ID compatibles; ensayo local admitido no acredita publicación ni obliga a adelantar VPS o usar un teléfono concreto.

### Observabilidad

EV-08 exige diagnóstico operativo verificable, no solo logs o un endpoint health. El [contrato de observabilidad](reference/platform-observability.md) define logs, métricas, tracing/correlación, privacidad, acceso/retención y exportación acotada. Sus casos sintéticos y verificación tras corte son obligatorios para GO. Audit y trazabilidad de datos conservan autoridad separada; traces muestreados no los reemplazan.

### Verificación, entrega y soporte

CI debe comprobar lockfiles, formato/lint/tipos Python, pruebas y builds pertinentes, contratos HTTP y PostgreSQL real descartable obligatorio para migraciones, permisos, RLS, concurrencia y restore. Mocks complementan; ausencia de PostgreSQL no debe convertir la prueba obligatoria en skip. Las suites frontend/MCP y controles de locales/artefactos siguen aplicando. Ni un CI verde histórico Node ni el harness simulado de AI Tutor acreditan estas garantías en Python.

Al implementar, actualizar guías operativas, API y artefactos de la entrega soportada. Inventariar Nix, Kubernetes, Helm, shells móviles, website y diagramas: adaptar lo soportado o identificarlo expresamente como legacy/fuera del objetivo. No anunciar despliegues Python con manifiestos que todavía ejecutan Node. No exigir nuevos builds/publicación nativa para esta entrega web ni romper clientes existentes sin resolver su alcance de compatibilidad.

## 11. Respaldos, restauración y rollback

**Objetivos candidatos, no garantías:** RPO 6 horas y RTO 24 horas. Requieren aprobación operativa, capacidad del proveedor y ensayo cronometrado de restauración completa.

- Backups automáticos cifrados externos al host principal, con retención y control de acceso por definir.
- La planificación debe contemplar fallos de ejecución, transferencia y verificación; programar una copia cada seis horas no acredita por sí solo RPO de seis horas.
- Backup PostgreSQL consistente y backup coordinado de medios, configuración y secretos necesarios. `pg_dump` lógico no equivale a PITR.
- PITR solo si se verifican backup base, archivado WAL continuo, retención y procedimiento del proveedor. No es capacidad confirmada.
- No copiar un directorio de datos PostgreSQL en caliente como si fuera un backup consistente.
- Manifiesto de revisión de aplicación, versión de esquema, alcance y punto recuperable; secretos protegidos separadamente cuando proceda.
- Restaurar en entorno aislado con coach, notificaciones y llamadas externas deshabilitados; validar identidad, relaciones, snapshots, recibos y referencias multimedia.
- Rotar generación Recovery y probar protección de pestañas anteriores. Probar linaje Training después de restore y clientes con cambios offline.
- Un restore a un punto anterior puede retroceder contadores WebAuthn/revocaciones; definir reconciliación de autenticación y revocación de sesiones según riesgo, sin prometer supervivencia segura de todas las sesiones.

Migración de autoridad:

1. Inventario confirmado y copias protegidas; pausar escritores HTTP e internos durante el corte.
2. Importar preservando identidad, credenciales, documentos internos y referencias.
3. Validar equivalencia antes de habilitar tráfico.
4. Activar una sola autoridad PostgreSQL; retirar lecturas/escrituras heredadas del dominio.
5. Conservar origen congelado y protegido durante una ventana de recuperación definida antes del corte, no como fallback.
6. Completar la retirada técnica de §9 y verificar nuevamente compatibilidad y recuperación antes de declarar terminada la migración.

Antes de retirar el código sustituido, conservar durante la ventana de recuperación la imagen/release anterior identificada por revisión y digest, su configuración compatible y los secretos necesarios bajo protección. Ensayar en un entorno aislado su recuperación con el origen congelado; conservar solo los datos no basta. Estos artefactos permiten ejecutar el procedimiento de reversión aprobado, sin mantener accesos legacy activos ni habilitar fallback automático; no eluden las restricciones sobre nuevas escrituras descritas a continuación.

La retirada del código y la eliminación de los datos originales son operaciones distintas. El vencimiento de la ventana de recuperación no autoriza su borrado: este requiere una decisión y autorización explícitas, comprobando previamente el respaldo y la restauración del sistema vigente. La especificación de migración debe definir la conservación, protección y disposición final del origen sin convertirlo en una segunda autoridad.

Antes de nuevas escrituras, rollback al origen es directo tras validación. Después, requiere exportación inversa validada o corrección hacia adelante; recuperar el backup anterior pierde cambios y exige autorización explícita. No habilitar doble escritura como seguro aparente.

PostgreSQL JSONB reordena claves y cambia representación. Validar equivalencia semántica, tipos/números y renderización/merge, no solo bytes. Prevalidar documentos con claves duplicadas, caracteres o valores no representables fielmente y datos corruptos; no normalizarlos silenciosamente al importar.

## 12. Gates y experimentos antes de producción

**Estado:** G0–G5, GP y GO pendientes para el destino objetivo. Foundation Node es evidencia histórica y no valida Python ni G1 operativo. G0 precede al corte real; los ensayos sintéticos autorizados pueden precederlo sin acreditar proveedor o recuperación operativa.

**Cierre de plataforma:** requiere G0, G1, GP, GO, G2 y G3. GP se demuestra antes del corte y G3 tras retirada; GO cubre ensayo previo y verificación operativa posterior, incluidos seguridad y observabilidad. **Recovery comienza a implementarse después de este cierre.** G4/G5 y sus tres sesiones reales pertenecen a la entrega posterior. Esta matriz gobierna la aceptación técnica de EV-01–EV-09.

Trazabilidad: EV-01 → GP/G3, incluido [seguridad](reference/platform-security.md#evidencia-de-aceptación); EV-02 → G0/G1/G2/G3; EV-03 → GO; EV-04 → G1/GO/G2/G3; EV-05 → G2/G3; EV-06 → GO/G3; EV-07 → cierre conjunto registrado antes de Recovery; EV-08 → GO y [casos de observabilidad](reference/platform-observability.md#evidencia-para-go). Registrar requisito → escenario OpenSpec → prueba → evidencia con revisión/entorno/resultados/límites.

EV-09 → GP/GO/G3: probar el slice piloto y revisar propiedad, contratos e imports de los módulos portados según la [referencia modular](reference/platform-modularity.md#slice-piloto-y-evidencia-de-aceptación). El resultado debe conservarse después de retirar Node; checks documentales y Foundation aislada no acreditan este cierre.

La [matriz de responsabilidad por fase](reference/platform-modularity.md#responsabilidad-y-aceptación-por-fase) añade evidencia concreta sin otro gate: transacción compartida y biblioteca neutral en GP/G3; build frío/caliente y runtime/ambientes soportados en GO; imports/builds independientes del árbol retirado en G3. Los OpenSpecs de port/operación deben contener sus requisitos, escenarios y tareas antes de implementar esos entregables.

| Gate | Evidencia de aceptación | Recuperación si falla |
| --- | --- | --- |
| G0: inventario/procedencia | Clientes/orígenes identificados; backups locales comprobados; imagen frontend identificable; correspondencia API documentada | No cortar persistencia existente ni borrar clientes; resolver diferencias. No impide Foundation sintética aislada |
| G1: foundation Python/PostgreSQL | Pool asyncpg/lifespan, roles, Alembic/locking, transacciones/RLS y backup/restore sobre PostgreSQL real; compatibilidad del entorno objetivo | No habilitar nuevo backend autoritativo; corregir con datos sintéticos. Evidencia Node no sustituye estas pruebas |
| GP: paridad Python | Matriz §9.1 contra Node y frontend actual sobre Python/PG; diferencias resueltas; contrato de seguridad probado: permisos por actor/recurso, revocación, RLS y audit | No cortar ni retirar capacidades; completar el port y su evidencia |
| GO: operación reproducible y observable | Checkout limpio, contenedores/CI, revisión identificable, guías/restore representativo y EV-08: correlación/traces, métricas, salud, fallos DB/exportación, privacidad/acceso/retención según referencia; ensayo previo y comprobación tras corte | No cerrar plataforma ni comenzar Recovery; resolver operación, recuperación o diagnóstico no demostrados |
| G2: corte identidad/Training | Importación equivalente, consumidores operativos sobre PostgreSQL, autoridad única, ausencia de accesos activos al almacenamiento sustituido y reversión ensayada | Rollback antes de escrituras; luego recuperación explícita sin pérdida silenciosa |
| G3: compatibilidad tras retirada | Capacidades §9 y seguridad/auth/audit sin regresión; GP/GO, diagnóstico y recuperación comprobados después de eliminar código sustituido | No cerrar plataforma ni comenzar implementación Recovery; resolver contrato |
| G4: dominio Recovery | Escenarios A-D del PRD, atomicidad, idempotencia, snapshots y aislamiento demostrados | Mantener Recovery no disponible y preservar Training |
| G5: experiencia web responsive/datos reales | Recorrido visible completo de captura, organización, sesión, guardado, continuación e historial; autenticación, persistencia, matriz §12.1 y restauración operables | No iniciar las tres sesiones reales si falta evidencia del recorrido o hay riesgo de pérdida; corregir primero |

Pruebas obligatorias para plataforma (G0–G3/GP/GO):

- PostgreSQL real descartable en CI, versión fijada acorde al objetivo; aislamiento por BD/esquema y sin credenciales ni acceso a producción. Mocks solo complementan.
- Migraciones desde BD vacía y desde el esquema anterior; ejecución simultánea, fallo/interrupción y lock. Constraints/RLS/versiones realmente aplicadas.
- Autenticación existente: passkeys, contadores, revocación, usuarios deshabilitados, roles, contraseñas opcionales y sesiones; no reidentificar usuarios.
- Training: revisiones/linaje, primer documento concurrente, stamps legacy, reset, importación, polling, pérdida de respuesta y dos dispositivos.
- Offline Training, sesión activa local y cambios pendientes: reconciliación tras migración/restauración sin sobrescritura silenciosa.
- Paridad Python de §9.1, incluyendo auth y coerciones/serialización, errores HTTP, runtime de proveedores coach y contrato MCP.
- Casos de [seguridad](reference/platform-security.md#evidencia-de-aceptación) y [observabilidad](reference/platform-observability.md#evidencia-para-go), con fixtures sintéticas y sin credenciales ni contenido privado emitido.
- RLS Foundation: fixtures de propietarios, contexto ausente y pool reutilizado tras commit/rollback; roles restringidos reales, sin tablas Recovery anticipadas.
- Medios: caída de BD no equivale a referencias vacías ni dispara GC destructivo.
- Restauración completa medida, con autenticación, archivos externos, linaje Training y clientes antiguos.
- Suites pertinentes y verificación de recorridos actuales, incluyendo auth/sync, con datos sintéticos y procedencia de artefactos. Instalación desde checkout limpio y documentación operativa coherente. Deuda histórica identificada no equivale a una regresión nueva.

Para G4/G5 posteriores, aplicar las [pruebas Recovery](reference/recovery-contracts.md#pruebas-g4-y-g5) y su matriz responsive; no adelantar ese dominio durante plataforma.

Experimentos propuestos, no ejecutados ni autorizados como implementación:

| Incertidumbre | Experimento acotado futuro | Regla de decisión |
| --- | --- | --- |
| Compatibilidad JSONB | Fixture representativa con historial, stamps y datos límite; comparar respuestas y merge | No cortar hasta equivalencia o incompatibilidades explícitamente resueltas |
| RLS/pool | Dos propietarios, conexión reutilizada y fallos transaccionales | Cualquier fuga bloquea Recovery; no quitar RLS silenciosamente |
| Port Node/Python | Casos HTTP, vectores auth/stamps y consumidores sobre fixtures equivalentes | No cortar hasta paridad o diferencias expresamente resueltas |
| Tooling de migración Python | Dos ejecutores, interrupción y recuperación en BD descartable, sesión acotada de evaluación | Adoptar runner Alembic solo si cumple locking y ejecución reproducible en el stack Python |
| Restore operativo | Ensayo completo y medición con conjunto representativo | Confirmar RPO/RTO solo con evidencia y proveedor; ajustar plan/coste si no cumple |

Cada experimento debe acordar su timebox al autorizarlo. Nada de lo anterior se ejecutó sobre datos reales en esta etapa de arquitectura.

### 12.1 Validación web responsive

El [protocolo responsive Recovery](reference/recovery-contracts.md#validación-web-responsive) conserva viewports, recorridos, accesibilidad y evidencia Playwright CLI. Pertenece a G5 después del cierre de plataforma; GP/GO necesitan sus propios casos sobre capacidades actuales.

## 13. Riesgos y mitigaciones

| Riesgo | Mitigación |
| --- | --- |
| Asincronía rompe supuestos de identidad y escritura | Repositorios/transacciones y revisión de referencias mutables; no migrar por sustitución textual de funciones |
| JSONB altera datos límite o contratos | Prevalidación, equivalencia semántica y tests de sync/render |
| Lectores JSON quedan estancados | Inventario de consumidores y gate de corte integral |
| Clientes offline reintroducen datos o pisan restore | Preservar stamps/linaje, probar dispositivos y no borrar estados locales |
| RLS aparente por rol propietario | Roles no exentos y pruebas reales con conexiones reutilizadas |
| Dual-write o fallback oculto | Autoridad única, fallo explícito ante BD indisponible |
| Backups solo nominales | Copia externa cifrada, alertas y restauración completa medida |
| Divergencia upstream | Adaptadores localizados y contratos verificables; el fork conserva un coste de mantenimiento real |
| Ampliar el port con rediseño o servicios sin necesidad | Training JSONB, frontend actual y backend Python modular único; nuevas funciones después de aceptar plataforma |
| Port Python rompe contratos o pierde proveedores actuales | Caracterización y GP antes del corte; G3 tras retirada; resolver explícitamente bibliotecas y sandbox del coach |
| Persistencia residual permanente no inventariada | Responsabilidad y salida por almacén; medios/secretos explícitamente diferenciados |

## 14. Secuencia conceptual confirmada de futuras OpenSpecs y handoff

**Estado:** prioridad documental revisada el 2026-10-22. Foundation Node está archivada; la plataforma Python y Recovery no están implementados. Los siguientes tramos son handoffs conceptuales, no OpenSpecs creadas ni tareas autorizadas por esta edición:

1. **Caracterización y Foundation Python/PostgreSQL:** contratos de referencia, entorno sintético, pool/lifespan, roles, Alembic, recuperación y CI. Añadir inventario JS compartido, prueba transaccional de colaboradores sintéticos y matriz de caché sobre imágenes de ensayo. Reutilizar requisitos/escenarios históricos, aportando evidencia nueva de G1 para Python sin acreditar operación.
2. **Port de capacidades y migración ensayada:** backend Python compatible por módulos, identidad mínima previa al slice piloto Training y luego consumidores §9.1; frontend actual operando en el entorno nuevo, importación equivalente y recuperación representativa. Trasladar biblioteca JS neutral y adaptar generadores/builds; implementar desarrollo/CI y transacciones intermodulares de negocio. Cada OpenSpec de port declara contratos, dependencias y componentes del recorrido según §5.1. GP, EV-09 y parte previa de GO.
3. **Operación, corte, retirada y aceptación de plataforma:** targets test/runtime/migrate y herramientas operativas puntuales, ambientes explícitos, soporte de plataformas y matriz de caché entregable; G0, G1 operativo, GP/GO previos al corte, autoridad única, compatibilidad tras retirada y verificación operativa posterior. Cierre G2/G3/GO y EV-01–EV-09; ningún lector activo del almacenamiento sustituido ni API Node de negocio necesaria. Preparar/probar imágenes y operación antes del corte; no posponer su aceptación hasta recibir datos nuevos.
4. **Recovery:** `add-recovery-foundation` y `add-recovery-experience`, únicamente después del cierre de plataforma. Dominio de procesos/indicaciones/sesiones/correcciones/recibos y experiencia completa según PRD, G4/G5 y §12.1. Después, tres sesiones reales para evaluar utilidad.
5. **Garmin Connect:** tras Recovery, definir datos/acceso/autenticación/procedencia y deduplicación; conector Python sin sesiones Recovery implícitas. La exportación `.fit` existente no equivale a esta integración.
6. **Ampliaciones de IA:** después de las etapas anteriores, casos de uso, consentimiento, límites y evaluación propios. Mantener el coach actual durante plataforma no habilita datos Recovery/Garmin automáticamente.

No se exige completar G0 para ensayos sintéticos aislados; sí antes de un corte real. No completar primero una migración productiva Node/PostgreSQL como paso obligatorio. Los tramos pueden descomponerse en cambios acotados cuando se autoricen; no implementar toda la transición en un solo salto.

**Handoff obligatorio de migración y retirada:** el alcance antes denominado `migrate-opengym-persistence` debe revisarse para el destino Python. Incluir matriz §9.1, inventario de todos los almacenes/consumidores, paridad, equivalencia, restauración/reversión y corte §11. Contener un tramo final de eliminación del código sustituido, pruebas posteriores, guías actualizadas y conservación protegida del origen/versión anterior. Importar datos o conectar FastAPI no acredita el cierre.

Antes de declarar lista una especificación de corte deben resolverse entorno objetivo, clientes/credenciales compatibles, capacidades coach/MCP, plazos de recuperación y procedimientos antes/después de nuevas escrituras. Las guías operativas describen el sistema actual hasta la entrega correspondiente; esta revisión de planificación no cambia su contrato.

Trabajos duraderos, LangChain/LangGraph, pgvector y colas requieren una necesidad posterior; no se crean por anticipación. Ningún futuro módulo o servicio administra el esquema compartido con un segundo migrador.

### 14.1 Evidencia histórica: `add-postgres-foundation`

**Estado:** [OpenSpec archivado](../openspec/changes/archive/2026-10-22-add-postgres-foundation/proposal.md), con 18/18 tareas sintéticas completadas y sync/archive autorizado el 2026-10-22. El [tracker archivado](../openspec/changes/archive/2026-10-22-add-postgres-foundation/tasks.md), la [evidencia consolidada](../openspec/changes/archive/2026-10-22-add-postgres-foundation/design.md#evidencia-consolidada-de-entrega), el [README](../api/foundation/README.md) y el [contrato vigente de esa capacidad](../openspec/specs/postgres-foundation/spec.md) conservan su trazabilidad.

La entrega probó Node 22.23.2, `pg` 8.23.1, `node-pg-migrate` 9.0.0 y PostgreSQL 18.6 en un stack sintético aislado. Registra pool, migraciones, roles/RLS con fixtures, backup cifrado/restore separado, CI y resultados históricos de compatibilidad. No está importada por `api/server.js` ni por la imagen normal y no migró autoridad.

Esos resultados no fueron reejecutados en esta edición. No acreditan proveedor, TLS operativo, restore completo externo/PITR, RPO/RTO productivos, HTTP auth, políticas Recovery, GP/GO ni el port de Python. No reescribir el archivo histórico ni presentar el locking del runner Node como propiedad verificada de Alembic.

### 14.2 Handoff de Foundation Python

**Entradas:** PRD Evolution EV-01–EV-09, esta arquitectura §§5.1 y 7–12, referencias de modularidad/seguridad/observabilidad, contratos actuales y evidencia histórica. Seleccionar versiones estables compatibles y documentar licencias/lockfiles antes de implementarlas.

**Alcance sintético:** PostgreSQL descartable, sin perfiles, secretos, medios ni configuración real; pool Python/lifespan, límites/timeouts/cancelaciones, roles, migración única con locking/fallos, RLS de fixtures, backup/restore y job CI obligatorio con DB real. No migrar usuarios ni crear el dominio Recovery por adelantado.

**Salida esperada:** comandos y evidencias reproducibles, versiones fijadas y límites explícitos, pruebas de ausencia de DB que fallen y estado de cada gate. El entorno sintético puede preceder decisiones finales de proveedor, pero G1 operativo requiere validar el entorno objetivo antes del corte. Ni Foundation Python aislada ni su futura aprobación reemplazan GP/GO o autorizan migración real.

**Salida modular acotada:** infraestructura compartida bajo `core/`, contratos/probes Foundation bajo `health/`, composición en la factory y revisión de dependencias. El inventario de caracterización añade módulo propietario y recorrido frontend existente como handoff. El port funcional y sus reorganizaciones justificadas requieren un cambio posterior; no se declara EV-09 satisfecho con ese mapa.

**Salida de build/handoff:** resultados nuevos de caché e instalación bloqueada para imágenes de ensayo, rollback de dos colaboradores sintéticos y mapa JS/ambientes/targets con responsable y criterio por fase. Runtime de producción, traslado a `shared/coach-core/`, ambiente dev del port, proveedor y arm64 siguen pendientes. Conservar toda evidencia histórica con su alcance original.

## 15. Pendientes operativos y de verificación

| Pendiente | Recomendación/criterio | Bloquea |
| --- | --- | --- |
| Versiones Python y herramientas | Fijar Python/FastAPI/Pydantic/Uvicorn, asyncpg/Alembic/uv y verificadores compatibles; demostrar instalación/runtime reproducibles | Foundation Python y GO |
| Tooling en el entorno objetivo | Ensayos nuevos Python sobre PostgreSQL real: pool, contexto/roles, locking, interrupción y restore; evidencia Node como antecedente únicamente | G1 operativo |
| Entorno/major PostgreSQL | Definir Compose local y despliegue objetivo, versión, conexiones, TLS/pooler, backup/PITR si corresponde, coste y ubicación | G1 operativo/GO y corte; no obliga a adelantar VPS |
| Paridad auth y clientes | Biblioteca WebAuthn/material heredado, scrypt/NFKC, sesiones existentes o reautenticación controlada y clientes nativos admitidos | GP y continuidad de acceso |
| Coach/MCP | Probar proveedores/SDK/CLI/sandbox, lectura restringida y credencial MCP; delimitar autoridad/salida de cada almacén | GP/G3 y retirada completa |
| RPO 6 h / RTO 24 h | Objetivos candidatos históricos, no garantías; acordar y medir restauración representativa | GO y uso real con garantías de recuperación |
| Retención/cifrado/destino externo | Acordar ubicación, acceso, claves y alertas; DB y elementos externos necesarios | GO y recuperación operativa |
| Inventario de clientes | Identificar perfiles/orígenes/cuentas, teléfonos utilizados, sesión activa y datos pendientes; backups comprobados | G0 y corte |
| Procedencia de artefactos | Referencia Node e imágenes nuevas por revisión/digest; observación histórica `dev` no equivale al estado actual | GP/G0/GO |
| Publicación web | HTTPS, origen/RP ID/certificado y transición de passkeys; localhost compatible para ensayo local | Publicación/autenticación; no exige un dispositivo concreto |
| Soporte y documentación | Adaptar artefactos soportados, marcar alternativas legacy, verificar comandos desde checkout limpio | GO/EV-06 |
| Observabilidad operativa | Seleccionar instrumentación y destino de ensayo, acceso, retención, muestreo y alertas; demostrar casos EV-08 sin datos privados | GO; no requiere otro gate ni dashboard específico |
| Ventana de mantenimiento/rollback | Pausar todos los escritores y resolver procedimiento antes/después de nuevas escrituras | Corte definitivo |

**Siguiente trabajo:** continuar las tareas pendientes del [cambio activo Foundation Python](../openspec/changes/add-python-platform-foundation/proposal.md) solo bajo su autorización de ejecución, con los criterios modulares de §5.1; después especificar el port funcional y su piloto. Esta revisión no implementa esas tareas. Las pruebas y evidencias, no el cierre documental, acreditarán los gates.
