# Plan de verificación y exportaciones

## Estado y alcance

Planificación completada sobre revisión 5f8f70519214744a94984e1a002e9ccbc676e34d y archivos locales inspeccionados; el árbol contiene trabajo concurrente, por lo que esa revisión no certifica todos sus bytes. Los comandos/casos siguientes existen en el checkout inspeccionado y sus rutas se comprobaron sin ejecutar Docker. No dependen del estado de otra OpenSpec. Antes de modificar, 1.1–1.3 solo registran drift, estado de baseline y entorno; no son decisiones de diseño pendientes. Si hay drift, actualizar la selección equivalente del slice, sin reabrir alcance ni resucitar tooling retirado.

Esta propuesta está Implementation Ready como especificación de ejecución por slices. No significa implementación autorizada, baseline aprobado ni aceptación de producto. Una condición de ejecución bloquea únicamente el trabajo que necesita ese recurso. La implementación no puede aceptarse sin sus pruebas obligatorias.

## Comandos backend exactos, casos y observadores

Todos desde raíz; cada fila ejecuta una suite/caso completo, sin -k ni omisiones. El runner crea recursos sintéticos propios y no toma el env de una instancia real. Las rutas corresponden al comando empaquetado por el manifest, no a pytest del host. Resultado exigido: exit 0 y prueba requerida completa; sin skips/xfail acreditados. Para escenarios específicos se conserva el caso entero, aunque contenga pruebas adicionales.

| Suite/caso | Comando | Pruebas actuales / observación |
| --- | --- | --- |
| lifecycle/readiness | `node scripts/platform.mjs verify lifecycle --case readiness` | `tests/platform/test_lifecycle.py`; HTTP/PG restringido y observador independiente; browser real si target browser |
| database/pool | `node scripts/platform.mjs verify database --case pool` | `tests/core/test_database.py`; integración de pool/transacciones PostgreSQL, no recorrido HTTP/browser |
| checks/toolchain | `node scripts/platform.mjs verify checks --case toolchain` | `tests/platform/test_toolchain.py tests/platform/test_proof_policy.py`; locks, dependencias, lint/formato/types y política de pruebas; no acredita HTTP/RLS |
| training_read/owner_and_types | `node scripts/platform.mjs verify training_read --case owner_and_types` | `tests/platform/test_training_read.py`; HTTP/PG restringido y observador independiente; browser real si target browser |
| training_write/lineage_retry | `node scripts/platform.mjs verify training_write --case lineage_retry` | `tests/platform/test_training_lineage.py`; HTTP/PG restringido y observador independiente; browser real si target browser |
| training_write/first_write | `node scripts/platform.mjs verify training_write --case first_write` | `tests/platform/test_training_write.py`; HTTP/PG restringido y observador independiente; browser real si target browser |
| training_browser/offline_sync | `node scripts/platform.mjs verify training_browser --case offline_sync` | `tests/platform/test_training_browser.py`; frontend compilado/Chromium → HTTP Python → PG, con fixture y observaciones independientes |
| identity_session/restricted_pool | `node scripts/platform.mjs verify identity_session --case restricted_pool` | `tests/core/test_database.py tests/platform/test_identity_restricted_pool.py`; HTTP/PG restringido y observador independiente; browser real si target browser |
| identity_session/actor | `node scripts/platform.mjs verify identity_session --case actor` | `tests/platform/test_identity_session.py`; HTTP/PG restringido y observador independiente; browser real si target browser |
| identity_password/login | `node scripts/platform.mjs verify identity_password --case login` | `tests/platform/test_identity_password.py`; HTTP/PG restringido y observador independiente; browser real si target browser |
| identity_passkey/interoperability | `node scripts/platform.mjs verify identity_passkey --case interoperability` | `tests/platform/test_identity_passkey.py`; HTTP/PG restringido y observador independiente; browser real si target browser |
| identity_links/redeem | `node scripts/platform.mjs verify identity_links --case redeem` | `tests/platform/test_identity_links.py`; HTTP/PG restringido y observador independiente; browser real si target browser |
| identity_account/passkey_management | `node scripts/platform.mjs verify identity_account --case passkey_management` | `tests/platform/test_passkey_management.py`; HTTP/PG restringido y observador independiente; browser real si target browser |
| identity_account/password_email | `node scripts/platform.mjs verify identity_account --case password_email` | `tests/platform/test_identity_account.py`; HTTP/PG restringido y observador independiente; browser real si target browser |
| coach_state/late_result | `node scripts/platform.mjs verify coach_state --case late_result` | `tests/platform/test_coach_lifecycle.py`; HTTP/PG restringido y observador independiente; browser real si target browser |
| coach_state/atomic_enqueue | `node scripts/platform.mjs verify coach_state --case atomic_enqueue` | `tests/platform/test_coach_jobs.py`; HTTP/PG restringido y observador independiente; browser real si target browser |
| coach_state/deferred_provider | `node scripts/platform.mjs verify coach_state --case deferred_provider` | `tests/platform/test_coach_state.py`; HTTP/PG restringido y observador independiente; browser real si target browser |
| coach_http/validated_proposal | `node scripts/platform.mjs verify coach_http --case validated_proposal` | `tests/platform/test_coach_http.py tests/platform/test_coach_vectors.py`; HTTP/PG restringido y observador independiente; browser real si target browser |
| coach_admin/credentials | `node scripts/platform.mjs verify coach_admin --case credentials` | `tests/platform/test_coach_admin.py`; HTTP/PG restringido y observador independiente; browser real si target browser |
| coach_client/consent_and_availability | `node scripts/platform.mjs verify coach_client --case consent_and_availability` | `tests/platform/test_coach_client.py`; HTTP/PG restringido y observador independiente; browser real si target browser |
| media/roundtrip | `node scripts/platform.mjs verify media --case roundtrip` | `tests/platform/test_media.py`; HTTP/PG restringido y observador independiente; browser real si target browser |
| media/quota_and_missing | `node scripts/platform.mjs verify media --case quota_and_missing` | `tests/platform/test_media_limits.py`; HTTP/PG restringido y observador independiente; browser real si target browser |
| media_gc/fail_safe | `node scripts/platform.mjs verify media_gc --case fail_safe` | `tests/platform/test_media_gc.py`; HTTP/PG restringido y observador independiente; browser real si target browser |
| admin_users/actor_target | `node scripts/platform.mjs verify admin_users --case actor_target` | `tests/platform/test_admin_users.py`; HTTP/PG restringido y observador independiente; browser real si target browser |
| admin_delete/external_retry | `node scripts/platform.mjs verify admin_delete --case external_retry` | `tests/platform/test_admin_cleanup.py`; HTTP/PG restringido y observador independiente; browser real si target browser |
| admin_delete/atomic_delete | `node scripts/platform.mjs verify admin_delete --case atomic_delete` | `tests/platform/test_admin_delete.py`; HTTP/PG restringido y observador independiente; browser real si target browser |
| admin_invites/consumed_history | `node scripts/platform.mjs verify admin_invites --case consumed_history` | `tests/platform/test_admin_invites.py`; HTTP/PG restringido y observador independiente; browser real si target browser |
| admin_audit/failure_and_retention | `node scripts/platform.mjs verify admin_audit --case failure_and_retention` | `tests/platform/test_audit.py`; HTTP/PG restringido y observador independiente; browser real si target browser |
| notifications/device_isolation | `node scripts/platform.mjs verify notifications --case device_isolation` | `tests/platform/test_notification_activity.py`; HTTP/PG restringido y observador independiente; browser real si target browser |
| notifications/local_dates | `node scripts/platform.mjs verify notifications --case local_dates` | `tests/platform/test_notification_delivery.py tests/platform/test_notification_authorization.py`; HTTP/PG restringido y observador independiente; browser real si target browser |
| notifications/subscription | `node scripts/platform.mjs verify notifications --case subscription` | `tests/platform/test_notifications.py`; HTTP/PG restringido y observador independiente; browser real si target browser |
| images/isolation | `node scripts/platform.mjs verify images --case isolation` | `--test scripts/platform-images.test.mjs`; CLI/containers/archivos sintéticos |
| backup/verified_bundle | `node scripts/platform.mjs verify backup --case verified_bundle` | `--test --test-reporter=tap scripts/platform-bundle.test.mjs`; CLI/containers/archivos sintéticos |
| backup/writer_shutdown | `node scripts/platform.mjs verify backup --case writer_shutdown` | `--test --test-reporter=tap scripts/platform-maintenance.test.mjs`; CLI/containers/archivos sintéticos |
| backup/sql_files_coherence | `node scripts/platform.mjs verify backup --case sql_files_coherence` | `--test --test-reporter=tap scripts/platform-maintenance.test.mjs`; CLI/containers/archivos sintéticos |
| backup/interrupted_capture | `node scripts/platform.mjs verify backup --case interrupted_capture` | `--test --test-reporter=tap scripts/platform-maintenance.test.mjs`; CLI/containers/archivos sintéticos |
| contracts/python_routes | `node scripts/platform.mjs verify contracts --case python_routes` | `tests/platform/test_openapi.py`; HTTP/PG restringido y observador independiente; browser real si target browser |

El target indica entorno de ejecución, no la garantía observada. Las filas HTTP/PG requieren contrastar las aserciones de la prueba seleccionada: no acreditan todas las rutas/ownership por sí solas. Toolchain no acredita seguridad funcional, HTTP no acredita UI y browser sintético no acredita hardware. La futura prueba de arquitectura en checks tampoco convierte la suite en prueba HTTP/RLS.

## Comandos frontend exactos y aplicación por tarea

Desde frontend, con pnpm fijado y dependencias ya instaladas; no instalar herramientas por inferencia. Vitest observa operaciones y efectos de transporte/storage, no acredita browser ni hardware.

| Capacidad / tareas | Comando |
| --- | --- |
| Training/sync | `pnpm exec vitest run src/store/useStore.sync.test.jsx src/store/useStore.adopt.test.jsx src/store/useStore.adopt-hold.test.jsx src/store/useStore.import-check.test.jsx src/lib/sync-merge.test.js` |
| Identity | `pnpm exec vitest run src/views/Settings.password.test.jsx src/views/Settings.passkeys.test.jsx src/store/useStore.device-link.test.jsx src/store/useStore.adopt.test.jsx` |
| Coach | `pnpm exec vitest run src/lib/coach.test.js src/lib/coach-local.test.js src/lib/coach-demo.test.js src/lib/coach-parity.test.js src/views/AdminCoach.test.jsx src/views/AdminCoach.config.test.jsx` |
| Media | `pnpm exec vitest run src/lib/media-sync.test.js src/lib/media-refs.test.js src/store/useStore.media.test.jsx src/views/Settings.media.test.jsx src/components/ServerSync.media.test.jsx` |
| Administration | `pnpm exec vitest run src/views/Admin.test.jsx src/views/Admin.password.test.jsx` |
| Notifications | `pnpm exec vitest run src/lib/push.test.js src/lib/rest-alert.test.js src/lib/rest-alert.native.test.js src/store/useUI.rest-alert.test.js src/store/useUI.rest-reload.test.js src/views/Settings.schedule.test.jsx src/views/Settings.nudge.test.jsx` |

- 2.1: lifecycle/readiness, admin_delete/external_retry y backup/writer_shutdown; agregar a los tests de lifecycle actuales la comprobación de import de metadata pura sin cargar application.
- 2.2–2.3: training_write/first_write y lineage_retry, coach_state/late_result y atomic_enqueue. La prueba existente test_failed_withdrawal_rolls_back_training_and_does_not_cancel_authorized_work observa PG independiente; conservarla. Añadir éxito y marca de cancelación posterior al commit si la caracterización no las distingue.
- 4.1–4.3: selección Training/sync más training_browser/offline_sync y ambos casos training_write.
- 5.5: selección Identity + identity_password/login, identity_session/actor, identity_account/password_email. 5.6: identity_passkey/interoperability, identity_links/redeem, identity_account/passkey_management y training_browser/offline_sync.
- 5.7: selección Coach + coach_state/deferred_provider, coach_client/consent_and_availability, coach_admin/credentials. 5.8: coach_http/validated_proposal, coach_state/late_result y atomic_enqueue.
- 6.7: selección Media + media/roundtrip y quota_and_missing. 6.8: media_gc/fail_safe y training_browser/offline_sync.
- 6.9: selección Administration + admin_users/actor_target. 6.10: ambos casos admin_delete. 6.11: admin_invites/consumed_history y training_browser/offline_sync. 6.12: admin_audit/failure_and_retention.
- 6.13: selección Notifications + notifications/subscription. 6.14: notifications/device_isolation. 6.15: notifications/local_dates.

Browser: comando exacto training_browser/offline_sync de la tabla, entrada frontend/e2e/platform/training.mjs mediante backend/tests/platform/test_training_browser.py. Ya cubre offline/auth/conflictos/respuesta perdida/passkeys/pairing/medios e invitaciones admin. Para recorridos UI Coach, borrado/audit y Notifications que el browser actual no cubra, se amplía ese caso y sus módulos de recorrido durante el slice respectivo, manteniendo su entrada/observador existentes; actualizar la lista de evidencias esperadas del runner junto con cada ampliación. No crear setters públicos ni endpoints de test de producto: usar acciones UI, control de fixture sintético ya existente y observador independiente. Ésta es cobertura nueva prevista, no un check actualmente aprobado. Los casos backend y Vitest no sustituyen ese recorrido cuando se modifica UI.

### Aceptación browser de recorridos afectados

| Recorrido / tareas | Acción UI mínima | Observación independiente |
| --- | --- | --- |
| Coach / 5.7–5.8 | Consentir, solicitar propuesta y cancelar o retirar consentimiento | Estado/job observado desde fixture/PG; respuesta tardía no aplica Training |
| Administration: borrado / 6.10 | Eliminar usuario autorizado y observar cleanup pendiente/completo | Cuenta inaccesible y tarea/archivos propios observados fuera de la UI |
| Administration: audit / 6.12 | Leer/limpiar audit con actor permitido y comprobar rechazo indebido | Eventos/resultado persistente observados independientemente |
| Notifications / 6.13–6.15 | Cambiar preferencia/opt-out y cancelar timer del dispositivo | Estado autorizado y transporte fake existente; dispositivo ajeno intacto |

Reutilizar cada recorrido existente que ya pruebe esas observaciones. El runner actual reconoce admin-audit: comprobar ejecución/aserciones y reutilizarlo antes de añadir otra prueba. Añadir solo cobertura faltante dentro del harness actual. Una captura sola no satisface el caso. Actualizar juntos productor, lector de evidencia y lista de casos requeridos en frontend/e2e/platform/training.mjs, backend/tests/platform/test_training_browser.py y scripts/platform.mjs según sus consumidores reales; nunca relajar la lista para admitir omisiones. El comando sigue siendo training_browser/offline_sync. Son mínimos de recorridos afectados, no nuevas capacidades ni pruebas reales de proveedores/dispositivos.

## Exportaciones e interfaces: decisión concreta

Se permite la superficie explícita siguiente, no cualquier nombre exportado. No añadir archivos public.py de paso ni contratos por cada método. Los participantes usan contexto autorizado; no aceptar owner del caller HTTP como autoridad.

| Propietario | Exportaciones actuales permitidas / contrato de destino | Consumidores permitidos |
| --- | --- | --- |
| Composición | application.create_app | Uvicorn, tests/factory; ningún módulo funcional/comando la usa para metadata |
| Metadata de esquema | Destino elegido core/schema.py: SCHEMA_REVISION, movida desde application sin duplicar valor | application, administration.cleanup y backup; stdlib solamente, sin carga HTTP |
| Identidad/contexto | identity.sessions.Session, select_token, verify, authorize, lock_media_owner | routers/operaciones autorizadas y módulos que requieren ese contexto; sign solo emisión de sesión/fixtures independientes |
| Training lectura | training.service.admin_projection, coach_consent, coach_document, notification_document; training.references.media_references y referenced_hashes | administration; Coach; Notifications; Media según proyección, con handle/actor y owner comprobado |
| Guardado coordinado | Destino elegido training_save.py: save(database, session, body, note_state=None, *, coach); único iniciador | training.router inyecta la instancia Jobs propiedad del lifespan de application; sin registry/event bus |
| Training escritura participante | Destino training.service.write_participant(handle, session, body); devuelve resultado/estado necesario sin commit ni objeto Coach | training_save.save; no accede a jobs/cuotas Coach |
| Coach participación | Jobs.training_changed(handle, owner, current, document) y Jobs.cancel(job_id) | iniciador; cancel solo después del commit; owner proviene del contexto autorizado |
| Coach entrada/lifecycle | Jobs.preflight, status, enqueue, resolve, forget, close | router/ejecución y composición; métodos con _ y SQL propios privados |
| Secretos | Destino core.platform_settings.load_secret(variable), renombrando el helper _secret sin nueva fachada | configuración y coach.secrets; mismos límites/formatos/permisos, sin nueva semántica de secretos |
| Media | Media.missing, receive, download, sweep, note_state; remove_deleted_owner | router, composición y cleanup administrativo; no usar directorio/estado interno como interface cruzada |
| Administration | administration.service.handle y checked | router/operaciones administrativas; no convertir permiso admin en owner arbitrario |
| Audit | Audit.read, clear, append, identity_result | router y productores de eventos autorizados; persistencia audit sigue privada |
| Notifications | notifications.service.preflight y handle; Presence.update/live/clear/sweep | router, scheduler/composición; estado interno/timers no se importan de otra capacidad |
| Frontend estado | useStore, useUI y acciones ya existentes pushState/pullState/adoptProfile; helpers puros existentes | features/hooks; se prohíbe un segundo store persistente de documento/revisiones |
| Frontend transporte/Coach | lib/api.api y beacon; lib/remote.loadRemote/chooseLocal/forgetRemote/connect/renewToken; operaciones explícitas de lib/coach-api | clientes/hooks de capacidad, reutilizando transporte; selección local/demo/HTTP no se duplica |
| Frontend medios | media-sync.createMediaSync/startMediaSync/syncMedia/fetchToStore/mayFetch/localMediaGc/settleMediaSync | bootstrap y capacidad Media; _setSharedMediaSync es seam de test, no interface de producto |

El coordinador reutiliza la instancia inyectada: no crea Jobs, no consulta un singleton y no importa application. Training.write_participant no recibe Coach. Probar que training_changed y cancelación usan el mismo colaborador, que no hay cancelación tras rollback/commit fallido y que una respuesta tardía conserva sus restricciones.

Los destinos nuevos son decisiones de planificación, no símbolos existentes ni código entregado. En 2.1 se corrige el consumo cruzado de _secret; no se añade excepción permanente. En 2.3 se adapta router al iniciador y participantes anteriores con pruebas de rollback/commit. El módulo raíz training_save tiene una responsabilidad concreta, no un framework global. Las rutas frontend pueden moverse por slices conservando operaciones; el mapa se actualiza en el mismo cambio.

## Reglas nuevas y fixtures decididas

Integrar en la suite checks/toolchain existente una prueba nueva de dependencias (backend/tests/platform/test_architecture.py, añadida al caso existente durante 3.2–3.3). Ejecutar con el comando exacto checks/toolchain de la tabla. No implementar checker en esta fase de planificación.

Casos obligatorios: core importa Training → falla; cleanup importa application incluso localmente → falla; consumidor usa Training projection declarada → pasa; consumidor usa repositorio/privado ajeno → falla; Training recibe objeto Coach → prueba de operación falla aunque imports pasen; UI compartida importa feature o feature importa interno ajeno → falla; import dinámico literal se resuelve; destino computado se informa como revisión requerida sin pase automático. Excepciones: ninguna aprobada para producción; fixtures/tests son consumidores explícitos de sus seams privados y no habilitan su uso desde producto.

Contrato: exit no-cero y ruta origen/destino para violación; exit cero para grafo permitido; computado no resuelto no recibe crédito sin revisión registrada. No parser general de flujo; usar AST Python y lectura de imports JS acotada al estilo existente, declarando límites. Actualizar la lista junto con cualquier nueva interface, no mantener allowlist global de paquetes.

## Docker: bloqueo de ejecución local, no de planificación

La falta actual de acceso Docker/Buildx impide acreditar builds, contextos y suites HTTP/PG/browser que requieren containers. No es decisión de diseño abierta, no obliga a esperar otra OpenSpec y no bloquea la preparación documental ni un slice cuyos checks estén disponibles. Antes de modificar cada slice se ejecuta su preflight; si necesita Docker y no hay acceso, ese slice no se inicia ni se acredita. Un entorno autorizado Linux/amd64 con los pins actuales satisface el requisito; no instalar ni cambiar permisos por inferencia.

Comandos exactos desde raíz:

- docker compose version
- docker info --format '{{.ServerVersion}}'
- docker buildx version
- node --test scripts/docker-layout.test.mjs scripts/docker-build-context.test.mjs
- node --test scripts/platform-images.test.mjs
- node --test scripts/platform-build.test.mjs
- node scripts/platform.mjs verify lifecycle --case readiness
- node scripts/platform.mjs verify backup --case writer_shutdown
- node scripts/platform.mjs verify backup --case sql_files_coherence

Los tests layout/images generan env sintético privado y renders con directorio raíz y proyecto propios; nunca sustituirlos por .env real. Antes/después comparar puertos, identidades de volúmenes/proyectos, secretos por servicio, roles, redes, readonly/capabilities, logging y maintenance. Contextos prueban todos los COPY del inventario y sentinel privado. Cache prueba frío/repetido/fuente/lock; imagen inspecciona no-root y ausencia de tooling ajeno. No ejecutar toda la matriz para cada cambio pequeño: prueba específica del slice, aceptación integrada al final.

## Documentación y aceptación

Comandos exactos: node scripts/docs/okf.mjs check; node scripts/build-api-docs.mjs --check; node scripts/build-coach-assets.mjs --check; node scripts/build-coach-library.mjs --check; node scripts/build-push-assets.mjs --check; git diff --check. Build web: pnpm --dir frontend run build. Bundle portable: node scripts/platform.mjs verify shared_client --case formats_and_bundles, que hoy usa comparación transitoria; no eliminarla por otra OpenSpec. Si ya cambió el árbol, registrar equivalente nativo con misma garantía. No ejecutar build:mobile como sustituto: incluye cap sync.

Stage 9 registra matriz afirmación→fuente/comando→resultado/límite de revisión final. No se exige ejecutar producción/hardware; cualquier afirmación que sí los requiera conserva su límite y no se acredita por prueba sintética. La condición Implementation Ready de planificación no marca completas tareas 1–10, no levanta el bloqueo del slice Docker ni equivale a aceptación integrada.
