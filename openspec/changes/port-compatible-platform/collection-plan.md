# Recolección de evidencia S11

[tasks.md](tasks.md) es la única fuente de estado y cierre.
Este documento conserva permisos, cobertura y checks; no es otro tracker.
El procedimiento con recursos privados vive en el workspace aprobado:
`runbook-11.1.md` §11 y `runbook-11.1.parameters.json`. Su nombre histórico
no reabre 11.1. La [plantilla](inventory.template.json) versionada sigue vacía.

## 1. Preparación que no toca la instancia

La cadena Node → PostgreSQL → backup cifrado → restore aislado, la reparación Q2
sobre destino superviviente y los inspectores pre_cutover/authorized_cutover ya
están entregados con evidencia sintética. Reutilizarla tras comprobar procedencia
y aplicabilidad; ejecutar de nuevo solo lo afectado por cambios, fallos o evidencia
insuficiente. No ampliar fixtures, auditorías del SO ni runbooks por rutina.

El inventario privado contiene observaciones pasivas parciales de Compose,
cliente/origen, host/WSL/tareas/sincronización. No demuestra ausencia universal de
escritores. El operador y revisor están identificados; no se repite esa selección.
Quedan por resolver para operar:

- Revisar la transición a la imagen Node con drenaje ya construida y concretar la
  comprobación de escritores externos/custodia para la topología real; no está
  desplegada en el origen observado históricamente.
- Revisar aplicabilidad del candidato y las configuraciones privadas ya
  materializados; el destino final de producción sigue separado de los ensayos.
- Cobertura/custodia concreta de clientes y escritores; copias de pendientes,
  disco físicamente independiente, staging cifrado, clave separada y fuente
  protegida de decisiones posteriores por acceso.
- Ventana America/Santiago, pausa ensayada, máximo aprobado, reserva de recuperación
  y condiciones de aborto; permisos de las acciones seleccionadas.

HEAD excluye cambios locales. La prueba images/reproducibility toma HEAD: no
acredita ediciones sin commit. Verificar CI aplicable al candidato exacto; si exige
publicar cambios, continúa bloqueada bajo no commit/push. No crear otra CI ni
atribuirle resultados locales como sustitución implícita.

El paquete privado `runs/s11-attempt-a/P2-review.md` y `P2.request.json` concreta
esta revisión. `candidate/release.json` identifica siete imágenes Linux/amd64
(Node más los seis roles de plataforma), head `p004_audit` e identidad completa
de la copia de fuentes usada para construirlas. `source-manifest.json` y hashes
de evidencia conservan procedencia; no se capturó `.env` ni datos de aplicación.
Importación y staging usan Compose standalone sin puertos y con redes internas,
resueltos offline; la API de staging solo se prevé creada/detenida. Restore mantiene
la plantilla congelada y rechaza resolver mientras falten disco/identity. ADMIN_UIDS,
clave/disco/cifrado, clientes/custodia y ventana siguen sin seleccionar; bundle,
incidente y prueba cliente se producirán durante la operación autorizada.
La validación es documental: imágenes/configs preparados no conceden P2/Q1/P3,
no acreditan CI/paridad del candidato ni reservan proyectos/volúmenes.

## 2. Permisos y decisiones antes de recolectar

Cada autorización identifica recurso/ruta, comando/método, responsable, efectos,
destino privado, fecha/duración y aborto en collectionActions. Preparar documentos
no concede operación. El operador puede entregar evidencia saneada sin dar claves
ni acceso global al agente.

| Permiso | Alcance | Referencia del runbook / estado |
| --- | --- | --- |
| P1 | Metadatos/observación pasiva concretos | A1; alcance previo parcial. Sin export, sync, refresh, lectura de secretos o elevación implícita |
| Preparación de candidato | Selección y checks faltantes en recursos propios aislados | A2; CI remota necesita permiso específico. Sin commit/push |
| P2 | Copias de clientes/config, pausa/captura/reanudación Node y ensayo aislado | A3–A5; pendiente. A4 bloqueado hasta resolver drenaje, custodia, almacenamiento y ventana |
| Q1 | Revisión por cuenta/credencial; nueva vía privada cuando proceda | A6; condicional y pendiente. Accesos dudosos, cuentas eliminadas/disabled o sin identidad suficiente siguen bloqueados; sin elevar roles |
| Revisión de evidencia | Preparar/leer paquete saneado y aceptar su suficiencia | A7; lectura privada ya autorizada, aceptación operativa pendiente |
| P3 | Corte final, autoridad única y recuperación sobre candidato/ventana exactos | Separado y pendiente; solo después de aceptar G0/G1/GP/GO |
| Limpieza | Solo recursos/rutas propias revisadas después de preservar evidencia | A8 para temporales; permiso de retirada distinto para 11.3. Sin borrar originales, parciales inciertos o material ajeno |

Jobs, proveedores/dispositivos reales, publicación, sync/archive y Recovery no se
incluyen por omisión. No ejecutar automáticamente los comandos de este documento.

## 3. Campos a rellenar en el inventario privado

Las listas vacías significan **no recolectado**, no cero recursos. Registrar fecha,
responsable, cobertura e incertidumbres; una incógnita va en unresolvedItems.

| Campo | Columnas mínimas de cada entrada futura |
| --- | --- |
| collectionActions | Acción/recurso/método exactos, efectos posibles, permiso, observación esperada, límite/aborto y salida privada |
| clients | ID saneado, dispositivo/navegador/perfil, cuenta o invitado, origen, build, última comprobación |
| origins | ID, URL/hostname privado, RP ID, API actual y prefijo candidato, clientes cubiertos |
| accountsAndGuestProfiles | ID privado, clientes vinculados, estado y cobertura de identidad; sin credenciales |
| pendingActiveAndMedia | Cliente, activo/dirty/offline, cola/medios, copia comprobada, riesgo de reconciliación |
| writers | Servicio/proceso/job, datos que escribe, responsable y mecanismo autorizado de parada/reanudación |
| storageDevices | Rol instancia/backup, identidad física privada, rutas, capacidad/espacio, permisos y comprobación de independencia |
| backupPoints | Captura de origen y fecha de corte de datos, importación, snapshot/bundle, alcance SQL/archivos/config/secretos, verificación/restore, edad y hashes; sin clave |
| keyCustodyReferences | Propósito, referencia privada, custodio, separación y prueba de disponibilidad; nunca el valor |
| laterAccessEvidence | Cuenta/credencial, snapshot, fuente posterior, cobertura/fecha, decisión y comprobación aislada |
| protectedRecoveryMaterial | Origen/release/config/secretos, referencia privada, custodio, integridad y plazo mínimo de conservación |
| cleanupCandidates | Ruta exacta/recurso propio, consumidores, retirar/conservar/protegido, cobertura sustituta y permiso |
| evidenceReferences | Gate/check/EV, comando, fecha, revisión/digest/plataforma, alcance, resultado/skips, artefacto/hash y límites |

Completar operator/reviewer/privateWorkspace/candidate, referencias de permisos y
maintenanceWindow solo cuando se seleccionen y autoricen. La ventana necesita
duración ensayada, duración aprobada, zona horaria, fecha y condiciones de aborto.
No introducir secretos en observaciones ni en evidencia saneada.

Las evidencias históricas conservan identidad y fecha originales. La revisión de
aplicabilidad al candidato es una entrada adicional, no reescritura de esa identidad.
Cada check debe identificar qué instancia/cliente/copia y momento cubre. Una prueba
sin binding suficiente no se recupera rellenando la revisión candidata a posteriori.

## 4. Matriz operativa previa al corte

Se conservan los veinte identificadores del inspector existente. Las suites/casos
se resuelven en [platform-suites.json](../../../backend/platform-suites.json).
Una fila indica evidencia y permiso mínimo; no autoriza su recolección.

| Check | Recolección/observación exigida | Reutilización técnica inicial | Permiso mínimo futuro |
| --- | --- | --- | --- |
| G0 clients_origins | Cobertura por cliente/perfil/cuenta/invitado, hostname/RP ID y origen | Ningún fixture demuestra el inventario real | P1 |
| G0 client_pending_active_media | Estado activo/offline/dirty y medios observables pasivamente; comprobar copias locales en los ensayos operativos autorizados | training_browser/offline_sync prueba semántica, no esos clientes | P1 pasivo; P2 antes de export/copia/sync |
| G0 frontend_api_mapping | Build identificable y correspondencia API/prefijo/origen/RP ID | contracts/python_routes y training_browser | P1 |
| G0 physical_backup_keys | Identidad física distinta de disco de instancia, capacidad/permisos, copia verificable y clave separada | backup/verified_bundle y restore/isolated_target no prueban discos físicos | P1; P2 para uso de clave/copia/restore |
| G0 protected_later_access_source | Fuente posterior por acceso, cobertura, decisión y resultado; duda mantiene credencial bloqueada | restore/reviewed_access; audit best effort no prueba vigencia | P1 y P2/Q1 si hay ensayo de acceso |
| G0 rehearsed_window | Runbook definido antes del ensayo, tiempo completo representativo, aborto, responsables y ventana acordada | backup y restore/full_timing aportan método, no duración real | P2 para ensayo y aprobación de ventana |
| G1 target_environment | Host/plataforma/Docker/Compose/almacenamiento/configuración compatibles | images/isolation y reproducibility; falta binding objetivo | P1/P2 |
| G1 pool_lifecycle | Arranque/cierre, caída/reconexión y pool con PG descartable del candidato | database/pool y lifecycle/readiness | P2 para recursos aislados |
| G1 roles_rls_transactions | Catálogo/roles/FORCE RLS y aislamiento observados independientemente | identity_session/restricted_pool y actor | P2 |
| G1 migrations_lock_interrupt | Vacío/revisión anterior, lock, fallo/interrupción y head sin avance incorrecto | schema/history_lock | P2 |
| G1 backup_restore | Captura representativa y observación SQL/secuencias/archivos/accesos | gates/node_capture, node_capture_import y node_capture_recovery; fuentes S10 para negativos de backup/restore | P2; Q1 si aplica |
| GP capability_parity_q6 | Matriz completa vigente contra referencia independiente; diferencias/Q6 explícitas | S2–S8 y contracts; revisar fuentes y casos de cada capacidad | P2; permisos externos solo si el alcance los requiere |
| GP frontend_offline_sync | Frontend real y observador PG; pendientes/activo/offline/401/409/respuesta perdida/linaje | training_browser/offline_sync y training_write | P2 en aislamiento; P1 para cobertura de clientes reales |
| GP security_audit | Auth, roles, revocación, disabled/deleted, audit y negativos | S2/S6, identity_session y admin_audit | P2 |
| GP module_contracts | Propiedad, seams, transacción compartida, imports/generadores y JS neutral | S8 y revisión EV-09; revisar el candidato | Revisión de repo; P2 para nuevas ejecuciones |
| GO clean_checkout_images_ci | Contenido exacto, clean checkout, builds/cache/CI y digests | images/reproducibility y checks/toolchain; CI remota no acreditada | Ejecución aislada; CI remota solo con alcance autorizado |
| GO runtime_environments | Separación dev/ops/test, redes, secretos por fichero y runtime restringido | images/isolation | P1/P2 |
| GO restore_rpo_rto | Restore completo con acceso/cliente/revisión dentro de RPO 6 h/RTO 24 h | restore/full_timing; no extrapolar sus milisegundos a datos reales | P2 y Q1 si aplica |
| GO diagnostics_privacy_retention | Salud/correlación/fallos DB-sink, privacidad y retención de todas las copias | diagnostics, fuentes de 9.2–9.4; falta seleccionar artefactos aplicables | P2; P1 para configuración objetivo |
| GO forward_repair_new_writes | W1/W2 conservadas bajo fallos y W3 posterior en destino superviviente | repair/acknowledged_writes | P2 en target aislado |

La procedencia histórica no se reetiqueta con la identidad del candidato. Conservar
la decisión de aplicabilidad separada. Dispositivos/proveedores necesarios según
el inventario requieren evidencia específica o excepción explícita, sin inventar
cobertura. No pedir credenciales reales para garantías ya probadas con fixtures.

### Cadena de origen Node a ensayo Python

El runbook privado contiene la secuencia operativa y sus guards; aquí se conserva
el contrato técnico del procedimiento ya ensayado.

### Procedimiento ensayado de captura Node detenida

`captureStoppedNode` de [platform-node-capture.mjs](../../../scripts/platform-node-capture.mjs)
solo copia fuentes ya detenidas; el caller posee admisión, drenaje, cese/custodia,
aborto y recuperación explícita. No existe `operate node-capture`.
El adaptador [drainAndCaptureNode](../../../scripts/platform-node-drain.mjs) ya
conecta ese capturador con Docker: recibe identidad exacta api (id/image/startedAt/
project), sources, destination, externalWritersStopped y timeoutMs. Prevalida rutas
y /data, comprueba custodia y montajes RW ajenos, envía SIGTERM y exige salida 0,
PID 0 y prueba NODE_DRAINED fresca; revalida identidad/cese/custodia/plazo durante
la copia. No reinicia, importa ni autoriza corte. La comprobación externa debe
observar escritores conocidos bajo custodia, nunca devolver true sin prueba.
El ensayo `node --test scripts/platform-node-drain-docker.test.mjs` usa esos
controles con Docker real y el harness existente: red interna sin puertos, datos
propios y descubrimiento filtrado por etiqueta del proyecto; antes de inspeccionar,
señalar o leer logs exige IDs propios. Verifica escritura HTTP admitida, bloqueos
por escritores host/RW o imagen ajena, salida 0 sin prueba y lector RO/sentinel
intactos. Evidencia en `.scratch/s11-node-capture/drain-real-docker-final.log` y
result.json/docker-commands.json del proyecto citado allí. No acredita instancia.
En la versión entregada, SIGTERM/SIGINT cierran admisión y scheduling; esperan
handlers, trabajos Coach/push/warmup y sus resultados antes de emitir prueba.
NODE_DRAIN_TIMEOUT_MS limita el drenaje (30 s por defecto, 50 ms–30 min); fallo o
plazo vencido sale 1 sin prueba. Evitar el SIGKILL automático de docker stop antes
del plazo: el adaptador señala y espera sin forzar ni reiniciar. Su timeout incluye
drenaje y copia, y debe respetar la ventana/reserva aprobadas. Nada está desplegado.
Exige raíces data/configuration, destino nuevo sin solapamiento, corte original y
comprobación real reiterada de escritores. Límites: 2–16 raíces, 10.000 entradas,
profundidad 32 y 4 GiB; sin enlaces/hardlinks ni archivos especiales. Verifica
identidad/hashes antes/después y relee destino; solo publica capture.json final.
Error/interrupción conserva origen y parcial privado sin promoción/reuso/limpieza.
Antes de recuperar servicios, acreditar cese de copia/controlador y fuente intacta;
reanudar únicamente los IDs antes activos. El health HTTP puede escribir y necesita
permiso. La función no acredita preservación de ACL/xattrs ni escritores arbitrarios.

### Ensayo integrado: captura Node → importación PostgreSQL

Importar solo la copia congelada RO en un PostgreSQL nuevo aislado. El importador
existente exige revisión/esquema compatibles, destino propio vacío, permisos POSIX,
CONNECT runtime revocado y ausencia de peers. Límites: 64 MiB por fichero y 512 MiB
por origen. Verificar IDs/documentos/revisiones/tipos/medios/secretos y cuarentena;
no normalizar discrepancias ni reutilizar parciales. Los materiales cliente y de
proveedores diferidos permanecen protegidos fuera de la autoridad activa.

### Ensayo integrado hasta backup cifrado y restore aislado

El wrapper de backup Python se aplica al staging Python importado, nunca al Node
origen. Cifrar/verificar en disco independiente con clave separada; restaurar en
otro target nuevo sin tráfico/egress, revisar Q1 y comprobar cliente/persistencia.
El coordinador restore-rehearse ya realiza restore: no ejecutarlo dos veces sobre
el mismo target. Conservar tiempos originales Node/captura/import/snapshot/incidente/
cierre; RPO efectivo ≤6 h y RTO completo ≤24 h incluyen revisión y cliente.
Un snapshot Python reciente no rejuvenece el corte Node. No extrapolar tiempos
sintéticos a la ventana real. Recuperar Node después del ensayo permite nuevas
escrituras: antes de P3 se requiere revalidación y captura final coherente.

## 5. Fuentes sintéticas existentes, sin duplicar archivos

Rutas relativas al repo; PASS histórico no es reejecución actual ni aceptación.
Los marcadores PLATFORM_CASE_OK necesitan sus detalles/observadores antes de
considerarse evidencia suficiente. Conservar archivos, identidad y hashes originales.

| Fuente conservada | Resultado leído / garantía candidata | Pendiente para reutilizar |
| --- | --- | --- |
| `.scratch/capture-blocks-quiescence-green.log` | Marcador backup/capture_quiescence | Revisar detalle de probes/desaparición y binding; no prueba escritores host arbitrarios |
| `.scratch/capture-blocks-maintenance-final.log` | 9/9 sin skips: captura/recuperación host sintéticas | Revisar cobertura/observer y recursos/versión |
| `.scratch/capture-blocks-repair-final.log` | Marcador repair/acknowledged_writes | Vincular detalle W1/W2/W3 y alcance destino superviviente |
| `.scratch/capture-blocks-bundle-final.log` | Marcador backup/verified_bundle | Vincular verificación EOF/independiente; no disco físico |
| `.scratch/capture-blocks-restore.log` | Marcador restore/isolated_target | Vincular detalle SQL/roles/archivos; no acceso real |
| `.scratch/capture-blocks-images.log` | Marcador images/isolation | Vincular inventario de imágenes/revisión y plataforma |
| `.scratch/capture-blocks-checks-final.log` | 12 pytest PASS y marcador checks/toolchain | Comprobar revisión/locks y cambios posteriores |
| `.scratch/capture-blocks-lifecycle-final.log` | 19 pytest PASS y marcador lifecycle/readiness | Comprobar revisión/imagen y entorno objetivo |
| `.scratch/restore-10-7/full-timing-final-verified.log` | Marcador restore/full_timing | Usar detalle/revisión/cliente del directorio, sin extrapolar RPO/RTO |
| `.scratch/restore-10-5/access-detail-final.log` | Resumen sin fallos/skips de acceso sintético | Revisar cobertura y binding de revisión por cuenta/target |
| `.scratch/platform-10-9/accepted-scheduling.log` | Marcador backup/scheduling_and_age | No acredita jobs instalados ni calendario real |
| `.scratch/backup-10-8/import.log` | 29 pytest PASS y marcador import/faithful_or_blocked | Revisar candidate/detalle y datos representativos antes del corte |
| `.scratch/s11-node-capture/public-final.log` | Captura sintética: 7/7 sin skips y marcador público | Detalle/negativos en el mismo directorio; no acredita drenaje operativo |
| `.scratch/s11-node-import/public-final.log` | Cadena Node→PG; import-regression.log registra 29 pytest PASS | Vincular productor/receptor y candidato |
| `.scratch/s11-node-recovery/public-final.log` | Cadena completa; result.json/lineage.json bajo el directorio de ejecución; restore-regression.log conserva regresión | No acredita disco, clientes o aceptación reales |
| `.scratch/s11-authorized-cutover/verification.txt` | Inspector y regresión runner/verificador/layout: 18/18 sin skips | Estructura únicamente, no permiso ni ejecución del corte |

Las notas S2–S10 en tasks.md conservan las pruebas de capacidades y recuperación.
La evidencia pasiva y sus correcciones están en el inventario privado. No duplicar
logs/dumps en documentación ni borrar intentos/originales como parte de esta
simplificación. Si cambia el candidato, revisar únicamente la cobertura afectada.

## 6. Paquete de evidencia y decisión humana

Usar los formatos entregados de [pre_cutover](execution-plan.md#delivered-pre-cutover-evidence-validator-synthetic-preparation)
y [authorized_cutover](execution-plan.md#delivered-authorized-cutover-evidence-validator).
El inventario vacío no es un índice válido. En custodia privada, conservar originales
y preparar artefactos saneados con hashes, manifiesto completo, procedencia/
aplicabilidad, cobertura EV y cronología de recuperación; nunca datos ni secretos.

Los comandos `node scripts/platform.mjs verify gates --case pre_cutover --evidence <index.json>`
y `node scripts/platform.mjs verify gates --case authorized_cutover --evidence <index.json>`
solo inspeccionan el paquete seleccionado. Sin --evidence ejecutan fixtures.
Exit 0 prueba estructura; siempre manualReviewRequired=true, realGateCompleted=false
y cutoverAuthorized=false. No autentican permisos ni aceptan operación.

El operador acepta la suficiencia de G0/G1/GP/GO antes de P3 y revalida cambios de
candidato/clientes/orígenes/config/seguridad/edad de backups antes del corte. La
revisión no reabre 11.1. No autorizar la operación con checks fallidos/skips,
escrituras requeridas sin preservar o recursos/ventana pendientes.

## 7. Fases posteriores, todavía bloqueadas

El orden y los checkboxes viven en tasks.md. No se exige implementar nuevos casos
cleanup/protected_sentinel, parity/post_retirement o gates/acceptance. Los checks
existentes siguientes y la revisión del cambio aportan la prueba; siguen pendientes
hasta ejecutarse sobre la retirada real, sin rebajar sus requisitos conductuales.

### Checks existentes para retirada y cierre

| Tarea / garantía | Check reutilizado y resultado exigido |
| --- | --- |
| 11.2 corte | pre_cutover y authorized_cutover con índices privados, más autorización y revisión humanas de ejecución/autoridad única. Conservar origen/release/config/secretos ≥30 días desde corte aceptado, sin borrado automático. Antes de nuevas escrituras, reversión validada; después, Q2 preservándolas, sin vuelta a Node congelado ni exportador inverso |
| 11.3 consumidores y protección | Inventario de rutas/consumidores y diff; `rg` para localizarlos, no como prueba suficiente. `node scripts/platform.mjs verify harness` cubre ownership/sentinels de su harness; el ensayo de la retirada concreta además debe demostrar hashes intactos del sentinel ajeno y material protegido, eliminando solo rutas propias autorizadas. Si falta esa prueba, registrar el hueco, sin crear otro verificador general |
| 11.3 negativos | En checkout desechable, introducir un consumidor de una ruta retirada, observar que su test/build dependiente falla y revertir la inyección antes del GREEN. Migrar loaders/COPY/filtros/runners/CI y cobertura pytest/Vitest antes de eliminar contratos; sin trasladar dumps completos ni derivar expectativas del código probado |
| 11.4 backend/seguridad | Suites pytest actuales invocadas con `node scripts/platform.mjs verify <suite>`: database, schema, lifecycle, identity_*, training_*, media, media_gc, coach_*, admin_*, notifications y checks, usando los nombres exactos registrados. Reutilizar comandos de la CI adaptada en 11.3; ninguna suite puede seguir necesitando la implementación o contratos retirados |
| 11.4 frontend/browser/builds | `pnpm --dir frontend test`, `node scripts/platform.mjs verify training_browser --case offline_sync`, `node scripts/platform.mjs verify shared_client --case formats_and_bundles` y `node scripts/platform.mjs verify images --case reproducibility`. Migrar previamente sus dependencias transitorias y conservar builds web/mobile/generadores, prefijo /api/v1 y observación PG independiente |
| 11.4 operación | `node scripts/platform.mjs verify restore --case full_timing`, `node scripts/platform.mjs verify diagnostics` e imágenes/aislamiento. Pruebas sobre checkout limpio del contenido retirado; conservar procedencia y cero skips/fallos no resueltos |
| 11.5 aceptación | Revisar una sola vez el paquete de 11.2 y resultados de 11.3–11.4, EV-01–EV-09 y G2/G3/GO; actualizar guías al runtime entregado y registrar aceptación atribuida/fechada. Sin nuevo CLI, otro reporte permanente ni autorización implícita de Recovery/sync/archive |

Las suites indicadas deben adaptarse en la retirada si aún consumen Node/contracts;
que hoy pasen antes de retirar no satisface 11.4. Reutilizar los mismos resultados
finales entre tareas, sin reejecutar ni duplicar informes salvo cambios/fallos que
invaliden la prueba. No se autoriza ejecutar esta tabla durante la simplificación.
