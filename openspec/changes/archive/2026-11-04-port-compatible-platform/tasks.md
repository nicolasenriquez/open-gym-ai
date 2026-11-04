## Acceptance and scope

Accepted by the promoter on 2026-11-04 (America/Santiago): **57/57 tasks complete**. Repository delivery covers the Python port, synthetic operational tooling, retirement and documentation. Actual instance migration/cutover remains deferred; Recovery, commit and push require separate authorization. The promoter subsequently authorized spec synchronization, archive and removal of .scratch.

## Completed tasks

- [x] 1.1 Congelar baseline independiente y revisión fuente, handoff Foundation y matriz de rutas/errores/consumidores; impedir cambiar expectativas para admitir divergencias.
- [x] 1.2 Entregar runner verify mínimo reutilizando ejecución/ownership Foundation sin duplicar cleanup; mapeo e imagen iniciales, suite futura/desconocida exit 2 y regresiones Foundation tras extracción. Browser pins se entregan en 3.4.
- [x] 1.3 Entregar arranque HTTP dev aislado, health/config compatibles y readiness interna sin migración automática; rechazar esquema desconocido.
- [x] 1.4 Entregar bootstrap de roles e historial/lock Alembic, vacío/revisión anterior, interrupción y fallo sin adelantar head; DDL de negocio solo con su slice.
- [x] 1.5 Entregar base/overlays dev/ops y targets runtime/migrate/ops sobre pins comunes; configurar secretos por ficheros y no-root sin SDK/CLI/Node runtime.
- [x] 2.1 Entregar verificación/selección cookie-bearer y lock_actor de p001; probar versiones, expiración/duplicados/forgery y revocación durante espera sin acceso ajeno.
- [x] 2.2 Entregar login password con scrypt/NFKC y respuestas/cookie/token vigentes, dummy hash y fallo seguro; revalidar hash/versión tras trabajo criptográfico.
- [x] 2.3 Entregar registro password/alias/invitación y primer-admin atómicos; p001 conserva namespace Unicode y fechas históricas sin inventar datos.
- [x] 2.4 Entregar registro/login WebAuthn con webauthn 3.0.1 y vectores independientes; incluir replay/revocación/counter, sin acreditar autenticador físico.
- [x] 2.5 Entregar contraseña/email propios y logout/all, prueba de acceso actual, reserva expirada y última vía; cambio revoca sesiones/enlaces sin quitar passkeys.
- [x] 2.6 Entregar añadir/listar/renombrar/quitar passkey con cap 20, ownership y última vía; denegar ceremonia obsoleta tras revocación.
- [x] 2.7 Entregar consumo de reset 24 h con digest, alias/password/versión en misma TX; expiración y carrera de doble canje fallan sin cambios parciales.
- [x] 2.8 Entregar pairing/device-link reemplazable/10 min y ceremonia vinculada; consumo único y cuenta eliminada/revocada no emiten sesión.
- [x] 2.9 Verificar catálogo SQL/ACL/FORCE RLS y pool max=1 con HTTP Python real tras todos los desenlaces; ningún rol privilegiado se usa en peticiones.
- [x] 3.1 Entregar p002/proyecciones y GET data/rev bajo actor/RLS: A propio/B vacío, metadata canónica y tipos SQL inválidos rechazados sin redondeo.
- [x] 3.2 Entregar PUT/primera escritura concurrente/conflicto y diferencia rev respuesta/almacenada; fallo de marca externa no altera commit reconocido.
- [x] 3.3 Entregar stamps/baseWid/linaje/reset/legacy y retry de respuesta perdida, preservando _prior/_unstamped/ausente-null y límite de incremento.
- [x] 3.4 Verificar frontend real contra Python: offline/dirty/active, 401, 409 repetido y respuesta perdida; observar cliente y PG independientes.
- [x] 4.1 Entregar upload/download propio con hash/tipo/headers y ajeno 404; referencias Training mediante interfaz pública, sin tabla de medios nueva.
- [x] 4.2 Entregar missing/cuotas/temporales y cola cliente; fallo DB/permiso no publica ni elimina datos de otro propietario.
- [x] 4.3 Entregar GC con marks/referencias, archivo ilegible y upload concurrente; demostrar sentinel y bytes conservados ante error de lectura.
- [x] 5.1 Entregar p003/config/status e indisponibilidad Q6 con selección importada preservada, sin job/cuota/refresh/remapeo ni launcher.
- [x] 5.2 Entregar reserva atómica job/caps UTC, single-flight/dos ejecuciones y transición restart sin replay; índices/constraints p003 reales.
- [x] 5.3 Entregar transports HTTP/payload/pipeline/propuesta validada con fixture privada; consentimiento requerido y fallo externo sin aplicación automática.
- [x] 5.4 Entregar resolve/history/expiry/forget y cancelación; respuesta tardía tras retirar consentimiento/borrar cuenta no recrea contenido ni cuota.
- [x] 5.5 Entregar admin config/model/test/connect/disconnect y cuenta por perfil, secretos externos/vínculos personales y fallos de decrypt; SDK/CLI siguen no disponibles.
- [x] 5.6 Entregar cohort/scheduling consentidos y UI local/HTTP con disponibilidad Q6/locales, sin owner arbitrario ni nuevas capacidades IA.
- [x] 6.1 Entregar listado/inspección/disable con actor-target separados, proyección Training admin actual sin media, hasPush, rechazo de disable de cualquier admin y revocación bajo locks ordenados.
- [x] 6.2 Entregar p004 y eliminación SQL + tarea externa + desconexión coach atómicas; preservar invitaciones/audit y denegar acceso inmediato.
- [x] 6.3 Entregar cleanup externo idempotente, fallos/reintentos acotados y estado pendiente/completo; no borrar secretos/bytes de otro propietario.
- [x] 6.4 Entregar invitaciones y emisión admin de reset con facultades vigentes; consumidas no se reabren tras eliminar usuario.
- [x] 6.5 Entregar audit read/clear/retención/sequence, IP off y degradación best effort en unidad separada; fallo audit no altera éxito de negocio.
- [x] 7.1 Entregar p005 y subscribe/status/unsubscribe, upsert global/cap 20/device fallback y SSRF sin acceso ajeno.
- [x] 7.2 Entregar scheduler/reminder/nudge con fechas locales y preferencias Training, candidato interno autorizado y transporte fake; no prometer exactamente una entrega.
- [x] 7.3 Entregar activity/rest timer/test/cancel con dispositivo/ownership y presencia efímera; reinicio no inventa persistencia de timers.
- [x] 8.1 Trasladar JS neutral/prompts a fuente canónica shared, actualizar generadores/imports y probar coach local/paridad sin duplicar biblioteca.
- [x] 8.2 Verificar CSV/JSON/media backup/FIT/catálogo y builds web/mobile pertinentes con fuente neutral y casos hostiles; sin publicación de shells.
- [x] 8.3 Mover autoridad YAML a backend/openapi.yaml, actualizar generator/CI/enlaces y cobertura Python método/ruta/respuesta; mantener --check y errores compatibles.
- [x] 9.1 Verificar checkout limpio/targets/digests, matriz caché frío-repetido-fuente-lock-tests y lifecycle/caída-reconexión; CI sin secretos ni runtime installs.
- [x] 9.2 Entregar logging estándar estructurado/estado mínimo y diagnose privado, salud diferenciada y señales de audit/backup; seleccionar y fijar tooling estándar de rotación/retención antes de implementar 9.2–9.4.
- [x] 9.3 Entregar correlación por request_id de HTTP→DB→dependencia simulada, resultado/duración y errores seguros; sin OpenTelemetry, exporter propio, spans ni snapshots métricos.
- [x] 9.4 Verificar edad/espacio/archivo activo/API detenida y reinicio, sink lleno/caído, cierre/buffers acotados y marcadores sensibles en todas las copias, incluida captura Docker.
- [x] 10.1 Entregar importador separado/frozen-source/new-target y matriz de equivalencia por capacidad, secuencias/IDs/secret refs y excepción Q6; dato no representable bloquea intacto.
- [x] 10.2 Entregar wrapper host de parada limpia con exclusión/journal y captura SQL consistente; verificar cese de API y escritores, PG disponible y pendientes cliente conservados; sin leases ni socket de control.
- [x] 10.3 Entregar age/manifest/copia cifrada/verificación EOF/rename y estado recuperable; key errónea/truncamiento/disco lleno no desplazan punto válido.
- [x] 10.4 Entregar restore de SQL/roles/RLS/medios en nuevo destino aislado y secuencias, sin tráfico ni egress ni bootstrap en API.
- [x] 10.5 Especificar primero autorización local y entrega privada de vía nueva Q1; después entregar continuidad con evidencia o recuperación explícita de acceso en target aislado, sin reactivar credenciales dudosas ni elevar roles. Probar firma nueva sin perder decrypt coach, sesiones/links invalidados y cliente dirty/linaje.
- [x] 10.6 Entregar/ensayar Q2 sobre destino superviviente con W1/W2 independientes y W3 posterior; imagen/DDL/commit incierto reparan sin fallback ni restaurar datos viejos; incompatible falla no-go.
- [x] 10.7 Entregar restore-rehearse mensual y medición completa RPO/RTO con revisión/accesos bloqueados; informe parcial nunca acredita recuperación completa.
- [x] 10.8 Entregar captura coherente de medios/GC/config/secretos y SQL con escritores detenidos, observador independiente, staging protegido y pausa medida; escritor externo desconocido bloquea captura.
- [x] 10.9 Entregar plantillas Windows/Linux de backup 3 h/arranque/pre-migración, restore mensual y retain horario; mutex/antigüedad/códigos de fallo verificables sin instalar jobs reales.
- [x] 10.10 Entregar recuperación del journal tras fallo de wrapper/host/captura/reinicio; comprobar procesos cesados y compatibilidad, restaurar solo servicios antes activos, no apertura por TTL ni backup startup recursivo; migración no reinicia entre copia y DDL.
- [x] 11.1 Cerrar administrativamente la preparación pre-cutover: conservar evidencia sintética, inventario pasivo, plan/runbook y límites documentados, sin acreditar validación operativa ni autorizar corte.
- [x] 11.2 Registrar el aplazamiento explícito del corte y migración real, preservando tooling, runbook y material de recuperación para una intervención operativa posterior autorizada.
- [x] 11.3 Ejecutar inventario cleanup retirar/conservar/protegido, migrar consumidores/tests y retirar implementación/config/deps sustituidas; probar sentinel y material protegido.
- [x] 11.4 Repetir checkout limpio/builds/paridad/seguridad/browser/restore/diagnóstico después de retirada; acreditar G3/GO del repositorio sin confundirlos con gates de la instancia real.
- [x] 11.5 Consolidar EV/gates/resultados/límites y actualizar guías al runtime realmente entregado; registrar aceptación antes de Recovery sin borrar originales ni sync/archive.

## Verification and provenance

Evidence baseline: commit `13a1b6fde7a219640ddae34338bef8608def8ffb` plus the uncommitted test syntax/import/format fixes and LF diagnostics rule verified in 11.4. Runtime sources were unchanged. The clean-checkout proof used HEAD with process-only core.autocrlf=false/core.eol=lf; Windows checkout separately verified the LF correction.

- Backend: 29 suites/42 CLI cases; 860 pytest tests, zero skips.
- Frontend: 416 files/5198 Vitest tests; host Node 24.14.0, two workers.
- Browser: 14 journeys, zero errors; Node 22.23.2, Chromium 151.0.7922.34; independent PostgreSQL observation and injected 401/conflicts/lost response.
- Builds: web/mobile, shared generators, image isolation and clean-HEAD cache/lifecycle matrices passed.
- Restore: full_timing passed directly and through the public CLI, including access review, client reconciliation and closure. Diagnostics privacy, retention, correlation and sink failures passed.
- Retirement: 154 obsolete paths removed; 712 source backup files hash-verified. Foreign sentinel/protected material survived. Injected retired consumer failed its build; removing the injection passed.
- Quality: lint, locales, generated OpenAPI, OKF, strict OpenSpec and diff checks passed.

### Suite traceability

Historical run identifiers and log hashes identify the accepted results; they do not reconstruct deleted logs or prove a new run. Public case mappings live in [the verifier manifest](../../../../backend/platform-suites.json).

| Suite | Cases | Pytest | Log SHA-256 |
| --- | --- | ---: | --- |
| harness | ownership | 0 | `8cf435ed98d44e311ca1dff245a0eb929dedbbb2071ae7f7dd96f50bcec5017c` |
| database | pool | 20 | `8c8e36344ba1d408facfa126d49d3d7679b9ec14498d2c211934d82782b64dc6` |
| checks | toolchain | 12 | `0c5fc394933210547832d80cc67f4cfeef0551dfceb411404b80e3ce5385e998` |
| schema | history_lock | 12 | `eda9f37137a53ca6426042d6a3d060fea9f048f67f618d3c74603c5de7cd3f13` |
| lifecycle | readiness | 19 | `a57a5fec1f2fcf4fa8240c58ac1452fd779fb784c24683eaca026052a37cddb7` |
| identity_session | restricted_pool, actor | 57 | `f877d2cfd0e53eb777e45b93f50cc40732c67cbbafa448dc42f56fde21720eae` |
| identity_password | login | 27 | `3dd0dda7eae1025fcf5d36b9b3e0ef1a735ba03488f402d80779bd2fae4da81a` |
| identity_register | concurrent_claim | 125 | `5caec165801349e3c0e34b4d430d102db0b00574ba57416922b78efa7df24027` |
| identity_passkey | interoperability | 25 | `01a282e585bf450b1db5e36edaf2b4dfa88eda7e1a3f948fd7a801890140cecb` |
| identity_account | passkey_management, password_email | 59 | `b41bab71e0a55a33e2dad5d96f3ae1e0ae2f6a07698364dcb7a7136f9b5477f8` |
| identity_reset | single_use | 21 | `b30b8872752f4892f1b5465a08d2d127d392fa55c7cdba3727346c22e4ab0392` |
| identity_links | redeem | 29 | `a3917144bfcf40b1ca0e0bf1aae1b8bb91e07eda473d85a0a8b4a7cae0a686ce` |
| training_read | owner_and_types | 8 | `a04bcdf41f5c8e3efe53d2a14a63d5a36fb0fd4fd185f28ec6a66a245c590269` |
| training_write | lineage_retry, first_write | 55 | `300230a66b9129cef002c45a1fdbf76c5b5644b4b59235159537621ae3fc349d` |
| training_browser | offline_sync | 1 | `3bf5c6ecc36113d69f5d7b28a4d97c670ff0646e1da6a3db97c4670b09ea165d` |
| media | roundtrip, quota_and_missing | 11 | `01a14e775817f1f821ddabfcef424e3ac21f025f4afc0cbf6e74e37ad48ef82c` |
| media_gc | fail_safe | 13 | `7e543aacea834efbd05e10863e64bfdbf0356d59b9faa71443ea0cbb6adb3b5f` |
| coach_state | late_result, atomic_enqueue, deferred_provider | 35 | `64b07b40de98cc66a1f4d777328efe8ac0e5c9d9022a433349ae8ec277ba8ba9` |
| coach_http | validated_proposal | 85 | `7b4fdaaaf317d9efa75e8e4a1f524523cdcb89b31be6c38cf8d599eda31353b2` |
| coach_admin | credentials | 28 | `9883aeb6c65b0ce3a028977b3d07e4f4ac20a708d2a9d42f60609efacb2d4615` |
| coach_client | consent_and_availability | 23 | `f8966c006df5643ca52894111450e4a923e600c40a615670e436054108ec3532` |
| admin_audit | failure_and_retention | 21 | `e2951eb7eb223e28cdd748e43bfc11ccfc9fd11138c0ed011762b7a79b367096` |
| admin_invites | consumed_history | 27 | `f3be22c1f342d7094a7eee464fee52f5f7a42b47b1611fa6eefbd98afff26403` |
| admin_users | actor_target | 24 | `af8f5485ab3ffe7b68137fc46ede185eb71a01d0d58904a89489b4fcc04e53fa` |
| admin_delete | external_retry, atomic_delete | 34 | `3a37c15753d6fc6cc7a06acdbfa65f49c04b8371725d7626005f91cf16a08931` |
| notifications | device_isolation, local_dates, subscription | 76 | `f486627bd699b97936989475d1a3290c05a3682cc89fe4dd672336a7bf7a974c` |
| contracts | python_routes | 1 | `64411d38c532fec6e626cd9b92526f6c21a6e38b84561de5c585641d2183b29f` |
| shared_client | canonical_sources, formats_and_bundles | 0 | `9fe88bc4af8825bc598b921e96f5a349f1fcfaa9b84b45ea1b8dc02cebeb3519` |
| diagnostics | retention_and_failure, correlation, operator_status, collector_retention | 12 | `abcba6730378fde16ee64916cf390ac6e504fad0443be44338a68c48a6b3b6cb` |

### Limits and observed failures

No remote CI, physical devices, real providers, independent physical backup disk, host reboot or real-instance acceptance was demonstrated. RPO 6 h/RTO 24 h remain operational objectives. SDK/CLI Coach providers remain deferred under Q6. The verify-opengym skill still targets retired Node topology; registered training_browser supplied Python coverage.

Initial sandbox restrictions, Vitest saturation and concurrent diagnostic subnet collisions were resolved or avoided before final passing runs. Earlier restore/import intermittent failures were retained during review and followed by isolated passing runs; no assertions were weakened. Historical results are scoped to their original revision and synthetic environment. Revalidate affected behavior when the candidate or environment changes.

## 11. Cierre del repositorio; migración real aplazada — S11

11.1 was administratively closed on 2026-11-03. The promoter explicitly deferred actual migration in 11.2; 11.3 retired source/contracts and migrated regression coverage; 11.4 verified the retired tree. On 2026-11-04 the promoter accepted the documented EV-01–EV-09 results and limits and closed 11.5. [The operational reference](../../../../docs/reference/platform-operations.md#evidencia-de-aceptación-y-límites-de-esta-revisión) owns the EV/gate mapping. Synthetic G1/GP/GO/G3 evidence supports repository acceptance; real G0/G2/G3 and candidate/environment binding remain uncredited.

## Archive and cleanup

On 2026-11-04, synchronized compatible-platform-persistence (2 requirements added, 2 updated) and local-platform-operation (3 updated), preserving previous scenarios. Archived with .openspec.yaml and all tasks complete. The archive contains only native proposal/design/specs/tasks artifacts and metadata.

The promoter authorized deletion of .scratch: 2565 files/74188418 bytes removed after preserving results and independent tickets. The exact in-repository target and absence of reparse points were verified. CIM process inspection was unavailable; no absence-of-writers claim relies on it. No own verifier was running. Operational originals outside .scratch and Docker resources were untouched. Raw logs/screenshots/exports are intentionally unavailable; references to them are historical provenance.

This editorial compaction replaces copied execution history with decisions, completion and evidence. Previous consolidated tasks SHA-256: `a7270baf7314fa513e60a1d253a81b9be3f427381c8d5257cec7d9ca923c84a0`; design SHA-256: `9c24c01e4136820d66678d9a3db00254b86c2b7b1664b9ee50b86385478662aa`. A temporary pre-edit copy is retained outside the repository. Main requirement specs remain unchanged by compaction.

## Independent follow-ups preserved from .scratch

These are historical triage items, not incomplete platform tasks:

| Original ticket | State | Follow-up and completion criterion |
| --- | --- | --- |
| documentation-lean/01-control-accessible-names | needs-triage | Revalidate Settings alert/appearance switches with the accessibility tree; associate visible labels if still missing. Observation: 2026-10-19 runtime 1.4.1, source 28b7e4dc. Preserve dialog regression coverage. |
| documentation-lean/02-accent-text-contrast | needs-triage | Recheck composed accent/text colors in both themes and custom extremes. Historical green text measured ~1.77:1 on tinted light background and ~2.22:1 on white. Apply normal-text 4.5:1/large-text 3:1 thresholds; 17px/600 alone is not large text. Agree a text-ink policy before palette changes. |
| documentation-lean/03-device-accessibility-coverage | needs-triage | Agree supported devices; verify zoom, keyboard/safe areas, reduced motion including JS/media, effective touch areas and overlap. Historical ~30px chips alone do not establish failure of the 24px WCAG minimum. Emulation is not physical-device proof. |
| documentation-lean/04-documentation-ci | needs-triage | Recheck current workflow before acting: the ticket historically requested OKF check/tests for documentation-only changes. Reuse existing tooling; structural checks do not establish semantic acceptance. |
| streamline-platform-codebase/01-review-proposal | ready-for-agent | Planning-only, Implementation Ready; separate change with 55 pending tasks. Per-slice Docker/Buildx preflight; no dependency on this archive, no implementation authorized by this routing ticket. [Read its tasks](../../streamline-platform-codebase/tasks.md). |

Final closeout checks: five main specs valid in strict mode; OKF and diff-check passed. Runtime suites were reused for this documentary operation.
