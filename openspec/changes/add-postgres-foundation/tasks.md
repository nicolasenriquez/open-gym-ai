## 1. Prerrequisito compartido: entorno y versiones

- [x] 1.1 Fijar releases estables candidatas y resolver lockfile/licencias transitivas/engines en Node 22 exacto; registrar versiones de imagen y tooling, sin instalar en la instancia real.
  Traceability: Controlled migration history and privilege separation / Empty database and previous test schema; design / Fuentes y versiones investigadas.
  Notes: Autorización limitada a 1.1 y descarga/instalación desechable confirmada por el usuario. Paquete aislado api/foundation/: pg 8.23.1, node-pg-migrate 9.0.0, lock v3 y 36 paquetes con licencias/engines contrastados con instalación. PASS en Linux/amd64 no root con Node 22.23.2/npm 10.9.8 fijados por digest: npm ci --ignore-scripts --engine-strict, npm run check:toolchain, npm ls --all y npm audit --json (0 vulnerabilidades reportadas); TLS strict-ssl=true. PASS rechazo de versión lock/instalación divergente en copia temporal. PostgreSQL 18.6-trixie fijado por digest; postgres/pg_dump/pg_restore/psql --version verificados sin arrancar BD. Comandos, inventario y límites: api/foundation/README.md y api/foundation/evidence/{toolchain,checker-negative,images}.txt. Revisión ponytail-review sin bloqueantes; OpenSpec estricto y consistencia/whitespace PASS. Prueba de configuración, no cambio runtime: no RED artificial; suites legado/BD/Compose no ejecutadas y pertenecen a tareas posteriores. Sin instalar en host/instancia ni modificar API normal. 1.2–6.3 pendientes; G1 operativo no acreditado.
- [x] 1.2 Añadir entorno Compose Foundation independiente y runner Node 22; credenciales sintéticas, sin montajes/env reales ni puertos públicos; implementar guardas de target y limpieza acotada.
  Traceability: Isolated synthetic environment / Independent foundation run; Unsafe target rejected.
  Notes: Usuario autorizó 1.2, seams CLI/config efectiva y build/creación/limpieza desechables. compose.foundation.yml + api/foundation/environment.mjs/run.mjs: proyecto aleatorio, red interna, volumen propio, sin puertos/binds/env reales; runner Node 22.23.2 no root con PostgreSQL 18.6 fijados. TDD: RED conductuales observados y GREEN; node --test api/foundation/{environment,configuration,environment-docker}.test.mjs PASS (6 pruebas), guardas también PASS en Node 22 aislado; recorrido real run environment y limpieza PASS. Rechazo de target ajeno/BD ajena, preflight de propiedad completo y sentinel ajeno intacto. Config --quiet PASS; build revalida 1.1 con npm ci/check:toolchain. Revisión ponytail-review resuelta: limpieza del tag de imagen propio sin prune; regresiones repetidas. Evidencia/comandos/límites: api/foundation/README.md y evidence/{environment-green,environment-node22,environment-run,*-red}.txt. OpenSpec estricto y checks de árbol actual PASS. 1.3, smoke API legado, pool/migraciones/RLS/restore/CI no ejecutados; checkpoint compartido y G1 operativo pendientes. Índice staged preexistente preservado; sin commit/sync/archive.
- [x] 1.3 Verificar configuración, rechazo de target ajeno y arranque API legado sin PostgreSQL; documentar invocación reproducible por slice.
  Traceability: Isolated synthetic environment / Independent foundation run; Unsafe target rejected.
  Notes: Verificación autorizada de 1.3, sin cambios runtime/tests/dependencias: caracterización en seams CLI/config y HTTP ya aprobados, no RED artificial. PASS config --quiet y 3 regresiones existentes (evidence/prerequisite-checks.txt); 2 guardas PASS también en Node 22.23.2 aislado (prerequisite-node22.txt). Smoke existente de 6 archivos API: 15/15 PASS, 0 skips, Linux UID 1000, network none, Foundation/pg ausentes y datos tmpfs (legacy-smoke.txt). Fallo inicial del bind Windows: timeouts de arranque, conservados con probes; mismo smoke PASS al copiar código/dependencias existentes a tmpfs, sin tocar API/timeouts ni instalar. README documenta comando ejecutado, prerequisitos, diagnóstico y estado por slice. ponytail-review sin bloqueantes; OpenSpec estricto y consistencia/whitespace PASS. Checkpoint compartido listo; 2.1–6.3 y G1 operativo pendientes. No full suites/build/API image, commit, sync ni archive. Evidencia bajo api/foundation/evidence/.

Checkpoint: entorno identificado y aislado; versiones resueltas y comandos reproducibles disponibles. Verificación: compose config --quiet y pruebas de guardas/smoke mediante runner. Dependencia: autorización explícita posterior para implementar.

## 2. Slice: conexiones y transacciones seguras

- [x] 2.1 Escribir primera prueba de comportamiento fallida del API público de pool/transacción: write seguido de fallo no persiste; reuso sin estado previo. Añadir saturación, cierre y conexión rota.
  Traceability: Bounded connection lifecycle and transactions / Failure and reuse; Pool saturation and shutdown; Connection loss and safe diagnostics.
  Notes: Alcance autorizado solo RED 2.1 sobre seam aprobado. pool.test.mjs usa createDatabase/query/transaction/close y PostgreSQL real con pool=1; pool.mjs es esqueleto cargable sin control transaccional, aislado de API normal. `node api/foundation/environment.mjs run pool`: Node 22.23.2 no root/PostgreSQL 18.6, salida 1 esperada; 4 fallos conductuales (fila persiste tras fallo, contexto transaccional ausente en commit/aborto, siguiente operación falla tras conexión terminada), 2 PASS (saturación/recuperación y cierre), 0 skips/cancelaciones; import/setup/conexión válidos y cleanup completo. Evidencia: api/foundation/evidence/pool-red.txt. Regresiones harness: 6/6 PASS en evidence/pool-harness-regressions.txt; build usó capa de dependencias cacheada, sin nuevas dependencias. Revisión ponytail-review del diff/seam sin bloqueantes para este RED aislado; no es aprobación para uso real. 2.2/2.3, suites completas, TLS/RLS y G1 operativo pendientes.
- [x] 2.2 Implementar pool, contexto transaccional local, límites/timeouts, rollback, descarte y saneamiento de errores; rechazar TLS sin verificación.
  Traceability: Bounded connection lifecycle and transactions / todos sus escenarios.
  Notes: Autorización limitada a 2.2; índice previo 2.1 preservado. pool.mjs implementa transacción en un cliente, contexto SQL local, commit/rollback, descarte por conexión rota/rollback fallido, cierre, límites positivos finitos, errores genéricos sin cause/driver/payload y TLS verificable (sin DSN ni overrides). Maneja evento de error del cliente y rechaza COMMIT convertido en ROLLBACK e interfaz usada fuera del callback. RED previo repetido (4 fallos); ciclos RED/GREEN de configuración, errores sensibles, commit abortado y handle caducado conservados en api/foundation/evidence/pool-2.2-*.txt. PASS implementación: run pool, 12/12 sin skips/cancelaciones, Node 22.23.2 no root/PostgreSQL 18.6, salida 0 y cleanup completo (pool-2.2-green.txt); defaults SQL y cancelación statement/client comprobados. Regresiones harness 6/6 PASS (pool-2.2-regressions.txt). Sin nuevas dependencias ni integración API. Revisión ponytail-review de delta/callers/contrato sin bloqueantes; README/design actualizados. 2.3 (checkpoint dedicado de terminación/logs) sigue pendiente; no full suites, TLS proveedor, roles/RLS/restore/CI ni G1 operativo. Sin commit/push/sync/archive.
- [x] 2.3 Ejecutar pruebas reales en Node 22 y PostgreSQL fijados; comprobar terminación, timeout acotado y ausencia de DSN/contraseñas en logs.
  Traceability: Bounded connection lifecycle and transactions / todos sus escenarios.
  Notes: Verificación autorizada solo 2.3, sin cambios runtime/tests/dependencias ni RED artificial. run pool del árbol actual: 12/12 PASS, 0 skips/cancelaciones, Node 22.23.2 no root/PostgreSQL 18.6; proceso termina naturalmente, orquestador salida 0 en 13985 ms con build/cleanup. Assertions PASS: adquisición <2000 ms, statement <2000 ms, client timeout/recuperación <1000 ms; write/rollback, contexto/reuso, reemplazo de conexión y cierre PASS. Auditoría stdout/stderr capturados sin DSN ni marcadores de contraseña/payload sintéticos, controles del scanner PASS; no incluye logs PostgreSQL ni RED históricos. Consulta Docker independiente: cero recursos container/volume/network/image del proyecto exacto. Evidencia y SHA-256 de fuentes: api/foundation/evidence/pool-2.3-{run,audit}.txt; reproducción y cobertura en README. Revisión ponytail-review de pool/tests/runner/callers y mapeo de todos los escenarios sin bloqueantes; regresiones harness 6/6 de 2.2 aplican sin cambio runtime, no repetidas. Slice 2 verificado sintéticamente; 3.1–6.3, full suites, TLS/pooler proveedor y G1 operativo pendientes. Sin commit/push/sync/archive.

Checkpoint: el cliente se libera o descarta en éxito/fallo y el proceso termina; verificación: grupo pool del runner, con pool máximo 1 en pruebas de reuso.

## 3. Slice: migraciones controladas y roles

- [ ] 3.1 Crear primera prueba fallida del runner como proceso: base vacía y prefijo previo llegan al mismo historial; runtime no puede ejecutar DDL. Añadir dos procesos e interrupción coordinada mediante señal de lock adquirido, sin sleeps arbitrarios.
  Traceability: Controlled migration history and privilege separation / todos sus escenarios.
- [ ] 3.2 Implementar bootstrap desechable, roles separados, migrador con lock habilitado, historial y migraciones mínimas; mantener fixtures fuera de migraciones funcionales.
  Traceability: Controlled migration history and privilege separation / todos sus escenarios.
- [ ] 3.3 Probar concurrencia, fallo transaccional, terminación de proceso/conexión, liberación del lock y reejecución sin historial ficticio; verificar atributos/membresías y ausencia de privilegios DDL del runtime.
  Traceability: Controlled migration history and privilege separation / todos sus escenarios.

Checkpoint: aplicación única y recuperable sobre base vacía/prefijo, sin DDL runtime; verificación: grupo migrations del runner y SQL de historial/privilegios.

## 4. Slice: aislamiento sintético por propietario

- [ ] 4.1 Crear primera prueba fallida con roles reales A/B y contexto ausente: lectura/escritura cruzada denegada; misma conexión después de commit/rollback/error.
  Traceability: Synthetic owner isolation / Cross owner and missing context; Connection reused after commit rollback or error.
- [ ] 4.2 Añadir fixtures desechables RLS con USING/WITH CHECK, contexto local y permisos mínimos; incluir rol Training-only sin acceso y denegación TRUNCATE/elevación.
  Traceability: Synthetic owner isolation / todos sus escenarios.
- [ ] 4.3 Ejecutar matriz CRUD/propietario/contexto y permisos con pool máximo 1; comprobar runtime no propietario/superuser/BYPASSRLS y retirar fixtures al finalizar.
  Traceability: Synthetic owner isolation / todos sus escenarios.

Checkpoint: aislamiento comprobado en PostgreSQL real y reuso sin fugas; verificación: grupo isolation del runner. No certifica políticas Recovery.

## 5. Slice: recuperación cifrada verificable

- [ ] 5.1 Crear primera prueba fallida del recorrido backup cifrado/copia/restore: ambos propietarios, historial y permisos; añadir clave incorrecta, corrupción y destino ajeno.
  Traceability: Verifiable isolated backup and restore / Restore and verify; Corrupt artifact or wrong key; Isolated synthetic environment / Unsafe target rejected.
- [ ] 5.2 Implementar dump consistente, manifiesto, cifrado autenticado con clave separada, transferencia a destino de ensayo y restore aislado con roles explícitos; proteger logs/artefactos y desactivar salidas externas.
  Traceability: Verifiable isolated backup and restore / todos sus escenarios.
- [ ] 5.3 Ejecutar recuperación completa, comparar datos semánticos de A/B, historial, grants y RLS, verificar fuente intacta y cronometrar; destruir solo recursos sintéticos identificados.
  Traceability: Verifiable isolated backup and restore / todos sus escenarios; Isolated synthetic environment / Unsafe target rejected.

Checkpoint: recuperación reproducible y rechazo de contenido no verificado; verificación: grupo recovery del runner. Destino separado simulado no acredita backup off-host, PITR ni RPO/RTO real.

## 6. Comprobaciones finales: CI, compatibilidad y evidencia

- [ ] 6.1 Integrar runner completo en CI con PostgreSQL real, trigger de archivos de Foundation y fallo obligatorio por BD ausente; comprobar configuración CI y ejecutar la misma entrada de local.
  Traceability: Real database CI and explicit gate evidence / Changed environment definition; Missing database or failed proof.
- [ ] 6.2 Ejecutar suites/build/locales y loadable checks pertinentes de API/frontend/MCP, smoke de imagen normal sin BD y comprobaciones POSIX en Linux no root; resolver regresiones propias sin ampliar alcance.
  Traceability: Real database CI and explicit gate evidence / Synthetic success; Isolated synthetic environment / Independent foundation run.
- [ ] 6.3 Documentar comandos/resultados/versiones/licencias, duración del restore, alcance sintético, fallos y estado G1 operativo pendiente; comprobar coherencia con arquitectura/PRD y validar OpenSpec estrictamente, sin archivar ni cortar persistencia.
  Traceability: Real database CI and explicit gate evidence / Synthetic success; Verifiable isolated backup and restore / Restore and verify.

Checkpoint: evidencia sintética completa, sin regresión observada y límites explícitos. Verificación: entrada Compose completa, comandos existentes de design / Verification Commands y `openspec validate add-postgres-foundation --strict --no-interactive`.

## Execution Order

Prerrequisitos compartidos: 1.1 → 1.2 → 1.3.

Slice conexiones: 2.1 → 2.2 → 2.3.

Slice migraciones: 3.1 → 3.2 → 3.3.

Slice aislamiento: 4.1 → 4.2 → 4.3.

Slice recuperación: 5.1 → 5.2 → 5.3.

Comprobaciones finales: 6.1 → 6.2 → 6.3.

Dependencias: conexiones usa entorno; migraciones usa conexiones; aislamiento usa roles y transacciones; recuperación usa fixtures e historial validados; CI/evidencia reúne todos los recorridos. Cada slice agrupa prueba fallida, implementación y verificación. No ejecutar tareas durante esta fase de especificación. Cada tarea completada añadirá Notes con evidencia concisa, sin diario paralelo.
