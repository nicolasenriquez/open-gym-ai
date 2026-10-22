## Context

Estado: **Implementation Ready** para el alcance sintético acordado. Cambio runtime. La autorización actual cubre investigación y especificación, no implementación. El usuario confirmó local/CI sintético y proveedor real pendiente, PostgreSQL 18/Compose separado sin pooler, seams y recuperación sintética cifrada. Confirmó comprensión compartida al cerrar el grill.

Prime del checkout `7162a1d4`, rama `docs/opengym-evolution-discovery`, inicialmente limpio: React 19/Vite/Zustand y Capacitor, frontend/API 1.4.1, API Node ESM con `node:http`, MCP stdio opcional. Vitest en frontend/MCP y node:test en API. Sin ORM, ESLint ni Prettier. CI e imágenes usan Node 22; el host inspeccionado usa Node 24.14.0, que no prueba compatibilidad con Node 22.

Historia relevante: `3cc0e9d5` conserva PRD, glosario y arquitectura aprobados; `f2f83c16` añade benchmark sin ampliar Foundation; `56731cd9`, `e9bf04c5`, `73625b57`, `9a58ef4a` y `71ce4d55` corrigen portabilidad/fixtures de pruebas. No interpretar fallos POSIX de Windows como regresión PostgreSQL sin reproducir en Linux.

Mapa de persistencia actual:

| Superficie | Evidencia y consecuencia |
| --- | --- |
| API identidad | `api/server.js:117–164`, `api/durable.js`: db.json, memoria, escritura durable y backup. No cambiar en Foundation. |
| API Training | `api/server.js:168–193`, `2223–2290`: state-UID.json, revisión/linaje y escritura síncrona sin awaits entre comparar/escribir. No introducir acceso async aquí. |
| Health | `api/server.js:1888–1915`: DATA_DIR escribible. Conservar su contrato. La prueba de readiness PostgreSQL pertenece a la herramienta aislada. |
| Frontend | `frontend/src/main.jsx`, `frontend/src/store/useStore.js`, `frontend/src/lib/api.js`: estado local, sync, medios, modo móvil y mismo origen. Sin cambios Foundation. |
| Lectores | `mcp/src/state.js`, `api/coach/jobs.js`, `api/media.js`: consumidores de archivos. Su adaptación corresponde al corte posterior. |
| Empaquetado | `api/Dockerfile`: COPY explícito y runtime normal sin npm/npx; `docker-compose.yml`: api/web con data/ y coach-auth/. No usar estos volúmenes para ensayos. |
| CI | `.github/workflows/test.yml`: Node 22, suites, build, locales e imágenes, sin PostgreSQL. Añadir disparadores para los nuevos archivos de ensayo. |

Se leyeron AGENTS.md, CLAUDE.md, README, CONTRIBUTING, docs/README.md, docs/SELF_HOSTING.md (investigación delegada), arquitectura §§3,7–12,14.1, PRD §§6–9, glosario y benchmark. La arquitectura contiene decisiones técnicas; no duplicarlas como ADR nuevo. No aparecieron términos funcionales nuevos que requieran modificar el glosario.

## Goals / Non-Goals

**Goals:** demostrar base PostgreSQL reproducible con datos sintéticos: conexiones, transacciones, roles mínimos, migraciones controladas, aislamiento de propietarios, recuperación y evidencia CI. Separar validación sintética de G1 operativo.

**Non-Goals:** datos o secretos reales, G0/corte, importación identidad/Training, cambios en autenticación/HTTP/health, consumidores JSON, esquema funcional Recovery, UI, proveedor contratado, pooler remoto, PITR y garantías RPO/RTO. No habilitar PostgreSQL como autoridad durante Foundation.

## Decisions

### Decisiones acordadas y detalles técnicos recomendados

- Acordado: local/CI sintético, sin decidir hosting de producción. G1 operativo permanece pendiente.
- Arquitectura ya aprobada: `pg` + `node-pg-migrate`, SQL explícito, Node, roles separados, historial único, locking habilitado, migración previa al tráfico compatible. No migrar al arrancar el servidor.
- Aprobado: PostgreSQL 18 estable en Compose de ensayo independiente y CI; conexión privada directa sin pooler. Pin exacto de minor e imagen/digest verificable antes de ejecutar. No utilizar tags `latest` ni prereleases. PostgreSQL 18 figura soportado en la política oficial consultada; no equivale a verificar una imagen descargada.
- Propuesto: módulos nuevos bajo `api/` que no importe el arranque legado; herramientas de migración separadas de la imagen API normal. El entorno aislado no carga `.env` real ni monta data/, coach-auth/ o medios; sin puertos públicos. Credenciales sintéticas propias, proyecto/red/volúmenes únicos; teardown solo de esos recursos verificados.
- Propuesto: pool máximo 4 conexiones, adquisición 5 s, idle 10 s, statement timeout 5 s y lock timeout 2 s en el ensayo. Son valores de prueba configurables, no sizing operativo. Cada transacción reserva un solo cliente, instala contexto local, hace commit/rollback y libera; una conexión no recuperable se descarta. Cierre explícito sin procesos colgados; errores saneados sin DSN/payload.
- Bootstrap privilegiado únicamente en el entorno desechable crea roles. Propietario/migrador separado de runtime; runtime no propietario, sin superuser/BYPASSRLS ni membresía elevable, CREATE/TRUNCATE/DDL denegados. No añadir extensiones.
- RLS sobre fixture sintética en esquema exclusivo de pruebas, no migración de tablas Recovery. Contexto de propietario instalado por el servidor dentro de la transacción, nunca desde payload cliente. Probar lectura y escritura A/B, contexto ausente, rollback y reutilización con pool máximo 1. Eliminar fixtures sin dejar políticas funcionales anticipadas.
- Migraciones reales de Foundation solo establecen infraestructura mínima e historial. Un prefijo de migraciones de ensayo representa el esquema previo; no fingir que existe un esquema productivo previo. Ejecutar dos procesos con lock habilitado y comportamiento fail explícito, interrupción y reejecución. Fallo no se falsea con fake/no-lock; no modificar migraciones ya aplicadas ni prometer checksums no verificados.
- Propuesto para el ensayo de recuperación: pg_dump custom y pg_restore de la misma major, cifrado autenticado AES-256-GCM mediante Node crypto, clave aleatoria separada, manifiesto de versión/hash/alcance, copia a almacenamiento de ensayo separado del volumen fuente y restore en instancia/BD nueva. Verificar rechazo por clave incorrecta/archivo alterado. Es un destino externo simulado; no acredita backup off-host real. Herramientas de backup usan identidad apropiada para capturar todos los propietarios, sin ampliar privilegios runtime. Reaprovisionar roles explícitamente: pg_dump no incluye roles globales. No usar estos scripts con datos reales en este cambio.
- TLS debe validar certificados cuando se habilite; no usar rejectUnauthorized=false ni desactivar validación global. Ensayo directo en red privada no acredita TLS ni pooler de un proveedor. Configuración insegura y logs deben tener pruebas; handshake proveedor queda pendiente operativo.

### Fuentes y versiones investigadas

Consulta del registro oficial npm por HTTPS con validación de Windows el 2026-10-21, sin instalar: `pg` 8.23.1 (MIT, engines >=16), `node-pg-migrate` 9.0.0 (MIT, engines >=20.11). Son candidatos estables comprobados en metadata, no ejecución validada ni lockfile fijado. Dependencias directas revisadas: pgpass/pg-pool/pg-types/pg-protocol/pg-cloudflare/pg-connection-string; glob/jiti/yargs respectivamente. Inventario transitivo/licencias y engines resueltos siguen pendientes de lockfile durante implementación.

La documentación web actual de node-pg-migrate menciona un mínimo >=22.12; no atribuirlo automáticamente a 9.0.0. Usar documentación y fuente taggeadas al candidato y probar Node 22 exacto. npm falló primero por DNS sandbox y luego por cadena CA del host; Invoke-RestMethod obtuvo metadata sin deshabilitar TLS. La instalación reproducible deberá resolver confianza CA legítima, nunca strict-ssl=false.

Fuentes primarias:

- https://registry.npmjs.org/pg/latest y https://registry.npmjs.org/node-pg-migrate/latest — versiones/engines/licencia/dependencias consultadas.
- https://github.com/salsita/node-pg-migrate/blob/v9.0.0/src/runner.ts — fuente de referencia del candidato; locking deberá probarse realmente.
- https://salsita.github.io/node-pg-migrate/upgrading — documentación vigente, posible diferencia con release estable.
- https://node-postgres.com/features/transactions — misma conexión para toda transacción.
- https://node-postgres.com/features/pooling y https://node-postgres.com/features/ssl — lifecycle y TLS.
- https://www.postgresql.org/docs/18/ddl-rowsecurity.html — bypass de propietarios/superuser y límites de RLS.
- https://www.postgresql.org/docs/18/app-pgdump.html — dump consistente, roles globales fuera de alcance.
- https://www.postgresql.org/support/versioning/ — major soportada; confirmar minor/digest antes de ejecución.

### Seams públicos y aprobación

| Seam | Prueba y límite |
| --- | --- |
| API pública del pool/transacción | PostgreSQL real: apertura/cierre, saturación, timeouts, rollback, conexión rota y reutilización. No acredita proveedor externo. |
| CLI de migraciones como proceso | BD vacía/prefijo previo, privilegios, historial, concurrencia, interrupción y recuperación. No acredita corte real. |
| SQL de fixtures RLS con roles reales | A/B y contexto ausente, CRUD prohibido/cruce de propietario, commit/rollback/reuso. No acredita políticas Recovery ni autenticación HTTP. |
| CLI de backup/restore | Dump, cifrar/copiar/descifrar, otra BD, roles/grants/RLS/historial/datos y corrupción. No acredita restore de medios/secretos/identidad. |
| HTTP/consumidores existentes | Suites API/frontend/MCP e imagen normal sin BD. No sustituye G3 con datos migrados. |

Estado: los cinco seams aprobados expresamente durante la conversación. La aprobación cubre esos límites para futura entrega; no autoriza implementar. Cambios materiales de seam requieren reconfirmación.

Concreción del seam de pool en 2.1–2.2: `createDatabase(options)` expone `query(text, values)`, `transaction(work)` y `close()`; el callback recibe una interfaz query, sin acceso a internals del pool. Pruebas mediante SQL real y pool máximo 1; PID/contexto se observan por esa misma interfaz. `node api/foundation/environment.mjs run pool` conserva target guards/cleanup y ejecuta las pruebas con Node 22 fijado. Tras autorización explícita de 2.2, `api/foundation/pool.mjs` implementa BEGIN/COMMIT/ROLLBACK, descarte, cierre y errores genéricos sin cause/detalles driver. Acepta configuración explícita con límites positivos finitos y TLS verificable; rechaza DSN/opciones desconocidas para impedir overrides TLS. Defaults de ensayo: max 4, adquisición 5 s, idle 10 s, statement 5 s, query 6 s, lock 2 s. El contexto local se instala mediante SQL de trabajo confiable; la interfaz del callback caduca al terminar. SQL timeouts no cancelan JavaScript arbitrario; close drena el trabajo activo. No está integrado en la API. Implementación 2.2 y checkpoint 2.3: 12 pruebas PASS en el árbol actual, salida natural 0, timeouts acotados y diagnóstico stdout/stderr sin marcadores DSN/contraseña/payload; recursos del proyecto ausentes tras limpieza. Evidencia: api/foundation/evidence/pool-2.3-{run,audit}.txt. No acredita logs del servidor, proveedor TLS, RLS ni G1 operativo.

## Risks / Trade-offs

- [Pruebas sintéticas confundidas con producción] → informe separado: evidencia sintética por área y G1 operativo pendiente; G0/G2–G5 no acreditados.
- [RLS prueba con rol exento] → inspeccionar atributos, propiedad/membresías y conectar realmente con runtime.
- [Contexto se filtra por pool] → contexto local y prueba con conexión única después de commit/rollback/error.
- [Backup omite propietarios por RLS o roles] → usar identidad de backup adecuada, recrear roles y verificar todos los propietarios y permisos tras restore.
- [CI verde porque no se ejecuta PostgreSQL] → job requerido falla si falta BD, sin skip silencioso y filtros incluyen tooling/Compose/docs operativas relevantes.
- [Contaminar app actual] → ensayo independiente, módulos no importados y smoke de API original sin BD.
- [Ruptura de dependencias/CA] → Node 22 exacto, lockfile, instalación reproducible con CA válida, sin relajar TLS.

## Migration Plan

No hay migración de autoridad. Implementación futura: entorno aislado → pool/roles → migraciones → aislamiento → recuperación → CI/regresiones/evidencia. Cada slice prueba su comportamiento antes de avanzar. Un fallo detiene la validación; se repara o recrea exclusivamente el entorno sintético. Nunca restaurar encima de la instancia actual. La entrega no sincroniza main specs, archiva, despliega ni migra datos automáticamente.

## Open Questions

No quedan decisiones materiales abiertas para el alcance sintético: el usuario aprobó entorno, seams, recuperación y comprensión compartida. Los detalles técnicos recomendados anteriores concretan esas decisiones y deberán verificarse, sin presentar resultados anticipados.

Pin exacto Node 22/imagen PostgreSQL y tooling resuelto: metadata verificada; compatibilidad práctica e inventario transitivo se demostrarán en la implementación y son condición para su checkpoint, no resultado de esta especificación. El proveedor, TLS/pooler operativo, backup off-host real, retención, RPO/RTO, G0, HTTPS iPhone y corte permanecen pendientes de sus fases, sin bloquear el alcance sintético acordado.

## Verification Commands

Superficie propuesta que la entrega debe crear, no comandos ya existentes: `docker compose -f compose.foundation.yml -p opengym-foundation-test run --rm foundation-test` ejecutará Node 22, las pruebas de pool/migración/RLS/restore y limpieza acotada. La misma entrada se usará en local y CI; un fallo devuelve estado no cero. El runner documentará comandos individuales por slice y no activará API/web. Validar configuración con `docker compose -f compose.foundation.yml -p opengym-foundation-test config --quiet`.

Regresiones existentes: desde api/, `npm test` y, como smoke, `node --test test/durable.test.js test/server-db-unreadable.test.js test/server-data-rev.test.js test/server-data-wid.test.js test/server-data-reset.test.js test/server-health-writable.test.js`; desde frontend/, `npm test`, `npm run build`, `node scripts/check-locales.mjs`; desde mcp/, `npm test`, `npm run check:node-loadable`. Usar npm.cmd en PowerShell y exponer sh de Git según CONTRIBUTING para la suite frontend. Los checks POSIX se ejecutan como no root en Linux. La entrega conservará las comprobaciones actuales de imágenes y módulos loadables de CI.

## Specification Readiness Evidence

El 2026-10-21 se ejecutó `openspec validate add-postgres-foundation --strict --no-interactive`: válido. `openspec status --change add-postgres-foundation --json`: proposal/design/specs/tasks completos. Comprobación semántica local con Node: 18 tareas con Traceability adyacente, IDs únicos y orden acíclico exacto, seis requisitos cubiertos por tareas y escenarios presentes; Markdown sin espacios finales. `git diff --check` no produjo errores sobre cambios rastreados; las comprobaciones de archivos nuevos se hicieron explícitamente mediante lectura. El intento inicial de comprobación con Python no pudo arrancar el alias Windows; se repitió con Node satisfactoriamente. No se ejecutaron suites runtime, PostgreSQL, migraciones ni restores; no se instalaron dependencias ni se modificaron código, infraestructura o datos existentes. No se acredita ningún gate operativo con esta validación documental.
