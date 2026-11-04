# Recolección de evidencia S11

Estado: preparación documental y verificación del CLI con fixtures sintéticas
autorizadas; ninguna inspección u operación real autorizada/ejecutada por este
documento. El inventario está vacío y 11.1 pendiente.
Este plan es propietario del procedimiento de recolección; [tasks.md](tasks.md) mantiene
exclusivamente el progreso. No ejecutar automáticamente los comandos citados.

## 1. Preparación que no toca la instancia

Revisar referencias sintéticas existentes, decidir qué garantías cubren y preparar
los campos/permisos. La revisión documental actual localizó los doce logs citados
abajo y leyó sus marcadores/resúmenes; no reejecutó suites, no certificó toda su
procedencia ni comprobó aplicabilidad al candidato. El verificador pre_cutover
cuenta con regresión CLI/layout de 15/15 sin skips y runner público sintético,
según las notas y logs de continuación de 11.1 de este cambio. Esto no vuelve
vigentes los doce logs históricos ni acredita su aplicación a una instancia real.

No rellenar datos reales en Git. El operador debe seleccionar y autorizar un
workspace privado para copiar [inventory.template.json](inventory.template.json).
El archivo versionado permanece vacío. Antes de atribuir pruebas a una release,
fijar contenido/revisión/digests de imágenes y plataforma; HEAD por sí solo no
incluye los cambios sin commit actuales. Esta selección no autoriza commit/push.

El manifiesto de release debe enumerar web/API/PG/migrate/ops/colector y herramientas
usadas: servicio/target, ID inmutable, plataforma, revisión o identidad de fuentes
y locks; registrar también head SQL. `candidate.digest` y el digest del índice son
de la API, no de todas las imágenes. Adjuntar el manifiesto completo con hash al
paquete como `releaseManifest`; el verificador exige los seis roles base, bindings,
head declarado e identidad del contenido, sin inspeccionar imágenes o Git.
`candidate.images` no puede quedar vacío al aceptar 11.1. Si las pruebas
de checkout limpio toman HEAD y excluyen cambios locales, no acreditan esos cambios.

### Secuencia de 11.1 y límites de los pasos posteriores

1. Seleccionar instancia, operador/revisor y custodia privada; obtener P1 concreto antes de inspeccionar.
2. Fijar candidato/manifiesto y revisar procedencia/aplicabilidad sintética; redactar acciones y runbooks, sin ejecutar pruebas en esta revisión documental.
3. Inspeccionar pasivamente bajo P1 y registrar incertidumbres; no crear copias ni activar sync.
4. Obtener P2 y Q1 cuando corresponda; ensayar primero captura Node coherente con fixtures, después capturar/importar en PG nuevo aislado y verificar copias, G1/GP/GO, recuperación, RPO/RTO y ventana.
5. Consolidar evidencia y revisión humana de 11.1; la validación estructural no autoriza 11.2.

11.2 revalida ese mismo runbook y evidencia antes de solicitar P3 y ejecutar el corte.
11.3 revisa rutas/consumidores y migra cobertura antes de la retirada expresamente
autorizada. 11.4 verifica el árbol resultante; 11.5 registra aceptación y guías.
Estas fases tienen como único seguimiento los cinco puntos de tasks.md.

## 2. Permisos y decisiones antes de recolectar

Cada autorización futura debe identificar responsable, instancia, recursos/rutas
exactos, acciones, efectos permitidos, destino privado, duración y exclusiones.
Conservar su referencia y decisión humana; la mera existencia de un fichero de
autorización no demuestra que el permiso fue otorgado.

| Fase | Autoriza, solo si se concede expresamente | Estado actual |
| --- | --- | --- |
| P0 | Mantener plan, inventario vacío y referencias; implementar/verificar el CLI con fixtures sintéticas sin instancia | Concedido por las solicitudes de preparación y continuación sintética |
| P1 | Inspeccionar los clientes/orígenes y metadatos/configuración/rutas seleccionados; exportar evidencia saneada | Pendiente; instancia, responsables y rutas sin seleccionar |
| P2 | Crear recursos aislados, usar material privado, capturar/copiar datos, pausar/reanudar escritores y ensayar recuperación en ventana concreta | Pendiente; no se deriva de P1 |
| Q1 | Revisar identidad/cobertura y, si procede, entregar vía nueva privada por cuenta/target de restore | Pendiente y condicional; aplicar el contrato existente de 10.5 |
| P3 | Ejecutar 11.2 sobre instancia/release/ventana/recovery revisados | Pendiente; se solicita después de aceptar 11.1 |
| Retirada | Modificar/eliminar únicamente las rutas obsoletas y consumidores revisados en 11.3 | Pendiente; no se infiere de P3 ni permite borrar originales protegidos |

La preparación documental redacta acciones/runbooks sin ejecutar pruebas; la inspección de 11.1 limita P1 a observación
pasiva sobre recursos autorizados, con salida al workspace privado permitido.
P1 no habilita abrir una vista o realizar una petición que pueda activar sync,
heartbeat, refresh, VAPID u otra escritura/efecto externo. Tampoco habilita leer
valores de secretos: registrar solo referencias/metadatos autorizados. Si no existe
una vía pasiva fiable, dejar el check pendiente y pedir P2 sobre esa acción exacta.
Crear/verificar un export o copia local, cambiar conectividad, pausar o arrancar
servicios y ejecutar pruebas faltantes ocurre únicamente en los ensayos autorizados de 11.1 tras P2/Q1.

Antes de conceder P1/P2, revisar `collectionActions`: acción, recurso exacto,
método/comando, lector/escritor, efectos posibles, permiso requerido, resultado
esperado, límite/aborto y salida privada. Incluir en P2 el cese/verificación y
limpieza de recursos sintéticos propios; conservar evidencia y parciales inciertos.
No basta conceder una fila de la matriz sin concretar sus recursos y efectos.

Publicación, instalación de jobs, llamadas a proveedores/dispositivos reales,
commit/push, sync/archive o borrado de originales necesitan su alcance explícito;
no se incluyen en estos permisos por omisión. Si el operador reúne las pruebas
personalmente, puede entregar solo sus resultados saneados y referencias privadas;
el agente no necesita recibir claves o acceso global para revisar el paquete.

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

## 4. Matriz de recolección previa a 11.1

Los identificadores siguientes son exactamente los del verificador entregado.
Los comandos sintéticos se resuelven con `node scripts/platform.mjs verify <suite>`
y, cuando corresponde, `--case <case>` según backend/platform-suites.json. La
solicitud de continuación autoriza fixtures propias aisladas; no recolección real.
La matriz de permisos siguiente rige el trabajo con recursos/datos operativos.

| Check | Recolección/observación exigida | Reutilización técnica inicial | Permiso mínimo futuro |
| --- | --- | --- | --- |
| G0 clients_origins | Cobertura por cliente/perfil/cuenta/invitado, hostname/RP ID y origen | Ningún fixture demuestra el inventario real | P1 |
| G0 client_pending_active_media | Estado activo/offline/dirty y medios observables pasivamente; comprobar copias locales en los ensayos autorizados de 11.1 | training_browser/offline_sync prueba semántica, no esos clientes | P1 pasivo; P2 antes de export/copia/sync |
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

P1/P2 son permisos para acciones concretas, no autorización indiscriminada por
fila. Las pruebas sintéticas pueden reutilizarse solo tras revisar su procedencia,
alcance y compatibilidad. No pedir credenciales reales para un check que se prueba
con fixture. Para autenticadores/dispositivos/proveedores que el inventario declare
necesarios, resolver su evidencia específica o una excepción explícita antes del gate.

### Cadena de origen Node a ensayo Python

El origen Node/JSON exige un runbook de captura coherente propio: seleccionar
archivos y configuración/secretos necesarios, identificar todos sus escritores,
detenerlos bajo permiso, verificar cese, copiar/contrastar integridad y reanudar
solo servicios antes activos. Definir de antemano fallo/interrupción, protección
de parciales y comprobación de recuperación. La guía de backups Node orienta
sobre archivos; no acredita por sí misma esa coherencia ni la captura de clientes.
El procedimiento siguiente se ensaya con fixtures; su adaptación a servicios,
escritores, permisos y ventana concretos sigue pendiente antes de usar datos reales.

#### Procedimiento ensayado de captura Node detenida

`node scripts/platform.mjs verify gates --case node_capture` ejecuta el ensayo en
la imagen de contratos existente, con dependencias fijadas, red interna sin puertos
publicados y almacenamiento temporal propio. No recibe rutas ni configuración de
instancia. El ensayo usa la API Node real, peticiones HTTP locales, medios sintéticos,
un escritor auxiliar y un proceso ajeno propio que debe permanecer intacto. Los
exports cliente son archivos sintéticos declarados: no se acredita exportación de
un navegador real ni descubrimiento de su estado offline.

1. **Preparar antes de pausar.** Seleccionar fuentes explícitas y no solapadas:
   `data` contiene el DATA_DIR completo, incluidos db/backup, estados, medios,
   marcas GC, temporales, audit, Coach y secretos existentes; `configuration`
   conserva configuración y referencias de release/imagen. Añadir separadamente
   exports cliente comprobados y material de acceso externo solo si corresponde
   y está autorizado. No explorar ni copiar automáticamente `coach-auth`; el
   material Q6 diferido se conserva protegido, no se instala en el destino activo.
   Definir custodio, mecanismo de exclusión, almacenamiento privado cifrado,
   espacio, permisos/ACL, recuperación y todos los escritores/descendientes/jobs.
2. **Cerrar entrada y drenar.** Impedir tráfico nuevo/reconexión de clientes y
   esperar confirmaciones pendientes, uploads y trabajos; conservar exports locales
   sin forzar sync. Node no implementa un manejador de apagado que garantice drenaje:
   SIGTERM por sí solo no lo demuestra. Incertidumbre sobre peticiones/jobs o un
   descendiente externo mantiene el corte bloqueado. El fixture espera todas sus
   respuestas HTTP antes de parar; no acredita un drenador de producción.
3. **Detener y comprobar.** Registrar qué servicios estaban activos. Detener solo
   los escritores seleccionados y observar su cese mediante identidad/supervisor,
   no solo PID, señal enviada o puerto cerrado. En el ensayo se espera `close` de
   cada ChildProcess propio. API detenida con escritor auxiliar vivo debe rechazar
   captura. Mantener custodia/exclusión durante inventario, copia y comprobación.
4. **Capturar a destino nuevo.** `captureStoppedNode` de
   [platform-node-capture.mjs](../../../scripts/platform-node-capture.mjs) recibe
   fuentes explícitas, destino absoluto nuevo, `sourceCutoffAt` original y una
   comprobación `writersStopped` que debe devolver exactamente true; error/duda
   aborta. La función solo copia: no detiene/arranca procesos, instala jobs ni tiene
   subcomando `operate`. No interpreta `.env` ni ejecuta comandos de configuración.
   No usar una comprobación constante como prueba operativa. Límites de esta entrega:
   2–16 fuentes, 10 000 entradas, profundidad 32 y 4 GiB totales; revisar suficiencia
   para el inventario real antes de autorizar. Rechaza solapamientos, rutas relativas,
   destinos existentes, enlaces/hardlinks y archivos especiales. Exige db.json,
   secret y configuración; conserva todos los demás archivos seleccionados sin
   normalizar ni descartar temporales. Buffers de 64 KiB, destino 0700/archivos 0600,
   fsync de archivos y sincronización de directorios según soporte del sistema.
5. **Verificar antes de acreditar.** Inventariar/hash antes, comparar identidad y
   hashes del origen después, releer íntegramente el destino y comparar archivos y
   directorios; comprobar de nuevo cese de escritores. Solo entonces publicar
   `capture.json`, con inventario/tamaños/SHA-256 y tiempos, sin autorización de
   importación ni aceptación. El corte de datos es el original aportado, no la hora
   de copiar: una fuente congelada antigua no se rejuvenece. `writersStoppedAt` y
   `capturedAt` son observaciones de este ensayo; no prueban frescura de los exports.
   Otro observador comprueba bytes, referencias Training/medios y material protegido.
6. **Fallo o interrupción.** Conservar origen y parcial privado sin reutilizar,
   promover ni limpiar automáticamente. Muerte real del controlador se ensaya con
   SIGKILL: deja servicios detenidos y destino sin recibo de éxito. Un archivo o
   recibo aislado no resuelve una finalización incierta; verificar procedencia,
   inventario y observaciones antes de cualquier uso. No existe auto-resume ni
   recuperación por TTL; operación incierta requiere decisión explícita.
7. **Recuperar únicamente el origen.** Una vez comprobado el cese del capturador,
   que el origen está intacto y que release/configuración siguen compatibles,
   reanudar solo servicios antes activos bajo la autorización correspondiente.
   Verificar HTTP y estado reconocido antes de abrir entrada. No arrancar Node
   sobre la copia congelada ni servicios inicialmente detenidos/ajenos. Un fallo
   de recuperación mantiene entrada cerrada y escala al operador. Conservar la
   copia protegida; una importación futura monta únicamente su `data/` como origen
   del importador existente, sobre PG nuevo aislado y bajo permiso separado.

La comprobación de cese es una frontera de confianza del llamador, no un detector
universal de escritores. El ensayo detecta cambios persistentes y corrupción, pero
no excluye procesos host arbitrarios, escritores transitorios ni una declaración
falsa de custodia/corte de datos. No preserva ACL/xattrs/streams alternativos ni
acredita cifrado físico, power loss, RPO/RTO reales, importación o restore. Los
archivos/secretos de fixtures se eliminan solo dentro de sus temporales propios;
los logs saneados quedan aparte. Adaptador operativo de parada/drenaje, selección
real y recuperación incierta siguen sujetos al inventario y permisos concretos.

#### Ensayo integrado captura Node → importación PostgreSQL

`node scripts/platform.mjs verify gates --case node_capture_import` une la fase
anterior con el importador ya entregado, sin nuevo comando operativo ni cambios de
esquema. El harness crea un proyecto/volumen exclusivamente sintéticos y construye
las imágenes fijadas de contratos y tests. El productor Node registra dos cuentas,
confirma Training y medios por HTTP, espera sus respuestas, detiene su API y captura
origen/configuración, export cliente simulado y acceso diferido protegido. Conserva
también el origen original para observar que la importación no lo cambie.

El productor termina antes de abrir un PostgreSQL nuevo. El receptor Python monta
el volumen de captura **solo lectura**, hace bootstrap/migración con las fixtures
existentes y ejecuta el CLI import sobre `capture/data/`, nunca sobre el origen
activo ni sobre la carpeta contenedora con configuración/tokens/exports. El recibo
`import.json` y un observador SQL/archivos independiente contrastan IDs, nombres,
hashes de contraseña, documentos completos/revisiones y bytes de medios/secretos.
El fingerprint de origen coincide con el recibo, el corte Node original se conserva
separado y los exports locales/material diferido permanecen protegidos fuera del
destino activo. No se importa el estado local dirty como si fuera Training confirmado.

En éxito se exige `IMPORT_OK`, destino en cuarentena y CONNECT runtime denegado,
incluido un intento real de conexión; no se inicia API Python ni se concede acceso.
Repetir sobre destino ocupado debe bloquear sin alterar documentos/archivos. Una
segunda captura de JSON deliberadamente duplicado debe bloquear sin crear destino
ni alterar tablas/secuencias. Ambos casos verifican por hashes que origen, capturas,
configuración, export simulado y material protegido no cambian. El receptor se
invoca explícitamente como `tests/platform/node_capture_import.py` porque necesita
ese volumen; no añade una dependencia externa al descubrimiento pytest por defecto.

No hay puertos publicados, montajes host/datos reales, credenciales reales, egress
de runtime ni dependencia de la instancia existente. El harness exige pruebas
ejecutadas sin omisiones y limpia solo contenedores/imágenes/red/volúmenes propios;
los logs saneados quedan en `.scratch/s11-node-import/`. Este ensayo no demuestra
backup/restore/RPO/RTO, todos los clientes o capacidades, autenticadores físicos,
aceptación ni permiso de corte; 11.1 y los gates operativos permanecen pendientes.

#### Ensayo integrado hasta backup cifrado y restore aislado

`node scripts/platform.mjs verify gates --case node_capture_recovery` reutiliza el
productor Node y los proofs de backup/restore S10. La captura congelada se importa
mediante el CLI existente en PG nuevo. En Windows el destino inicial del importador
es un directorio POSIX privado del contenedor; solo tras IMPORT_OK se exporta el
resultado verificado al temporal privado del fixture. No se relajan las comprobaciones
de ownership/permisos del importador para admitir un bind Windows.

Solo dentro del fixture, el origen Python importado obtiene acceso temporal y una
API privada para ensayar el wrapper host real: parada/comprobación de escritores,
captura coherente SQL/archivos y recuperación de servicios antes activos. No se
construye manualmente un journal para simular esa captura. El wrapper publica y
relee/verifica el bundle age completo con clave sintética separada de sus fuentes.
La selección de configuración incluye la procedencia Node: corte original,
captura/importación, fingerprints e imágenes identificadas, además del recibo y
release del origen. No usar la fecha más reciente de PG para rejuvenecer los datos.

El restore existente prepara otro proyecto/cluster/volumen, roles y credenciales
nuevos, sin puertos publicados ni egress. Un observador independiente compara todas
las tablas/digests/secuencias, catálogo/ACL/FORCE RLS, documentos por los IDs Node
originales, bytes de medios, secretos de sesión/Coach y configuración de procedencia.
La clave age no se incluye en el material restaurado. El ensayo privado RLS abre
CONNECT temporalmente solo para comprobar el rol restringido A/B y lo revoca al
cerrar; no inicia API restaurada ni admite tráfico. El destino final conserva gate
cerrado, acceso en cuarentena y Q1 pendiente.

Se conserva la matriz S10 de claves incorrectas, truncamiento/checksums, cobertura,
rutas/enlaces, compatibilidad, targets ajenos/expuestos/ocupados, disco lleno real
acotado e interrupción de decrypt. Fallos no promueven parciales ni autorizan reuso.
Origen Node, exports simulados, material protegido, origen PG y bundle deben seguir
intactos. Se usan únicamente binds a temporales privados propios y volúmenes de
fixtures; se limpian los recursos propios y se conservan logs saneados en
`.scratch/s11-node-recovery/`. La preparación ACL del fixture Windows modifica solo
la DACL y verifica propietario/protección, sin requerir cambios de propietario o
auditoría ni desactivar controles operativos.

Esto acredita el recorrido sintético declarado, no backup físico independiente,
cifrado del disco, host Linux nativo, recuperación de identidad Q1, navegador real,
RPO/RTO operativos, aceptación o permiso de corte. Los exports cliente y credenciales
diferidas siguen protegidos aparte: no se convierten en datos activos por incluir
sus referencias en la procedencia. 11.1 y todos los gates operativos siguen pendientes.

No usar `operate backup` de Python para capturar Node. Con P2, importar una copia
Node congelada/protegida en un PG **nuevo** aislado según el
[contrato de importación](../../../docs/reference/platform-operations.md#importación-aislada-de-origen-node),
comparar equivalencia y preservar el origen. Solo después usar ese target Python
para captura/bundle/restore/reparación de la plataforma, en recursos distintos de
la instancia activa, sin tráfico público y con efectos externos deshabilitados.
La copia de ensayo no es el origen final congelado del corte: 11.2 debe capturar
y comparar la fuente vigente durante su propia pausa autorizada.

Conservar por separado fecha de captura/corte de datos Node, importación y snapshot
Python. Crear un dump/bundle nuevo de un PG importado no rejuvenece los datos del
origen: la medición representativa de pérdida usa la fecha de corte de datos más
antigua que limite la recuperación, no la fecha del bundle más reciente. El recibo
Python por sí solo no acredita frescura de la fuente Node ni de pendientes cliente.

## 5. Fuentes sintéticas existentes, sin duplicar archivos

Rutas relativas al repositorio. Presencia y resúmenes comprobados en esta preparación;
PASS histórico no es reejecución actual ni aceptación operativa. Los siete logs
pequeños de runner solo contienen PLATFORM_CASE_OK; vincular detalle/observador
desde las notas de tareas antes de usarlos como evidencia suficiente. No inventar
binding de revisión/digest cuando el archivo no lo contiene.

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

La fuente narrativa propietaria es [tasks del port](tasks.md):
10.2–10.10 y seguimiento capture-blocks; allí también constan intentos fallidos,
repeticiones y límites que deben conservarse. Para S2–S9 y browser, empezar en
sus Proof/Check/Notes y elegir sus artefactos; **no se ha inventariado ni revisado
todo ese material en esta preparación**. No regenerar contratos para admitir drift.

Estos temporales no son almacenamiento permanente. Antes del gate, preservar solo
evidencia necesaria saneada en el root privado autorizado, con hashes y procedencia,
sin mover ni borrar originales de otros trabajos. No copiar dumps/secretos al índice.

## 6. Paquete de evidencia y decisión humana

Usar el [formato pre_cutover existente](execution-plan.md#delivered-pre-cutover-evidence-validator-synthetic-preparation),
no el inventario vacío. Crear el índice solo tras recolectar: instance/revision/
digest/platform exactos, synthetic según el alcance real, G0/G1/GP/GO con veinte
checks, comando/resultado/skips/alcance/límites/EV/binding y referencias a artifacts/
con SHA-256, revisión y permiso de inspección. No convertir un paquete sintético
en operativo cambiando únicamente synthetic a false.

Límites: índice 1 MiB; archivos regulares sin links, hasta 4 MiB cada uno,
128 archivos/32 MiB total. La ruta artifacts/ es hermana del índice, privada y
estable bajo custodia. Reducir/sanear informes grandes sin perder garantía ni
ocultar fallos; conservar su procedencia y originales protegidos.

En fase autorizada, `node scripts/platform.mjs verify gates --case pre_cutover
--evidence <indice-privado.json>` solo inspecciona estructura/hashes. Aunque exit 0,
manualReviewRequired=true, realGateCompleted=false y cutoverAuthorized=false.
La revisión humana comprueba autenticidad, cobertura completa, aplicación al
candidato, permisos y todas las lagunas. Solo entonces puede documentarse 11.1
cumplida en tasks.md; P3 sigue pendiente. Registrar no-go si falta prueba,
hay skips/fallo o no puede preservarse una escritura requerida.

El índice debe incluir `releaseManifest`, `provenance` por check y `recovery`
según el formato enlazado. El reporte de restore es un subconjunto saneado del
reporte existente, con binding explícito; conservar procedencia y originales
privados. El CLI comprueba cronología, corte de datos original y RPO/RTO, sin
ejecutar captura/importación/restore ni certificar sus afirmaciones.

La revisión incluye manifiesto completo de imágenes y la procedencia original de
cada resultado, no solo el digest singular o las etiquetas del índice. Las EV se
referencian por garantía/fase: la evidencia previa no declara cerrada EV-07 ni
G2/G3/GO posterior, reservados a la aceptación de 11.5.

Antes de P3 y otra vez al iniciar el corte, revalidar clientes/orígenes, candidatos,
configuración, decisiones de seguridad posteriores y edad/alcance de backups.
Cambios invalidan los checks afectados y reabren la revisión humana de 11.1 antes de continuar. Medir
edad desde snapshot, no desde copia/verificación: >6 h incumple RPO; el backup
pre-corte y la ventana deben corresponder al runbook ensayado. No imponer un TTL
inventado a todos los artefactos ni dar validez indefinida al inventario.

## 7. Fases posteriores, todavía bloqueadas

11.2 requiere P3 y finalización/revalidación del procedimiento ensayado bajo 11.1.
Preservar origen/release/config/secretos ≥30 días desde corte aceptado; nunca
borrado por vencimiento. Antes de nuevas escrituras, reversión validada; después,
Q2 preservando nuevas escrituras, sin volver a Node congelado ni exportador inverso.

11.3 inventaría consumidores y retirar/conservar/protegido, migra tests nativos y
consumidores antes de eliminar backend/contracts y negocio sustituido. 11.4 repite
checkout/builds/paridad/seguridad/browser/restore/diagnóstico en el árbol retirado,
con sentinel ajeno y material protegido intactos. 11.5 consolida EV-01–EV-09 y
aceptación humana antes de Recovery. Los verificadores futuros de esas fases
deben entregarse o sustituirse por pruebas equivalentes revisadas; no se ejecutan
comandos inexistentes ni se simula su éxito con Markdown.
La equivalencia debe cubrir las observaciones conductuales y negativos exigidos
con ejecución real en el seam aplicable; no se sustituye por una aprobación manual
del texto. Antes de retirar en 11.3 hace falta permiso explícito de retirada sobre rutas exactas.
