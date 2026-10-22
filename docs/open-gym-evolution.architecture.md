# OpenGym Evolution — arquitectura PostgreSQL-first

## Estado y alcance del documento

**Estado:** arquitectura aprobada formalmente por el usuario; `plan-architecture` cerrado documentalmente. La aprobación final, registrada en la conversación bajo «Aprobación final — OpenGym Evolution Architecture», comprende la dirección, los límites, las herramientas seleccionadas y la secuencia conceptual aquí descritos, con las precisiones incorporadas en este cierre.

**Alcance de la aprobación:** no certifica gates satisfechos, versiones de herramientas verificadas, proveedor validado ni preparación para producción. No autoriza generar OpenSpecs, instalar dependencias, modificar código/Docker/infraestructura ni migrar datos. El siguiente cambio requiere autorización expresa independiente. No reabrir decisiones aprobadas sin nueva evidencia técnica que demuestre un problema; cualquier ajuste deberá documentar esa evidencia.

**Fuente funcional:** [PRD aprobado de Recovery](open-gym-recovery.prd.md). Complementos: [discovery](dev/personal-recovery-discovery.md) y [glosario](../GLOSSARY.md). Si difieren las precisiones funcionales, prevalece el PRD aprobado. Este documento no amplía su MVP.

**Método:** `plan-architecture`: investigación brownfield, alternativas, decisiones del usuario y consolidación. No es un esquema SQL aprobado, un listado de cambios de archivos ni un plan de tareas definitivo.

**Clasificación:**

- **Verificado:** inspeccionado en código, configuración, metadatos o ejecución de comandos de lectura.
- **Aprobado:** decisión expresamente tomada por el usuario; no implica implementación o validación operativa.
- **Recomendado:** orientación técnica dentro de la arquitectura aprobada; no equivale a detalle de implementación o validación operativa.
- **Pendiente/hipótesis:** no demostrado o necesita información del usuario/proveedor.

**Revisión aprobada del alcance web:** Recovery se entregará como web responsive; se sustituye la aceptación obligatoria en Safari/iPhone por la matriz de §12.1. Las guías móviles y observaciones As-Is conservan su contexto histórico y no amplían esta entrega. La revisión documental no acredita nuevas pruebas ni gates.

## 1. Objetivo y límites

Incorporar Recovery como primera entrega funcional de OpenGym Evolution, con indicaciones, sesiones, contexto histórico, correcciones y guardado confiable. Preservar Training, su sincronización y offline, así como catálogo, autenticación y capacidades actuales del coach. Converger hacia PostgreSQL sin reemplazar simultáneamente frontend y backend.

**Recovery MVP:** Node, PostgreSQL, identidad preservada, Training compatible, dominio Recovery aislado, respaldo/restauración, pruebas reales y recorrido web responsive completo, con HTTPS para publicación y autenticación.

**Evolution posterior:** Garmin mediante Python cuando se justifique; ampliación de agentes; trabajos duraderos; normalización adicional de Training solo por necesidad. FastAPI, LangChain/LangGraph, pgvector y Kubernetes no son dependencias del MVP. No habilitar extensiones por anticipación.

## 2. Base de evidencia y límites de la auditoría

### 2.1 OpenGym

Checkout inspeccionado: `666d9080374a39ab0edd28fc8c15d2a72d153412`. Frontend/API declaran versión `1.4.1`; no se verificó que sea la última versión upstream.

Contenedores existentes observados en ejecución y saludables:

- API: `sha256:ecfa3156057b2b76231dc3d4fc598c54913098344d1062e156962a81863a1d20`.
- Web: `sha256:1b7008edb7215f483af7ddd4ba8b769115cb8a88e88c0c25c6a68c5060875b5d`.

Las imágenes etiquetadas `latest` declaran revisión/versión `dev`. Una comparación SHA-256 de los 47 archivos JavaScript y manifiestos encontrados por el recorrido de aplicación API —raíz y árbol `coach`, sin dependencias instaladas— coincidió con los archivos correspondientes del checkout. Esto acredita esa comparación, no la identidad de toda la imagen, dependencias, configuración ni frontend.

No existe `frontend/dist` local para comparar con la imagen web. **Correspondencia frontend/build pendiente:** antes del corte se necesita procedencia reproducible y revisión/digest identificables; no basta la etiqueta `latest`.

El contenedor API monta el `data/` del proyecto en `/data`. En el inventario agregado observado no hay `db.json` ni `state-*.json`; sí existen secretos de instancia y VAPID. No se imprimieron valores de secretos. No se encontraron uploads ni configuración persistida del coach en ese inventario. Es una observación puntual, no prueba de ausencia histórica ni inventario de datos de clientes.

Configuración no secreta observada en API: `RP_ID=localhost`, `ORIGIN=http://localhost:8080`, `DATA_DIR=/data`. **No acredita HTTPS accesible desde iPhone.**

No se ejecutaron suites funcionales, restauraciones, pruebas PostgreSQL ni validaciones Safari durante esta investigación. Estado saludable de contenedores no acredita estos resultados.

### 2.2 Datos locales de clientes

Pendiente: inventario asistido de navegadores, perfiles y teléfonos realmente utilizados. `frontend/src/store/useStore.js` mantiene estado local (`gym_state_v1`), copias apartadas (`gym_stash`), propietario y metadatos de sincronización; los clientes móviles tienen persistencia específica. También pueden existir medios locales.

Antes del corte: identificar cada origen/perfil, cuenta o modo invitado, trabajo pendiente, sesión activa y medios; respaldar mediante las capacidades existentes y verificar el resultado. Un export ordinario no debe suponerse suficiente para restaurar todos los borradores o metadatos internos. No borrar almacenamiento, cerrar sesiones indiscriminadamente ni cambiar origen antes de resolver este inventario. No se inspeccionaron perfiles personales del navegador ni se accedió al iPhone.

### 2.3 AI Tutor como referencia

Repositorio disponible: `C:/Users/nenri/OneDrive/Desktop/proyectos/pry-ai-evaluator/ai-tutor`, revisión `c28d4c36559218565845c447bcc64a89565881d9`. Solo lectura.

| Evidencia, relativa a AI Tutor | Patrón y utilidad |
| --- | --- |
| `app/backend/db/postgres.py` | Pool `asyncpg` inicializado/cerrado por lifecycle. Transferir el principio a un pool Node; no importar ajustes pgvector. |
| `app/backend/alembic/env.py` | SQLAlchemy async para ejecutar Alembic; acceso de aplicación mediante `asyncpg`, no ORM SQLAlchemy general. |
| `app/backend/evolution_exports/service.py` | Operaciones relacionadas bajo transacción; separar responsabilidades y fallos. No importar el sistema de exportación dental. |
| `app/backend/alembic/versions/0024_condition_corrections.py` | Restricciones, antecedentes de corrección y operación identificable. Referencia para integridad, no modelo de pacientes. Su downgrade no garantiza reversión de datos. |
| `app/backend/routes/patients.py` | Validación explícita y ownership; reutilizar principios, no cuentas clínicas ni dominio dental. |
| `app/backend/tests/conftest.py` | Entorno aislado; PostgreSQL sustituido por defecto y pruebas reales opt-in. No confundir fixtures simuladas con integridad relacional probada. |
| `.github/workflows/ci.yml` | Comprobaciones de calidad, tests y build; no acredita por sí sola ejecución de todas las pruebas PostgreSQL reales. |
| `deploy/Dockerfile`, `deploy/docker-compose.yml` | Lockfiles, etapas, runtime no root y healthchecks. No copiar topología blue/green ni imagen conjunta sin necesidad. |
| `app/backend/main.py` | Migra al arrancar: patrón observado, no recomendado literalmente para OpenGym. |
| `app/backend/clinical_assistant/agent.py`, `llm/tool_loop.py` | Bucle de herramientas acotado y aprobación humana; no se verificó necesidad de LangGraph. |

## 3. Decisiones y alternativas consideradas

### 3.1 Aprobadas

| Decisión | Alcance |
| --- | --- |
| PostgreSQL principal | Nuevas capacidades duraderas y convergencia del estado heredado. Retirada de JSON aislado como propuesta Recovery. |
| Node como API inicial | Preservar semántica de autenticación y contratos; no introducir FastAPI solo por preferencia tecnológica. |
| SQL explícito | Sin ORM obligatorio ni normalización completa de Training. |
| Training en JSONB | Documento compatible, revisiones, linaje, stamps, sync y offline existentes. |
| Recovery relacional + JSONB selectivo | Relaciones/invariantes y snapshots históricos sin normalización excesiva. |
| Identidad y Training antes de Recovery | Inventario, foundation, corte controlado, validación de compatibilidad y experiencia web responsive Recovery. |
| RLS para Recovery, condicionada | Debe pasar pruebas reales de propietario, transacciones y pool; no se puede declarar efectiva antes. |
| Frontend y experiencia actuales | React/Vite/Zustand, componentes, catálogo, acceso rápido y PWA. |
| Una autoridad por dominio | Sin dual-write permanente, espejos autoritativos ni fallback silencioso a archivos. |
| `pg` y `node-pg-migrate` seleccionados | Versiones exactas pendientes; preferir releases estables compatibles y verificadas. Foundation debe probar compatibilidad, locking y recuperación. |
| G0 obligatorio antes del corte | Foundation puede investigarse y probarse previamente con datos sintéticos; eso no habilita el corte ni acredita el inventario. |
| Garmin Connect y ampliaciones del AI Coach | Iniciativas posteriores independientes; no bloquean el MVP Recovery. |

### 3.2 Alternativas históricas

A conservadora sobre archivos, B híbrida y C modernización amplia fueron evaluadas. El usuario seleccionó PostgreSQL; **no se reabre esa decisión**. La dirección adoptada mantiene el carácter incremental de A en frontend/API y moderniza la persistencia. No implica reescritura Python ni superioridad general de C.

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
Frontend actual
  ├─ Training: store/offline/sync existentes
  └─ Recovery: edición y API separadas
                   │ mismo origen, autenticación actual
                API Node
       ┌───────────┼────────────┐
    Identidad   Training     Recovery
       └──── repositorios PostgreSQL ────┘
                   │
             PostgreSQL
  identidad / documento Training / Recovery

Medios: filesystem protegido, referencias duraderas.
Secretos: gestión externa/protegida, no frontend ni tablas de dominio.
Coach/MCP: contrato Training autorizado, sin acceso Recovery.
Garmin futuro: servicio Python y contratos específicos.
```

Mantener inicialmente una sola réplica API. PostgreSQL no distribuye automáticamente retos WebAuthn, presencia, limitadores ni estado de jobs en memoria.

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

Compartir catálogo y búsqueda (`frontend/src/lib/exercises.js`) y controles (`frontend/src/components/ui.jsx`). Reutilizar selectivamente componentes con props. No reutilizar íntegros `Workout.jsx`, `session-edit.js`, `finish-workout.js` o temporizadores conectados a `S.active`/`useUI.work`: contienen reglas de progresión, récords, filtrado o estado específico.

`registerCustom()` modifica el índice global. Las instrucciones y ejercicios personales Recovery permanecen dentro de su dominio; usar catálogo público de referencia sin registrar información de rehabilitación en ese índice. No crear otro catálogo general.

Separación modular no equivale a sandbox frente al administrador del host ni a una API Node comprometida. Se requieren permisos y contratos, no solo carpetas diferentes.

## 6. Modelo conceptual PostgreSQL

**No es DDL aprobado ni nomenclatura definitiva.**

| Concepto | Relacional | JSONB selectivo |
| --- | --- | --- |
| Usuario | ID heredado, estado, roles, versión de sesión | Atributos heredados preservados durante transición |
| Credencial e identidad auxiliar | Propietario, ID credencial, contador, relaciones relevantes | Metadatos WebAuthn/atributos heredados cuando corresponda |
| Training compatible | Propietario, revisión/linaje sincronizados con el documento | Documento existente completo |
| Proceso Recovery | Propietario, ID, estado, fechas | Detalle opcional acotado |
| Indicación y revisión | Proceso, propietario, ID/revisión, vigencia, registro | Texto, ejercicios identificables y objetivos |
| Sesión | Proceso, propietario, estado, versión, fechas y asociación conocida | Trabajo registrado y snapshot contextual |
| Corrección | Objeto, propietario, operación y fecha | Anterior/nuevo o diferencias explícitas interpretables |
| Hito | Proceso, propietario, fecha efectiva y registro | Detalle del acontecimiento |
| Recibo idempotente | Propietario, operación única, huella, resultado y fecha | Respuesta compacta |
| Garmin futuro, sin crear todavía | Propietario, proveedor, ID externo y procedencia | Payload/métricas según necesidad |

Invariantes:

- Conservar IDs de usuario; no exigir UUID para identidades heredadas.
- Coherencia de propietario en asociaciones, preferiblemente respaldada por claves/constraints adecuadas, además de RLS.
- Como máximo un proceso activo por propietario, con restricción de BD.
- Versiones para escritura condicional y estados de sesión limitados a en curso/completada.
- Fechas de calendario efectivas donde corresponda; instantes automáticos para registro/corrección. No convertir fechas retrospectivas indiscriminadamente a medianoche UTC.
- Revisiones conocidas de indicaciones preservadas y snapshots estables de sesiones. Cambios posteriores no los reescriben.
- Objetivos y resultados separados; ejercicios pendientes no se presentan como realizados.
- Contexto desconocido explícito; no asignar la indicación vigente por defecto a retrospectivas inciertas.
- Corrección y su antecedente se confirman en la misma transacción; no recalcular otras sesiones ni progresiones.
- Conservar nombres, instrucciones y unidades necesarios para interpretar la historia, aunque cambie el catálogo.
- JSONB no autoriza contenido sin contrato: validación de estructura, tamaño y versión, con IDs estables para elementos corregibles.

Para Training, evitar dos copias discordantes de revisión/linaje entre columnas y JSONB. Si se proyectan como columnas, su actualización y serialización deben tener una única regla transaccional probada. Importar también campos internos de sincronización, no solo lo que expone `forClient`.

## 7. Contratos, concurrencia e idempotencia

### Training compatible

Conservar `GET /api/data`, `GET /api/data/rev`, `PUT /api/data`, sus envoltorios y errores, `baseRev`, `baseWid`, `_wid`, `_wids`, stamps, resets y respuestas `409`. Preservar explícitamente comportamientos legacy, incluidas escrituras sin revisión cuando el contrato existente las admite; no endurecerlos inadvertidamente durante el cambio de almacenamiento.

Lectura/comparación/estampado/escritura bajo transacción y serialización por perfil, incluido el caso de primer documento inexistente. No depender del event loop. Conservar la sesión activa como local en Training y sus metadatos de propietario/base. Pruebas de paridad con las suites de revisiones y stamps existentes.

### Recovery

Comando autenticado con ID estable de operación, versión esperada, generación y contenido validado. El propietario procede de la sesión. Usar IDs estables en creaciones.

Dentro de la transacción y con serialización apropiada: comprobar generación, reconocer recibo existente, comparar contenido, comprobar versión/invariantes y guardar cambio/corrección/recibo. Una restricción única respalda la identidad de operación; un simple consultar-y-luego-insertar no resuelve carreras.

- Misma operación y contenido: devolver el recibo previo antes de rechazar por versión antigua.
- Misma operación y contenido distinto: rechazar.
- Conflicto de versión: conservar edición del cliente y solicitar revisión, sin last-write-wins ni merge automático.
- Confirmación de éxito solo después de commit y validación del recibo correcto.
- Timeout significa resultado no confirmado. Reintentar la misma operación; no inventar otra creación.
- Una confirmación no limpia cambios posteriores a la versión enviada. Un recibo antiguo no sustituye una lectura actual del recurso.
- Continuar una sesión consulta su versión guardada en servidor. No confundir sesión en curso con borrador no guardado.
- Sin colas offline Recovery ni promesa de recuperar contenido no confirmado tras cierre forzado.

Restauraciones renuevan la generación Recovery y rechazan contextos anteriores. Probar la restauración Training con su linaje y no solo con el número de revisión. La renovación evita sobrescrituras posteriores; no recupera por sí misma datos posteriores al backup.

## 8. Migraciones: herramientas seleccionadas y alternativas evaluadas

**Selección aprobada:** driver `pg` y migrador `node-pg-migrate`, sin migrador propio ni ORM obligatorio. Las versiones exactas y su compatibilidad se verificarán en Foundation antes de fijarlas. Priorizar versiones estables: no adoptar alpha, beta, release candidate ni otra prerelease sin justificación técnica y aprobación expresa del usuario.

| Candidata | Locking/versionado | CI y recuperación | Evaluación |
| --- | --- | --- | --- |
| `node-pg-migrate` | Advisory lock PostgreSQL verificado en runner v9.0.0, modos fail/wait y opción de desactivación; no desactivarlo. Historial de migraciones y soporte transaccional. | Migrar una BD descartable, probar concurrencia y fallos. Up/down no garantiza deshacer datos. | **Seleccionada:** específica de PostgreSQL y apropiada para Node/SQL explícito; validación práctica pendiente. |
| Knex migrations | Lock persistente con `SELECT ... FOR UPDATE`, historial y transacciones configurables. Documenta desbloqueo manual tras ciertos fallos. | CI con BD real; `migrate:unlock` exige comprobar que no existe otro ejecutor. | Viable, pero incorpora una capa de query/schema builder que no necesitamos como decisión inicial. |
| Alembic | Referencia de AI Tutor; locking del despliegue debe verificarse, no asumirlo por la herramienta. | Añade tooling Python/SQLAlchemy para una API Node. | No recomendado ahora; reconsiderar si aporta una necesidad concreta. |

Verificación remota de metadata: `node-pg-migrate` v9.0.0 declara Node >=20.11.0; compatible en principio con Node 22 del proyecto. Knex publicado consultado: 3.3.0. Son referencias de investigación, no versiones instaladas ni lockfiles aprobados. Confirmar versión/dependencias/licencia y ejecución ESM en el gate de foundation.

Referencias técnicas:

- https://github.com/salsita/node-pg-migrate/blob/v9.0.0/src/runner.ts
- https://www.npmjs.com/package/node-pg-migrate
- https://knexjs.org/guide/migrations.html
- AI Tutor: `app/backend/alembic/env.py`.

Política arquitectónica aprobada:

- Un historial y un responsable del esquema compartido; futuros servicios no crean otro migrador sobre las mismas tablas.
- Migrador con rol separado; runtime sin DDL.
- Ejecución única controlada antes de habilitar tráfico compatible, no al arrancar cada réplica.
- Migraciones aplicadas inmutables en Git y releases; no atribuir a la herramienta verificación de checksums no comprobada.
- Cambios aditivos/expandir-compatibilizar-retirar. Operaciones fuera de transacción solo con procedimiento explícito.
- Error bloquea el despliegue; no marcar manualmente una migración como aplicada para eludir validación.
- Cada cambio declara compatibilidad, prueba y recuperación. DDL reversible no implica datos reversibles; usar restore o avance correctivo cuando corresponda.

La selección de herramientas está aprobada, no su validación operativa ni una versión concreta. Las versiones citadas son evidencia histórica de investigación, no una fijación de dependencias. Su código/documentación no reemplaza un ensayo real de compatibilidad Node/ESM, locking, interrupción y recuperación. Un fallo exige investigar y documentar evidencia antes de proponer cambiar la selección; no reabre automáticamente la decisión.

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

No basta cambiar `/api/data`. JSON de entrenamiento congelado no puede seguir siendo leído como verdad por MCP/coach.

Cada almacén residual de configuración/jobs/credenciales del coach debe clasificarse y tener autoridad y salida explícitas. No son duplicados de Training, pero no deben convertirse en excepción perpetua e indocumentada a la convergencia. Secretos y bytes multimedia pueden permanecer fuera de PostgreSQL con contratos de respaldo; moverlos a tablas no es requisito del MVP.

## 10. Seguridad y operación

### Roles, RLS y autorización

- Rol propietario/migrador separado del runtime, sin superusuario ni `BYPASSRLS` para runtime.
- Privilegios mínimos y sin instalación automática de extensiones.
- RLS Recovery condicionada a pruebas: rol de aplicación no propietario exento, políticas por propietario y contexto transaccional del servidor. Contexto ausente deniega.
- Establecer contexto con alcance local a la transacción; probar reutilización y abortos en el pool. Nunca derivarlo de campos cliente.
- FK/constraints coherentes con propietario; RLS no sustituye estas invariantes.
- Pools/roles restringidos para consumidores Training. Un rol MCP/coach no recibe acceso Recovery.
- Administración de cuentas no autoriza exportación clínica implícita. Deshabilitación y eliminación deben incluir Recovery y estado relacionado, con limpieza recuperable de archivos externos.
- Una petición cuya autorización cambió durante una espera no debe confirmar usando una sesión obsoleta; definir y probar su punto de serialización con revocación/eliminación.
- SQL parametrizado, validación estricta y respuestas privadas/no-store. Rate limits y límites de cuerpo razonables; errores sin payloads.

### Conexión y despliegue

Compose es la base recomendada. Runtime no root, versiones/lockfiles fijados y healthchecks, aprovechando lo existente. No se modificó Docker.

PostgreSQL no se expone públicamente. TLS con verificación de certificado para conexiones que crucen redes no confiables o lo exija el proveedor; no desactivar verificación para hacer funcionar un DSN. Conexión local privada también requiere autenticación y permisos.

Pool acotado, timeouts y transacciones cortas. Proveedor, major PostgreSQL, límites de conexiones, proxy/pooler y compatibilidad con advisory locks están pendientes. Migraciones con conexión de sesión apropiada si un pooler transaccional impide el locking esperado.

Secretos fuera de Git/frontend/logs, credenciales migrador/runtime separadas y procedimiento de rotación. Preservar el secreto de firma de sesiones y el requerido por credenciales cifradas del coach. No registrar URLs con contraseñas.

### HTTPS y acceso web

La publicación y la autenticación requieren un origen estable, HTTPS con certificado confiable, RP ID compatible y proxy de mismo origen. Cambiar hostname puede requerir nuevas passkeys; preservar credenciales no elimina esta restricción. La verificación local puede usar localhost/HTTP cuando el contrato del navegador y WebAuthn lo permita; esto no acredita HTTPS del despliegue público.

Pendientes: dominio/origen de publicación, certificados y transición de passkeys. La validación responsive de §12.1 no exige acceso desde un teléfono físico, apps nativas ni VPS definitivo.

### Observabilidad

Registrar códigos de error, latencia, conflictos, recibos/reintentos y saturación sin instrucciones, notas, credenciales, cookies ni parámetros SQL sensibles. Health/readiness distingue proceso vivo, BD disponible y esquema compatible. No volcar errores de validación con el contenido personal recibido.

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
5. Conservar origen congelado y protegido durante ventana de recuperación, no como fallback.

Antes de nuevas escrituras, rollback al origen es directo tras validación. Después, requiere exportación inversa validada o corrección hacia adelante; recuperar el backup anterior pierde cambios y exige autorización explícita. No habilitar doble escritura como seguro aparente.

PostgreSQL JSONB reordena claves y cambia representación. Validar equivalencia semántica, tipos/números y renderización/merge, no solo bytes. Prevalidar documentos con claves duplicadas, caracteres o valores no representables fielmente y datos corruptos; no normalizarlos silenciosamente al importar.

## 12. Gates y experimentos antes de producción

**Estado al cierre documental:** ningún gate G0–G5 se declara satisfecho. La aprobación de arquitectura no sustituye sus evidencias. G0 es obligatorio antes de cualquier corte de persistencia; Foundation puede investigarse y probarse previamente solo en entornos aislados con datos sintéticos y autorización independiente. La validación sintética no acredita el proveedor ni la recuperación completa del despliegue objetivo.

| Gate | Evidencia de aceptación | Recuperación si falla |
| --- | --- | --- |
| G0: inventario/procedencia | Clientes/orígenes identificados; backups locales comprobados; imagen frontend identificable; correspondencia API documentada | No cortar persistencia existente ni borrar clientes; resolver diferencias. No impide Foundation sintética aislada |
| G1: foundation | Pool/roles/migraciones/RLS sobre PostgreSQL real; backup y restore aislado; compatibilidad del proveedor | No habilitar nuevo backend autoritativo; corregir con datos sintéticos |
| G2: corte identidad/Training | Importación equivalente, consumidores adaptados, autoridad única y reversión ensayada | Rollback antes de escrituras; luego recuperación explícita sin pérdida silenciosa |
| G3: compatibilidad | Auth, sync, offline, medios, coach, MCP y administración sin regresión | No comenzar datos reales Recovery; resolver contrato |
| G4: dominio Recovery | Escenarios A-D del PRD, atomicidad, idempotencia, snapshots y aislamiento demostrados | Mantener Recovery no disponible y preservar Training |
| G5: experiencia web responsive/datos reales | Recorrido visible completo de captura, organización, sesión, guardado, continuación e historial; autenticación, persistencia, matriz §12.1 y restauración operables | No iniciar las tres sesiones reales si falta evidencia del recorrido o hay riesgo de pérdida; corregir primero |

Pruebas obligatorias:

- PostgreSQL real descartable en CI, versión fijada acorde al objetivo; aislamiento por BD/esquema y sin credenciales ni acceso a producción. Mocks solo complementan.
- Migraciones desde BD vacía y desde el esquema anterior; ejecución simultánea, fallo/interrupción y lock. Constraints/RLS/versiones realmente aplicadas.
- Autenticación existente: passkeys, contadores, revocación, usuarios deshabilitados, roles, contraseñas opcionales y sesiones; no reidentificar usuarios.
- Training: revisiones/linaje, primer documento concurrente, stamps legacy, reset, importación, polling, pérdida de respuesta y dos dispositivos.
- Offline Training, sesión activa local y cambios pendientes: reconciliación tras migración/restauración sin sobrescritura silenciosa.
- Recovery: escenarios A-D completos del PRD; correcciones sucesivas y ejercicios editados sin reescritura de snapshots.
- Atomicidad: fallo antes/después del commit, recuperación y consistencia de cambio/corrección/recibo.
- Idempotencia concurrente: mismo ID/contenido, ID reutilizado con otro contenido, reinicio, respuesta perdida y reintento tras otras escrituras.
- RLS: propietario distinto, contexto ausente, pool reutilizado tras commit/rollback y roles que no pueden leer Recovery; probar sin superusuario.
- No filtración a coach, MCP, export/admin Training, sincronización global, cachés o logs.
- Medios: caída de BD no equivale a referencias vacías ni dispara GC destructivo.
- Restauración completa medida, con autenticación, archivos externos, generación y clientes antiguos.
- Suites frontend/API/MCP, locales/builds pertinentes y verificación web responsive según §12.1, separada de las tres sesiones reales de adopción.

Experimentos propuestos, no ejecutados ni autorizados como implementación:

| Incertidumbre | Experimento acotado futuro | Regla de decisión |
| --- | --- | --- |
| Compatibilidad JSONB | Fixture representativa con historial, stamps y datos límite; comparar respuestas y merge | No cortar hasta equivalencia o incompatibilidades explícitamente resueltas |
| RLS/pool | Dos propietarios, conexión reutilizada y fallos transaccionales | Cualquier fuga bloquea Recovery; no quitar RLS silenciosamente |
| Tooling de migración | Dos ejecutores, interrupción y recuperación en BD descartable, sesión acotada de evaluación | Adoptar runner solo si cumple locking y ejecución reproducible en Node/ESM |
| Restore operativo | Ensayo completo y medición con conjunto representativo | Confirmar RPO/RTO solo con evidencia y proveedor; ajustar plan/coste si no cumple |

Cada experimento debe acordar su timebox al autorizarlo. Nada de lo anterior se ejecutó sobre datos reales en esta etapa de arquitectura.

### 12.1 Validación web responsive

La entrega actual se acepta como web responsive mediante **Playwright CLI con Edge/Chromium**. La matriz mínima usa viewports genéricos, sin perfiles de dispositivos:

| Vista | Viewport (ancho × alto, píxeles CSS) |
| --- | --- |
| Escritorio | 1440×900 |
| Intermedia | 768×1024 |
| Pequeña | 390×844 |
| Estrecha | 320×740 |

En cada tamaño, recorrer captura → organización → inicio de sesión de entrenamiento → guardado de avances → continuación → completado → historial. Verificar también autenticación y los escenarios A–D del PRD. Registrar caso, revisión probada, navegador, viewport, acciones, resultado y rutas de evidencia; los datos técnicos serán sintéticos y las sesiones de navegador aisladas.

- Conducir la interfaz con Playwright CLI, fijar el tamaño con `resize`, obtener snapshots y capturas y revisar visualmente las pantallas y estados relevantes. Una captura existente sin revisión no acredita aceptación visual.
- Comprobar controles etiquetados, acceso por teclado y foco visible, textos legibles y ausencia de solapamientos o recortes que impidan operar. El recorrido debe poder completarse en los cuatro tamaños.
- Para cada guardado, comprobar el resultado, recargar y continuar o consultar desde otra vista. Una confirmación visual aislada no acredita persistencia. El historial debe conservar resultados y contexto, sin prometer recuperación de ediciones no guardadas.
- Revisar consola y solicitudes fallidas; conservar evidencia sin credenciales, cookies ni datos personales. Cerrar únicamente las sesiones de navegador creadas para la prueba.

Reutilizar [verify-opengym](../.agents/skills/verify-opengym/SKILL.md) para los recorridos invitados que ya cubre. Su helper actual no constituye una matriz responsive ni prueba autenticación o Recovery: estos recorridos necesitan casos dedicados cuando se implementen. Esta revisión no amplía ni modifica el harness. Playwright CLI es la superficie interactiva; no se presupone una suite Playwright Test nueva.

G5 requiere este recorrido visible completo y las garantías de datos/restauración de los gates anteriores antes de iniciar las tres sesiones reales. Estas últimas evalúan utilidad y fricciones desde cualquier navegador/tamaño admitido; las pruebas técnicas no prueban adopción. No se exige teléfono físico, emulación de dispositivo, apps nativas ni otros motores de navegador en esta entrega. HTTPS/origen/RP ID se verifican para publicación y autenticación según §10; localhost compatible puede utilizarse durante el ensayo local.

**Estado:** protocolo acordado, pendiente de ejecución para Recovery. Esta revisión documental no presenta capturas, pruebas visuales ni G5 como aprobados.

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
| Normalización o servicios retrasan Recovery | Training JSONB, Node único y exclusión de componentes futuros |
| Persistencia residual permanente no inventariada | Responsabilidad y salida por almacén; medios/secretos explícitamente diferenciados |

## 14. Secuencia conceptual confirmada de futuras OpenSpecs y handoff

**Estado de la secuencia:** `add-postgres-foundation` ya está creado y en implementación autorizada por tareas; tiene 6/18 completadas (1.1–2.3). El [tracker OpenSpec](../openspec/changes/add-postgres-foundation/tasks.md) es la fuente de progreso. Los demás cambios enumerados siguen siendo handoffs conceptuales y requieren autorización para su elaboración e implementación:

1. `add-postgres-foundation`: conectividad, roles, migraciones, pruebas reales y recuperación. Gate G1; incorpora decisiones operativas pendientes antes del uso real.
2. `migrate-opengym-persistence`: identidad, Training JSONB, contratos y consumidores. Gates G0/G2/G3; debe incluir inventario y reversión, no solo importación.
3. `add-recovery-foundation`: procesos, indicaciones, sesiones, correcciones, recibos y contexto histórico. Gate G4.
4. `add-recovery-experience`: captura, ejercicios, guardado, continuación, historial cronológico sencillo y validación web responsive de §12.1. Gate G5 y validación funcional del PRD.
5. `add-garmin-connector`: iniciativa posterior independiente, tras validar Recovery y definir producto/proveedor/autenticación. Python, import incremental, reintentos y deduplicación por identidad externa; sin escribir archivos ni sesiones Recovery implícitamente.

Foundation y experiencia Recovery no constituyen entregas de producto independientes incompletas: el experimento funcional requiere el recorrido completo del PRD. No iniciar validación de adopción solo por disponer del backend.

Trabajos con PostgreSQL se evaluarán cuando existan tareas duraderas: leases/locks, reintentos, recuperación y deduplicación, sin prometer ejecución externa exactamente una vez. No crear ahora un sistema de colas. LangChain/LangGraph, FastAPI y pgvector requieren justificación separada; ningún servicio futuro administra el esquema de otro sin contrato.

### 14.1 Handoff preparado: `add-postgres-foundation`

**Estado:** [OpenSpec generado](../openspec/changes/add-postgres-foundation/proposal.md), con implementación parcial autorizada: 6/18 tareas completadas, hasta 2.3. Entorno y pool tienen evidencia sintética; migraciones, roles/RLS, recuperación y CI siguen pendientes. G1 operativo no está acreditado. El tracker prevalece sobre este corte de estado.

**Objetivo del primer cambio:** establecer una base PostgreSQL verificable para la posterior migración de identidad/Training, sin convertirla aún en autoridad de los datos existentes. No incluir el corte ni la experiencia funcional Recovery en este cambio.

**Entradas:**

- Este documento aprobado: decisiones §3, contratos §7, tooling §8, seguridad §10, recuperación §11 y gates §12.
- PRD aprobado y escenarios A–D como restricciones de integridad del dominio posterior, no como alcance funcional de Foundation.
- Evidencia As-Is, inventario de consumidores §9 y guías existentes `docs/SELF_HOSTING.md`, `api/openapi.yaml`, Compose/Docker y CI. Revalidar la configuración cuando se autorice trabajo; la observación de §2 no es un inventario permanente.
- Selección `pg`/`node-pg-migrate`; evaluar versiones estables compatibles con Node 22/ESM y fijarlas solo tras verificación.

**Dependencias y límites:**

- Autorización expresa para elaborar el primer OpenSpec y, posteriormente, para implementarlo. Este handoff no sustituye ninguna de las dos.
- Entorno PostgreSQL descartable aislado, versión de ensayo identificada, credenciales de prueba y datos exclusivamente sintéticos. No usar perfiles, secretos ni medios reales.
- Decidir o registrar explícitamente proveedor/major objetivo, TLS, pooler y límites de conexiones. Si no están resueltos, limitar conclusiones al entorno sintético y mantener G1 operativo pendiente.
- No es requisito completar G0 para ensayar Foundation; sí lo es antes del corte de persistencia, que pertenece a `migrate-opengym-persistence`.
- No migrar usuarios ni Training, cambiar autenticación, adaptar consumidores como si el corte ya hubiera ocurrido, ni crear un esquema funcional Recovery por adelantado. Probar RLS con fixtures sintéticas; las políticas reales Recovery se verificarán también en G4.

**Criterios de verificación concretados por el OpenSpec vigente; su cumplimiento se registra por tarea:**

| Área | Evidencia de aceptación esperada |
| --- | --- |
| Compatibilidad | Releases estables identificadas de `pg`/`node-pg-migrate`, dependencias/licencias revisadas y ejecución reproducible en Node 22/ESM. Cualquier prerelease requiere aprobación expresa previa. |
| Pool y conexiones | Apertura/cierre controlados, límites/timeouts, rollback y reutilización segura; credenciales sin exposición en logs. TLS/pooler validados en el entorno que corresponda. |
| Migraciones | Historial único, rol separado, runtime sin DDL, aplicación sobre BD vacía y esquema previo de prueba, ejecución concurrente serializada y recuperación tras fallo/interrupción. |
| Aislamiento | Roles reales no exentos de RLS; fixtures con dos propietarios, contexto ausente, commit/rollback y conexión reutilizada sin filtración. Autorización por propietario y separación Recovery siguen siendo requisitos. |
| Respaldo/restauración | Backup sintético consistente, cifrado/destino externo ensayados en entorno de prueba y restore aislado verificable; declarar alcance y tiempo medido, sin certificar RPO/RTO del despliegue real. |
| CI e integridad existente | PostgreSQL real descartable en pruebas reproducibles, sin acceso a producción; suites pertinentes de frontend/API/MCP sin regresiones. Foundation no cambia autoridad ni contratos Training/auth/coach/MCP/medios. |
| Salida documental | Versiones verificadas, límites, resultados y fallos documentados; estado de G1 y pendientes operativos explícitos. No dar por satisfechos G0/G2–G5 ni autorizar el corte. |

**Dependencia de salida:** la migración de identidad/Training requiere Foundation validada, G0 satisfecho y un procedimiento de corte/recuperación aprobado. Las pruebas sintéticas no permiten omitir estas condiciones. La implementación posterior deberá producir evidencia de gates; este documento no certifica que ya se cumplan ni autoriza migrar datos.

## 15. Pendientes operativos y de verificación tras la aprobación

| Pendiente | Recomendación/criterio | Bloquea |
| --- | --- | --- |
| Versiones y pruebas del tooling seleccionado | `node-pg-migrate` + driver `pg` aprobados; releases estables exactas a verificar/fijar, con pruebas de compatibilidad, locking y recuperación | Validación de Foundation |
| Proveedor/plan/major PostgreSQL | Verificar versión, límites, TLS, pooler, backups/PITR, costes y ubicación | Operación y despliegue objetivo |
| RPO 6 h / RTO 24 h | Objetivos candidatos; aprobación operativa y restore medido | Uso real con garantías de recuperación |
| Retención/cifrado/destino externo | Acordar ubicación, acceso, claves y alertas | Respaldo operativo |
| Inventario de clientes | Identificar navegadores, perfiles, orígenes, teléfonos y datos pendientes | Corte de persistencia |
| Procedencia frontend desplegado | Artefacto/revisión reproducibles; hoy etiquetas `dev` y sin dist local | Corte verificado |
| Acceso web publicado | HTTPS, origen/RP ID/certificado confiable y transición de passkeys; localhost compatible para ensayo local | Publicación/autenticación; no obliga a un dispositivo concreto |
| Contrato MCP y persistencia residual coach | Seleccionar lectura restringida y delimitar autoridad/salida de cada almacén | Retirada de lectores JSON y convergencia |
| Ventana de mantenimiento/rollback | Pausa de todos los escritores y autorización del procedimiento | Corte definitivo |

**Cierre registrado:** el usuario aprobó formalmente esta arquitectura y autorizó el cierre documental de `plan-architecture`, manteniendo los pendientes anteriores sujetos a sus gates. Product Discovery/PRD y arquitectura quedan cerrados; los experimentos y gates técnicos siguen pendientes de ejecución y evidencia. No se reabren decisiones aprobadas sin nueva evidencia técnica que demuestre un problema.

**Siguiente punto de autorización:** continuar las tareas pendientes de `add-postgres-foundation` según su tracker y una solicitud explícita. Esta revisión documental no autoriza tareas PostgreSQL adicionales, corte de persistencia, despliegue, sincronización ni archivo de OpenSpec.
