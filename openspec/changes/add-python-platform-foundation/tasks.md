## Estado de entrega

Cambio de runtime/tooling. Durante la autoría no se implementaron tareas ni se ejecutaron pruebas runtime. En delivery, el usuario aprobó las seis seams de design §7, las tres aclaraciones recomendadas y el entorno desechable para 1.1. La autorización actual se limita a ese prerrequisito; no incluye 2.x ni cierre del cambio.

Cada slice runtime usa prueba conductual fallida → implementación mínima → verificación, con dependencias reales. Un error de import/setup/DB no cuenta como RED conductual. No escribir todas las pruebas por adelantado. Las comprobaciones documentales no necesitan RED runtime: se verifican por cobertura, referencias y validadores.

En caracterización, RED/GREEN corresponde al comparador/runner nuevo y su rechazo de respuestas alteradas. El baseline Node se comprueba por separado y puede pasar desde su primera ejecución; no fabricar una regresión del producto actual.

## 1. Prerrequisitos compartidos

- [x] 1.1 Confirmar las seams de design §7 antes de escribir tests; registrar alcance de la aprobación y cualquier cambio material. Resolver toolchain CPython 3.14 estable y dependencias en entorno desechable autorizado, fijar imágenes/patches/uv/lockfile y licencias; verificar instalación bloqueada, sin instalar en host. Si no es viable, detener y revisar la selección.
  Traceability: python-platform-foundation / Isolated reproducible Python environment / Dependency resolution fails; design §§2 y 7.
  Notes: PASS — seis seams y aclaraciones aprobadas mediante «proceed with recommended decision»; alcance de ejecución solo 1.1. Toolchain CPython 3.14.9 GIL/uv 0.13.5/PostgreSQL y tools 18.6 fijados por digest; 12 pins directos estables, lock transitivo y 38 licencias inventariadas (37 instaladas linux/amd64). `docker build -f backend/Dockerfile.toolchain backend` y contenedor no root/read-only sin mounts/puertos personales: `uv lock --check`, `uv sync --locked`, `uv pip check`, imports, assert versiones/GIL/inventario y lock offline/SHA sin cambios PASS. Binarios postgres/pg_dump/pg_restore 18.6 PASS, sin arrancar servidor. Primeros checks auxiliares corregidos por colorama condicional, licencia desde wheel y tmpfs noexec; no RED conductual. Comandos/evidencia/límites: `backend/README.md`, `backend/versions.json`, `backend/dependency-licenses.json`. Sin instalación host ni evidencia de compatibilidad productiva. `openspec validate add-python-platform-foundation --strict --no-interactive`, `node scripts/docs/okf.mjs check`, `git diff --check` y self-check de pins/lock/licencias/whitespace PASS. Revisión del diff completo de 1.1 (incluidos archivos nuevos): sin bloqueantes; sin cambios de convenciones runtime que requieran editar AGENTS.md.

Checkpoint: toolchain reproducible y seams confirmadas; no prueba de compatibilidad productiva. Verificación: inventario de versiones/licencias, `uv lock --check` y `uv sync --locked` en contenedor; registrar resultados.

## 2. Slice: entorno aislado ejecutable

- [ ] 2.1 Crear primer RED conductual de CLI: cleanup de proyecto ajeno falla antes de Docker y configuración no incorpora .env, COMPOSE overrides, datos/montajes o puertos reales. Añadir caso de ownership mixto con sentinel que permanezca intacto.
  Traceability: python-platform-foundation / Isolated reproducible Python environment / Independent run from a clean checkout; Unsafe cleanup target.
- [ ] 2.2 Implementar CLI host, Compose separado, paquete/runner Python, target Node de caracterización y guardas de recursos, grupos/exit codes y cleanup acotado. Añadir solo esqueleto necesario para ejecutar environment y pruebas; conservar stack y Foundation Node.
  Traceability: python-platform-foundation / Isolated reproducible Python environment / Independent run from a clean checkout; Unsafe cleanup target.
- [ ] 2.3 Verificar environment, CLI y ownership con Docker real: UID/root read-only/tmpfs/red/volumen propios, sentinel preservado y cleanup tras fallo; normal API arranca sin PostgreSQL con DATA_DIR sintético.
  Traceability: python-platform-foundation / Isolated reproducible Python environment / Independent run from a clean checkout; Unsafe cleanup target.

Checkpoint: entorno inicia/termina sin tocar instancia ni recursos ajenos. Comandos: `node --test scripts/python-foundation.test.mjs`, CLI `config` y `run environment`.

## 3. Slice: referencia de contratos actuales

- [ ] 3.1 Inventariar matriz de áreas y almacenes de arquitectura §9.1 con fuentes/casos existentes, autoridad/disposición y límites; crear primer RED del comparador/runner: ante una respuesta sintética alterada, todavía no detecta el mismatch ni produce el exit no cero esperado. No exigir RED del baseline Node.
  Traceability: platform-contract-characterization / Versioned capability and consumer reference / Complete baseline inventory; Reproducible synthetic contract cases / Meaningful compatibility difference detected.
- [ ] 3.2 Implementar detección de diferencias y salida no cero hasta pasar la prueba de rechazo; añadir casos mínimos faltantes sobre Node real, fixtures portables y expectativas independientes por caso/revisión. Reutilizar suites cliente/MCP, registrar normalizaciones permitidas y resolver documentalmente discrepancias de referencia sin modificar Node para fabricar RED.
  Traceability: platform-contract-characterization / Reproducible synthetic contract cases / Current behavior reproduced without personal state; Meaningful compatibility difference detected; Characterization preserves the existing product / Reference and intended contract disagree.
- [ ] 3.3 Ejecutar positivos/negativos de todas las áreas de la matriz, offline/import/export y proveedores fixture sin red externa; registrar resultados, comandos y handoff para port sin declarar paridad Python.
  Traceability: platform-contract-characterization / Versioned capability and consumer reference / Complete baseline inventory; Reproducible synthetic contract cases / Current behavior reproduced without personal state; Characterization preserves the existing product / Port handoff.

Checkpoint: matriz completa con pruebas ejecutadas y límites visibles; sin cambios de comportamiento. Comando: CLI `run contracts`; contraste de matriz con §9.1 y fuentes actuales.

## 4. Slice: conexiones y transacciones Python

- [ ] 4.1 Crear primer RED conductual en interfaz Database: escritura seguida de fallo no persiste y reuso max=1 sin contexto anterior. Añadir por ciclos el error SQL capturado y la respuesta COMMIT perdida tras escritura visible en PostgreSQL real mediante relay sintético, incluida cancelación con resultado incierto; después handle expirado, saturación, conexión rota, cierre y configuración/errores seguros.
  Traceability: python-platform-foundation / Bounded Python database lifecycle / Rollback and connection reuse; Caught SQL failure cannot confirm success; Commit response lost after server commit; Saturation connection failure and shutdown; Invalid TLS or unsafe diagnostics.
- [ ] 4.2 Implementar interfaz asyncpg, configuración validada/TLS, límites/contexto local, transacciones y rollback/descarte. Marcar transacción abortada aunque se capture el error SQL; separar commit reconocido, rollback confirmado y resultado incierto según design §4, sin retry automático y conservando tipo/metadata de cancelación. Mantener cierre acotado, SQL parametrizado y logs allowlisted.
  Traceability: python-platform-foundation / Bounded Python database lifecycle / todos sus escenarios; design §4.
- [ ] 4.3 Ejecutar pruebas sobre PostgreSQL real: error SQL capturado devuelve fallo y no persiste; respuesta COMMIT perdida/cancelada devuelve resultado incierto aunque la fila sea visible, con un solo intento, conexión descartada y siguiente adquisición limpia. Verificar además cancelación antes de commit/reuso, timeouts, terminación y scanner de secretos/SQL/payloads sintéticos.
  Traceability: python-platform-foundation / Bounded Python database lifecycle / todos sus escenarios.

Checkpoint: atomicidad/límites/reuso demostrados sin acceso HTTP de negocio. Comando: CLI `run pool`.

## 5. Slice: migraciones y roles

- [ ] 5.1 Crear primer RED conductual de CLI migrate sobre vacío/prefijo: historial correcto y runtime incapaz de DDL; añadir dos procesos con coordinación observable, revisión desconocida y fallo/interrupción sin historial falso.
  Traceability: python-platform-foundation / Serialized Alembic history and privilege separation / Empty database previous revision and rerun; Concurrent runners; Transactional failure interruption and recovery.
- [ ] 5.2 Implementar bootstrap sintético, roles/ACL mínimos, Alembic e infraestructura mínima; usar conexión dedicada/NullPool y advisory lock de sesión antes de leer historial. Mantener fixtures separadas y no exponer stamp/down/no-lock.
  Traceability: python-platform-foundation / Serialized Alembic history and privilege separation / todos sus escenarios.
- [ ] 5.3 Probar runner real: vacío/prefijo/rerun, historial desconocido, lock entre procesos, SIGTERM/desconexión/fallo transaccional, liberación y recuperación; comprobar atributos/membresías/privilegios efectivos del runtime.
  Traceability: python-platform-foundation / Serialized Alembic history and privilege separation / todos sus escenarios.

Checkpoint: esquema aplicado una vez sin tablas funcionales ni segundo migrador. Comando: CLI `run migrations`. Timebox del ensayo inicial de locking/interrupción: dos horas de trabajo activo; si no demuestra el mecanismo, registrar bloqueo antes de continuar, sin sustituir Alembic ni omitir exclusión.

## 6. Slice: aplicación y salud Foundation

- [ ] 6.1 Crear primer RED conductual mediante factory/lifespan/HTTP: DB o revisión incompatible produce ready 503 manteniendo live 200; probar startup sin DB y terminación Uvicorn como proceso.
  Traceability: python-platform-foundation / Foundation process health / Database or schema becomes unavailable; Startup and graceful stop.
- [ ] 6.2 Implementar FastAPI factory, lifespan del pool, live/ready internos y códigos seguros; recuperar readiness al volver DB/esquema compatible, sin migrar al arrancar ni fallback JSON.
  Traceability: python-platform-foundation / Foundation process health / todos sus escenarios; Bounded Python database lifecycle / Saturation connection failure and shutdown.
- [ ] 6.3 Ejecutar probes de salud y lifecycle, invocando lifespan explícitamente con httpx y smoke de proceso Uvicorn; registrar cierre dentro del deadline y ausencia de datos sensibles.
  Traceability: python-platform-foundation / Foundation process health / todos sus escenarios; Required real-database verification and honest gate evidence / Completed synthetic verification.

Checkpoint: proceso FastAPI diagnosticable y cerrado limpiamente; sin rutas de negocio. Comando: CLI `run environment` actualizado, seguido de `run pool` para integración lifespan.

## 7. Slice: aislamiento RLS real

- [ ] 7.1 Crear primer RED conductual con propietarios A/B y runtime restringido, max=1: lectura/escritura cruzada y contexto ausente; incorporar reuso después de timeout/cancelación y consumidor Training.
  Traceability: python-platform-foundation / Real restricted-role owner isolation / Ownership and privilege matrix; Reuse after every transaction outcome.
- [ ] 7.2 Implementar fixture desechable ENABLE/FORCE RLS, USING/WITH CHECK y grants mínimos; separar setup privilegiado de operaciones verificadas como runtime/consumidor.
  Traceability: python-platform-foundation / Real restricted-role owner isolation / todos sus escenarios.
- [ ] 7.3 Ejecutar matriz CRUD/owner forgery/missing context y TRUNCATE/DDL/elevación; comprobar reuso tras commit/rollback/error/timeout/cancelación, retirar fixtures y registrar metadata de roles/policies.
  Traceability: python-platform-foundation / Real restricted-role owner isolation / todos sus escenarios.

Checkpoint: RLS efectivo y ausencia de fugas en conexión reutilizada. Comando: CLI `run isolation`; no atribuirlo a autorización HTTP o Recovery.

## 8. Slice: recuperación cifrada

- [ ] 8.1 Crear primer RED conductual del recorrido backup/copy/restore y lectura restringida de ambos propietarios; añadir clave errónea, ciphertext/manifiesto alterados, path traversal/symlink/overwrite y DB fuente/ajena/no vacía.
  Traceability: python-platform-foundation / Authenticated isolated synthetic recovery / Restore and semantic verification; Tampered bundle or wrong key; Unsafe path destination or failed restore.
- [ ] 8.2 Implementar dump consistente, manifiesto autenticado, AES-GCM con clave separada y transferencia solo cifrada; restore transaccional en destino verificado con roles explícitos, tamaño/deadlines y guardas; señalar destino inutilizable tras fallo.
  Traceability: python-platform-foundation / Authenticated isolated synthetic recovery / todos sus escenarios.
- [ ] 8.3 Ejecutar recorrido real y negativos; verificar datos/historial/ownership/grants/RLS, fuente intacta y cleanup, medir tiempos y registrar límites de mismo cluster/sin recuperación productiva.
  Traceability: python-platform-foundation / Authenticated isolated synthetic recovery / todos sus escenarios.

Checkpoint: restore sintético verificable sin clave/plaintext en transferencia/logs. Comando: CLI `run recovery`.

## 9. Slice: CI y evidencia final

- [ ] 9.1 Crear primer RED conductual de ejecución `all` sin DB: estado no cero sin skips acreditados; añadir selección de workflow para cambios solo de entorno y propagación de fallo de prueba/cleanup.
  Traceability: python-platform-foundation / Required real-database verification and honest gate evidence / Environment-only change and unavailable database.
- [ ] 9.2 Implementar `all`, verificaciones lock/Ruff/mypy, negativos Docker y job CI obligatorio con filtros de cambios y mismo comando local; mantener jobs Node/frontend/MCP existentes sin publicación ni cambios de branch protection.
  Traceability: python-platform-foundation / Required real-database verification and honest gate evidence / Environment-only change and unavailable database; Completed synthetic verification.
- [ ] 9.3 Ejecutar `all`, harness y regresiones pertinentes API/frontend/MCP/build/locales/artefactos; repetir smoke normal API sin BD. Registrar fallos/deuda previa separados y demostrar comandos desde checkout limpio sin configuración personal.
  Traceability: python-platform-foundation / Isolated reproducible Python environment / Independent run from a clean checkout; Required real-database verification and honest gate evidence / Completed synthetic verification; platform-contract-characterization / Characterization preserves the existing product / Port handoff.
- [ ] 9.4 Consolidar en README y notas de tareas comandos/versiones/licencias/resultados/límites, referencia de contratos y estado de gates; validar OpenSpec estricto, OKF y diff sin modificar archivo histórico, sincronizar specs, archivar, commit o desplegar.
  Traceability: python-platform-foundation / Required real-database verification and honest gate evidence / Completed synthetic verification; platform-contract-characterization / Versioned capability and consumer reference / Complete baseline inventory.

Checkpoint: evidencia nueva sintética reproducible; G1 operativo/GP/GO y cierre de plataforma siguen pendientes. Comandos: CLI `run all`, `node --test scripts/python-foundation.test.mjs`, comandos de suites existentes y `openspec validate add-python-platform-foundation --strict --no-interactive`, `node scripts/docs/okf.mjs check`, `git diff --check`.

## Execution Order

Prerrequisito: 1.1.
Entorno: 2.1 → 2.2 → 2.3.
Contratos: 3.1 → 3.2 → 3.3.
Conexiones: 4.1 → 4.2 → 4.3.
Migraciones: 5.1 → 5.2 → 5.3.
Aplicación/salud: 6.1 → 6.2 → 6.3.
Aislamiento: 7.1 → 7.2 → 7.3.
Recuperación: 8.1 → 8.2 → 8.3.
CI/cierre de entrega: 9.1 → 9.2 → 9.3 → 9.4.

Dependencias: entorno usa toolchain; contratos y conexiones usan entorno; migraciones usa conexiones; salud usa conexiones/migraciones; aislamiento usa roles/transacciones; recuperación usa fixtures e historial; CI/cierre reúne todos los recorridos. Orden recomendado: el listado anterior. Cada slice completa su checkpoint antes de avanzar; grupos independientes preparan sus prerrequisitos al ejecutarse por separado.
