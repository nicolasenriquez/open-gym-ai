## Context

Estado: **implementación sintética completada (18/18 tareas)**; G1 operativo pendiente. El usuario autorizó la implementación por tareas, la consolidación de evidencia y el cierre mediante sync/archive. Este cierre no autoriza commit, push, despliegue, corte de persistencia ni datos reales.

La API y sus consumidores siguen usando archivos JSON. Foundation vive en `api/foundation/`, con dependencias y entorno propios, sin imports desde el arranque legado ni inclusión en la imagen API normal. No modifica los contratos de HTTP, health, autenticación, Training, frontend, coach, MCP o medios.

Contexto de investigación: checkout `7162a1d4`, React 19/Vite/Zustand/Capacitor, API Node ESM con node:http; frontend/API 1.4.1. Fuentes del repositorio: `docs/open-gym-evolution.architecture.md` §§3,7–12,14.1, `docs/open-gym-recovery.prd.md`, `GLOSSARY.md`, instrucciones y guías de self-hosting. Commits de contexto: `3cc0e9d5`, `f2f83c16`, `56731cd9`, `e9bf04c5`, `73625b57`, `9a58ef4a`, `71ce4d55`. Las rutas citadas son relativas a la raíz del repositorio.

## Goals / Non-Goals

**Goals:** demostrar conexiones/transacciones, migraciones controladas, privilegios mínimos, aislamiento RLS y recuperación cifrada sobre PostgreSQL real desechable; verificar compatibilidad legado y dejar evidencia sintética separada de G1 operativo.

**Non-Goals:** proveedor contratado, datos/secretos reales, inventario G0, corte/importación identidad o Training, políticas funcionales Recovery, UI, cambios en consumidores JSON, pooler remoto, PITR y garantías RPO/RTO. PostgreSQL no se convierte en autoridad de dominios existentes.

## Decisions

### Entorno y dependencias

- PostgreSQL 18.6 y Node 22.23.2/npm 10.9.8 fijados por versión/digest; conexión privada directa sin pooler. `pg` 8.23.1 y `node-pg-migrate` 9.0.0, sin ORM ni migrador propio. Lock independiente en Foundation.
- Compose separado, proyecto aleatorio `opengym-foundation-test-<16 hex>`, red interna, volumen propio, sin puertos públicos, bind mounts, Docker socket, `.env` real ni datos/credenciales/medios de instancia. Credenciales públicas sintéticas.
- Runner Linux UID 1000, root read-only, tmpfs, capacidades eliminadas y no-new-privileges. El host solo orquesta Docker. Guardas validan target antes de conectar o mutar.
- Cleanup valida el conjunto completo de recursos por proyecto/marker/service/nombres exactos antes de borrar solo sus IDs/nombres/tag de imagen. No prune ni remove-orphans. Base images y build cache quedan. Ownership labels previenen errores, no un administrador Docker malicioso.

### Pool y transacciones

`createDatabase(options)` expone `query(text, values)`, `transaction(work)` y `close()`. El callback recibe una interfaz query sin acceso a internals; reserva un cliente para BEGIN/work/COMMIT o ROLLBACK. Error de conexión/rollback fallido descarta cliente; COMMIT convertido en ROLLBACK rechaza; handle caduca al terminar. close drena trabajo activo.

Defaults sintéticos: max 4, adquisición 5000 ms, idle 10000 ms, statement 5000 ms, query 6000 ms y lock 2000 ms; límites positivos enteros finitos dentro de signed 32-bit. No sizing productivo. SQL timeouts no cancelan JavaScript arbitrario.

Conexión explícita sin DSN/opciones desconocidas. TLS valida certificados cuando se habilita y rechaza overrides inseguros/global bypass; ensayo privado usa ssl=false. Errores genéricos sin driver fields/cause/SQL/payload. Contexto de propietario se instala por trabajo confiable mediante `set_config('app.owner_id', value, true)` dentro de la transacción, nunca desde payload cliente. No transaction control ni contexto de sesión desde callers.

### Migraciones y privilegios

CLI separada, nunca al arrancar API. Dentro del runner: `node migrate.mjs bootstrap`, `node migrate.mjs up` o `node migrate.mjs up <directory> <schema> [count]`.

Bootstrap transaccional con lock propio provisiona migrador/runtime/Training restringidos y revoca privilegios públicos. Migrador separado aplica `migrations/001-foundation.cjs`, solo infraestructura/schema/permisos/historial `foundation.pgmigrations`; sin tablas Recovery/identidad/Training. Runtime sin propiedad/superuser/BYPASSRLS/DDL/TRUNCATE ni membresías elevables. Training CONNECT sin acceso a fixture.

node-pg-migrate mantiene session advisory lock en modo fail, singleTransaction y checkOrder; finally cierra conexión, diagnóstico saneado. Sin fake/down/no-lock. Migraciones aplicadas inmutables; no checksum enforcement prometido. Rehacer entorno desechable en vez de rollback.

Fixtures CJS fuera de migraciones funcionales, en paths canónicos `/tmp/foundation-migrations-*`, schemas `foundation_probe_<16 hex>` e historial propio pgmigrations; count positivo permite prefijo real. Concurrencia/interrupción coordinadas con IPC después de comprobar pg_locks en hijo y padre, sin sleeps arbitrarios ni hook de pausa funcional. Tras terminar backend se libera el gate JavaScript de fixture; no se presume cancelación de JS por SQL.

### Aislamiento RLS

Fixture migrator-owned `foundation_isolation_<16 hex>`, fuera del historial funcional. A/B son propietarios sintéticos de datos bajo runtime real compartido, pool max 1. ENABLE/FORCE RLS y política runtime FOR ALL con USING/WITH CHECK: `owner_id = nullif(current_setting('app.owner_id', true), '')`. Contexto ausente/vacío deniega. Grants USAGE/CRUD, no TRUNCATE. Training real sin grants de fixture. Teardown verifica schema ausente y PID runtime cerrado. No prueba autenticación HTTP ni políticas Recovery.

### Recuperación cifrada

CLI dentro del runner: `backup <bundle-dir> <key-file> <40-hex-revision>`, `copy <bundle-dir> <transfer-dir>`, `restore <transfer-dir> <key-file> <foundation_restore_16hex>` mediante `node recovery.mjs`.

Paths tmpfs canónicos/privados/propios `/tmp/foundation-recovery-*`, archivos regulares de un link, destinos vacíos y escrituras exclusivas. Clave aleatoria 32 bytes, modo 0600 y separada; bundle solo backup.enc/manifest.json. AES-256-GCM nonce 12/tag 16/ciphertext, bytes de manifiesto como AAD. Manifiesto identifica formato, revisión declarada, historial, versiones BD/tools, origen, owners/roles, cipher y dump SHA-256; revisión sintética de tests no es Git HEAD.

Dump custom pg_dump con snapshot exportado de transacción repeatable-read/read-only; metadata/historial del mismo snapshot. Identidad de backup captura ambos owners sin ampliar runtime. Copia solo ciphertext/manifiesto, nunca clave/plaintext.

Restore verifica autenticidad/hash/archivo mediante pg_restore --list antes de conectar destino. Exige nombre generado, owner bootstrap y BD vacía sin rutinas/tipos/ACL previas; advisory lock serializa cooperadores. pg_restore single-transaction/exit-on-error conserva owners/grants/RLS, sin create/clean. ACL de BD se establece explícitamente después del archive restore; fallo exige descartar target. libpq usa fixed target/allowlisted env/timeouts, sin overrides/servicios/DSN/salidas externas; stderr/SQL no expuestos.

Roles globales provisionados explícitamente por bootstrap y atributos/membresías verificados, compartidos entre dos BD del mismo cluster. No respaldo de globals/passwords ni reprovisión en cluster limpio demostrada. Buffers 32 MiB/timeouts 20 s son para fixtures pequeñas, no tooling productivo.

### Seams aprobados y cobertura

| Seam | Prueba y límite |
| --- | --- |
| API pública pool/transacción | SQL real, rollback/reuso, saturación/timeouts/cierre y conexión rota; no proveedor externo. |
| CLI migraciones como proceso | Vacío/prefijo, historial, privilegios, concurrencia, interrupción/rerun; no corte real. |
| SQL RLS con roles reales | A/B/contexto/CRUD/reuso/permisos; no autenticación HTTP ni políticas Recovery. |
| CLI backup/copy/restore | Cifrado/integridad, distinta BD, datos/historial/grants/RLS; no medios/secretos/identidad. |
| HTTP/consumidores existentes | Suites legado e imagen normal sin BD; no G3 con datos migrados. |

## Risks / Trade-offs

- Pruebas sintéticas no equivalen a producción: G1 operativo y G0/G2–G5 no acreditados.
- RLS exige runtime real no exento y contexto transaction-local; tests verifican atributos/propiedad/membresías y pool max 1.
- Dump no contiene roles globales: bootstrap explícito y comprobación de grants/roles, sin afirmar recuperación de cluster completo.
- BD ausente debe fallar, no skip; misma entrada local/CI y triggers de tooling/Compose.
- Windows-bind/POSIX no demuestra regresión PostgreSQL: checks ejecutados en Linux no root y staging tmpfs cuando fue necesario.
- npm/CA: instalación con trust válido, nunca desactivar TLS. Audit histórico no garantiza ausencia futura de vulnerabilidades.

## Migration Plan

No hay migración de autoridad. Secuencia ejecutada: entorno → pool → migraciones → RLS → recuperación → CI/regresiones/evidencia. Cada slice verificó su checkpoint antes del dependiente; solo recursos sintéticos propios se eliminaron. Nunca restaurar encima de la instancia actual. El cambio posterior de persistencia requiere G0, validación operativa y procedimiento de corte/recuperación aprobado.

## Open Questions

No quedan decisiones materiales abiertas en el alcance sintético. Proveedor, TLS/pooler/límites de producción, off-host/retención/PITR/RPO/RTO, recuperación completa representativa, inventario G0 y corte siguen pendientes de sus fases. No bloquean este archivo sintético ni quedan aprobados por él.

## Verification Commands

Desde la raíz, Docker Linux/Compose disponibles; el host no necesita instalar dependencias Foundation:

```bash
node api/foundation/environment.mjs config
node api/foundation/environment.mjs run all
# Grupos individuales: environment, pool, migrations, isolation, recovery
node --test api/foundation/environment.test.mjs api/foundation/configuration.test.mjs api/foundation/environment-docker.test.mjs
git diff --check
```

La entrada de `environment.mjs` es la usada en local/CI: crea proyecto/recursos identificados y ejecuta cleanup guardado. No sustituirla por `compose run` directo esperando esas garantías. Missing Docker/BD/prerequisitos y fallo de cleanup devuelven nonzero. El README Foundation conserva instrucciones de toolchain y cleanup; las descargas requieren CA/TLS válidos.

Regresiones: en api/, `npm test`; smoke fuente `node --test test/durable.test.js test/server-db-unreadable.test.js test/server-data-rev.test.js test/server-data-wid.test.js test/server-data-reset.test.js test/server-health-writable.test.js`. En frontend/, `npm test`, `npm run build`, `node scripts/check-locales.mjs`, `node scripts/check-source-strings.mjs`, `npm run test:fatigue-probe`. En mcp/, `npm test`, `npm run check:node-loadable`. Desde raíz: `node api/scripts/check-core-loadable.mjs`, `node scripts/build-coach-assets.mjs --check`, `node scripts/build-api-docs.mjs --check` con sus dependencias de build. POSIX en Linux no root; PowerShell usa npm.cmd y sh de Git según CONTRIBUTING.

Los scripts puntuales de suites/smoke de imagen se eliminaron por petición del usuario. Los comandos de suites/build siguen en CI; repetir las assertions exactas del smoke requiere recrear esa comprobación.

## Evidencia consolidada de entrega

La evidencia consolidada sustituye los logs de `api/foundation/evidence`, eliminados por autorización; se retiraron 86 logs rastreados, además de descartarse artefactos locales de la verificación final. También se eliminaron los dos scripts puntuales a petición del usuario. Se conservan conclusiones/comandos/fallos/límites, **no stdout/stderr completo ni hashes por ejecución para reauditar logs**. Los resultados son de la entrega, no nuevas ejecuciones durante consolidación/cierre.

### Fuentes y versiones investigadas

Verificado Linux/amd64 UID 1000: Node **22.23.2**, npm **10.9.8**, PostgreSQL/tools **18.6**, pg **8.23.1** MIT y node-pg-migrate **9.0.0** MIT. Digests:

- Node: `node:22.23.2-bookworm-slim@sha256:48e4b67d85f87bd551df43704e24d252f56cc5f8e9718841aace50f19948f0f9`.
- PostgreSQL: `postgres:18.6-trixie@sha256:edb0c08dc33befd0262ab3b5cf1c4f3f8cfd8b09e88c05b45adee29d6761ddb6`.

`api/foundation/versions.json` y lock v3 conservan pins, 36 versiones transitivas, SHA-512/licencias/engines. Lock SHA-256 observado: `dfa32b226d91be7bb3fae885073bae29f71054335ce0b3f33e1b39ed574e3027`. Host Windows/Node 24.14.0 orquestó Docker Engine 29.4.0/Compose 5.1.1; no acredita otra arquitectura CPU.

npm ci --ignore-scripts --engine-strict, check:toolchain, npm ls --all y npm audit --json PASS; cero vulnerabilidades reportadas entonces. Checker contrastó instalación/lock/exports ESM; cambiar solo pg a 8.23.0 en copia del lock produjo rechazo esperado. Licencias declaradas MIT/ISC/BlueOak-1.0.0; conservar avisos al redistribuir. No revisión legal ni inventario OS/npm-bundled. Algunos engines no declarados; no se inventó compatibilidad. Optional peers @types/pg/pg-native ausentes por diseño. node-pg-migrate --version imprime unknown: versión verificada por metadata instalada. TLS npm verificado.

Fuentes primarias de investigación (consulta original 2026-10-21):

- https://registry.npmjs.org/pg/latest y https://registry.npmjs.org/node-pg-migrate/latest — metadata, contrastada luego con lock/instalación; latest puede cambiar.
- https://github.com/salsita/node-pg-migrate/blob/v9.0.0/src/runner.ts — candidato versionado y locking.
- https://salsita.github.io/node-pg-migrate/upgrading — vigente, no sustituye engines de la versión instalada.
- https://node-postgres.com/features/transactions y https://node-postgres.com/features/pooling — mismo cliente/lifecycle.
- https://node-postgres.com/features/ssl — verificación TLS.
- https://www.postgresql.org/docs/18/ddl-rowsecurity.html — bypass de owners/superuser y políticas.
- https://www.postgresql.org/docs/18/app-pgdump.html y https://www.postgresql.org/docs/18/app-pgrestore.html — snapshot, archive y roles globales.
- https://www.postgresql.org/support/versioning/ — soporte de major.

### Resultados y trazabilidad

| Requisito / slice | Prueba ejecutada y resultado registrado |
| --- | --- |
| Entorno independiente / 1 | Config/guardas/cleanup PASS, target ajeno y ownership mixto rechazados sin modificación, sentinel intacto. Smoke legado inicial 15/15 sin BD en Linux no root/tmpfs, Foundation/pg ausentes. |
| Lifecycle/transacciones / 2 | 12/12 PASS: rollback/write, mismo cliente/contexto tras commit/aborto, saturación/recuperación, conexión rota/reemplazo, cierre, TLS inseguro rechazado, errores saneados, commit abortado/handle caducado. Adquisición/statement <2 s, client timeout/recuperación <1 s; salida natural 0, recorrido build/cleanup 13985 ms. |
| Historial/privilegios / 3 | 7/7 PASS: vacío/prefijo convergen, rerun sin replay; runtime restringido/no propietario/sin membresías, DML permitido y 14 denegaciones 42501; concurrencia con lock fail real, SQL 23505 revierte pendientes, SIGTERM/backend termination libera sesión/lock, rerun sin historial ficticio. |
| Aislamiento / 4 | 20/20 PASS: CRUD propio A/B, cruce/contexto ausente/vacío denegados, forgery INSERT/reasignación rechazada; mismo PID/pool max 1 tras commit/rollback/error, RLS real y atributos/permisos, Training sin acceso. Veinte teardowns schema/PID PASS. |
| Recuperación / 5 | 12/12 PASS: snapshot/dump/cifrado/manifiesto/hash/copia sin clave/restore distinto, A/B/historial/ownership/grants/RLS y CRUD restaurado, fuente intacta. Rechazos de wrong key/corrupción/manifiesto/archive inválidos/destinos ajenos o no vacíos/ACL excesiva/claves públicas o symlink/overwrite. Doce teardowns BD/schema/artifacts/clave PASS. |
| CI / 6.1 | run all 55/55 PASS (4 guardas + 12 pool + 7 migración + 20 aislamiento + 12 recuperación), sin skips; harness 9/9, BD ausente exit 1, actionlint PASS. Misma entrada local/CI, filtros tooling/Compose/OpenSpec. No Actions remoto/branch protection acreditado. |
| Compatibilidad / 6.2 | API 601/601, frontend 5069/5069, MCP 95/95 PASS en Linux UID 1000/Node 22.23.2; build, 18 locales/2258 keys, 1770 strings, fatigue/history probes, API/MCP loadable, coach assets y docs API (69 endpoints/30 schemas) PASS. |
| Imagen independiente / 6.2 | Imagen normal construida previamente y smoke repetido PASS: Node 22.23.2/UID 1000/network none/root read-only/data tmpfs; health/config HTTP y JSON VAPID válidos, Foundation/pg/AI runtime/npm ausentes, terminación limpia. No rebuild en la sesión final. |

Pruebas BD/inventario/restore no repetidas en 6.2–6.3 ni limpieza/cierre. Las suites legado sí tuvieron rerun completo exitoso en 6.2. Auditorías stdout/stderr capturado sin DSN/marcadores sintéticos de contraseña/payload, controles positivos del scanner PASS; no incluyen logs servidor ni todos los RED históricos. Auditorías Docker independientes confirmaron ausencia de recursos propios tras checkpoints.

Revisiones ponytail de seams/código/callers/contrato no dejaron bloqueantes para uso sintético. Validación OpenSpec estricta y whitespace PASS al cerrar 6.3 y consolidación; enlaces locales, 18 tareas con Traceability/Notes y sintaxis de scripts entonces conservados PASS. Esto no sustituye runtime proof.

### Fail-first, fallos y correcciones relevantes

- Pool: baseline 4 RED/2 PASS por write persistido, contexto ausente y reuso fallido tras conexión terminada. RED/GREEN de configuración/diagnósticos/commit abortado/handle caducado; evento de error del cliente arrendado corregido. Final 12 PASS; harness 6 PASS.
- Migraciones: baseline 4 RED por historial/rol/señal ausentes, sin atribuir éxito a ramas no alcanzadas. Implementación/infraestructura a 5 PASS; checkpoint SQL/privilegios/interrupción a 7 PASS. Regresiones pool 12/harness 7 PASS.
- RLS: baseline 11 RED exponían filas/escrituras ajenas, luego 11 GREEN. Rol Training ausente RED seguido de login/ACL real GREEN; implementación 13 PASS y migración 7 PASS; matriz final 20 PASS.
- Recovery: baseline 5 RED por artefacto/copia/rechazos ausentes; controles AEAD independientes evitaron falsos fallos por archivos faltantes. RED/GREEN destino con rutina/ACL excesiva. Final 12 PASS, regresiones pool 12/migración 7/aislamiento 20/harness 8 PASS. Primer checkpoint cronometrado falló por name[] del driver; seleccionar text[] corrigió solo el test. No se contó ese fallo como RED ni restore exitoso.
- CI: all inicialmente ausente RED. Recheck intermedio intentó all.test.mjs ausente tras ediciones externas; implementación restaurada y harness PASS, sin contar fallo de configuración como behavioral proof.
- Preparación: workdir root-owned, DNS/CA/npm downloads, quoting/staging y tmpfs noexec no fueron RED conductuales. Bind Windows provocó boot timeouts; mismo smoke PASS al usar tmpfs sin cambiar assertions/timeouts ni relajar TLS.
- Final legado: staging omitía website/; corregido. Checker luego detectó CRLF checkout frente a blob LF: normalizada solo copia temporal, rerun completo PASS. Build mantiene warnings chunk-size/imports mixtos; sin refactor fuera de alcance.

### Medición de recuperación y límites operativos

Una muestra de dos filas/propietarios, dump 7125 bytes, ciphertext 7153 bytes (manifiesto separado). Backup **104.069 ms**, copia **23.489 ms**, restore CLI **74.436 ms**, verificación semántica/runtime **20.532 ms**, restore+verificación **94.969 ms**, recorrido completo con comprobaciones **227.922 ms**. Reloj monotónico alrededor de procesos reales; excluye setup/build/teardown. Mismo host/cluster y roles globales compartidos, no reprovisión de cluster limpio ni off-host.

No se respaldan roles globales/passwords, medios, secretos o identidad reales. Buffers/timeouts y ACL posterior al restore limitan el uso a fixtures; fallo ACL requiere descartar target. Las verificaciones de datos restaurados revierten sus escrituras y comprueban origen/destino intactos.

Coherente con arquitectura §§12/14.1 y PRD: no entrega funcional Recovery, autoridad PostgreSQL, importación identidad/Training ni retirada de JSON/borrado real. **G1 operativo sigue pendiente** de proveedor/TLS/pooler/límites y recuperación completa representativa; no acredita G0/G2–G5, PITR ni RPO/RTO.

## Closeout

Cierre autorizado y ejecutado el 2026-10-22: seis requisitos y dieciséis escenarios sincronizados en `openspec/specs/postgres-foundation/spec.md`; cambio movido a `openspec/changes/archive/2026-10-22-add-postgres-foundation/` con metadata, evidencia y límites. Cuerpos de requisitos idénticos entre delta y main spec, 18 tareas completas, carpeta activa ausente y `openspec list --json` sin cambios activos. README/PRD/arquitectura/índice y filtros CI actualizados a las rutas vigentes.

Checks de cierre PASS: validación estricta de cambio antes de moverlo y main spec; `openspec validate --all --strict --no-interactive` después; 45 enlaces Markdown locales, whitespace y `git diff --check`; actionlint en contenedor sin red (ShellCheck/Pyflakes deshabilitados). Revisión documental final sin bloqueantes. No se ejecutaron nuevas suites runtime ni CI remoto, ni commit/push/despliegue. El archivo no autoriza migración ni satisfacción de gates operativos.
