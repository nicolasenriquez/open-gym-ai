---
type: Reference
title: Plataforma — esquema SQL compatible
description: Tablas, relaciones, índices e invariantes aprobados para portar las capacidades actuales a PostgreSQL.
---
# Plataforma — esquema SQL compatible

## Estado y autoridad

Diseño confirmado por el promotor tras revisar identidad, Training, coach y operación.
Es el contrato físico objetivo de plataforma, no DDL ejecutado ni evidencia de paridad.
Sustituye la nomenclatura de plataforma antes abierta en arquitectura §6. Recovery
conserva su [modelo posterior](recovery-contracts.md#modelo-conceptual).

Leer al especificar migraciones de negocio, repositorios, importación o índices.
El [PRD](../open-gym-evolution.prd.md) gobierna resultados;
[modularidad](platform-modularity.md) asigna operaciones y dependencias;
[seguridad](platform-security.md) posee roles, autorización y auditoría;
[operación local](platform-operations.md) posee redes, respaldo y corte.
El [OpenSpec de port y operación](../../openspec/changes/port-compatible-platform/proposal.md)
formaliza los escenarios futuros. Foundation mantiene solo infraestructura y fixtures.

## Mapa y convenciones

```text
identity.users
  +--< identity.login_aliases / passkeys / consumer_credentials
  +--- identity.password_credentials / password_resets / device_links
  +--- training.documents
  +--< notifications.subscriptions
  +--- notifications.delivery_state
  +--- coach.profile_state / jobs / pending_proposals
  +--< coach.history_events / daily_usage

identity.invitations: procedencia y consumo histórico
coach.settings / provider_settings: configuración de instancia
coach.instance_daily_usage / instance_results: agregado y resultados generales
audit.events: hechos históricos sin cascada desde users
administration.deletion_tasks: limpieza externa pendiente tras borrar cuenta
```

`PK` identifica filas; `FK` relaciona tablas; `UNIQUE` evita duplicados y `CHECK`
restringe valores. Esquemas SQL por módulo, una BD y un historial Alembic. Los nombres
de tabla/columna de esta referencia son el destino acordado; un cambio debe explicar
qué sustituye. El DDL literal y las funciones se revisan y prueban en el port.

- IDs heredados: `text`, sin conversión obligatoria a UUID ni restricciones nuevas
  de formato que rechacen identificadores válidos existentes.
- Instantes: `timestamptz(3)`; fechas de calendario: `date`; indicadores: `boolean`;
  contadores: `bigint` no negativo; configuración acotada: enteros con límites.
- Fechas históricas ausentes se conservan nulas, sin inventar fecha de migración.
  Serializadores mantienen por ruta ausencia frente a null; una columna nula no
  obliga a emitir un campo que antes se omitía.
- JSONB validado por estructura, tamaño y semántica; no aplicar defaults ni eliminar
  claves nulas del documento heredado por conveniencia.
- FKs de datos operativos `owner_id` apuntan a `identity.users(id)` con eliminación
  en cascada, salvo las excepciones históricas y de limpieza descritas abajo.
  Una FK a un objeto compuesto debe incluir propietario cuando corresponda.

## Identidad y acceso

| Tabla | Columnas | Integridad y compatibilidad |
| --- | --- | --- |
| `identity.users` | `id text PK`, `display_name text`, `created_at timestamptz NULL`, `is_admin boolean`, `disabled boolean`, `session_version bigint`, `last_pull_at timestamptz NULL`, `invited_by text NULL` | Nombre visible no único. Defaults efectivos de indicadores false y versión 0. `invited_by` FK a invitación, sin cascada al usuario. `last_pull_at` conserva actividad de sync, no preferencias push. |
| `identity.login_aliases` | `alias_key text PK`, `owner_id text FK`, `email_claim boolean`, `password_name_claim boolean`, `reset_name_until timestamptz NULL` | Clave normalizada global, comparación exacta; una fila puede representar nombre y correo del mismo propietario. Al menos un propósito o reserva temporal. |
| `identity.password_credentials` | `owner_id text PK/FK`, `scrypt_hash text`, `set_at timestamptz NULL` | Hash scrypt serializado completo; contraseña opcional y política vigente de instancia. |
| `identity.password_resets` | `owner_id text PK/FK`, `code_digest bytea`, `expires_at timestamptz`, `issued_by text` | Un reset por usuario, plazo actual de 24 h y consumo único. Emisor histórico sin FK destructiva. |
| `identity.passkeys` | `credential_id text PK`, `owner_id text FK`, `public_key bytea`, `counter bigint`, `transports text[]`, `label text NULL`, `created_at timestamptz NULL`, `last_used_at timestamptz NULL` | Decodificación/serialización WebAuthn compatible. Máximo 20 y conservación de última vía válida mediante operación serializada. No inventar contador de una credencial legacy inválida. |
| `identity.device_links` | `code_digest bytea PK`, `owner_id text UNIQUE/FK`, `created_at timestamptz`, `expires_at timestamptz` | Diez minutos, uso único. Nuevo enlace reemplaza anterior; revocación elimina pendientes. |
| `identity.consumer_credentials` | `id text PK`, `owner_id text FK`, `token_digest bytea UNIQUE`, `scope text`, `issued_session_version bigint`, `created_at timestamptz`, `expires_at timestamptz`, `revoked_at timestamptz NULL` | Scope limitado a `training:read`; emisión y validación según seguridad. Token en claro solo al emitir. |
| `identity.invitations` | `code text PK`, `note text`, `created_by text`, `created_at timestamptz NULL`, `consumed boolean`, `used_by text NULL`, `used_at timestamptz NULL`, `revoked boolean` | Aceptar códigos legacy sin exigir longitud nueva. `consumed` persiste aunque desaparezca cuenta. Creador/usuario históricos sin FK destructiva. `usedByName` se resuelve, no se duplica. |

### Alias y cambios de credenciales

Normalización compatible con `NFKC + trim + lowercase` del código Node, mediante
vectores Unicode independientes; no sustituir por casefold, citext o lower SQL.
El nombre visible puede repetirse. Su alias se reserva al existir contraseña o
reset vigente; el correo permanece reservado aun sin contraseña. Lookup con `@`
prioriza correo, luego nombre, conservando los campos legacy de entrada.

La operación identity bloquea transaccionalmente el namespace, vuelve a consultar
colisiones y libera reservas exclusivamente temporales expiradas antes de reclamar.
Actualiza aliases, contraseña/reset y versión de sesión juntos. No usar un índice
parcial con `now()`. El cálculo scrypt y la interacción con autenticador ocurren
fuera de la transacción; después se revalida lo observado y el acceso vigente.

La contraseña conserva NFKC sin recorte ni cambio de mayúsculas. Reset/cambio de
password mantiene passkeys, revoca sesiones y elimina enlaces/pairings pendientes.
El backend conserva tokens firmados actuales y `session_version`, sin tabla nueva
de sesiones ni sustitución por JWT. Toda diferencia de acceso requiere resolución
explícita y pruebas, conforme a seguridad.

## Training canónico

| Tabla | Columnas | Integridad |
| --- | --- | --- |
| `training.documents` | `owner_id text PK/FK`, `document jsonb NOT NULL`, `revision bigint GENERATED ALWAYS ... STORED`, `write_id text GENERATED ALWAYS ... STORED` | Documento objeto completo. Revisión derivada de `_rev`; write_id derivado de `_wid`. Sin escritura independiente de las proyecciones. |

```text
document JSONB: historial + configuración + stamps + _rev/_wid/_wids/_prior/...
                         |
                         +--> revision (GENERATED STORED)
                         +--> write_id (GENERATED STORED)
```

Sin fila significa `{state:null, rev:0}`; no crear un documento vacío. `_rev`
ausente/null proyecta 0; si existe, exigir número integral no negativo dentro del
rango seguro JavaScript. Validar integralidad antes de convertir numeric a bigint,
sin redondear revisiones fraccionarias ni convertir strings. Antes de escribir,
comprobar margen para incremento +2. `_wid` ausente/null proyecta SQL null; presente
debe ser string. El documento original conserva sus claves.

Importar `_unstamped`, `_prior`, linaje y demás campos internos, no solo `forClient`.
Prevalidación identifica JSON no representable fielmente, Unicode inválido, claves
duplicadas o tipos fuera del contrato. Bloquear importación/corte y resolver la
diferencia, sin corrección silenciosa. Comparar significado, tipos y renderización,
no orden de claves o bytes JSON.

Una transacción bloquea primero el propietario, incluso sin documento, revalida
sesión, compara baseRev/baseWid, aplica stamps/reset y escribe `document`. Preserva
409, escrituras legacy permitidas y respuesta rev+1 aunque el documento alcance
rev+2. La sesión activa permanece local. Tras el commit, un fallo al actualizar
marcas de medios no convierte el guardado confirmado en fallo.

## Notificaciones

| Tabla | Columnas | Regla |
| --- | --- | --- |
| `notifications.subscriptions` | `endpoint text PK`, `owner_id text FK`, `p256dh text`, `auth text`, `device_id text NULL`, `created_at timestamptz` | Upsert global de endpoint conserva fecha original y device ID previo cuando no llega uno válido. Límite actual 20 por usuario con poda de antiguas; validación SSRF preservada. |
| `notifications.delivery_state` | `owner_id text PK/FK`, `last_reminder_date date NULL`, `last_nudge_date date NULL` | Fechas locales del usuario; envío/reclamación evita duplicados del día conforme al contrato actual. |

Preferencias `reminder` permanecen en Training. Presencia, challenges, pairing,
limitadores y temporizadores efímeros tienen equivalentes de proceso; no se les
atribuye durabilidad adicional ni se crean tablas por anticipación.

## Coach actual

| Tabla | Columnas | Regla |
| --- | --- | --- |
| `coach.settings` | `id smallint PK CHECK(id=1)`, `enabled boolean`, `provider text`, `auth_mode text`, `community boolean`, `per_profile_daily integer`, `instance_daily integer`, `max_message_len integer`, `max_output_tokens integer` | Singleton; límites actuales validados. Proveedor elegido referencia `provider_settings`. |
| `coach.provider_settings` | `provider text PK`, `model text NULL`, `options jsonb`, `secret_ref text NULL`, `bound_owner_id text NULL` | Opciones no secretas allowlisted; material secreto externo. Vínculo personal FK restrictiva mientras exista: desconectar credencial antes de borrar cuenta; no reasignarla automáticamente. |
| `coach.profile_state` | `owner_id text PK/FK`, `sharing boolean`, `forget_generation bigint` | Sharing false por defecto, fuera de Training para impedir reactivación por sync antiguo. |
| `coach.jobs` | `owner_id text PK/FK`, `job_id text`, `kind text`, `trigger text`, `state text`, `started_at timestamptz`, `forget_generation bigint` | Solo trabajos actuales queued/running; PK owner garantiza single-flight. No persistir prompts/inputs efímeros por inercia. |
| `coach.pending_proposals` | `owner_id text PK/FK`, `document jsonb`, `proposal_id text GENERATED ... STORED`, `kind text GENERATED ... STORED`, `expires_at_ms bigint GENERATED ... STORED` | Una propuesta por usuario; JSONB canónico validado incluye createdAt/expiresAt, planHash, iteration y contenido. Expiración actual 14 días. |
| `coach.history_events` | `event_id bigint IDENTITY PK`, `owner_id text FK`, `job_id text NULL`, `kind text`, `outcome text`, `error_class text NULL`, `occurred_at timestamptz`, `details jsonb` | Últimos 20 eventos, no 20 jobs. reading personal acotado y conteos accepted/rejected en details. Job histórico sin FK a trabajo actual eliminado. |
| `coach.daily_usage` | `owner_id text FK`, `day date`, `count bigint`, PK `(owner_id,day)` | Día UTC; count no negativo. Conservar consumo de hoy al olvidar; eliminarlo al borrar cuenta. |
| `coach.instance_daily_usage` | `day date PK`, `count bigint` | Agregado UTC sin propietario; no derivarlo del historial podado. |
| `coach.instance_results` | `event_id bigint IDENTITY PK`, `occurred_at timestamptz`, `kind text`, `trigger text`, `outcome text`, `error_class text NULL`, `duration_ms bigint`, `summary jsonb` | Últimos 100 resultados sin contenido personal, prompts ni reading. |

Encolar actualiza ambos contadores y crea el trabajo bajo una transacción con orden
de bloqueos consistente. Tipos y estados tienen CHECK explícitos según contratos
caracterizados; el runtime único limita a dos ejecuciones globales. No mantener
transacciones durante llamadas al proveedor.

Al finalizar se verifica propietario existente, consentimiento y generación, se
actualiza propuesta/historial y se elimina el trabajo actual en la misma transacción.
El historial conserva varios eventos del mismo job (ready, applied, dismissed,
expired); su PK independiente evita colisiones. Reinicio convierte actuales en
failed/restart, sin reejecutar llamadas de coste incierto. El historial heredado se
importa como eventos, sin inventar filas de jobs pasados. El olvido incrementa la
generación y elimina jobs/propuestas/historial; resultados tardíos no los recrean.

## Auditoría y limpieza externa

| Tabla | Columnas | Regla |
| --- | --- | --- |
| `audit.events` | `id bigint IDENTITY PK`, `occurred_at timestamptz`, `event text`, `ok boolean`, `actor_id/target_id text NULL`, `actor_name/target_name text NULL`, `message/action/ip text NULL` | IDs históricos sin FK a cuentas, mensajes mínimos acotados; importar y avanzar secuencia sin reiniciarla al limpiar. Política en seguridad. |
| `administration.deletion_tasks` | `id uuid PK`, `deleted_owner_id text`, `created_at timestamptz`, `status text`, `attempts integer`, `last_error_code text NULL` | Sin FK a usuario ya eliminado. Solo identificadores, estado y errores seguros de limpieza externa. Retirar al verificar finalización. |

El coordinador verifica las restricciones actuales de borrado, desconecta vínculos
personales del coach y confirma eliminación SQL junto con la tarea de limpieza.
Medios y secretos ejecutan luego su parte mediante interfaces propietarias. La tarea
permite reintento acotado y fallo visible; no declara atómico el filesystem ni crea
un sistema general de colas. El acceso termina con el borrado SQL; la interfaz y
evidencia distinguen limpieza pendiente de eliminación externa comprobada.

Bytes multimedia, `.gc.json` y temporales permanecen fuera de SQL, con backup
coordinado. Falta de referencias/DB o marcas ilegibles conserva bytes de forma
segura. Catálogo continúa en web; datos pendientes y sesión activa en cliente.

## Índices y consultas

PK/UNIQUE ya generan índices; no duplicarlos. FKs operativas deben estar cubiertas
por PK/índice con propietario como prefijo adecuado.

| Tabla | Índice además de PK | Consulta o restricción |
| --- | --- | --- |
| `login_aliases` | `(owner_id)`; UNIQUE `(owner_id) WHERE email_claim`; UNIQUE `(owner_id) WHERE password_name_claim OR reset_name_until IS NOT NULL` | Liberar claims y limitar un alias por propósito/propietario; tiempo se evalúa en operación, no predicado. |
| `users` | Parcial `(invited_by) WHERE invited_by IS NOT NULL` | Soportar FK/procedencia por invitación. Sin UNIQUE display_name. |
| `passkeys` | `(owner_id)` | Listar, contar y borrar credenciales propias. |
| `device_links` | UNIQUE `(owner_id)` | Un pendiente por usuario. |
| `consumer_credentials` | UNIQUE `(token_digest)`, `(owner_id)` | Verificación y revocación por propietario. |
| `subscriptions` | `(owner_id,created_at)` | Envíos por usuario y poda de antiguas. |
| `history_events` | `(owner_id,event_id DESC)` | Últimos 20 y poda. |
| `provider_settings` | Parcial `(bound_owner_id) WHERE bound_owner_id IS NOT NULL` | Comprobar/desconectar credenciales ligadas antes del borrado. |
| `deletion_tasks` | Parcial `(created_at,id) WHERE status IN ('pending','retry')` | Procesar limpieza incompleta. |

Training, estado push, jobs/propuestas y consumos por propietario usan sus PK.
Auditoría y resultados generales recorren sus PK en sentido descendente; con sus
límites iniciales no se añaden índices por filtro. No GIN general Training, índice
de last_used ni índices de expiración masiva sin consulta/volumen demostrado.
El port debe verificar planes y límites con fixtures representativas.

## Evidencia requerida

DDL Alembic desde vacío/revisión anterior, constraints e índices reales; aliases
concurrentes/Unicode/reset expirado; WebAuthn/scrypt y serialización compatible;
Training primera escritura/conflicto/stamps/linaje y tipos límite; contador/job
atómicos, olvido y respuesta tardía; borrado con fallos externos; RLS con roles
restringidos y conexión reutilizada; importación/restore semánticamente equivalentes.
Los escenarios y tareas del OpenSpec enlazado permanecen pendientes; checks de
Markdown no acreditan ninguna de estas pruebas.

Referencias de mecanismo: [constraints PostgreSQL 18](https://www.postgresql.org/docs/18/ddl-constraints.html),
[columnas generadas](https://www.postgresql.org/docs/18/ddl-generated-columns.html),
[índices y expresiones inmutables](https://www.postgresql.org/docs/18/sql-createindex.html)
y [límites JSONB](https://www.postgresql.org/docs/18/datatype-json.html).
