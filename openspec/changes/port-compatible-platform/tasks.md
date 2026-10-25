## Estado y límites

Plan revisado de entrega sintética futura; ningún checkbox está implementado o
aceptado por esta edición. Checkpoints: port funcional → operación local recuperable
→ corte/retirada reales en cambio operativo separado. S11 conserva las obligaciones
de handoff: no ejecutarlas ni marcarlas completas por un ensayo sintético. Antes de
archivar, transferirlas explícitamente con trazabilidad; no autorizar Recovery por
cierre de este cambio. La autorización actual cubre solo esta revisión documental.
Se acepta diseñar backup con pausa; la autorización/entrega privada de la vía nueva
Q1 y la selección del tooling estándar de retención son prerrequisitos de sus slices,
no hechos resueltos ni permiso para implementarlos.

Notes: revisión documental de los seis hallazgos aplicada. PASS: `openspec validate
port-compatible-platform --strict --no-interactive`, `node scripts/docs/okf.mjs check`,
`node --test scripts/docs/okf.test.mjs` (41/41, cero skips) y
`git -c core.safecrlf=false diff --check`. Sin pruebas runtime, instalaciones,
implementación de 1.1/1.2 ni aceptación operativa; todos los checkboxes siguen pendientes.

El [plan ejecutable](execution-plan.md) fija alcance, actores/rutas,
almacenes, primera prueba conductual, errores y checkpoint de cada slice S1–S11.
Todos los comandos `verify` siguientes son **futuros**; 1.2 entrega solo el runner
mínimo y sus casos iniciales. Cada slice añade su mapeo/imagen antes de verificar;
ningún comando futuro se acredita por esta edición. Solo 1.1 usa el comando Foundation existente antes de ese runner. Cada tarea ejecuta primero su caso RED válido, después implementación,
caso GREEN y suite afectada completa. No adelantar toda la implementación a las pruebas.

Q3 cubre los seams de contrato/HTTP+PG/navegador/operación; Q6 excluye SDK/CLI.
Foundation permanece archivada y no se reabre. Esta planificación no autoriza código,
instalaciones, migraciones, datos reales, proveedores, programación host ni corte.
No sync/archive, commit, despliegue o inicio de Recovery. Se sustituye el mapa de
21 paquetes aún sin ejecutar por 57 tareas acotadas; no hay progreso runtime trasladado.

## 1. Bootstrap y verificador sintético — S1

- [ ] 1.1 Congelar baseline independiente y revisión fuente, handoff Foundation y matriz de rutas/errores/consumidores; impedir cambiar expectativas para admitir divergencias.
  Traceability: compatible-platform-persistence / Phase-bounded compatible capability port / Training pilot follows identity; Faithful import and retirement parity / OpenAPI authority moves without contract drift.
  Proof/Check: `node scripts/python-foundation.mjs run contracts` (comando existente para baseline sintético, solo bajo autorización de entrega; sin RED runtime artificial).
- [ ] 1.2 Entregar runner verify mínimo reutilizando ejecución/ownership Foundation sin duplicar cleanup; mapeo e imagen iniciales, suite futura/desconocida exit 2 y regresiones Foundation tras extracción. Browser pins se entregan en 3.4.
  Traceability: local-platform-operation / Isolated local Compose operation / Resolved topology and environment isolation; compatible-platform-persistence / Bounded legacy and temporary artifact cleanup / Cleanup preserves recovery and foreign artifacts; Phase-bounded compatible capability port / Slice preparation is incomplete.
  Proof/Check: `node scripts/platform.mjs verify harness --case ownership`.
- [ ] 1.3 Entregar arranque HTTP dev aislado, health/config compatibles y readiness interna sin migración automática; rechazar esquema desconocido.
  Traceability: local-platform-operation / Controlled images migrations and lifecycle / Incompatible schema or failed migration.
  Proof/Check: `node scripts/platform.mjs verify lifecycle --case readiness`.
- [ ] 1.4 Entregar bootstrap de roles e historial/lock Alembic, vacío/revisión anterior, interrupción y fallo sin adelantar head; DDL de negocio solo con su slice.
  Traceability: compatible-platform-persistence / Executable schema and privileged functions / Migration failure and function grants; local-platform-operation / Controlled images migrations and lifecycle / Incompatible schema or failed migration.
  Proof/Check: `node scripts/platform.mjs verify schema --case history_lock`.
- [ ] 1.5 Entregar base/overlays dev/ops y targets runtime/migrate/ops sobre pins comunes; configurar secretos por ficheros y no-root sin SDK/CLI/Node runtime.
  Traceability: local-platform-operation / Isolated local Compose operation / Resolved topology and environment isolation; Controlled images migrations and lifecycle / Deferred coach runtimes do not expand operation.
  Proof/Check: `node scripts/platform.mjs verify images --case isolation`.

## 2. Identidad compatible por operaciones — S2

- [ ] 2.1 Entregar verificación/selección cookie-bearer y lock_actor de p001; probar versiones, expiración/duplicados/forgery y revocación durante espera sin acceso ajeno.
  Traceability: compatible-platform-persistence / Authenticated session to RLS ownership / Mixed credentials and duplicate cookies resolve one actor; Invalid sessions never establish protected ownership; Session expires while waiting for protected work; Concurrent revocation is serialized with protected work.
  Proof/Check: `node scripts/platform.mjs verify identity_session --case actor`.
- [ ] 2.2 Entregar login password con scrypt/NFKC y respuestas/cookie/token vigentes, dummy hash y fallo seguro; revalidar hash/versión tras trabajo criptográfico.
  Traceability: compatible-platform-persistence / Legacy-compatible identity namespace and credentials / Credential and account access continuity.
  Proof/Check: `node scripts/platform.mjs verify identity_password --case login`.
- [ ] 2.3 Entregar registro password/alias/invitación y primer-admin atómicos; p001 conserva namespace Unicode y fechas históricas sin inventar datos.
  Traceability: compatible-platform-persistence / Legacy-compatible identity namespace and credentials / Concurrent alias reservation and reset expiry; Executable schema and privileged functions / Migration failure and function grants.
  Proof/Check: `node scripts/platform.mjs verify identity_register --case concurrent_claim`.
- [ ] 2.4 Entregar registro/login WebAuthn con webauthn 3.0.1 y vectores independientes; incluir replay/revocación/counter, sin acreditar autenticador físico.
  Traceability: compatible-platform-persistence / Legacy-compatible identity namespace and credentials / Credential and account access continuity.
  Proof/Check: `node scripts/platform.mjs verify identity_passkey --case interoperability`.
- [ ] 2.5 Entregar contraseña/email propios y logout/all, prueba de acceso actual, reserva expirada y última vía; cambio revoca sesiones/enlaces sin quitar passkeys.
  Traceability: compatible-platform-persistence / Legacy-compatible identity namespace and credentials / Concurrent alias reservation and reset expiry; Credential and account access continuity.
  Proof/Check: `node scripts/platform.mjs verify identity_account --case password_email`.
- [ ] 2.6 Entregar añadir/listar/renombrar/quitar passkey con cap 20, ownership y última vía; denegar ceremonia obsoleta tras revocación.
  Traceability: compatible-platform-persistence / Legacy-compatible identity namespace and credentials / Credential and account access continuity.
  Proof/Check: `node scripts/platform.mjs verify identity_account --case passkey_management`.
- [ ] 2.7 Entregar consumo de reset 24 h con digest, alias/password/versión en misma TX; expiración y carrera de doble canje fallan sin cambios parciales.
  Traceability: compatible-platform-persistence / Legacy-compatible identity namespace and credentials / Concurrent alias reservation and reset expiry.
  Proof/Check: `node scripts/platform.mjs verify identity_reset --case single_use`.
- [ ] 2.8 Entregar pairing/device-link reemplazable/10 min y ceremonia vinculada; consumo único y cuenta eliminada/revocada no emiten sesión.
  Traceability: compatible-platform-persistence / Legacy-compatible identity namespace and credentials / Credential and account access continuity.
  Proof/Check: `node scripts/platform.mjs verify identity_links --case redeem`.
- [ ] 2.9 Verificar catálogo SQL/ACL/FORCE RLS y pool max=1 con HTTP Python real tras todos los desenlaces; ningún rol privilegiado se usa en peticiones.
  Traceability: compatible-platform-persistence / Least-privilege access / Preauthentication and pool reuse; Authenticated session to RLS ownership / HTTP and real PostgreSQL prove the complete ownership path; Executable schema and privileged functions / Migration failure and function grants.
  Proof/Check: `node scripts/platform.mjs verify identity_session --case restricted_pool`.

## 3. Piloto Training — S3

- [ ] 3.1 Entregar p002/proyecciones y GET data/rev bajo actor/RLS: A propio/B vacío, metadata canónica y tipos SQL inválidos rechazados sin redondeo.
  Traceability: compatible-platform-persistence / Canonical compatible Training persistence / No document and legacy metadata; Authenticated session to RLS ownership / Verified session controls owner context despite client forgery.
  Proof/Check: `node scripts/platform.mjs verify training_read --case owner_and_types`.
- [ ] 3.2 Entregar PUT/primera escritura concurrente/conflicto y diferencia rev respuesta/almacenada; fallo de marca externa no altera commit reconocido.
  Traceability: compatible-platform-persistence / Canonical compatible Training persistence / First write and competing revision.
  Proof/Check: `node scripts/platform.mjs verify training_write --case first_write`.
- [ ] 3.3 Entregar stamps/baseWid/linaje/reset/legacy y retry de respuesta perdida, preservando _prior/_unstamped/ausente-null y límite de incremento.
  Traceability: compatible-platform-persistence / Canonical compatible Training persistence / First write and competing revision; No document and legacy metadata.
  Proof/Check: `node scripts/platform.mjs verify training_write --case lineage_retry`.
- [ ] 3.4 Verificar frontend real contra Python: offline/dirty/active, 401, 409 repetido y respuesta perdida; observar cliente y PG independientes.
  Traceability: compatible-platform-persistence / Phase-bounded compatible capability port / Training pilot follows identity; Canonical compatible Training persistence / First write and competing revision.
  Proof/Check: `node scripts/platform.mjs verify training_browser --case offline_sync`.

## 4. Medios — S4

- [ ] 4.1 Entregar upload/download propio con hash/tipo/headers y ajeno 404; referencias Training mediante interfaz pública, sin tabla de medios nueva.
  Traceability: compatible-platform-persistence / Faithful import and retirement parity / Parity after removing the replaced backend.
  Proof/Check: `node scripts/platform.mjs verify media --case roundtrip`.
- [ ] 4.2 Entregar missing/cuotas/temporales y cola cliente; fallo DB/permiso no publica ni elimina datos de otro propietario.
  Traceability: compatible-platform-persistence / Recoverable deletion and compatible audit / External cleanup or audit failure.
  Proof/Check: `node scripts/platform.mjs verify media --case quota_and_missing`.
- [ ] 4.3 Entregar GC con marks/referencias, archivo ilegible y upload concurrente; demostrar sentinel y bytes conservados ante error de lectura.
  Traceability: compatible-platform-persistence / Recoverable deletion and compatible audit / External cleanup or audit failure.
  Proof/Check: `node scripts/platform.mjs verify media_gc --case fail_safe`.

## 5. Coach local y HTTP — S5

- [ ] 5.1 Entregar p003/config/status e indisponibilidad Q6 con selección importada preservada, sin job/cuota/refresh/remapeo ni launcher.
  Traceability: compatible-platform-persistence / Explicitly bounded coach delivery / Imported deferred provider remains unavailable; Accepted delivery excludes agent infrastructure; Compatible notification and coach state / Provider feasibility before business port.
  Proof/Check: `node scripts/platform.mjs verify coach_state --case deferred_provider`.
- [ ] 5.2 Entregar reserva atómica job/caps UTC, single-flight/dos ejecuciones y transición restart sin replay; índices/constraints p003 reales.
  Traceability: compatible-platform-persistence / Compatible notification and coach state / Atomic limits and repeated job events.
  Proof/Check: `node scripts/platform.mjs verify coach_state --case atomic_enqueue`.
- [ ] 5.3 Entregar transports HTTP/payload/pipeline/propuesta validada con fixture privada; consentimiento requerido y fallo externo sin aplicación automática.
  Traceability: compatible-platform-persistence / Explicitly bounded coach delivery / Accepted delivery excludes agent infrastructure; Compatible notification and coach state / Forget and late provider response.
  Proof/Check: `node scripts/platform.mjs verify coach_http --case validated_proposal`.
- [ ] 5.4 Entregar resolve/history/expiry/forget y cancelación; respuesta tardía tras retirar consentimiento/borrar cuenta no recrea contenido ni cuota.
  Traceability: compatible-platform-persistence / Compatible notification and coach state / Forget and late provider response; Atomic limits and repeated job events.
  Proof/Check: `node scripts/platform.mjs verify coach_state --case late_result`.
- [ ] 5.5 Entregar admin config/model/test/connect/disconnect y cuenta por perfil, secretos externos/vínculos personales y fallos de decrypt; SDK/CLI siguen no disponibles.
  Traceability: compatible-platform-persistence / Explicitly bounded coach delivery / Imported deferred provider remains unavailable; Least-privilege access / Preauthentication and pool reuse.
  Proof/Check: `node scripts/platform.mjs verify coach_admin --case credentials`.
- [ ] 5.6 Entregar cohort/scheduling consentidos y UI local/HTTP con disponibilidad Q6/locales, sin owner arbitrario ni nuevas capacidades IA.
  Traceability: compatible-platform-persistence / Compatible notification and coach state / Forget and late provider response; Explicitly bounded coach delivery / Imported deferred provider remains unavailable.
  Proof/Check: `node scripts/platform.mjs verify coach_client --case consent_and_availability`.

## 6. Administración y audit — S6

- [ ] 6.1 Entregar listado/inspección/disable con actor-target separados, proyección Training admin actual sin media, hasPush, rechazo de disable de cualquier admin y revocación bajo locks ordenados.
  Traceability: compatible-platform-persistence / Executable schema and privileged functions / Existing administrative Training projection is preserved; Authenticated session to RLS ownership / Concurrent revocation is serialized with protected work.
  Proof/Check: `node scripts/platform.mjs verify admin_users --case actor_target`.
- [ ] 6.2 Entregar p004 y eliminación SQL + tarea externa + desconexión coach atómicas; preservar invitaciones/audit y denegar acceso inmediato.
  Traceability: compatible-platform-persistence / Recoverable deletion and compatible audit / External cleanup or audit failure.
  Proof/Check: `node scripts/platform.mjs verify admin_delete --case atomic_delete`.
- [ ] 6.3 Entregar cleanup externo idempotente, fallos/reintentos acotados y estado pendiente/completo; no borrar secretos/bytes de otro propietario.
  Traceability: compatible-platform-persistence / Recoverable deletion and compatible audit / External cleanup or audit failure.
  Proof/Check: `node scripts/platform.mjs verify admin_delete --case external_retry`.
- [ ] 6.4 Entregar invitaciones y emisión admin de reset con facultades vigentes; consumidas no se reabren tras eliminar usuario.
  Traceability: compatible-platform-persistence / Legacy-compatible identity namespace and credentials / Concurrent alias reservation and reset expiry; Recoverable deletion and compatible audit / External cleanup or audit failure.
  Proof/Check: `node scripts/platform.mjs verify admin_invites --case consumed_history`.
- [ ] 6.5 Entregar audit read/clear/retención/sequence, IP off y degradación best effort en unidad separada; fallo audit no altera éxito de negocio.
  Traceability: compatible-platform-persistence / Recoverable deletion and compatible audit / External cleanup or audit failure.
  Proof/Check: `node scripts/platform.mjs verify admin_audit --case failure_and_retention`.

## 7. Notificaciones y actividad — S7

- [ ] 7.1 Entregar p005 y subscribe/status/unsubscribe, upsert global/cap 20/device fallback y SSRF sin acceso ajeno.
  Traceability: compatible-platform-persistence / Compatible notification and coach state / Notification ownership and local dates.
  Proof/Check: `node scripts/platform.mjs verify notifications --case subscription`.
- [ ] 7.2 Entregar scheduler/reminder/nudge con fechas locales y preferencias Training, candidato interno autorizado y transporte fake; no prometer exactamente una entrega.
  Traceability: compatible-platform-persistence / Compatible notification and coach state / Notification ownership and local dates.
  Proof/Check: `node scripts/platform.mjs verify notifications --case local_dates`.
- [ ] 7.3 Entregar activity/rest timer/test/cancel con dispositivo/ownership y presencia efímera; reinicio no inventa persistencia de timers.
  Traceability: compatible-platform-persistence / Compatible notification and coach state / Notification ownership and local dates.
  Proof/Check: `node scripts/platform.mjs verify notifications --case device_isolation`.

## 8. Shared, formatos y OpenAPI — S8

- [ ] 8.1 Trasladar JS neutral/prompts a fuente canónica shared, actualizar generadores/imports y probar coach local/paridad sin duplicar biblioteca.
  Traceability: compatible-platform-persistence / Faithful import and retirement parity / Parity after removing the replaced backend.
  Proof/Check: `node scripts/platform.mjs verify shared_client --case canonical_sources`.
- [ ] 8.2 Verificar CSV/JSON/media backup/FIT/catálogo y builds web/mobile pertinentes con fuente neutral y casos hostiles; sin publicación de shells.
  Traceability: compatible-platform-persistence / Faithful import and retirement parity / Parity after removing the replaced backend.
  Proof/Check: `node scripts/platform.mjs verify shared_client --case formats_and_bundles`.
- [ ] 8.3 Mover autoridad YAML a backend/openapi.yaml, actualizar generator/CI/enlaces y cobertura Python método/ruta/respuesta; mantener --check y errores compatibles.
  Traceability: compatible-platform-persistence / Faithful import and retirement parity / OpenAPI authority moves without contract drift.
  Proof/Check: `node scripts/platform.mjs verify contracts --case python_routes`.

## 9. Imágenes y diagnóstico operativo — S9

- [ ] 9.1 Verificar checkout limpio/targets/digests, matriz caché frío-repetido-fuente-lock-tests y lifecycle/caída-reconexión; CI sin secretos ni runtime installs.
  Traceability: local-platform-operation / Controlled images migrations and lifecycle / Incompatible schema or failed migration.
  Proof/Check: `node scripts/platform.mjs verify images --case reproducibility`.
- [ ] 9.2 Entregar logging estándar estructurado/estado mínimo y diagnose privado, salud diferenciada y señales de audit/backup; seleccionar y fijar tooling estándar de rotación/retención antes de implementar S9.
  Traceability: local-platform-operation / Private bounded diagnostic operation / Local diagnosis has fixed tools and limits.
  Proof/Check: `node scripts/platform.mjs verify diagnostics --case operator_status`.
- [ ] 9.3 Entregar correlación por request_id de HTTP→DB→dependencia simulada, resultado/duración y errores seguros; sin OpenTelemetry, exporter propio, spans ni snapshots métricos.
  Traceability: local-platform-operation / Private bounded diagnostic operation / Local diagnosis has fixed tools and limits.
  Proof/Check: `node scripts/platform.mjs verify diagnostics --case correlation`.
- [ ] 9.4 Verificar edad/espacio/archivo activo/API detenida y reinicio, sink lleno/caído, cierre/buffers acotados y marcadores sensibles en todas las copias, incluida captura Docker.
  Traceability: local-platform-operation / Private bounded diagnostic operation / Age expiry sensitive fixture and unavailable sink.
  Proof/Check: `node scripts/platform.mjs verify diagnostics --case retention_and_failure`.

## 10. Importación y recuperación ensayada — S10

- [ ] 10.1 Entregar importador separado/frozen-source/new-target y matriz de equivalencia por capacidad, secuencias/IDs/secret refs y excepción Q6; dato no representable bloquea intacto.
  Traceability: compatible-platform-persistence / Faithful import and retirement parity / Unrepresentable legacy data; Explicitly bounded coach delivery / Imported deferred provider remains unavailable.
  Proof/Check: `node scripts/platform.mjs verify import --case faithful_or_blocked`.
- [ ] 10.2 Entregar wrapper host de parada limpia con exclusión/journal y captura SQL consistente; verificar cese de API y escritores, PG disponible y pendientes cliente conservados; sin leases ni socket de control.
  Traceability: local-platform-operation / Coordinated encrypted recovery points / Capture with internal writers and failed transfer; Interrupted capture remains controlled.
  Proof/Check: `node scripts/platform.mjs verify backup --case writer_shutdown`.
- [ ] 10.3 Entregar age/manifest/copia cifrada/verificación EOF/rename y estado recuperable; key errónea/truncamiento/disco lleno no desplazan punto válido.
  Traceability: local-platform-operation / Coordinated encrypted recovery points / Capture with internal writers and failed transfer; Monthly complete recovery rehearsal.
  Proof/Check: `node scripts/platform.mjs verify backup --case verified_bundle`.
- [ ] 10.4 Entregar restore de SQL/roles/RLS/medios en nuevo destino aislado y secuencias, sin tráfico ni egress ni bootstrap en API.
  Traceability: local-platform-operation / Coordinated encrypted recovery points / Monthly complete recovery rehearsal.
  Proof/Check: `node scripts/platform.mjs verify restore --case isolated_target`.
- [ ] 10.5 Especificar primero autorización local y entrega privada de vía nueva Q1; después entregar continuidad con evidencia o recuperación explícita de acceso en target aislado, sin reactivar credenciales dudosas ni elevar roles. Probar firma nueva sin perder decrypt coach, sesiones/links invalidados y cliente dirty/linaje.
  Traceability: local-platform-operation / Restore preserves later security decisions / Manual review with partial evidence; Historical access cannot be established; Deleted account or revoked credential exists in snapshot; Session invalidation does not destroy coach decryption.
  Proof/Check: `node scripts/platform.mjs verify restore --case reviewed_access`.
- [ ] 10.6 Entregar/ensayar Q2 sobre destino superviviente con W1/W2 independientes y W3 posterior; imagen/DDL/commit incierto reparan sin fallback ni restaurar datos viejos; incompatible falla no-go.
  Traceability: local-platform-operation / Single-authority cutover and verified retirement / New writes followed by rollback request; Forward repair cannot preserve new writes.
  Proof/Check: `node scripts/platform.mjs verify repair --case acknowledged_writes`.
- [ ] 10.7 Entregar restore-rehearse mensual y medición completa RPO/RTO con revisión/accesos bloqueados; informe parcial nunca acredita recuperación completa.
  Traceability: local-platform-operation / Coordinated encrypted recovery points / Monthly complete recovery rehearsal; Restore preserves later security decisions / Manual review with partial evidence.
  Proof/Check: `node scripts/platform.mjs verify restore --case full_timing`.
- [ ] 10.8 Entregar captura coherente de medios/GC/config/secretos y SQL con escritores detenidos, observador independiente, staging protegido y pausa medida; escritor externo desconocido bloquea captura.
  Traceability: local-platform-operation / Coordinated encrypted recovery points / Capture with internal writers and failed transfer.
  Proof/Check: `node scripts/platform.mjs verify backup --case sql_files_coherence`.
- [ ] 10.9 Entregar plantillas Windows/Linux de backup 3 h/arranque/pre-migración, restore mensual y retain horario; mutex/antigüedad/códigos de fallo verificables sin instalar jobs reales.
  Traceability: local-platform-operation / Coordinated encrypted recovery points / Scheduled failures do not satisfy recovery objectives; Private bounded diagnostic operation / Local diagnosis has fixed tools and limits.
  Proof/Check: `node scripts/platform.mjs verify backup --case scheduling_and_age`.
- [ ] 10.10 Entregar recuperación del journal tras fallo de wrapper/host/captura/reinicio; comprobar procesos cesados y compatibilidad, restaurar solo servicios antes activos, no apertura por TTL ni backup startup recursivo; migración no reinicia entre copia y DDL.
  Traceability: local-platform-operation / Coordinated encrypted recovery points / Interrupted capture remains controlled.
  Proof/Check: `node scripts/platform.mjs verify backup --case interrupted_capture`.

## 11. Handoff a cambio operativo separado — S11

Las cinco obligaciones siguientes se conservan pendientes para transferencia
explícita con sus requisitos, pruebas y permisos. Este cambio solo ensaya corte y
retirada en fixtures/checkouts propios; esos ensayos no completan estas tareas reales.
No archivar con obligaciones sin transferir ni confundir el handoff con aceptación.

- [ ] 11.1 Bajo permiso operativo separado, verificar G0/clientes/orígenes/backup físico/claves/fuente posterior protegida/ventana y G1/GP/GO antes de solicitar corte real.
  Traceability: local-platform-operation / Single-authority cutover and verified retirement / New writes followed by rollback request; Restore preserves later security decisions / Manual review with partial evidence.
  Proof/Check: `node scripts/platform.mjs verify gates --case pre_cutover --evidence <protected-index.json>` (inspección de evidencia autorizada, no lectura real implícita desde verify).
- [ ] 11.2 Solo tras autorización humana explícita, ejecutar corte/autoridad única, reversión sin nuevas escrituras o reparación Q2 tras ellas; preservar origen/release/configuración.
  Traceability: local-platform-operation / Single-authority cutover and verified retirement / New writes followed by rollback request.
  Proof/Check: `node scripts/platform.mjs verify gates --case authorized_cutover --evidence <protected-index.json>` (verifica evidencia; nunca ejecuta corte real como efecto de verify).
- [ ] 11.3 Ejecutar inventario cleanup retirar/conservar/protegido, migrar consumidores/tests y retirar implementación/config/deps sustituidas; probar sentinel y material protegido.
  Traceability: compatible-platform-persistence / Bounded legacy and temporary artifact cleanup / Active dependency prevents removal; Cleanup preserves recovery and foreign artifacts.
  Proof/Check: `node scripts/platform.mjs verify cleanup --case protected_sentinel`.
- [ ] 11.4 Repetir checkout limpio/builds/paridad/seguridad/browser/restore/diagnóstico después de retirada; ausencia de imports/lectores legacy activa G3/GO, no mera búsqueda textual.
  Traceability: compatible-platform-persistence / Faithful import and retirement parity / Parity after removing the replaced backend; local-platform-operation / Single-authority cutover and verified retirement / Post-retirement acceptance.
  Proof/Check: `node scripts/platform.mjs verify parity --case post_retirement`.
- [ ] 11.5 Consolidar EV/gates/resultados/límites y actualizar guías al runtime realmente entregado; registrar aceptación antes de Recovery sin borrar originales ni sync/archive.
  Traceability: local-platform-operation / Single-authority cutover and verified retirement / Post-retirement acceptance.
  Proof/Check: `node scripts/platform.mjs verify gates --case acceptance --evidence <protected-index.json>` (revisión de evidencia completa, no aprobación automática).

## Execution Order

- S1: 1.1 → 1.2 → 1.4 → 1.5 → 1.3.
- S2 mínimo para piloto: 2.1 → 2.2.
- S3: 3.1 → 3.2 → 3.3 → 3.4.
- S2 resto y regresión: 2.3 → 2.4 → 2.5 → 2.6 → 2.7 → 2.8 → 2.9.
- S4: 4.1 → 4.2 → 4.3.
- S5: 5.1 → 5.2 → 5.3 → 5.4 → 5.5 → 5.6.
- S7: 7.1 → 7.2 → 7.3.
- S6: 6.1 → 6.2 → 6.3 → 6.4 → 6.5.
- S8: 8.1 → 8.2 → 8.3.
- S9: 9.1 → 9.2 → 9.3 → 9.4.
- S10: 10.1 → 10.2 → 10.8 → 10.10 → 10.3 → 10.4 → 10.5 → 10.7 → 10.9 → 10.6.
- S11: 11.1 → autorización de corte separada → 11.2 → 11.3 → 11.4 → 11.5.

Es el orden de ejecución por defecto, sin trabajo horizontal de todas las pruebas
antes del código. Dependencias mínimas: S1 antes de S2; solo 2.1/2.2 preceden a S3,
no bloquear el piloto por todo registro/reset/device-link. S4–S7 consumen S2/S3; S7 precede a S6 por hasPush del listado admin, y eliminación S6 consume
secretos/medios S4/S5. S8 requiere sus consumidores
existentes portados antes de mover fuentes; S9 acepta imágenes/diagnóstico con todas
las rutas; S10 usa capacidades/digest/diagnóstico aceptados; S11 transfiere obligaciones al
cambio operativo separado, que requiere todos los ensayos y permisos reales. Instrumentación y DDL se entregan incrementalmente con
cada operación; S9 comprueba cobertura completa, no aplaza todo diagnóstico al final.
Si un caso requiere una ruta todavía no portada, el fixture prepara datos por setup
sintético independiente, no invoca el paquete futuro ni añade dependencia circular.
