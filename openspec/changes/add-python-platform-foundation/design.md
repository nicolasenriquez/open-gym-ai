## Context

Delivery 4.3 autorizado mediante solicitud explícita, «si» para builds bloqueados/fixtures PostgreSQL propios y «continuar» sobre scanner existente. Revalidación en 49ea6abb0 más diff: pool 39/39 (20 DB real + 19 scanner/proceso) y regresión final 29/29; checkpoint sintético del slice 4 completo, 10/26 tareas. Runner escanea antes de replay, usa spools tmpfs privados/lecturas acotadas y rechaza salida conjunta >4 MiB; no scanner universal ni logs del daemon/servidor PG. Evidencia, fallo transitorio del harness y límites en backend/README.md y tasks. Core/relay/dependencias/producto sin cambios; sin 5.1 ni cierre. Las notas siguientes conservan su contexto histórico.

Delivery 4.2 autorizado mediante solicitud explícita y «y» para builds bloqueados en contenedores y fixtures PG propias; seis seams sin cambios y sin 4.3/cierre. El primer RED histórico se hizo GREEN y se añadieron casos por ciclos; se completan 4.1/4.2, no el checkpoint del slice 4. Database permanece en core por instancia; relay exclusivamente privado en tests, con loopback sintético bajo los marcadores del harness y destino PG fijo. Suite enfocada final: 20 PASS, 29 regresiones host PASS; evidencia/limitaciones en backend/README y tasks. Sin permisos host/datos reales/nuevas dependencias ni cambios de runtime actual. Las notas siguientes conservan los checkpoints históricos.

Delivery posterior 4.1: solicitud exclusiva y confirmación «y» para builds bloqueados/fixtures PostgreSQL propios, sin host installs/datos reales/puertos/socket. Se conserva la seam Database/SQL aprobada y se acota a un primer RED antes de autorizar GREEN 4.2; no escribir toda la matriz por adelantado. CLI pool ejecuta una prueba real de dos colaboradores: mismo PID reusado, observador restringido ve dos filas tras fallo frente a cero esperadas. Scaffold no operacional bajo core, sin implementar transacciones/contexto; 4.1 sigue parcial y sin checkbox, con casos restantes por ciclos. Evidencia/límites en tasks y backend/README; 4.2 y posteriores no autorizados. El párrafo siguiente conserva el delivery anterior.

Delivery 3.3 autorizado exclusivamente para contratos sintéticos/inventarios/evidencia, sin avanzar a 4.1. La referencia `backend/CONTRACTS.md` consolida ocho áreas, propietarios/recorridos cliente, siete proveedores y fuentes/generadores compartidos. El manifest añade únicamente selección de tests existentes del comparador y adapters. Run final `opengym-python-foundation-test-feafd9ce288d9f11`: seis casos HTTP y cuatro suites PASS, cleanup confirmado. No cambios de seam, aplicación, dependencias o entorno normal; no paridad Python ni gates operativos. Estado y límites de entrega en `tasks.md`/`backend/README.md`; los párrafos siguientes conservan su contexto histórico.

Ampliación documental por solicitud del promotor: [arquitectura modular por vertical slices](../../../docs/reference/platform-modularity.md), EV-09 y correspondencia backend/frontend. Define propiedad y colocación para el trabajo pendiente; esta edición no implementa código, no mueve archivos, no repite pruebas runtime ni amplía permisos de ejecución históricos. Las tareas completadas conservan su evidencia original; la conformidad estructural nueva queda pendiente de verificación.

Cambio de runtime/tooling especificado el 2026-10-22. Delivery: 1.1 completado con seams aprobadas y toolchain aislado verificado. 2.1 registró el primer RED conductual de CLI. La solicitud posterior de 2.2 y su confirmación autorizan el esqueleto ejecutable y builds/instalaciones bloqueadas solo en contenedores; CLI/Compose/paquete y targets mínimos añadidos. La solicitud posterior de 2.3, con confirmación de builds y pruebas sintéticas en contenedores, verifica aislamiento/ownership real, fallo controlado, SIGKILL con cleanup explícito y API Node normal sin DB. Completa el checkpoint acotado del slice 2, sin acreditar checkout limpio/host Node 22/CI ni capacidades posteriores. Evidencia y comandos en `backend/README.md` (desde la raíz del repositorio). Checkout de referencia inspeccionado: `db6eb33ee8ec523d7efa7167f793701d288b87b5`, árbol inicialmente limpio. OpenSpec CLI 1.3.1, schema `spec-driven`, sin otros cambios activos al crear este cambio.

`docker-compose.yml` sigue ejecutando Node/JSON. `api/server.js` lee identidad, secretos y documentos Training bajo DATA_DIR; `api/coach/jobs.js` y `mcp/src/state.js` son consumidores adicionales. El frontend conserva estado local/offline y sesión activa. `api/openapi.yaml` describe HTTP, pero declara los handlers como fuente de comportamiento; resolver discrepancias mediante caracterización, no adaptar automáticamente Node a un documento.

`api/foundation/` y `compose.foundation.yml` son un ensayo aislado Node, con pool, migraciones, RLS y recuperación. Su historial y sus 55 pruebas sintéticas registradas son antecedentes, no resultados Python. `.github/workflows/test.yml` ya ejecuta esa Foundation. En el checkout de referencia anterior a delivery no había paquete backend Python ni migraciones productivas PostgreSQL. No se inspeccionaron datos ni configuración personales, servicios vivos o proveedor.

## Goals / Non-Goals

Handoff consolidado aprobado: [esquema SQL](../../../docs/reference/platform-schema.md)
y [operación local](../../../docs/reference/platform-operations.md) se implementarán
en [port-compatible-platform](../port-compatible-platform/proposal.md), dependiente
de esta Foundation. Aquí solo se enlazan y distingue su evidencia: tablas/roles
de negocio, MCP HTTP, backup programado, retención y corte no pertenecen a las
pruebas sintéticas actuales. Esta edición no modifica estado ni resultados previos.

**Goals:** referencia reproducible de compatibilidad, Foundation Python aislada, transacciones/roles/locking comprobados sobre PostgreSQL real, recuperación cifrada y CI con fallos explícitos. Aportar evidencia sintética a G1 y preparar GP conforme a arquitectura §§8–12 y 14.2.

**Non-Goals:** port de rutas de negocio, importar usuarios reales, cambiar frontend/nginx/Compose normal, decidir continuidad de sesiones productivas, activar PostgreSQL como autoridad, retirar Node, probar todas las bibliotecas WebAuthn/coach Python, cumplir GP/GO/G0/G2/G3, Recovery/Garmin/IA nueva, VPS/PITR/SLA, segundo migrador sobre tablas compartidas o almacenamiento de secretos/medios en tablas por anticipación.

## Decisions

### 1. Paquete y entorno independientes

Crear `backend/` con `pyproject.toml`, `uv.lock`, paquete `src/opengym_platform/`, `tests/`, configuración Alembic y README. `compose.python-foundation.yml` define DB y runner Python; un target de pruebas Node separado caracteriza el backend actual con sus fuentes/fixtures sintéticas. El orquestador `scripts/python-foundation.mjs` usa solo módulos estándar de Node 22 y Docker Compose v2. Así Windows no necesita Python, uv o PostgreSQL instalados. No extender el runner Node histórico con dos runtimes ni cambiar el servicio `api` normal.

Proyecto por ejecución `opengym-python-foundation-test-<16 hex>`, red interna, volumen y tags propios, sin puertos publicados ni montajes DATA_DIR/.env/coach-auth/medios personales/Docker socket. Configuración explícita, archivo env vacío y eliminación de overrides COMPOSE_* heredados. Cada recurso lleva etiquetas de proyecto, servicio y marcador sintético. Runtime UID 1000, root filesystem read-only, tmpfs privado, capabilities eliminadas y no-new-privileges. Las compilaciones pueden necesitar red; los casos ejecutados no llaman proveedores externos.

`config`, `run <group>` y `cleanup <exact-project>` son la interfaz host. Grupos: `contracts`, `environment`, `pool`, `migrations`, `isolation`, `recovery`, `all`. `all` ejecuta en ese orden, incluyendo verificaciones estáticas Python; desconocidos fallan. Cada grupo prepara sus prerrequisitos de forma independiente. Cleanup valida el conjunto completo y nombres/etiquetas antes de retirar recursos propios; preserva un recurso sentinel ajeno. No prune, remove-orphans ni eliminación por prefijos amplios. Fallos de startup, prueba o cleanup terminan con estado no cero; hard kill requiere cleanup explícito del proyecto impreso.

### 1.1 Propiedad modular y handoff del port

La [referencia modular](../../../docs/reference/platform-modularity.md) posee árboles objetivo, reglas de dependencia, contratos y correspondencia frontend. Dentro de este cambio, las piezas nuevas de configuración/pool/transacciones se colocarán en `src/opengym_platform/core/`, los esquemas/probes internos en `health/` y la factory en `app.py`. El runner sigue siendo tooling de ensayo; migración y recovery mantienen procesos separados. No se impone mover código ya entregado ni crear carpetas funcionales vacías para acreditar esta decisión.

`app.py` compone; health usa infraestructura; core no importa app, health o módulos de negocio. El pool se suministra por instancia/lifespan, no por singleton. Las pruebas observan las interfaces ya aprobadas; la colocación no añade una séptima seam ni reduce garantías transaccionales, de cleanup o recuperación. La revisión estructural de archivos/imports se registra además de los resultados conductuales.

La matriz del slice 3 añade propietario futuro y recorrido cliente actual por área, dependencias públicas previstas y límites. Los módulos identity/training/media/administration/notifications/coach/audit y sus contratos Pydantic funcionales se implementarán solo en el port posterior, con router, esquemas, operación, reglas y repositorio locales según necesidad. El piloto será Training compatible con identidad mínima previa; no se construye en Foundation.

Frontend conserva React/Vite/Zustand, pantallas y archivos actuales. El handoff identifica vista, componentes/hooks, transporte/store y helpers relevantes; `features/<area>/` es colocación para futuras intervenciones acotadas, no una tarea de traslado masivo. Reglas puras continúan en `lib/` con tests; ningún cliente funcional duplica auth/transporte o crea otra autoridad offline. Cada OpenSpec posterior aporta el recorrido, dependencias, casos positivos/negativos y evidencia EV-09 en GP/GO/G3.

El destino Docker operativo sigue siendo web/api/db y migrador puntual separado; Foundation no modifica Compose normal ni convierte los módulos en servicios. Los `.mjs` presentes son harness/orquestación de transición y no se convierten en backend HTTP Python. Su eventual recolocación o retirada debe tratar sus consumidores; esta edición no los mueve.

### 2. Toolchain: selección acotada antes del runtime

Ampliación de requisitos de entrega, aún sin ejecutar: las [reglas de construcción/caché](../../../docs/reference/platform-modularity.md#construcción-y-caché-verificables) se verifican sobre imágenes de ensayo en el slice 9. Mantener manifiestos antes de fuentes y cache mounts de descargas compatibles con UID/GID; separar caché de paquetes y caché externa de capas CI. Pruebas frías, repetidas, fuente/manifiesto y lock incoherente usan checkout/builder propios, sin editar el lock del usuario ni hacer prune compartido. Conservar comandos/resultados/plataforma/límites; no atribuir aceleración ni caché a pruebas anteriores. Runtime/test/migrate entregables se especifican en operación, sin convertir el harness Foundation en producción.

Usar CPython 3.14 (GIL normal), Debian slim y PostgreSQL 18 con herramientas pg_dump/pg_restore del mismo major. Python 3.14.9 es candidato publicado observado en python.org; PostgreSQL 18.6 y su digest constan en el ensayo Node. No atribuir a esas observaciones compatibilidad conjunta ni actualización de seguridad comprobada.

La tarea 1.1 fija patches estables, imágenes por digest, uv y dependencias exactas, lock transitivo y licencias en un contenedor desechable. Mantener las familias aprobadas: FastAPI/Pydantic 2/Uvicorn, asyncpg con SQL explícito, Alembic/SQLAlchemy 2 solo para migraciones; pytest/pytest-asyncio/httpx, Ruff/mypy; cryptography para AES-GCM. No ORM de aplicación, extras Uvicorn innecesarios, pre-releases ni SDK de telemetría por anticipación. Resolver con TLS verificado y comprobar `uv lock --check` + `uv sync --locked`; sin resolver de nuevo durante pruebas/build reproducible.

Los pins y la instalación verificables son un resultado de entrega previo a los slices runtime, no evidencia obtenida durante esta especificación. Si la resolución estable no admite Python 3.14 o un major elegido, detener el prerrequisito y revisar la decisión, sin downgrade silencioso ni ampliar dependencias. La planificación no instala dependencias ni crea un lock ficticio. En delivery 1.1 se verificaron CPython 3.14.9, uv 0.13.5 y PostgreSQL/tools 18.6; digests, pins y licencias quedan en `backend/versions.json`, `backend/pyproject.toml`, `backend/uv.lock` y `backend/dependency-licenses.json`. `uv lock --check`, instalación bloqueada e imports pasaron en linux/amd64; no prueba otras arquitecturas ni interacción con PostgreSQL. FastAPI incorpora `opentelemetry-api` transitivamente, sin añadir SDK/collector/exporter.

### 3. Caracterización antes del port

Mantener una matriz en `backend/CONTRACTS.md` y fixtures/casos ejecutables compartibles con el port posterior. Cada fila registra capacidad, productor/consumidor/almacén, interfaz, fuente y caso/comando actual, expectativas, límites y gate futuro. Cubrir todas las áreas de arquitectura §9.1. Ejecutar al menos un caso positivo y uno negativo por área cuando exista una operación protegida; rutas públicas usan éxito y entrada/fallo pertinente. No convertir una fila inventariada en una prueba ejecutada. La ruta inicialmente propuesta `backend/characterization/README.md` fue sustituida por la referencia realmente entregada desde 3.1; no crear otra matriz duplicada.

La referencia HTTP es el servidor Node real, arrancado como hijo en el target Node de pruebas con DATA_DIR temporal y secretos sintéticos; readiness por señal/HTTP con deadline, no sleeps arbitrarios. Reutilizar los tests existentes y añadir solo los casos de contrato faltantes. Inputs/expectativas serán independientes de internals Node, identificados por caso y revisión; no duplicar snapshots completos del usuario. Normalizar únicamente campos volátiles enumerados por caso (reloj/nonce/puerto), nunca IDs, tipos, null/ausencia, errores, cookies/headers semánticos, stamps o permisos. Fixtures no se generan a partir de producción ni se aceptan como correctas actualizando snapshots automáticamente.

El RED de este slice pertenece al comparador/runner nuevo: una respuesta sintética alterada debe producir mismatch y exit no cero; el primer RED muestra que el runner no detecta esa diferencia, y GREEN demuestra que la detecta. La expectativa de esa prueba es el rechazo, no un baseline roto. Los casos del Node actual se caracterizan por separado y pueden pasar desde el primer intento. No modificar Node ni falsear expectativas para fabricar RED.

| Área | Prior art y prueba observable de referencia |
| --- | --- |
| HTTP y configuración | `api/openapi.yaml`, handlers y tests HTTP: status/cuerpo/headers, ruta inexistente, límite de cuerpo y modo password deshabilitado. |
| Identidad/password/sesiones | `api/password.js`, `api/test/password.test.js` y pruebas de handlers: vector scrypt/NFKC, sesión válida/inválida/revocada, pairing y acceso a recurso ajeno. Inventariar WebAuthn/contadores y casos existentes; el port de biblioteca queda para GP. |
| Training/sync | `api/test/sync-stamps.test.js`, `api/sync-stamps.js` y pruebas HTTP: GET/PUT, stamps legacy, conflicto, borrado y respuesta perdida. |
| Cliente/offline/import/export | Suites de `frontend/src/store/useStore.*` y `ServerSync`: invitado, sesión activa y pendientes, reconciliación, export/import; conservar fixtures/casos y comandos, sin automatización UI nueva en esta spec. |
| Administración/push | Handlers/tests de invitaciones, roles, audit y suscripciones: permisos y modos habilitado/deshabilitado. Push se sustituye solo en su transporte externo, sin entregar notificaciones. |
| Catálogo/medios | Tests `api/test/media-*.test.js`, assets y referencias catálogo: lectura/ownership, import/export y error de referencias no interpretado como vacío para GC. |
| Coach | Tests de `api/coach/` con proveedor fixture: consentimiento, propuesta/aprobación y rechazo; inventario por proveedor/SDK/CLI/config/jobs/sandbox sin credenciales ni llamadas reales. |
| MCP | `mcp/test/state.test.js` y herramientas stdio: propietario, lectura válida, error de lectura y rechazo de selección ambigua. Sin migrar su transporte de datos en este cambio. |

La matriz diferencia estado persistente/memoria/cliente, bytes multimedia, secretos y autoridad futura. Identifica el destino de cada almacén (sustituir, conservar justificadamente o retirar); no diseña el esquema funcional ni cambia contratos. Las incompatibilidades futuras de sesiones, WebAuthn, coach y MCP se remiten explícitamente al port y bloquean GP, no el ensayo Foundation.

### 4. Interfaz DB y aplicación Foundation

`create_app(settings)` crea FastAPI por factory; lifespan abre/cierra el pool perteneciente a esa instancia de aplicación, sin singleton global compartido entre factories. Rutas exclusivas de ensayo `GET /health/live` y `GET /health/ready`, internas a la red descartable; no modifican `/api/health` actual. Live responde 200 mientras vive el proceso; ready 200 solo con DB accesible y revisión Alembic esperada, 503 con código seguro si falta DB/esquema. Startup con DB ausente falla acotadamente; las comprobaciones de caída se realizan también después del arranque.

Interfaz pública Python: `Database.open(settings)`, `execute(sql, *args)`, `fetch(sql, *args)`, `transaction(owner_id=None)` como context manager async y `close()`. El handle transaccional expone execute/fetch, usa una conexión y deja de ser válido al salir. No expone el cliente asyncpg. SQL parametrizado; consultas de propietario siempre en transacción con contexto `app.owner_id` instalado por código de confianza mediante set_config local. owner_id ausente no concede nada; las fixtures no implican autenticación HTTP. El acceso a datos protegidos solo se realiza mediante el handle de `transaction(owner_id)` con contexto local; `Database.execute/fetch` fuera de ese bloque no instala ni hereda propietario.

Defaults de ensayo: pool min=1/max=4; conexión/adquisición 5 s; statement 5 s; comando 6 s; lock SQL 2 s; cierre 10 s. Overrides positivos/acotados se usan para casos rápidos. Ante fallo antes de enviar COMMIT se hace rollback si la conexión lo permite; solo se reutiliza una conexión con estado limpio comprobado, en otro caso se descarta. El cierre deja de admitir trabajo y termina conexiones si agota su deadline. Contexto/callbacks no pueden sobrevivir a su transacción. Probar max=1 para forzar reuso, saturación y conexiones rotas.

Un error SQL que aborta la transacción marca el handle como fallido, aunque el caller capture la excepción. Ese handle rechaza consultas posteriores; al salir se revierte y se lanza un error público con código `DATABASE_TRANSACTION_ABORTED`. Salir del bloque sin excepción no acredita commit. Conservar esta garantía del test existente `api/foundation/pool.test.mjs` (caso de error SQL capturado); no depender únicamente del context manager asyncpg ni aceptar ROLLBACK como confirmación de COMMIT.

Distinguir tres resultados: commit reconocido, rollback confirmado y resultado incierto. Si COMMIT fue enviado y se pierde su respuesta sin poder determinar el resultado, descartar la conexión y lanzar error seguro `DATABASE_COMMIT_OUTCOME_UNKNOWN`, con atributo público `commit_outcome="unknown"`; no reintentar escrituras ni afirmar que el intento posterior de rollback deshizo un commit. Cancelación sigue propagándose como `CancelledError`; si el commit quedó sin resolver, esa cancelación lleva `commit_outcome="unknown"` sin reemplazar su tipo ni exponer la excepción del driver. Una confirmación ya recibida no se reclasifica como rollback por una cancelación posterior.

La prueba de respuesta perdida usa PostgreSQL real y un relay TCP controlado dentro del contenedor de pruebas: retiene la respuesta de COMMIT, una conexión independiente restringida comprueba la escritura visible y entonces el relay corta la conexión cliente antes de entregar la confirmación. Coordinación por eventos con deadline; no sleeps ni monkeypatch de internals del driver. Comprobar un solo intento, ausencia de éxito/rollback falsos, descarte y siguiente adquisición limpia. El relay solo admite la DB sintética, no publica puertos ni añade servicio Compose; probar también cancelación mientras espera la respuesta retenida. La fixture y el rol observador se preparan/retiran con setup SQL desechable, sin depender del runner Alembic del slice posterior. No crear recibos ni idempotencia de dominio por este caso.

Conexión por campos explícitos y configuración validada; no DSNs/opciones arbitrarias ni herencia de servicios libpq. TLS con verificación por defecto fuera de la red sintética; la excepción plaintext solo admite el destino descartable. Certificados sin hostname/CA verificados se rechazan, sin afirmar handshake de proveedor probado. Errores públicos y logs usan códigos allowlisted, no exceptions/cause/SQL/params/credenciales del driver.

### 5. Migración única y RLS sintético

La interfaz Database de §4 debe permitir que dos colaboradores sintéticos reciban el mismo handle explícito y participen de la única transacción iniciadora. El segundo falla: ambas escrituras se revierten; en éxito ambas se confirman una sola vez y el siguiente borrower no hereda contexto. Los colaboradores no adquieren otra conexión ni hacen commit; probar por la interfaz pública y consultas independientes. No crear módulos de negocio ni un framework de unidad de trabajo para esta prueba. En el port, las operaciones públicas de módulos usarán este contrato y declararán por caso autorización, audit y recuperación de efectos externos según la [referencia transaccional](../../../docs/reference/platform-modularity.md#transacción-entre-operaciones-de-módulos).

Bootstrap privilegiado solo dentro del entorno descartable, migrador separado como dueño del esquema y runtime sin DDL/owner/superuser/BYPASSRLS ni membresías elevadoras. Rol consumidor Training sin acceso a la fixture protegida. Revocar grants públicos innecesarios, incluidos CREATE/TEMP, y comprobar privilegios reales.

`python -m opengym_platform.migrate bootstrap|up` es una CLI controlada sin `stamp`, `down`, fake o desactivación de locks. Bootstrap restringido a ensayo; `up` usa Alembic mediante SQLAlchemy async/asyncpg, NullPool y conexión dedicada. Adquirir advisory lock de sesión con clave constante documentada ANTES de leer/aplicar historial, mantenerlo en la misma conexión durante toda la ejecución; otro ejecutor falla explícitamente si no lo obtiene. El cierre de conexión libera el lock. Alembic no proporciona esta garantía por su nombre.

Un historial Alembic; migraciones de infraestructura mínimas sin tablas identidad/Training/Recovery. Revisiones inmutables; fixtures de migración/RLS fuera del historial funcional. Probar vacío/prefijo, revisión desconocida, fallo transaccional, dos procesos, SIGTERM y desconexión; reejecución no inventa revisiones exitosas. Usar señales/pg_locks para coordinación con deadline. No ejecutar node-pg-migrate contra esta DB.

Fixture con owner A/B, ENABLE y FORCE RLS, USING/WITH CHECK por owner_id frente al contexto local, contexto ausente/empty denegado. Probar CRUD, falsificación de owner, TRUNCATE/DDL/elevación y reuso tras commit/rollback/timeout/cancelación con runtime real restringido. La identidad privilegiada solo prepara e inspecciona metadatos; no acredita acceso autorizado haciendo CRUD como superusuario.

### 6. Backup/restore y observabilidad acotados

CLI `python -m opengym_platform.recovery backup <bundle> <key> <revision>`, `copy <bundle> <destination>` y `restore <bundle> <key> <target-db>` solo para destinos sintéticos identificados. Snapshot consistente de pg_dump custom; manifiesto versionado con revisión, historial, versiones, roles requeridos, checksum y alcance. AES-256-GCM mediante cryptography, nonce nuevo de 12 bytes, clave aleatoria separada de 32 bytes, manifiesto autenticado como AAD; no implementar algoritmos propios. El bundle transferido no contiene clave ni plaintext.

Limitar artefactos de este ensayo a 32 MiB y subprocess a 30 s; directorios privados creados exclusivamente bajo tmpfs, sin symlinks/path traversal/sobrescrituras. Autenticar/verificar antes de conectar al destino; target distinto, vacío y propiedad confirmada del bootstrap, con nombres y marker verificados. Restore transaccional exit-on-error; no create/clean sobre destino arbitrario. Roles preprovisionados explícitamente en el cluster descartable; verificar ACL/ownership/RLS, historial y datos mediante runtime restringido en destino, conservando fuente. Un error de restore invalida el destino; no declararlo utilizable parcialmente.

La transferencia separa directorios y base destino, no demuestra copia off-host, pérdida del cluster, medios/auth completos ni RPO/RTO productivos. Medir alcance y tiempo incluyendo/excluyendo setup de manera explícita. Conservar evidencia saneada en temporales/CI, no logs brutos en Git.

Para este slice, salud, logs estructurados acotados y errores seguros son obligatorios. Evaluación de EV-08: no añadir aún un SDK/collector OpenTelemetry; mantener interfaz DB concentrada y registrar cobertura de salud/timeouts, quedando tracing, métricas/exportador, acceso/retención y ensayo completo de GO expresamente para port/operación. No declarar EV-08 satisfecho con health/logs. Esta elección evita instrumentar rutas de negocio inexistentes.

### 7. Seams públicas de prueba

Autorización actual: solicitud exclusiva 4.3 y confirmación «si» para builds con lockfiles existentes en contenedores desechables y fixtures PostgreSQL/cleanup propios. Continuación sobre scanner existente aprobada, seis seams conservadas; sin nuevas dependencias, datos personales, instalaciones host, puertos/socket montado, 5.1, commit/sync/archive/publicación o cierre.

Histórico de autorización 4.2: `/opsx-delivery-workflow openspec\changes\add-python-platform-foundation 4.2`, confirmación «y» para builds con locks existentes solo en contenedores y fixtures PostgreSQL/cleanup propios. Cubre GREEN y ciclos enfocados en Database/SQL/relay ya aprobados, conservando seis seams y aclaraciones. No cubre ejecución/cierre de 4.3, instalaciones host, nuevas dependencias, datos personales, puertos/socket montado, tareas posteriores, commit/sync/archive/publicación.

Histórico de autorización 4.1: `/opsx-delivery-workflow openspec\changes\add-python-platform-foundation 4.1` y confirmación «y» para builds con lockfiles existentes exclusivamente en contenedores y creación/cleanup de fixtures PG propias. La respuesta previa acotó a un único RED (scaffold ejecutable para llegar a aserción, no fallo de import/setup), sin GREEN/4.2 ni matriz completa adelantada. La primitiva colaborativa documental añadida se incorpora al primer caso mediante dos funciones sintéticas que reciben el mismo handle; no introduce módulos ni nueva seam. Los criterios restantes de 4.1 siguen pendientes por ciclos; no se autoriza commit/publicación/sync/archive/cierre.

Histórico de autorización para 3.2: solicitud explícita `/opsx-delivery-workflow openspec\changes\add-python-platform-foundation 3.2`, manteniendo ponytail ultra, y aprobación de builds/dependencias bloqueadas exclusivamente en contenedores desechables. Cubrió implementación/validación enfocada del comparador, fixtures HTTP y reutilización de suites cliente/MCP por el runner existente, incluidas comprobaciones de integración necesarias. Se conserva la seam aprobada; sin instalaciones host, datos personales, nuevas dependencias, cierre de 3.3 ni tareas posteriores. Esta revisión solo es documental.

Histórico de autorización para 3.1: la solicitud `/opsx-delivery-workflow openspec\changes\add-python-platform-foundation 3.1` cubrió solo inventario y primer RED del comparador/runner en su seam aprobada. Interfaz mínima de proceso `node backend/contracts-run.mjs compare <expected.json> <actual.json>`, sin instalaciones, builds ni ejecución del baseline. No amplió las seis seams ni autorizó GREEN/3.2, 3.3 o cierre. El estado posterior de entrega consta en `tasks.md`; este párrafo conserva el alcance de aquella solicitud.

**Seis seams aprobadas explícitamente en delivery**, tras la revisión comparativa de AI Tutor `c28d4c3` y la respuesta del usuario «proceed with recommended decision». La autorización inicial cubrió únicamente el prerrequisito 1.1: descargar imágenes y resolver/instalar dependencias en contenedores desechables, sin instalar en host, montar datos personales ni publicar puertos. La solicitud posterior `/opsx-delivery-workflow openspec/changes/add-python-platform-foundation 2.1` autoriza solo sus pruebas RED y scaffold CLI sin acciones; usa recursos Docker vacíos/temporales para ownership, sin arrancar contenedores ni instalar dependencias. La solicitud posterior `/opsx-delivery-workflow openspec/changes/add-python-platform-foundation 2.2` y el «yes» a builds/instalaciones bloqueadas en contenedores autorizan exclusivamente 2.2 y sus comprobaciones enfocadas. Ese permiso se limitó a 2.2. La solicitud posterior `/opsx-delivery-workflow openspec/changes/add-python-platform-foundation 2.3` y la confirmación «goç» a la pregunta de builds/pruebas sintéticas autorizan exclusivamente 2.3: reinstalación de los lockfiles existentes solo en builds/contenedores, fallos sobre recursos propios, sentinel vacío y API normal con DATA_DIR tmpfs sin PostgreSQL. No autorizan instalaciones host, nuevas dependencias, datos/credenciales personales, puertos publicados, socket montado, 3.1/tareas posteriores ni cierre.

Aclaraciones aprobadas: pool por instancia de aplicación, no singleton global; acceso protegido solo mediante transacción con contexto local; comparador, relay y recovery mínimos, con fixtures privadas y sin frameworks generales. El comparador reutiliza suites públicas existentes; el relay pertenece solo a las pruebas de resultado incierto. Recovery conserva el alcance sintético, sin scheduler, retención ni almacenamiento remoto. Toolchain/CI es prerrequisito/verificador de estas interfaces, no una séptima seam. No se modifican los escenarios ni las garantías exigidas.

| Seam | Detecta | No demuestra |
| --- | --- | --- |
| CLI host config/run/cleanup como proceso y Docker inspect | Aislamiento, target ajeno, ausencia DB, resultados/fallos/cleanup y entorno reproducible | Seguridad ante administrador Docker malicioso ni entorno productivo. |
| Comparador/runner y Node HTTP/cliente/MCP con fixtures y resultados públicos | Rechazo de respuesta alterada y baseline actual de status/payload/headers, sync/offline, permisos y errores | Paridad Python, navegador/dispositivo real ni proveedor coach real. |
| Factory/lifespan y HTTP Foundation mediante httpx con lifespan explícito; smoke Uvicorn como proceso | Readiness/liveness, startup y liberación al apagar | Autenticación/negocio ni GO. HTTPX por sí solo no ejecuta lifespan. |
| Interfaz Database y SQL PostgreSQL como interfaz pública de permisos, con relay de fallo de transporte sintético | Atomicidad, error SQL capturado, resultado incierto de commit, límites/cancelación/reuso y permisos/RLS | Autorización HTTP ni policies Recovery. El relay controla transporte; no sustituye PostgreSQL ni prueba un proveedor real. |
| CLI migrate como procesos separados e historial SQL observable | Exclusión, reejecución, fallos/interrupción y privilegios | Locks con pooler/proveedor no probado ni importación real. |
| CLI recovery y consultas con rol restringido en destino | Integridad/cifrado, guardas, equivalencia y aislamiento de restore | Recuperación completa externa/productiva o pérdida del cluster. |

### 8. Pruebas y comandos de entrega

Comandos **futuros**, no disponibles ni ejecutados al especificar:

```sh
node scripts/python-foundation.mjs config
node scripts/python-foundation.mjs run contracts
node scripts/python-foundation.mjs run environment
node scripts/python-foundation.mjs run pool
node scripts/python-foundation.mjs run migrations
node scripts/python-foundation.mjs run isolation
node scripts/python-foundation.mjs run recovery
node scripts/python-foundation.mjs run all
```

Cada grupo ejecuta pytest/casos pertinentes en contenedor; `all` añade `uv lock --check`, `ruff check`, `ruff format --check` y `mypy` sobre el paquete y tests tipados, sin modificar fuentes. Contratos ejecuta los casos de referencia Node/cliente/MCP registrados en la matriz. CLI/config/cleanup se verifican mediante `node --test scripts/python-foundation.test.mjs`; pruebas Docker negativas se incluyen en `all`. CI añade job obligatorio sin continue-on-error y filtros para backend, CLI, Compose, ambas capacidades y este cambio, manteniendo jobs actuales. El job no depende de secretos de instancia; no cambiar branch protection ni publicar imágenes.

Regresión final: suites API/frontend/MCP, build frontend, locales y checks de artefactos ya existentes en CI; además normal API smoke en contenedor sin DB y con DATA_DIR tmpfs. Documentar deuda previa separada de regresiones. No acreditar Actions remota o checkout independiente si solo se ejecutó localmente.

## Risks / Trade-offs

- [Versiones documentadas no equivalen a binarios compatibles] → Prerrequisito verificable antes de código runtime; sin instalaciones host ni declaración de pins validados en planificación.
- [Caracterización se convierte en un segundo backend o suite duplicada] → Reusar pruebas existentes, casos faltantes mínimos y matriz por área; port y nuevas funciones quedan fuera.
- [Dos Foundation confunden autoridades] → Paquetes/DB/proyectos/historiales separados; contrato Node histórico intacto.
- [Cancelación o pool reutilizado filtra contexto] → Max=1, contextos locales, pruebas reales y handles inválidos después de salida.
- [Error capturado o respuesta perdida simula guardado/rollback] → Error transaccional público, resultado incierto explícito, descarte y ningún retry automático; probar ambos recorridos por la interfaz pública.
- [Locks que solo protegen una parte del runner] → Misma conexión dedicada desde antes de leer el historial hasta finalizar, coordinación observable e interrupción.
- [Restore aparente omite roles o contenido] → Manifiesto/ACL/roles explícitos y pruebas como runtime; límites de mismo cluster y tamaño pequeños visibles.
- [Readiness en verde se confunde con plataforma completa] → Matriz de gates: G1 sintético es contribución; G1 operativo, GP/GO y corte permanecen pendientes.

## Migration Plan

No hay migración ni rollout de datos en esta entrega. Añadir tooling aislado y CI, ejecutar slices con fixtures, conservar comandos/resultados/versiones en README y tareas. Eliminar recursos de cada ensayo mediante cleanup acotado; las imágenes base/cachés pueden permanecer. No tocar el stack actual ni borrar datos. Quitar el tooling añadido revertiría esta entrega sin transformar persistencia existente; no implica autorización para revertir cambios ajenos.

El siguiente cambio será port de capacidades/migración ensayada; usará esta referencia y resolverá compatibilidad de credenciales/consumidores. Definirá el slice piloto Training con identidad previa, módulos propietarios, contratos Pydantic, repositorios, recorrido del frontend conservado y pruebas conforme a la referencia modular. La estructura Foundation prepara EV-09, sin acreditarlo completo. Corte y retirada requieren sus gates y autorización posteriores.

## Open Questions

Handoff de las cinco decisiones documentales: Foundation conserva Node en sus rutas actuales e inventaría imports, build web/Vite, generadores/prompts/catálogo y tests del coach local. El port trasladará la fuente canónica JS a `shared/coach-core/` y verificará clientes/paridad sin duplicar la biblioteca. La [matriz de ambientes](../../../docs/reference/platform-modularity.md#matriz-de-ambientes-y-comandos-objetivo) define entradas Foundation y nombres objetivo `compose.platform.yml` + overlays dev/ops para entregas posteriores. CI/desarrollo del port y targets de operación requieren sus OpenSpecs antes de implementarse. Linux/amd64 es evidencia sintética; arm64/proveedor/soporte final no se acreditan aquí. La [matriz por fase](../../../docs/reference/platform-modularity.md#responsabilidad-y-aceptación-por-fase) es la fuente de responsabilidades y criterios, no evidencia runtime nueva.

Las decisiones de alcance de este ensayo y su ampliación documental están definidas; pins/lock/licencias y su evidencia de 1.1 constan en `tasks.md`. Caché y colaboración transaccional añadidas siguen pendientes en 4 y 9. Proveedor/TLS/pooler, sesiones productivas, bibliotecas de port, inventario real, retención/observabilidad completa y RPO/RTO no condicionan este entorno sintético y siguen pendientes en sus futuras etapas. Las seis seams y autorizaciones históricas constan en §7; esta revisión documental no autoriza ejecutar tareas.

## Fuentes y límites de investigación

Fuentes locales: arquitectura §§8, 9.1, 12, 14.2; PRD EV-01–EV-08; referencias de seguridad/observabilidad; OpenAPI, servidor y suites; `api/foundation/README.md`, código y `versions.json`. Se inspeccionaron, no se reejecutaron sus resultados.

Fuentes oficiales consultadas el 2026-10-22, documentos actuales salvo indicación; no demuestran la instalación elegida:

- [Python releases](https://www.python.org/downloads/): rama 3.14 y candidato 3.14.9 publicados; elegir una rama estable evita adoptar automáticamente el nuevo minor 3.15.
- [FastAPI lifespan](https://fastapi.tiangolo.com/advanced/events/): recursos inicializados/cerrados en lifespan; aplicar pool allí.
- [asyncpg API](https://magicstack.github.io/asyncpg/current/api/index.html#connection-pools): pool, transacciones y timeouts; verificar cancelación/reuso mediante pruebas propias.
- [asyncpg 0.32.0, transacciones](https://github.com/MagicStack/asyncpg/blob/v0.32.0/asyncpg/transaction.py): no atribuir al context manager la garantía del error SQL capturado sin comprobar el wrapper; antecedente conductual en `api/foundation/pool.test.mjs`.
- [PostgreSQL 18, cancelación y protocolo](https://www.postgresql.org/docs/18/protocol-flow.html#PROTOCOL-FLOW-CANCELING-REQUESTS): cancelar no acredita que una operación ya terminada haya sido deshecha; distinguir resultado incierto de rollback confirmado.
- [Alembic cookbook](https://alembic.sqlalchemy.org/en/latest/cookbook.html#using-asyncio-with-alembic), encabezado observado 1.20.1: integración async por SQLAlchemy; no acredita exclusión entre procesos.
- [PostgreSQL 18 advisory locks](https://www.postgresql.org/docs/18/explicit-locking.html#ADVISORY-LOCKS): lock de sesión/conexión para proteger el proceso migrador completo.
- [uv Docker](https://docs.astral.sh/uv/guides/integration/docker/): instalación con lock e imagen uv fijada; no usar tags flotantes para reproducción.
- [cryptography AESGCM](https://cryptography.io/en/stable/hazmat/primitives/aead/#cryptography.hazmat.primitives.ciphers.aead.AESGCM), documentación estable 50.0.2: cifrado autenticado con datos asociados; no reusar nonce con una clave. Se descartó como referencia de versión el enlace `latest`, cuyo encabezado era 51.0.0-dev1.

Las páginas de releases de [FastAPI](https://pypi.org/project/fastapi/), [asyncpg](https://pypi.org/project/asyncpg/) y [Alembic](https://pypi.org/project/alembic/) mostraron respectivamente 0.161.0, 0.32.0 y 1.20.1. Son candidatos observados, no un conjunto resuelto; 1.1 debe verificar compatibilidad conjunta y licencias transitivas antes de fijar los pins.

La consulta de metadata PyPI desde PowerShell falló por DNS; no se dedujo una versión ni licencia de respuestas vacías. Las páginas oficiales se pudieron consultar por navegación. Resolución transitiva, disponibilidad de imágenes/digests y compatibilidad conjunta no se ejecutaron ni se presentan como verificadas.

## Readiness de especificación

**Veredicto de walkthrough: YES — Implementation Ready (especificación)**. Alcance, interfaces, seams propuestas, escenarios, slices y dependencias definidos. Durante la autoría, aprobación de seams pendiente e implementación no autorizada; la aprobación posterior de delivery y su alcance constan en §7. Resolución/pinning de toolchain es el prerrequisito verificable de delivery 1.1, no un resultado afirmado aquí.

Comprobaciones ejecutadas durante la autoría:

- `openspec validate add-python-platform-foundation --strict --no-interactive`: válido.
- `openspec status --change add-python-platform-foundation --json`: proposal, design, specs y tasks completos; esto es estado de artefactos, no ejecución de tareas.
- `node scripts/docs/okf.mjs check`: OK, 28 conceptos, 7 índices y 322 enlaces locales del bundle documental. OpenSpec queda fuera de ese bundle.
- Inspección programática de los seis archivos del cambio: 26 tareas sin duplicados, Traceability adyacente, orden completo sin IDs ajenos y enlaces locales resolubles; 10 requisitos y 25 escenarios. Los dos escenarios transaccionales añadidos están referenciados expresamente en la tarea 4.1. Ninguna tarea de implementación completada.
- `git diff --check` y revisión de espacios de los archivos nuevos: sin hallazgos.

Walkthrough tras correcciones localizadas: requisito → escenario → decisión/interfaz → prueba → tarea → checkpoint. Se verificaron el error SQL capturado (fallo público sin persistencia), COMMIT sin respuesta (resultado incierto sin retry/rollback falsos) y caracterización (RED del comparador y baseline Node separado). La revisión independiente de solo lectura no encontró nuevos bloqueantes; se actualizó el conteo de escenarios. El relay permanece dentro de la seam Database/transporte sintético propuesta y su setup no depende del runner Alembic posterior. No se ampliaron producto, permisos ni infraestructura operativa.

Durante la autoría no se ejecutaron suites runtime, Docker, resolución de dependencias ni pruebas PostgreSQL, ni se completó implementación. El estado posterior de delivery corresponde a `tasks.md` y `backend/README.md`; esta sección conserva la evidencia de especificación, no el estado de ejecución actual.
