## Evidencia y estado

**18/18 tareas completadas para el alcance sintético. G1 operativo pendiente.**
Resultados, versiones/licencias, comandos, fallos y límites consolidados en
[design.md — Evidencia consolidada de entrega](design.md#evidencia-consolidada-de-entrega).
Los logs brutos se eliminaron por autorización; las notas siguientes conservan
la trazabilidad y no representan nuevas ejecuciones durante la consolidación.

## 1. Prerrequisito compartido: entorno y versiones

- [x] 1.1 Fijar releases estables candidatas y resolver lockfile/licencias transitivas/engines en Node 22 exacto; registrar versiones de imagen y tooling, sin instalar en la instancia real.
  Traceability: Controlled migration history and privilege separation / Empty database and previous test schema; design / Fuentes y versiones investigadas.
  Notes: PASS Node 22.23.2/npm 10.9.8, pg 8.23.1/node-pg-migrate 9.0.0, 36 paquetes; ci engine-strict/checker/ls/audit (0 vulnerabilidades entonces). PG/tools 18.6 y digests verificados. Negativo lock divergente rechazado. Inventario y límites en design, slice 1; metadata completa en lock/versions.
- [x] 1.2 Añadir entorno Compose Foundation independiente y runner Node 22; credenciales sintéticas, sin montajes/env reales ni puertos públicos; implementar guardas de target y limpieza acotada.
  Traceability: Isolated synthetic environment / Independent foundation run; Unsafe target rejected.
  Notes: RED conductuales y GREEN; harness 6/6, run environment PASS, Linux no root. Ownership mixto rechazado antes de borrar, sentinel intacto, cleanup incluye tag propio sin prune. Detalle en design, slice 1.
- [x] 1.3 Verificar configuración, rechazo de target ajeno y arranque API legado sin PostgreSQL; documentar invocación reproducible por slice.
  Traceability: Isolated synthetic environment / Independent foundation run; Unsafe target rejected.
  Notes: Config/guardas PASS y smoke legado 15/15 sin skips, Linux UID 1000/network none/tmpfs, Foundation/pg ausentes. Timeouts de bind Windows resueltos solo cambiando staging; no RED artificial. Detalle en design, slice 1 y fallos relevantes.

Checkpoint: entorno identificado y aislado; versiones/comandos reproducibles y smoke sin BD verificados.

## 2. Slice: conexiones y transacciones seguras

- [x] 2.1 Escribir primera prueba de comportamiento fallida del API público de pool/transacción: write seguido de fallo no persiste; reuso sin estado previo. Añadir saturación, cierre y conexión rota.
  Traceability: Bounded connection lifecycle and transactions / Failure and reuse; Pool saturation and shutdown; Connection loss and safe diagnostics.
  Notes: run pool: 4 RED conductuales y 2 PASS, imports/setup/BD válidos, cleanup completo; harness 6/6. Fallos concretos y seam createDatabase/query/transaction/close en design.
- [x] 2.2 Implementar pool, contexto transaccional local, límites/timeouts, rollback, descarte y saneamiento de errores; rechazar TLS sin verificación.
  Traceability: Bounded connection lifecycle and transactions / todos sus escenarios.
  Notes: RED/GREEN adicionales configuración/errores/commit abortado/handle caducado; final pool 12/12 y harness 6/6 PASS. Sin dependencias nuevas ni integración API. Contrato/límites y resultados en design, slice 2.
- [x] 2.3 Ejecutar pruebas reales en Node 22 y PostgreSQL fijados; comprobar terminación, timeout acotado y ausencia de DSN/contraseñas en logs.
  Traceability: Bounded connection lifecycle and transactions / todos sus escenarios.
  Notes: run pool 12/12 PASS sin skips, salida natural 0; adquisición/statement <2 s, client timeout/recuperación <1 s. Scanner stdout/stderr y cleanup independiente PASS; no acredita logs servidor. Detalle en design, slice 2.

Checkpoint: cliente liberado/descartado y proceso terminado; pool máximo 1 en pruebas de reuso.

## 3. Slice: migraciones controladas y roles

- [x] 3.1 Crear primera prueba fallida del runner como proceso: base vacía y prefijo previo llegan al mismo historial; runtime no puede ejecutar DDL. Añadir dos procesos e interrupción coordinada mediante señal de lock adquirido, sin sleeps arbitrarios.
  Traceability: Controlled migration history and privilege separation / todos sus escenarios.
  Notes: 4 RED conductuales por historial/rol/señal ausentes; sin contar ramas no alcanzadas como pruebas exitosas. Pool 12 y harness 7 PASS. Fixtures/IPC/seam documentados en design.
- [x] 3.2 Implementar bootstrap desechable, roles separados, migrador con lock habilitado, historial y migraciones mínimas; mantener fixtures fuera de migraciones funcionales.
  Traceability: Controlled migration history and privilege separation / todos sus escenarios.
  Notes: Baseline RED repetido; fixtures e infraestructura RED/GREEN, final migrations 5/5, pool 12 y harness 7 PASS. Lock fail/singleTransaction/checkOrder y cierre finally; sin tablas de dominio ni fake/no-lock/down. Detalle en design, slice 3.
- [x] 3.3 Probar concurrencia, fallo transaccional, terminación de proceso/conexión, liberación del lock y reejecución sin historial ficticio; verificar atributos/membresías y ausencia de privilegios DDL del runtime.
  Traceability: Controlled migration history and privilege separation / todos sus escenarios.
  Notes: migrations 7/7 PASS; SQL 23505 revierte pendientes conservando prefijo, rerun consistente; concurrencia/SIGTERM/backend termination y 14 denegaciones 42501 PASS. Sin cambios runtime ni RED artificial. Detalle en design, slice 3.

Checkpoint: aplicación única/recuperable sobre vacío y prefijo, sin DDL runtime.

## 4. Slice: aislamiento sintético por propietario

- [x] 4.1 Crear primera prueba fallida con roles reales A/B y contexto ausente: lectura/escritura cruzada denegada; misma conexión después de commit/rollback/error.
  Traceability: Synthetic owner isolation / Cross owner and missing context; Connection reused after commit rollback or error.
  Notes: isolation 11 RED conductuales sin skips; harness 7 PASS. A/B son data owners bajo runtime real compartido, pool max 1. Fixture inicial sin RLS; no acredita políticas funcionales. Detalle en design.
- [x] 4.2 Añadir fixtures desechables RLS con USING/WITH CHECK, contexto local y permisos mínimos; incluir rol Training-only sin acceso y denegación TRUNCATE/elevación.
  Traceability: Synthetic owner isolation / todos sus escenarios.
  Notes: 11 RED repetidos → GREEN; Training ausente RED → login/ACL GREEN; final isolation 13 y migrations 7 PASS. ENABLE/FORCE RLS/USING/WITH CHECK, contexto local y grants mínimos; sin tablas Recovery. Detalle en design, slice 4.
- [x] 4.3 Ejecutar matriz CRUD/propietario/contexto y permisos con pool máximo 1; comprobar runtime no propietario/superuser/BYPASSRLS y retirar fixtures al finalizar.
  Traceability: Synthetic owner isolation / todos sus escenarios.
  Notes: isolation 20/20 PASS sin skips, matriz A/B/contexto/forgery/reuso/permisos completa; 20 teardowns schema/PID y auditoría Docker PASS. Solo verificación, implementación 4.2 sin cambios. Detalle en design, slice 4.

Checkpoint: aislamiento y reuso sin fugas comprobados en PostgreSQL real; no certifica políticas Recovery.

## 5. Slice: recuperación cifrada verificable

- [x] 5.1 Crear primera prueba fallida del recorrido backup cifrado/copia/restore: ambos propietarios, historial y permisos; añadir clave incorrecta, corrupción y destino ajeno.
  Traceability: Verifiable isolated backup and restore / Restore and verify; Corrupt artifact or wrong key; Isolated synthetic environment / Unsafe target rejected.
  Notes: recovery 5 RED conductuales, controles AEAD independientes y fuente intacta; harness 8 PASS. CLI baseline no restaura ni acredita happy path. Contrato y fallos consolidados en design.
- [x] 5.2 Implementar dump consistente, manifiesto, cifrado autenticado con clave separada, transferencia a destino de ensayo y restore aislado con roles explícitos; proteger logs/artefactos y desactivar salidas externas.
  Traceability: Verifiable isolated backup and restore / todos sus escenarios.
  Notes: baseline 5 RED → GREEN; rutina/ACL destino RED/GREEN; final recovery 12, pool 12, migrations 7, isolation 20 y harness 8 PASS. Sin nuevas dependencias. Paths/AEAD/libpq/targets protegidos; límites de buffers y ACL posterior documentados en design.
- [x] 5.3 Ejecutar recuperación completa, comparar datos semánticos de A/B, historial, grants y RLS, verificar fuente intacta y cronometrar; destruir solo recursos sintéticos identificados.
  Traceability: Verifiable isolated backup and restore / todos sus escenarios; Isolated synthetic environment / Unsafe target rejected.
  Notes: recovery 12/12 PASS, teardowns/auditoría PASS; comparación semántica y roles reales, fuente intacta. Restore 74.436 ms, con verificación 94.969 ms, recorrido 227.922 ms; dos filas/mismo cluster, no RPO/RTO. Fallo inicial name[] corregido solo en test, no RED. Detalle en design, slice 5.

Checkpoint: recuperación reproducible y rechazo de contenido no verificado; no acredita off-host/PITR/RPO/RTO real.

## 6. Comprobaciones finales: CI, compatibilidad y evidencia

- [x] 6.1 Integrar runner completo en CI con PostgreSQL real, trigger de archivos de Foundation y fallo obligatorio por BD ausente; comprobar configuración CI y ejecutar la misma entrada de local.
  Traceability: Real database CI and explicit gate evidence / Changed environment definition; Missing database or failed proof.
  Notes: run all 55/55 PASS, harness 9/9 y actionlint PASS; ausencia BD exit 1. RED previo all ausente; restauración posterior/harness PASS descritos en design. No ejecución GitHub remota ni branch protection acreditada.
- [x] 6.2 Ejecutar suites/build/locales y loadable checks pertinentes de API/frontend/MCP, smoke de imagen normal sin BD y comprobaciones POSIX en Linux no root; resolver regresiones propias sin ampliar alcance.
  Traceability: Real database CI and explicit gate evidence / Synthetic success; Isolated synthetic environment / Independent foundation run.
  Notes: Linux UID 1000/Node 22.23.2: API 601, frontend 5069, MCP 95 PASS; build/locales/strings/probes/loadable/assets/docs PASS. Imagen normal sin BD/red PASS. Staging website/LF corregido solo en tmpfs. Scripts puntuales eliminados posteriormente por petición del usuario; resultado histórico y límites en design, slice 6.
- [x] 6.3 Documentar comandos/resultados/versiones/licencias, duración del restore, alcance sintético, fallos y estado G1 operativo pendiente; comprobar coherencia con arquitectura/PRD y validar OpenSpec estrictamente, sin archivar ni cortar persistencia.
  Traceability: Real database CI and explicit gate evidence / Synthetic success; Verifiable isolated backup and restore / Restore and verify.
  Notes: Evidencia consolidada en design y README operativo; OpenSpec estricto/whitespace PASS al cerrar entrega, review sin bloqueantes. BD/restore no repetidos en 6.2–6.3. Coherencia arquitectura/PRD comprobada; G1 operativo y G0/G2–G5 no acreditados. Sin sync/archive/corte/despliegue.

Checkpoint: evidencia sintética completa, sin regresión observada y límites explícitos.

## Execution Order

Prerrequisitos: 1.1 → 1.2 → 1.3.
Conexiones: 2.1 → 2.2 → 2.3.
Migraciones: 3.1 → 3.2 → 3.3.
Aislamiento: 4.1 → 4.2 → 4.3.
Recuperación: 5.1 → 5.2 → 5.3.
Comprobaciones finales: 6.1 → 6.2 → 6.3.

Dependencias: conexiones usa entorno; migraciones usa conexiones; aislamiento usa
roles/transacciones; recuperación usa fixtures/historial; CI reúne los recorridos.
Tracker completado, no autorización de acciones adicionales de cierre.
