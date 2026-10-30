---
type: Reference
title: Plataforma — autenticación, autorización y auditoría
description: Contrato objetivo de autenticación, autorización, aislamiento y auditoría de plataforma.
---
# Plataforma — autenticación, autorización y auditoría

**Estado:** contrato objetivo autorizado documentalmente el 2026-10-22; implementación y pruebas pendientes. [Arquitectura §12](../open-gym-evolution.architecture.md#12-gates-y-experimentos-antes-de-producción) gobierna los gates. [SELF_HOSTING](../SELF_HOSTING.md), [SECURITY](../../SECURITY.md) y [OpenAPI](../../api/openapi.yaml) describen el sistema actual.

Leer al modificar identidad, sesiones, permisos, consumidores o eventos de seguridad. Esta referencia define el detalle técnico objetivo; el [PRD Evolution](../open-gym-evolution.prd.md) define resultados. La migración preserva la seguridad existente; OIDC/SSO u otros proveedores de identidad son ampliaciones independientes.

## Identidad y acceso

Preservar IDs, passkeys y material WebAuthn, contadores, scrypt/NFKC, passwords opcionales, pairing/device links, cookies y bearer de clientes móviles. Caracterizar firma/encoding, expiración, revocación y límites del sistema Node con fixtures antes del port. Conservar sesiones si es seguro/compatible; reautenticación o reemparejamiento excepcional solo documentado y respaldado por pruebas, preservando pendientes locales. Seleccionar biblioteca WebAuthn compatible; evitar conversión implícita a Google/JWT/bcrypt. El [esquema aprobado](platform-schema.md#identidad-y-acceso) separa nombres visibles, alias y credenciales sin cambiar el mecanismo firmado de sesiones.

Mantener origen/RP ID y HTTPS para publicación, proxy de mismo origen y clientes/subpaths admitidos. Cambiar hostname puede exigir nuevas passkeys; localhost compatible sirve para ensayos, no acredita publicación HTTPS. El contrato CORS/bearer móvil requiere pruebas propias además del navegador. La confianza en headers de proxy se limita a la topología realmente desplegada.

## Autorización por actor y recurso

El servidor resuelve identidad y permisos en cada operación protegida; el propietario procede de esa identidad, no de un campo cliente. Denegar cuando no exista una concesión válida y conservar las rutas públicas y el uso invitado local previstos. Definir la matriz completa de recurso × acción en el cambio implementable, incluyendo lectura, creación, modificación y borrado.

| Actor | Contrato |
| --- | --- |
| Público/invitado | Rutas públicas previstas y Training local; sin acceso a datos servidor privados por conocer un ID. |
| Usuario propietario | Sus recursos según operación y estado de cuenta/sesión. |
| Otro usuario | Sin acceso a recursos ajenos, incluidos medios y operaciones por ID. |
| Administrador | Facultades actuales inventariadas y privilegios explícitos; sin acceso clínico o exportación Recovery implícitos. |
| Coach | Acceso a Training limitado al propietario autorizado; sin privilegios sobre Recovery. Conserva consentimiento y aprobación explícita de propuestas. |

Una autorización que cambió durante una espera no confirma con una sesión obsoleta: definir y probar serialización con revocación, deshabilitación y eliminación. Conservar respuestas HTTP/errores de compatibilidad; validar acceso en backend aunque la UI oculte controles.

## Roles, RLS y datos

Diseño de roles aprobado para el port, pendiente de DDL y pruebas:

| Rol | Facultades |
| --- | --- |
| `schema_owner` NOLOGIN | Posee objetos/esquemas; no atiende peticiones. ENABLE/FORCE RLS y políticas explícitas. |
| `migrator` LOGIN | Puede asumir propietario únicamente en el proceso Alembic puntual; credencial ausente del runtime. |
| `api_runtime` LOGIN | Operaciones autorizadas por contexto transaccional/RLS y funciones allowlisted; sin ownership, DDL, superusuario o BYPASSRLS. |
| `identity_executor` NOLOGIN | Funciones limitadas para preauth y credenciales; grants/políticas solo sobre tablas necesarias. |
| `administration_executor` NOLOGIN | Funciones administrativas concretas, comprobando actor activo, privilegio, versión de sesión y acción/recurso. |
| Rol operativo de backup | Lectura completa explícita y comprobada para dump coherente, separado de runtime y acceso cliente. |

Runtime no puede asumir roles ejecutores; recibe EXECUTE sobre funciones revisadas.
Preauth busca solo material mínimo para verificar una credencial, sin inventar un
owner autenticado ni dar SELECT global a anónimos. Funciones SECURITY DEFINER usan
propietario dedicado, search_path seguro, objetos cualificados, ausencia de SQL
dinámico y EXECUTE PUBLIC revocado; sus políticas/grants siguen siendo explícitos,
no se asume que el nombre SECURITY DEFINER eluda FORCE RLS. Administración coordina
interfaces propietarias con el handle compartido, sin SET owner arbitrario.

- Separar propietario/migrador y runtime; runtime sin DDL, superusuario o `BYPASSRLS`, con privilegios mínimos y sin extensiones anticipadas.
- Fijar contexto de propietario desde el servidor con alcance transaccional y denegar contexto ausente. Probar conexión reutilizada tras commit, rollback, timeout y cancelación.
- Respaldar asociaciones coherentes con propietario mediante constraints/FK; RLS complementa la autorización HTTP y no sustituye estas invariantes.
- Aislar roles/contratos Training para consumidores. RLS Recovery y sus políticas reales se prueban en G4; Foundation utiliza fixtures, sin crear su dominio anticipadamente.
- Deshabilitación/eliminación incluyen estado relacionado y, cuando exista Recovery, sus datos; limpieza de archivos externos recuperable y sin GC destructivo ante error DB.
- SQL parametrizado, validación acotada, límites de cuerpo/rate limits, respuestas privadas/no-store y errores sin payloads personales.

## Catálogo SQL y contexto transaccional

Contrato de funciones a entregar mediante Alembic, no funciones existentes. Ninguna
función acepta SQL, nombre de tabla, rol o owner de contexto suministrado por cliente.
`api_runtime` solo tiene EXECUTE exacto en este catálogo y DML propietario descrito
abajo. La firma HMAC/selección cookie-bearer y la criptografía permanecen en Python;
una función SQL no convierte un owner recibido en sesión autenticada.

| Función objetivo / firma semántica | Rol definidor y resultado acotado | Condiciones/efectos |
| --- | --- | --- |
| `identity.lookup_password(alias_key text)` | identity_executor; cero/una fila owner, hash scrypt, disabled, session_version | Lookup correo/nombre compatible; sin listado ni perfil/Training. Dummy hash y rate limit también para inexistente; no respuesta pública distinguible. |
| `identity.lookup_passkey(credential_id text)` | identity_executor; cero/una fila owner, clave pública, counter, transports, disabled, session_version | Exact ID, nunca enumeración global. Challenge de proceso de uso único y biblioteca verifican firma fuera de TX. |
| `identity.lookup_reset(code_digest bytea)` / `lookup_device_link(code_digest bytea)` | identity_executor; cero/una fila owner, expiración y versión/estado | Digest de tamaño esperado, sin devolver código original; verificación final revalida fila/expiración bajo lock. Pairing/challenges efímeros no adquieren durabilidad nueva. |
| `identity.alias_available(alias_key text)` / `release_expired_alias(alias_key text)` | identity_executor; boolean de disponibilidad / void, con owner autenticado en contexto | Excepción aprobada para 2.5: consulta acotada excluye al owner propio; liberación elimina solo la reserva temporal expirada de ese alias, nunca claims de correo/password ni reservas vigentes. Sin owner devuelve false/no-op; iniciador toma namespace antes de lock_actor y conserva ambos locks. No concede lectura global ni cambia firmas existentes. |
| `identity.public_user_count()` | identity_executor; un único bigint | Conteo público compatible de health; no IDs, perfiles ni SELECT global concedido al runtime. |
| `identity.lock_actor(owner text, expected_sv bigint, expires_at timestamptz)` | identity_executor; id, is_admin, session_version | SELECT users FOR UPDATE; deniega ausente/disabled/versión distinta o expiry <= clock_timestamp() después de espera. Solo con owner derivado por identidad verificada; conserva lock hasta commit/rollback del iniciador. |
| `identity.lock_media_owner(owner text)` | identity_executor; solo id existente, bajo FOR UPDATE | Ajuste de 4.3 autorizado expresamente: GC interno deriva candidatos de directorios locales verificados de medios, nunca de HTTP. La interfaz de identidad confirma existencia bajo lock antes de instalar contexto propio y leer referencias por Training; una cuenta ausente no se recoge. Sin sesión fabricada, perfil, credenciales, listado ni SELECT global runtime. Incluye cuentas deshabilitadas como la referencia Node; no concede acceso de usuario. |
| `identity.register_password(owner text, display_name text, alias_key text, email_key text, scrypt_hash text, invite_code text, created_at timestamptz)` / `register_passkey(owner text, display_name text, invite_code text, credential_id text, public_key bytea, counter bigint, transports text[], created_at timestamptz)` | identity_executor; nuevo id y metadatos públicos mínimos | Parámetros tipados de registro, alias ya normalizados y evidencia criptográfica interna; lock namespace, invitación vigente, primer-admin atómico, usuario/credential/claims/consumo juntos. No aceptar is_admin del cliente. |
| `identity.finish_password_login(owner text, observed_hash text, observed_sv bigint)` / `finish_passkey_login(credential_id text, observed_key bytea, observed_counter bigint, new_counter bigint, observed_sv bigint)` | identity_executor; actor apto para emitir sesión | Releer bajo lock; comparar material/versión observado tras trabajo criptográfico; no usar resultado obsoleto. Passkey actualiza counter/last_used_at solo según resultado WebAuthn verificado. |
| `identity.finish_reset(owner text, digest bytea, new_hash text)` / `finish_device_link(owner text, digest bytea, credential_id text, public_key bytea, counter bigint, transports text[], label text)` | identity_executor; actor mínimo | Consumo único y expiración revalidada; límites/última vía. Reset revoca sesiones/enlaces y reserva/alias conjuntamente; link agrega solo la passkey verificada, nunca hash elegido por anónimo sin código vigente. |
| `administration.list_users(actor text, sv bigint, exp timestamptz, page_size integer, after_id text)` / `inspect_user(actor text, sv bigint, exp timestamptz, target text)` | administration_executor; proyección admin compatible | Revalidar actor admin activo y límites antes de leer otro recurso; devuelve parte identity. Handler coordina proyección Training admin vigente mediante su interfaz, nunca documento interno completo ni secretos. Paginación interna no cambia respuesta pública vigente. |
| `administration.set_disabled(actor text, sv bigint, exp timestamptz, target text, disabled boolean)` / `delete_user(actor text, sv bigint, exp timestamptz, target text, task_id uuid)` | administration_executor; resultado mínimo | Namespace y owners ordenados, actor revalidado; disable rechaza cualquier admin, delete rechaza propio actor y último admin, conforme a Node. Coordinador Python usa interfaces propietarias con mismo handle; delete exige vínculo coach desconectado y realiza cascadas + tarea externa. Solo el iniciador confirma. |
| `administration.issue_reset(actor text, sv bigint, exp timestamptz, target text, digest bytea, expiry timestamptz)` / `create_invitation(actor text, sv bigint, exp timestamptz, code text, note text, created_at timestamptz)` / `revoke_invitation(actor text, sv bigint, exp timestamptz, code text)` | administration_executor; resultado admin vigente | Sin cambio implícito de flags; reset/versión/enlaces/alias en misma TX. Invitación consumida persiste y no se reabre al eliminar cuenta. Código de reset solo sale al operador autorizado, nunca a telemetría. |
| `audit.append_event(at timestamptz, event text, ok boolean, actor_id text, target_id text, actor_name text, target_name text, message text, action text, ip text)` / `read_events(actor text, sv bigint, exp timestamptz, after_id bigint, page_size integer)` / `clear_events(actor text, sv bigint, exp timestamptz)` | administration_executor; append sin filas retornadas; read/clear solo admin activo | Campos tipados/allowlisted y tamaño acotado; append en TX separada, secuencia no se reinicia al clear. Retención aplica 90 d/5000 o configuración compatible; fallo separado no revierte negocio. |

En el canje reset entregado, Python instala mediante `SET LOCAL` (`set_config`
transaccional) `app.reset_identifier`, `app.reset_alias`, `app.reset_name` y
`app.reset_sv` desde su lookup validado y normalización interna, nunca desde
campos de owner/versión del cliente. `finish_reset` conserva su firma tipada;
toma namespace antes del lock de usuario y revalida digest, vencimiento,
identificador, nombre, versión y estado antes de modificar claims/credenciales.
El runtime solo puede invocar las dos funciones acotadas; no recibe lectura global
de códigos ni privilegios de executor. El hash scrypt se calcula fuera del lease.

En device-link, `lookup_device_link` exige digest vigente y cuenta activa; devuelve
owner/nombre/versión y solo IDs/transports de passkeys necesarios para las opciones
públicas. Python vincula el challenge a digest/owner/versión e instala `app.link_sv`
transaccional desde esa ceremonia, nunca desde el body del cliente. `finish_device_link`
revalida código/cuenta/versión bajo namespace→usuario y consume el enlace junto con
la passkey, sin cambiar la versión de sesión. El upsert de enlaces concede lectura
y escritura únicamente bajo RLS del owner autenticado; el runtime no asume executor.
Pairing continúa efímero: su código de cinco minutos conserva owner/versión/deadline,
se extrae una sola vez y revalida `lock_actor` antes de emitir el bearer. La versión
actual invalida códigos pendientes tras logout/password aunque todavía no se hayan
purgado de memoria; reiniciar el proceso también los descarta.

En el registro password entregado, Python instala `app.invite_only`,
`app.first_user_admin` y `app.admin_uids` desde configuración del servidor mediante
`set_config(..., true)` en la misma transacción; nunca desde el body HTTP.
`register_password` devuelve únicamente resultado de disponibilidad/colisión o
id/nombre/admin nuevos. La comprobación previa usa `scrypt_hash = NULL`, no escribe
ni libera reservas; permite validar invitación/nombre antes de gastar scrypt.
La llamada final lleva el hash verificado por política y repite los checks bajo
el mismo namespace antes de crear usuario/claims y consumir invitación juntos.
Crypto se ejecuta entre ambas transacciones, sin retener conexión ni locks.

El registro passkey usa esa misma configuración transaccional. Su precheck de
invitación lleva `public_key = NULL`, no crea usuario ni reserva credencial; la
llamada final revalida invitación/credential ID y confirma usuario/passkey/consumo
bajo el namespace. `finish_passkey_login` compara clave/counter/versión bajo lock;
Python compara además el owner observado con el actor devuelto dentro de la misma
transacción y la revierte si la credencial cambió de dueño. El executor solo puede
actualizar counter/last_used_at de passkeys, no reasignar su propietario o clave.
Los errores de verificación no reflejan campos arbitrarios del autenticador;
la guía de configuración solo muestra RP_ID/ORIGIN del servidor.

En las firmas, argumentos opcionales admiten SQL NULL expresamente; el resto se
rechaza si falta. Resultados son proyecciones explícitas, nunca SETOF tabla con
secretos o SELECT *. page_size queda entre 1 y 500 (solo lotes internos para
componer la respuesta pública compatible), after_id nullable. Errores esperados
usan códigos internos estables de acceso/colisión/expiración; los handlers conservan
status/code/cuerpo Node, no exponen SQLSTATE. No nuevas variantes ni catch-all. Funciones owner normales (renombrar passkey, contraseña/email propios,
logout/all, Training, push, coach) usan repositorios bajo RLS; cambios de credenciales
además revalidan prueba de acceso vigente y conservan última vía. Las funciones
privilegiadas no hacen HTTP, scrypt, filesystem ni commit interno.

Cada función justifica el acceso que no puede concederse al runtime y la invariancia
atómica que protege. Python posee transporte, criptografía y coordinación; SQL
posee constraints, autorización privilegiada e invariantes concurrentes. No mantener
dos implementaciones independientes de una regla de negocio; validación de entrada
y constraints de integridad protegen fronteras distintas y pueden coexistir.
No añadir funciones por simetría: demostrar primero que repositorio/grants/RLS no
satisfacen la operación. Reducir una firma requiere pruebas equivalentes de permisos,
concurrencia y respuestas; nunca SELECT global ni BYPASSRLS como atajo. Esta revisión
no cambia firmas, roles, RLS ni grants aprobados.

**DDL de privilegios:** revocar CREATE de PUBLIC en public, CONNECT público a BD
operativa, todos los EXECUTE públicos/default EXECUTE de funciones y grants de
objetos nuevos. Funciones definer pertenecen al executor NOLOGIN correspondiente,
con `SET search_path = pg_catalog, pg_temp`, objetos siempre cualificados y sin SQL
dinámico. Migrator/owner pueden definirlas; runtime no es miembro de executor/owner
ni puede CREATE/ALTER/SET ROLE a ellos. Executor tiene solo SELECT/INSERT/UPDATE/DELETE
de las tablas usadas por su catálogo y USAGE de secuencias necesarias; ninguna
concesión a otros esquemas por defecto. Las firmas exactas se conceden explícitamente,
no `ALL FUNCTIONS`. Tests inspeccionan pg_proc.prosecdef/proconfig/ACL y pg_roles.

ENABLE y FORCE RLS en todas las tablas de negocio. Para api_runtime, políticas
USING y WITH CHECK `owner_id = nullif(current_setting('app.owner_id', true), '')`
en datos por propietario; users usa `id` en vez de owner_id. Ningún contexto o
cadena vacía concede filas. Runtime SELECT de users solo proyección pública propia;
no lectura directa de hashes/aliases/credenciales globales, invitaciones, audit,
settings globales ni deletion_tasks. Repositorios propios de credenciales reciben
DML por columna/owner indispensable, no autorización administrativa general.
Settings/config/resultados globales coach y subscription endpoint global usan el
catálogo adicional siguiente, con executor NOLOGIN por módulo (sin membresía runtime):

- `coach.read_instance(actor text, sv bigint, exp timestamptz)` y
  `coach.write_instance(actor text, sv bigint, exp timestamptz, settings jsonb,
  providers jsonb)` pertenecen a coach_executor, requieren admin activo y devuelven
  únicamente vista admin sin secretos. JSONB tiene exactamente la estructura
  settings/provider_settings aprobada, sin claves extra ni material secreto; no es
  un dispatcher. Bound owner anterior/nuevo se bloquean antes de singleton.
- `coach.reserve_job(actor text, sv bigint, exp timestamptz, job_id text, kind text,
  trigger text, expected_generation bigint, at timestamptz)` pertenece a
  coach_executor; revalida actor, disponibilidad, consentimiento y generación bajo
  mismo handle, crea/incrementa filas UTC de consumo y job atómicamente. Retorna
  solo job_id/estado. Cap cero ilimitado; colisión/sin consentimiento/diferido no
  cambia cuotas. El límite de dos ejecuciones usa semáforo del único worker, no
  transacción abierta durante HTTP. El executor recibe únicamente la proyección
  document/owner_id de Training con RLS del actor ya revalidado, para comprobar
  consentimiento dentro de la reserva; no lectura global. Python usa la interfaz
  pública Training para sus revalidaciones antes/después de la llamada externa.
- `coach.fail_interrupted_jobs() RETURNS bigint` es la excepción de recuperación
  aprobada para 5.2: solo al arrancar el worker único, antes de aceptar tráfico,
  archiva los jobs actuales como failed/restart y los retira en una transacción.
  Executor NOLOGIN, search_path fijo, EXECUTE runtime explícito; devuelve solo
  cardinalidad, sin owners/contenido ni parámetros arbitrarios. Conserva cuotas,
  generaciones y configuración, no reejecuta proveedores; historial personal
  limitado a 20 eventos. No concede SELECT global al runtime ni usa migrator.
- `coach.disconnect_owner(actor text, sv bigint, exp timestamptz, target text)`
  permite propio owner o admin activo, conserva referencia de limpieza y desconecta
  sin transformar una credencial personal en compartida. `coach.read_results(actor
  text, sv bigint, exp timestamptz)` requiere admin y devuelve últimos 100 resultados
  mínimos. No concede lectura global de Training ni secretos al executor.
- `notifications.upsert_subscription(actor text, sv bigint, exp timestamptz,
  endpoint text, p256dh text, auth text, device_id text, created_at timestamptz)`
  pertenece a notifications_executor, revalida propietario y aplica transferencia
  global de endpoint/poda compatibles sin revelar propietario anterior; no cambia
  fecha original ni device_id válido si se omite el nuevo. La autorización/SSRF y
  parámetros criptográficos se validan también antes del SQL. Lock advisory xact
  728324 antes de owners, luego fila endpoint; releer propietarios bajo ese orden.
  `notifications.delivery_candidates(at timestamptz)` retorna solo IDs candidatos
  al scheduler interno; no credenciales, documentos ni preferencias. Para cada ID,
  el service deriva contexto de trabajo desde esa lista autorizada, vuelve a
  comprobar cuenta/preferencias bajo owner lock y reclama fecha/envía por su
  interfaz, nunca desde un owner recibido por HTTP anónimo.

- `coach.public_disclosure()` devuelve solo enabled/provider/auth_mode/community
  compatibles sin actor/secreto, aplicando disponibilidad Q6. `coach.cohort_candidates
  (actor text, sv bigint, exp timestamptz)` exige actor vigente y participación
  consentida, devuelve solo IDs candidatos opt-in a la colaboración interna, nunca
  esos IDs al cliente. Revalidar consentimiento bajo cada owner lock al preparar
  agregados y conservar umbrales/supresión del cohort actual.
- `training.read_admin_summary(actor text, sv bigint, exp timestamptz, target text)`
  y `training.read_admin_detail(actor text, sv bigint, exp timestamptz, target text)`
  pertenecen a administration_executor con SELECT/política explícita sobre documents.
  Verifican admin activo/actor-target y retornan exclusivamente las proyecciones
  actuales de `GET /api/admin/users` y `/api/admin/user`: conteo/último workout/sync
  y detalle unit/routines resumidas/bodyweight/workouts sin media, respectivamente.
  No SET owner=target ni acceso Recovery. Esto preserva una facultad existente,
  no inventa exportación global ni elimina silenciosamente el drill-down admin.

Las políticas executor permiten solo las tablas necesarias para estas operaciones;
no lectura directa de Training global: la colaboración Training recibe contexto
interno explícito autorizado. Cambios de grant/catálogo se prueban por función y
rol, no se solventan con una política global para api_runtime. Executor necesita políticas TO executor USING/WITH CHECK
true únicamente sobre sus tablas de catálogo: SECURITY DEFINER no evita FORCE RLS.
Backup tiene SELECT y políticas completas explícitas, sin BYPASSRLS/superusuario;
usa `pg_dump --enable-row-security` y verifica conteos/digests de todos los owners.
Pruebas demuestran ausencia de TRUNCATE, DDL, GRANT o SET ROLE para runtime.

Orden único dentro de la API activa: lock namespace identity si hay cambios
credenciales/claims/admin → lock endpoint 728324 si corresponde → users afectados
en orden `id COLLATE C` → singleton/
contadores coach → recursos propios. Namespace usa advisory xact lock 728323;
no usar hash de owner como único lock: users FOR UPDATE serializa incluso sin
Training. Operaciones admin bloquean actor/target en orden, no siempre actor primero.
No adquirir namespace después de owner. Si cambia un vínculo mientras se calcula
el conjunto de locks, abortar/reintentar acotadamente con nueva lectura, sin mantener
TX durante cálculo criptográfico/red. Errores esperados se traducen al contrato
HTTP vigente; detalle SQL/constraints/parámetros nunca sale al cliente ni al diagnóstico.

`set_config('app.owner_id', actor.id, true)` ocurre únicamente después de verificar
firma, selección de credencial y lock_actor con expiración/versión vigentes. Actor
admin no se sustituye por target; contexto actor/versión/expiración también se fija
transaccionalmente para funciones globales, no por headers/body. PostgreSQL confía
en el backend para esos valores: RLS evita errores de alcance y no protege de una
API comprometida capaz de ejecutar SQL arbitrario. Un handle compartido se invalida
al terminar TX; pool max=1 debe quedar sin contexto tras todos los desenlaces.
El orden de lock decide revocación concurrente: si revocación confirma primero,
trabajo viejo falla; si trabajo autoriza primero bajo lock puede confirmar antes
de la revocación. Expiración se comprueba tras cada espera previa a autorización,
no se promete deshacer un commit ya reconocido.

## Secretos y conexiones


### Protección de material y proveedores

Secretos fuera de Git, frontend y logs; separar credenciales runtime/migrador y claves del coach. Proteger rotación, firma de sesiones y restauración de credenciales conforme al contrato. PostgreSQL privado, autenticación y mínimo privilegio; verificar certificados TLS al cruzar redes no confiables o por requisito del proveedor. Las URLs con contraseñas no se registran.

Preservar el sandbox/límites de cada proveedor del coach o resolver su tratamiento explícitamente. Separación de módulos y RLS no son un sandbox frente al administrador del host o un backend comprometido.

## Auditoría y trazabilidad de datos

El audit actual es un registro operativo JSON con retención, borrable por administración; no acredita inmutabilidad. El destino aprobado es `audit.events`, con lectura/clear administrativos explícitos, secuencia conservada y máximos configurables de 90 días/5000 eventos, aplicando ambos límites; IP off por defecto. IDs/nombres históricos no tienen FK destructiva al borrar usuario, e invitaciones consumidas conservan su marca. Inventariar eventos/consumidores y probar recuperación; no incluir credenciales o contenido personal de negocio en nuevos eventos.

Cada evento definido identifica actor/recurso/acción/instante/resultado con datos mínimos; controlar acceso y evitar credenciales, contenido de entrenamiento/rehabilitación o secretos. No copiar nombres o payloads personales al tracing por reutilizar audit. El historial de correcciones Recovery tiene su contrato propio y no se reemplaza por audit operativo.

Política aprobada: preservar best effort de eventos heredados, incluido login y administración, con fallo observable/código seguro. Audit se intenta en unidad separada o después del commit de negocio, sin abortarlo mediante un error SQL de auditoría ni devolver fallo tras éxito confirmado. No prometer entrega garantizada, atomicidad o reintento ilimitado; endurecimiento obligatorio por operación requiere otro cambio explícito. [Telemetría técnica](platform-observability.md) y audit son canales distintos: el muestreo de traces no decide qué eventos de seguridad/historia se conservan.

### Eliminación y restauración

Eliminar cuenta borra datos SQL operativos, desconecta credenciales personales
ligadas del coach y registra limpieza externa pendiente en la misma transacción.
Medios/secretos se eliminan después por sus propietarios; fallo conserva tarea y
señal de pendiente, no resucita acceso ni se presenta como limpieza completa.
Olvidar coach conserva únicamente cuota del día; eliminar cuenta borra su cuota,
conservando agregado de instancia sin vínculo personal.

La [restauración aislada](platform-operations.md#restauración-y-decisiones-de-seguridad-posteriores)
invalida sesiones/tokens restaurados y reconcilia bajas/revocaciones posteriores,
incluidas passkeys. Sin evidencia suficiente, las credenciales históricas permanecen
bloqueadas. El procedimiento local explícito de recuperación de acceso puede crear
una vía nueva en el destino aislado sin reactivar las dudosas, cambiar ID/rol ni
habilitar automáticamente una cuenta eliminada o disabled. No hay endpoint público
ni bootstrap admin; autorización local y entrega privada de la vía nueva se definen
y prueban antes del slice. Retención de backups no elimina copias históricas.

## Evidencia de aceptación

GP antes del corte y G3 después de retirada deben demostrar:

- Login/passkeys/passwords/pairing, sesiones inválidas/expiradas/revocadas y cuentas deshabilitadas; vectores Node/Python y clientes compatibles.
- Lectura/escritura/borrado por actor, IDs de otro propietario, elevación no autorizada y revocación durante espera, preservando el acceso público legítimo.
- Roles reales no exentos, contexto ausente y reutilización del pool; políticas Recovery solo en su etapa.
- Eventos audit definidos, permisos/retención/restore y fallo de escritura identificable; ausencia de credenciales o payloads sensibles en errores y registros.

Registrar revisión, entorno, fixtures, resultados y limitaciones. Una prueba de autenticación correcta no demuestra autorización; mocks o SQL como superusuario no prueban RLS efectivo.

Referencias: [OWASP Authorization](https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html), [OWASP Logging](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html). Los patrones pertinentes de AI Tutor y sus límites están en la [evidencia histórica](../research/evolution-architecture-evidence.md#23-ai-tutor-como-referencia).
