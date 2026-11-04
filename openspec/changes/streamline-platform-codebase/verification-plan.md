# Plan de verificación y exportaciones

## Estado y alcance

Revisión de auditoría: 2026-11-04, HEAD 13a1b6fde7a219640ddae34338bef8608def8ffb y worktree con cambios ajenos staged/unstaged. HEAD no certifica todos los bytes. Los 38 selectores backend únicos citados aquí resuelven en el manifest actual; las seis selecciones Vitest suman 29 referencias a archivos, todas existentes. Eso prueba selección/rutas, no comportamiento. Revalidar drift antes de cada slice, sin resucitar tooling retirado ni depender del estado de otra OpenSpec.

Estado: Implementation Ready de planificación. D8 preserva compatibilidades activas y D12 fija Oxfmt 0.76.0 con la configuración ensayada. No hay decisiones materiales abiertas; las 60 tareas de entrega siguen pendientes. Una condición de entorno bloquea el trabajo que necesita ese recurso; no equivale a defecto del producto ni permite aceptar pruebas omitidas.

## Auditoría local ejecutada el 2026-11-04

| Comprobación ejecutada | Resultado | Límite |
| --- | --- | --- |
| openspec list/status + validate streamline-platform-codebase --strict --no-interactive | Validación original y posterior pasan; 0/55 tareas antes, 0/60 después de revisión | Esquema completo no acredita readiness semántica ni implementación |
| node scripts/docs/okf.mjs check | Exit 0; 30 conceptos, siete índices, 449 enlaces | Aviso histórico por enlace a api/coach/core/payload.js en research/recovery-reference-benchmark.md; no bloquea ni se reescribe el histórico |
| node scripts/build-api-docs.mjs --check | Exit 0; 68 endpoints, 30 schemas, website/api.html vigente | Generación/consistencia, no comportamiento HTTP |
| git diff --check | Exit 0 antes de revisión | Solo whitespace del diff comprobado; no certifica cambios ajenos |
| node node_modules/oxlint/bin/oxlint frontend/src frontend/e2e scripts backend shared | Exit 0; 737 archivos, cinco reglas, cero errores/avisos | No comprueba ownership, ciclos ni comentarios con configuración actual |
| Desde frontend: node node_modules/vitest/vitest.mjs run src/store/useStore.legacy-upgrade.test.jsx src/store/useStore.sync.test.jsx src/lib/coach-core/parse.test.js src/lib/coach-core/payload.test.js | Cuatro archivos, 60 tests pasan | Dependencias ya instaladas; Node host 24.14.0, no imagen CI Node 22; sin prueba browser/PG |
| docker compose version / docker buildx version / docker info --format '{{.ServerVersion}}' | Compose 5.1.1, Buildx 0.33.0-desktop.1; info falla por acceso denegado a pipe Docker | No se ejecutaron builds, renders Docker ni suites HTTP/PG/browser en esta auditoría |
| pnpm --version | Corepack intenta obtener pnpm 10.34.8; falla DNS a registry.npmjs.org | No se acredita gestor disponible ni instalación; pruebas focalizadas ejecutadas mediante binarios locales existentes |

Las lecturas/auditoría no marcan tareas de implementación completas. No se ensayaron sesiones nuevas de onboarding de clientes, no se instaló P-stack ni se ejecutaron sus workflows. No se arrancó una instancia real ni se leyeron datos/secretos de usuario.

Después de editar: OKF check y diff-check del cambio pasan; los 60 IDs de tarea aparecen exactamente una vez en Execution Order, sin referencias inexistentes. Los enlaces locales de los cuatro artefactos principales resuelven y los archivos comprobados no tienen BOM. El aviso histórico OKF sigue separado de los checks requeridos. Ninguna tarea runtime se marca completa por estas validaciones.

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

El acceso al daemon Docker está denegado en esta auditoría; las versiones CLI/Buildx sí se pudieron consultar. No se acreditan builds, contextos ni suites containerizadas. No obliga a esperar otra OpenSpec ni bloquea preparación documental o slices independientes. Repetir preflight antes del slice; no instalar ni cambiar permisos por inferencia.

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

Comandos exactos: node scripts/docs/okf.mjs check; node scripts/build-api-docs.mjs --check; node scripts/build-coach-assets.mjs --check; node scripts/build-coach-library.mjs --check; node scripts/build-push-assets.mjs --check; git diff --check. Build web: pnpm --dir frontend run build. Bundle portable: node scripts/platform.mjs verify shared_client --case formats_and_bundles, que ejecuta scripts/formats-and-bundles.test.mjs sobre formatos y bundles actuales sin la API Node retirada. No ejecutar build:mobile como sustituto: incluye cap sync.

Stage 9 registra matriz afirmación→fuente/comando→resultado/límite. No exige producción/hardware; cualquier afirmación que los requiera conserva su límite y no se acredita por fixture. La validación de planificación no marca completas tareas ni levanta restricciones de entorno.

## V11: formato, comentarios y retirada de implementaciones

Formatter seleccionado/ensayado: Oxfmt 0.76.0 y [formatter.config.json](formatter.config.json), para trasladar a .oxfmtrc.json raíz en 3.5 y fijar dependencia/lock con pnpm add --save-dev --save-exact oxfmt@0.76.0. No se ha instalado ni integrado en el proyecto; tampoco se entregó el checker de comentarios/grafo. Esas tareas siguen pendientes, usando el runner/toolchain existente.

Invocación de destino exacta desde raíz, idéntica en local y CI:

```sh
pnpm exec oxfmt --config .oxfmtrc.json --disable-nested-config --check "frontend/**/*.{js,jsx,mjs,css}" "scripts/**/*.{js,mjs}" "shared/**/*.js"
```

fmt:check contendrá esa invocación; fmt cambia --check por --write. CI quality invoca pnpm run fmt:check tras install frozen. No usar latest/rangos, sorting/plugins, wrapper nuevo, oxfmt . ni --no-error-on-unmatched-pattern. La plantilla se mueve, no se duplica como otra autoridad. Selección vacía o inexistente debe fallar; un check de exclusión mezcla un positivo conocido con sentinelas ignorados para evitar confundir cero archivos con éxito.

Alcance de fuente propia: frontend/src, frontend/e2e, frontend/scripts, backend/src, backend/tests, scripts, shared, web y configuraciones propias de deploy/.github. Excluir generados identificados por generador, catálogo/media, vendor/node_modules, bundles/dist y shells generados; Markdown/históricos no son fuente que reformatear. Registrar lista exacta revisada por lote, sin exclusión por mera cantidad de comentarios. Python/JS/JSX con tokens/AST; otros formatos requieren clasificación contextual explícita hasta disponer de parser. No afirmar análisis automático universal.

Pruebas nuevas exigidas: formatter dos pasadas (segunda sin diff), fixture mal formateada rechazada, import privado rechazado y público permitido, narración rechazada, strings/regex/URLs/prompts no confundidos, directiva Vitest y docstring observable preservados o reemplazados con igual efecto. Postcommit distingue fallo de bookkeeping de fallo del guardado. No basta comparar AST si un pragma influye en build/test.

Activación incremental: desarrollar el check con fixtures, aplicar a archivos ya aceptados de 7.2 y no anunciar limpieza global hasta recorrer todo el alcance. En 8.2 el gate completo no depende de lista parcial ni baseline permanente que excuse comentarios antiguos. Excepciones técnicas exactas y comprobadas, sin allowlist general de narración. Inventario Git/build/consumidores demuestra ausencia de implementaciones sustituidas sin prohibir Node herramienta, JS neutral o vectores independientes.

## Ensayo del formatter completado el 2026-11-04

Ensayo de planificación ejecutado en una copia aislada. La ubicación local anterior se retiró por decisión del promotor: resultados necesarios consolidados en esta OpenSpec y temporales propios descartados; futuros ensayos usan el temporal del sistema. Descargas npm con TLS verificado, sin scripts de instalación. CLI y Vitest se ejecutaron con Node 22.23.2 Windows x64, extraído del archivo oficial cuyo SHA-256 se contrastó con SHASUMS256.txt. No cambió la instalación Node del equipo. No se operó Docker ni una instancia real.

| Prueba | Resultado observado |
| --- | --- |
| Oxfmt 0.76.0 / objectWrap=preserve / printWidth=100 | 716 candidatos; seis archivos cambian otra vez en segunda pasada |
| Oxfmt 0.76.0 / preserve / ancho 120 | Mismos 716; cuatro inestables. Aumentar ancho no soluciona la causa |
| Prettier 3.9.10 sobre los seis casos encontrados | Reproduce seis inestables a 100 y cuatro a 120; ambos formatters estabilizan esos seis con collapse |
| Oxfmt 0.76.0 / configuración final con collapse | 716 candidatos: 451 JS/MJS, 261 JSX y cuatro CSS; sin errores; segunda pasada byte a byte idéntica; check final exit 0 |
| Fixture deliberadamente mal formateada | --check exit 1; --write exit 0; --check posterior exit 0; archivo inexistente exit 2 |
| Exclusiones | 38 fuentes generadas y ocho sentinelas ajenos/protegidos intactos; también ante selección explícita junto al positivo |
| Conservación de código | Imports, directivas efectivas y contenido raw de templates contrastados. Comparación AST JS/JSX y CSS compilado, con normalización de representación equivalente; cero diferencias sin explicar |
| Regresión sobre copia formateada | 28 archivos únicos de las seis selecciones V4, 660 tests pasan, cero fallos/skips; no prueba de UI real/PG |
| Originales | 999 rutas fuente/config/manifiestos/locks contrastadas por SHA-256, cero cambios |

Casos inestables originales a ancho 100: frontend/e2e/platform/training.mjs, components/WorkoutMedia.jsx, sheets.jsx, store/useStore.restore.test.jsx, views/Plan.jsx y views/RoutineEdit.jsx bajo frontend/src cuando corresponde. El primer caso divide una cadena locator(...).setInputFiles({...}) en la primera pasada y la vuelve a unir en la siguiente. Se descarta preserve en este proyecto, no se presenta como ventaja exclusiva de Prettier u Oxfmt.

715 de 716 copias cambian con la política final; la migración tendrá un diff mecánico amplio y separable, nunca mezclado con el refactor funcional. El check final del ensayo incluyó además dos archivos de instrumentación, 718 targets; la cifra de producto auditada sigue siendo 716. No se copió el resultado formateado al proyecto.

La comparación estructural inicial señaló 52 archivos por diferencias de representación. Se revisaron normalizando solo EmptyStatement sin efecto en cuerpos de bloques, grafía equivalente de keys, cadenas contiguas de children JSX y whitespace de comas fuera de strings en CSS compilado por Lightning CSS 1.33.0. Los 52 quedan explicados; no es prueba formal de equivalencia ni reemplaza las regresiones. Babel parser 7.29.11 y transformWithOxc de Vite ya instalado se usaron solo como observadores del ensayo, sin nuevas dependencias de producto. Las pruebas nativas leen Java copiado, no ejecutan Android.

Resultados necesarios consolidados en este plan; logs, scripts de diagnóstico, dependencias y copias del ensayo descartados. La reproducción usa el comando documentado y formatter.config.json, sin runner permanente ni tracker paralelo. Configuración ensayada SHA-256: 6d655497435f97997a5543b9b6b6613419626ff50e4537ed8b37a81af8321bbf.

Corrección de ubicación solicitada por el promotor: el ensayo propio y su directorio scratch fueron retirados tras verificar escritores detenidos y desvincular dos junctions sin borrar sus dependencias destino. Se corrigieron AGENTS, política/plantilla de tracker y skills que lo recreaban. Siete scripts de verificación dejaron de escribir en el repositorio; usan temporales del sistema o el directorio temporal ya propietario. node --test scripts/platform.test.mjs pasa siete tests, incluido el guard de directorios retirados. Ese guard comprueba referencias textuales convencionales, no todo flujo dinámico posible. Las integraciones Docker afectadas requieren ejecución posterior; no se acreditan por este check host.

Límites: Windows x64 con Node de CI comprobado; Linux binding/CI remoto, build web completo, browser, HTTP/PG y hardware no ensayados aquí. Son pruebas obligatorias de las tareas afectadas durante entrega; 3.5 verifica binding Linux y fmt:check en CI antes de aceptar integración. Las tareas de comentarios/grafo no se declaran implementadas por ensayar el formatter.

Gate de planificación final: propuesta/diseño/tres delta specs/tareas completos, decisiones D8/D12 cerradas, interfaces/seams/casos/comandos y límites explícitos; 60 tareas con trazabilidad y orden sin duplicaciones. openspec validate --strict --no-interactive, OKF check y diff-check del cambio pasan. Configuración anexada coincide byte a byte con la comprobada. Este gate establece Implementation Ready, no aceptación del refactor ni ejecución de las 60 tareas.

## V12: onboarding por cliente

Mismos seis briefs antes (1.5) y después (9.6), en sesión nueva aislada por cliente. No se invoca un comando universal de agentes inexistente. Objetivo inicial propuesto: Codex y Cursor; acceso efectivo y mecanismo de arranque deben registrarse antes del ensayo. Sin acceso, soporte del cliente queda sin verificar, no PASS.

| Brief | Respuesta esperada contra el mapa actual/final |
| --- | --- |
| Training | Owner de escritura/sync, autoridad useStore, colaboración Coach, casos training_write y training_browser |
| Identity | Owner de sesiones/acceso, contexto autorizado, contratos seguridad y caso identity_session/actor |
| Coach | Jobs/proveedor/consentimiento, selección cliente neutral y coach_state/late_result |
| Media | Owner/cola/referencias y media/roundtrip o media_gc/fail_safe según cambio |
| Administration | Actor-target, cleanup transaccional/externo y admin_delete/external_retry |
| Notifications | Dispositivo/opt-out/presencia efímera y notifications/device_isolation |

Para cada respuesta: ruta propietaria verificada, interface permitida, estado, regla y comando vigente. Seis de seis correctas por cliente; cero acceso privado/comandos inventados. Registrar fuentes cargadas, documentos abiertos, tiempo, intervención humana y un diagnóstico de violación arquitectónica. Medición de navegación no acredita que se hayan ejecutado las suites ni que un agente arregle bugs. Evidencia en tarea/CI, no nuevo tracker; no inventar valores iniciales faltantes.
