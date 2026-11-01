---
type: Reference
title: Plataforma — observabilidad y tracing
description: Contrato objetivo de señales, tracing, privacidad y evidencia de operación para GO.
---
# Plataforma — observabilidad y tracing

**Estado:** contrato objetivo revisado de EV-08 para operación personal local.
La retención 9.2, correlación 9.3 y matriz sintética 9.4 se describen abajo.
La revisión sustituye el
perfil OpenTelemetry/JSONL propio por diagnóstico mínimo verificable; tracing
avanzado queda diferido. [Arquitectura §12](../open-gym-evolution.architecture.md#12-gates-y-experimentos-antes-de-producción)
gobierna GO y [seguridad](platform-security.md) gobierna audit y secretos.

## Señales y correlación

| Señal | Contrato de primera entrega |
| --- | --- |
| Logs | Logging estándar Python con registros estructurados: instante, revisión, servicio, severidad, request_id, operación, resultado y duración. |
| Correlación | Un request_id interno aleatorio relaciona HTTP, espera/TX DB y llamada externa dentro de una operación. Sin spans persistidos ni contexto enviado a proveedores. |
| Estado | Diagnóstico puntual de DB/esquema, ocupación del pool, audit degradado y último backup verificado/antigüedad. No necesita un almacén de series. |
| Salud | Liveness del proceso y readiness de DB/esquema diferenciados; interfaces internas, sin credenciales ni detalles privados en health pública. |

No entregar OpenTelemetry, exporter propio, sampling, almacenamiento de spans ni
snapshots métricos. Incorporarlos exige una necesidad diagnóstica concreta y otro
cambio. No alterar el contrato público para añadir headers diagnósticos.

9.3 genera hex32 con secrets por petición y lo conserva con ContextVar durante
adquisición del pool, consultas, transacción y transporte HTTP del coach. Las
tareas asíncronas heredan el contexto de la petición iniciadora aun después de su
202; las peticiones concurrentes tienen identificadores distintos. No se guarda en
tablas ni se envía al proveedor. Trabajo periódico sin petición no recibe un ID HTTP.
Los registros DB son del adaptador Python alrededor de PostgreSQL real; el stream
nativo PostgreSQL conserva solo servicio/severidad según la política de privacidad.

HTTP conserva su status y plantilla completa /api/v1; DB informa ok, failed,
timeout, cancelled o commit_unknown. provider.invoke/provider.models registran
códigos cerrados, sin mensajes del proveedor. coach.execution distingue ready,
nochange, auth, provider, timeout, cancelled e internal, entre otros códigos
internos de validación. Un timeout del job cancela el transporte y registra el
resultado timeout bajo el mismo request_id. Las duraciones usan reloj monotónico;
la duración HTTP del 202 no incluye la finalización posterior del job.

## Privacidad y acceso

Atributos allowlisted: revisión/servicio, plantilla de ruta, método, operación,
resultado/código, duración y request_id. Excluir cookies, tokens, nombres, notas,
historial, prompts, parámetros SQL, URLs crudas y stack/message de excepción sin
sanear. No usar owner como etiqueta ni identificador de búsqueda. Ignorar
X-Request-ID, traceparent y baggage externos; el identificador no autentica ni
confirma un guardado. Audit e historial mantienen sus garantías independientes.

Diagnóstico privado sin servicios externos. Logs hasta siete días y 256 MiB totales;
una cuota puede acortar conservación. Inventariar todas las copias duraderas,
incluida captura Docker, y no conservar copias fuera de la política. No incluir
logs en backups de negocio ni artefactos CI sin saneado.

## Ejecución y fallos

Usar logging estándar y tooling de rotación/retención existente en la imagen
operativa, no implementar un exporter o framework de almacenamiento. Antes de
implementar 9.2–9.4 seleccionar y fijar la herramienta, su configuración de cuota/edad
y su política para archivos activos; 9.2 entrega la selección concreta descrita abajo. Si no satisface la política, detener
ese slice y revisar la decisión, no añadir silenciosamente un subsistema propio.

Los límites se verifican con archivos activos y rotados, reinicio, API detenida y
espacio agotado. La tarea horaria de retención usa el mismo mecanismo. Host apagado
no puede borrar físicamente: limpiar expirados antes de reanudar acceso diagnóstico.
No reemplazar `compose logs` por un sink propio sin declarar cómo se diagnostican
también nginx y PostgreSQL; resolver sus copias y posibles datos sensibles en S9.

### Selección de retención entregada en 9.2

Colector local no-root con rsyslog **8.2302.0-1+deb12u1** y logrotate
**3.21.0-1**, fijados en backend/diagnostics/Dockerfile y backend/versions.json.
La imagen conserva su manifiesto dpkg; producción exige su image ID probado.
No se instala nada al arrancar ni en el host. Esta configuración concreta fue
verificada; no se declara rsyslog universalmente libre de vulnerabilidades.

El promotor aprobó Unix para API y el driver syslog de Docker para nginx/PG,
mode=non-blocking, buffer en memoria de 1 MiB y cache-disabled=true. El colector
escucha UDP 5514 solo en una red Docker internal, sin puertos publicados ni egress.
La dirección/subred se fijan mediante PLATFORM_DIAGNOSTICS_IP/SUBNET
(por defecto 10.253.245.2 y 10.253.245.0/29); una colisión bloquea el arranque y
requiere seleccionar otra red antes de operar. No necesita socket Docker,
root o capacidades nuevas. El intento anterior de enlace /dev/log en imagen
PostgreSQL fue descartado porque Docker sustituye /dev al ejecutar.

| Copia / productor | Política efectiva |
| --- | --- |
| API | Logging estándar Python, campos fijos y plantilla de ruta; Unix no bloqueante, incluso al reconectar. Driver Docker none para no duplicar stderr. |
| nginx / PostgreSQL | Driver syslog sin caché durable. Ruleset UDP exclusivo descarta mensajes crudos, URLs, SQL e identificadores; conserva servicio y severidad. Ni un tag UDP falsificado selecciona el JSON de API. |
| PostgreSQL local | logging_collector=off y log_destination=stderr explícitos; no copia de logs dentro del volumen SQL. |
| Otros procesos / operaciones | Driver none; salida nativa desconocida recibida por el colector se reduce a servicio ops y severidad. |
| Archivos | Cuatro streams fijos, directorio 0700/archivos 0600, sin dynaFile ni rutas del request. Límite 352 KiB más un registro de 8 KiB, 168 rotados y activo por stream: menos de 238 MiB lógicos, con margen para metadata/copia dentro de 256 MiB. |
| Estado / buffers | Estado y locks en tmpfs acotado de 1 MiB; cola rsyslog FixedArray de 256, sin spool persistente. Sin copias de Docker fuera de la política. |
| Edad / activo | Barrido estándar find/truncate y logrotate antes del arranque y cada hora, independiente de API. maxage 6, ifempty, copytruncate y bloqueo compartido entre callbacks y timer. Margen hasta siete días para activo e intervalo. |
| Acceso | diagnose consulta estado vivo por socket 0600; no expone histórico ni endpoint HTTP. Antes de leer archivos manualmente ejecutar el mismo --retain del colector. Host apagado no elimina bytes; el barrido precede al reinicio. |

La API informa pool/DB/esquema, audit degradado, fallos de transporte y espacio
del sink; envío de datagrama siempre significa delivery=unconfirmed. No hay
garantía de entrega ni replay. Un fallo puede perder eventos, pero no cambia
respuestas/commits. Backup ausente se informa como missing/degradado: S10 aún no
ha entregado evidencia de un punto verificado; no se inventa una fecha.
La correlación 9.3 usa este mismo transporte y retención. Con ENOSPC puede quedar
un registro incompleto, incluso unido al siguiente tras recuperar espacio; el
transporte best effort no garantiza registros íntegros ni entrega. El diagnóstico
de estado y los commits conservan sus contratos. La comprobación de privacidad
examina todos los bytes, también los fragmentos no parseables.

Aplicabilidad de CVE de la versión fijada, según
[Debian Security Tracker](https://security-tracker.debian.org/tracker/source-package/rsyslog):

| Hallazgo | Condición excluida |
| --- | --- |
| CVE-2026-93403 / CVE-2026-61548 | mmpstrucdata no se carga ni usa. Mensajes máximo 8 KiB. |
| CVE-2026-93402 | Sin mdtls/TLS. |
| CVE-2026-19654 | Sin imptcp. |
| CVE-2026-55556 | Sin imhttp/Basic Auth. |
| CVE-2026-78002 / TEMP-0000000-FAE309 | Sin replace(); Linux/amd64. |
| CVE-2026-92709 | Sin dynaFile; rutas literales fijas. |
| CVE-2015-3243 | Permisos efectivos 0700/0600 comprobados. |

Cambiar módulos, templates, permisos o transportes invalida esta evaluación.
La rotación usa [logrotate](https://github.com/logrotate/logrotate/blob/main/logrotate.8.in)
y el [callback estándar de tamaño de rsyslog](https://docs.rsyslog.com/doc/tutorials/log_rotation_fix_size.html),
sin implementar almacenamiento ni retención propios en Python. El supervisor solo
coordina esos comandos y sus locks.

### Configuración cerrada y límites iniciales

- Logs <= 256 MiB/siete días, registro <= 8 KiB; salida estructurada saneada.
- I/O y buffers acotados, fuera del event loop cuando puedan bloquear; cierre <= 5 s.
- Sink lleno/no disponible no cambia commits ni bloquea indefinidamente HTTP.
- Fallo visible mediante estado/código seguro; no reintento ni bucle de logs ilimitado.
- Archivos privados y acceso solo de API/tooling operador; sin puertos diagnósticos públicos.

Comando `ops diagnose --config /run/operator/config.json`, con el prefijo
Compose del [plan ejecutable](../../openspec/changes/port-compatible-platform/execution-plan.md#commands-and-safety-contract),
reporta salud diferenciada, pool y audit_degraded; backup missing hasta S10.
Sale 0 saludable, 1 degradado, 2 configuración/uso inválido. Las advertencias de
edad de backup a 3 h y objetivo RPO a 6 h quedan sujetas a la evidencia de S10.

La consulta por request_id usa grep estándar en el shell privado del colector,
con el mismo prefijo Compose y servicio diagnostics. Ejecutar primero `rotate`;
después `grep -hF '<hex32>' /logs/api.log*`, sustituyendo hex32 por el ID del
registro. El barrido de edad precede al acceso; la rotación puede acortar el
histórico. grep sale 0 con coincidencias, 1 sin ellas, 2 por error. No hay índice,
comando --request ni endpoint público. Los registros distinguen HTTP 409 de negocio,
503/500 con fallo DB y timeout externo, incluso con HTTP 202 ya confirmado.

## Evidencia para GO

`node scripts/platform.mjs verify diagnostics --case retention_and_failure`
ejecuta la matriz sintética con el colector estándar y Compose dev/ops, nginx
construido desde web/Dockerfile, API/PG reales y proveedor HTTP privado. Los
contenedores de prueba no publican puertos ni usan datos de la instancia personal.

La retención se comprueba en un volumen persistente, con archivo activo/rotados
de todas las fuentes, 32 rotaciones concurrentes, ingreso real, cuota lógica y
bloques físicos. Un control reciente y un archivo ajeno sobreviven al reinicio;
los vencidos desaparecen antes de readiness. Para ejercitar el timer sin esperar
una hora se adelanta solo el reloj monotónico del supervisor desechable y se
envejecen los fixtures con utime. No se cambia el reloj del host ni de rsyslog ni
se añade una configuración de pruebas al producto. También se detiene la API real
y se verifica el barrido horario sin su participación, seguido de su reinicio.

La fixture lleva el volumen de logs de Compose a ENOSPC y detiene el colector;
ambas escrituras HTTP atraviesan nginx y se observan confirmadas en PostgreSQL.
Se comprueba cierre inferior a cinco segundos, sin SIGKILL del contenedor,
buffer Docker de 1 MiB, cola rsyslog de 256 y estado tmpfs de 1 MiB sin spool.
`verify diagnostics --case operator_status` cubre además socket Unix lleno/ausente
y cierre HTTP. La captura Docker se comprueba con LogPath vacío, configuración
efectiva sin caché y rechazo específico de lectura por el driver; un fallo de
permisos o conexión no acredita ausencia de copia.

Los marcadores de URL/cookie/agente/nota/prompt/error de proveedor y SQL están
ausentes de los archivos activos/rotados y del estado. Se inspeccionan los streams
no vacíos, permisos, metadatos de health de Docker y el proveedor simulado; los
productores nativos conservan solo los campos fijos. nginx conserva sus enlaces
stdout/stderr y PG no crea current_logfiles ni directorios de logging. Los datos
de negocio y audit tienen sus propias políticas; no son copias diagnósticas.
Esto no ensaya un apagado físico del host ni acredita aceptación operativa GO.

| Caso sintético | Evidencia necesaria |
| --- | --- |
| Operación correcta y fallida | Correlacionar HTTP, DB y dependencia simulada por request_id, resultado y duración, sin exigir un grafo de spans. |
| DB caída/pool saturado/esquema incompatible | Readiness y diagnóstico diferenciados, fallos acotados y sin fallback a archivos. |
| Backup fallido/restore | Estado accionable y backup verificado identificable; restore mantiene diagnóstico operable. |
| Sink lleno/no disponible | HTTP y commits conservan contrato; buffers/cierre acotados y fallo observable. |
| Fixture sensible y retención | Marcadores ausentes de todos los sinks; cuota/edad también con archivo activo, reinicio y API detenida. |

Registrar comandos, revisión, entorno, resultados y límites en OpenSpec/CI, no en
otro informe permanente. Repetir lo aplicable tras corte en el cambio operativo.
La primera entrega no ofrece tracing distribuido, búsqueda avanzada ni históricos
métricos. Estas limitaciones no reducen audit, autorización ni integridad de datos.
