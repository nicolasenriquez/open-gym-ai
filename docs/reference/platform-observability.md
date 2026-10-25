---
type: Reference
title: Plataforma — observabilidad y tracing
description: Contrato objetivo de señales, tracing, privacidad y evidencia de operación para GO.
---
# Plataforma — observabilidad y tracing

**Estado:** contrato objetivo de EV-08, autorizado documentalmente el 2026-10-22; implementación y evidencias pendientes. Leer al instrumentar el backend, integrar dependencias o preparar operación/aceptación. [Arquitectura §12](../open-gym-evolution.architecture.md#12-gates-y-experimentos-antes-de-producción) gobierna GO; [seguridad](platform-security.md) gobierna acceso, secretos y audit. Esta referencia define resultados comprobables, no un runbook de herramientas ya instaladas.

## Señales y correlación

| Señal | Contrato objetivo |
| --- | --- |
| Logs | Eventos estructurados en stdout/stderr: instante, servicio/revisión, severidad, código estable y contexto de correlación; tamaño acotado y acceso definido. |
| Traces | Contexto de petición y spans de aplicación, DB y dependencias externas relevantes; propagación validada y errores/latencias interpretables. Un monolito también cruza estas fronteras. |
| Métricas | Peticiones/errores/duración por plantilla de ruta, espera/saturación del pool y resultado/antigüedad del backup; etiquetas de cardinalidad acotada. |
| Salud | Liveness del proceso y readiness de DB/esquema diferenciados; informar fallos sin exponer credenciales, datos privados o detalles innecesarios en endpoints públicos. |

`request_id` correlaciona una petición; `trace_id`/span conectan trabajo causal. Un ID de operación idempotente identifica un comando/reintento y el token de sesión autentica. Mantener sus contratos separados: telemetría no autoriza ni confirma un guardado. Definir tratamiento de contexto entrante malformado/no confiable y no aceptar headers de proxy de cualquier origen.

## Privacidad y acceso

Aplicar allowlist de atributos y revisar tanto instrumentación propia como automática. Excluir credenciales, cookies, tokens, notas, historial personal, prompts y parámetros SQL con valores. Usar rutas normalizadas y códigos estables en vez de URLs crudas, nombres de usuario o texto libre como etiquetas. No transportar datos personales en baggage ni considerar un hash de usuario como anonimato garantizado.

Diseño aprobado: diagnóstico privado accesible al operador local, sin envío a servicios externos. Logs hasta 7 días, trazas hasta 24 h y métricas hasta 7 días en perfil local opcional, con cotas de espacio documentadas y eliminación efectiva por edad. Cotas pueden acortar conservación; no prometer retener toda señal durante el máximo. Rotación Docker solo por tamaño no acredita borrado por antigüedad: probar también todas las copias duraderas. El historial de negocio, audit y recibos no dependen del muestreo ni de disponibilidad de traces. Para pruebas de filtración, usar contenido sensible sintético reconocible y comprobar su ausencia.

## Ejecución y fallos

Selección para esta entrega: OpenTelemetry API/SDK Python, instrumentación manual
en middleware FastAPI, Database y transporte HTTP coach/push; exporter local a
archivos JSONL acotados y lector CLI. No collector, base de series, dashboard ni
servicio externo: web/api/db siguen siendo los únicos servicios permanentes. Un
módulo local pequeño comparte escritura/rotación entre logs y señales opcionales;
no construir un framework de exporters. El perfil diagnóstico habilita spans y
snapshots métricos, sin abrir un puerto. Logs/estado operativo mínimo siguen
habilitados sin perfil. Foundation no acredita EV-08.

Dependencias a fijar durante delivery: `opentelemetry-api==1.45.1` y
`opentelemetry-sdk==1.45.1`. Metadata oficial PyPI inspeccionada: Python >=3.10,
API exacta 1.45.1 y semantic-conventions 0.66b1; lock/licencias/imagen Python 3.14
se prueban en entrega, no se instalaron aquí. No instalar autoinstrumentación
FastAPI/asyncpg ni exporters de red: sus defaults pueden capturar excepciones/SQL
con valores. Spans propios usan códigos de operación; instrumentación manual no
exime de demostrar cobertura HTTP→pool/TX/query→dependencia/job. Las dependencias
transitivas resueltas quedan en el lock e inventario, no en otra lista editable.

Se descartó usar collector fileexporter como solución automática de retención:
[documentación upstream](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/v0.163.0/exporter/fileexporter/README.md)
describe formato alpha y rotación por tamaño, no por edad del archivo activo.
No incorporarlo ni usar max_days como evidencia de borrado efectivo.

Acotar buffers, exportación, timeouts y overhead. Un destino de telemetría caído no bloquea indefinidamente las peticiones ni cambia el resultado de un commit ya confirmado. Su fallo debe ser identificable sin un bucle ilimitado de logs. La política de fallo de audit se define separadamente en seguridad.

### Configuración cerrada y límites iniciales

| Recurso | Límite de entrega y prueba |
| --- | --- |
| Logs | 7 d, 256 MiB totales; registro <= 8 KiB; archivo <= 4 MiB. |
| Traces opcionales | 24 h, 128 MiB; root sampling determinista 10 %, pruebas 100 %; 32 atributos/span, strings <= 128 caracteres. No prometer todos los errores con head sampling. |
| Métricas opcionales | Snapshot cada 60 s, 7 d, 64 MiB; <= 1000 series, labels solo servicio/plantilla/método/status-clase/código allowlisted. |
| Buffers | <= 2048 spans, lote <= 128, export cada 1 s en worker separado; cola de logs <= 1024; exceso descarta telemetría, nunca bloquea negocio. Export/file I/O fuera de event loop. |
| Fallos y cierre | Deadline export 1 s, cierre <= 5 s incluido vaciado; sin reintento infinito. Contador drops/export_failed y aviso seguro rate-limited 1/min. |
| Copias y acceso | Un volumen diagnóstico privado, directorios 0700/archivos 0600; solo API y tooling operador. Nada en backup de negocio, frontend, nginx o artefactos CI sin saneado. |

Retención se aplica por instante del evento, no mtime: sellar segmentos UTC cada
hora como máximo, retirar segmento antes de que su evento más antiguo supere la
edad límite; puede acortar conservación hasta una hora. Ejecutar sweep cada 60 s
mientras corre API y en inicio **antes** de habilitar lectura/exportación. Los tests
usan reloj controlado y margen de sweep explícito, incluyen archivo activo poco
usado, reinicio, reloj retrocedido (no extender edad) y cuota. Mantener metadato de
límite temporal monotónico observado; no renombrar datos viejos para rejuvenecerlos.
La tarea operativa horaria `diagnostics-retain` limpia incluso con API detenida;
host apagado no puede borrar físicamente: limpiar antes de volver a operar, sin
anunciar retención temporal garantizada durante apagado. No backups del volumen ni
copias Docker duraderas: `logging.driver: none` en combinación ops para los tres
servicios, access logs nginx off; diagnósticos app al sink privado y stdout/stderr
no capturado por Docker. DB/nginx mantienen probes/códigos de tooling y sin query/
URL logging persistente. Documentar esta diferencia respecto de `compose logs`.

Cada request genera request_id/trace_id internos aleatorios; ignorar traceparent,
baggage y X-Request-ID externos, sin reflejarlos ni añadir headers públicos nuevos.
Propagar solo dentro del proceso/job; no enviar contexto de diagnóstico a proveedores.
Allowlist: revisión/servicio, plantilla de ruta, método, resultado/código, duración,
operación DB sin SQL ni valores. No record_exception ni stack/message crudos.
Health pública conserva su cuerpo; live/ready/métricas permanecen internos.

Superficie operador: comando futuro `ops diagnose --config /run/operator/config.json`
con el prefijo Compose O del [plan ejecutable](../../openspec/changes/port-compatible-platform/execution-plan.md#commands-and-safety-contract)
imprime códigos, estado/redacted readiness, ocupación pool,
drops/audit_degraded y último backup verificado/antigüedad. `--trace <hex32>` permite
leer spans saneados del volumen, sin buscar por owner/nombre. Diagnóstico general
sale 0 saludable, 1 degradado, 2 configuración/error de uso. Último backup ausente,
fallido o edad > 3 h produce advertencia; > 6 h marca objetivo RPO incumplido.
No depende del muestreo ni del perfil para esas señales mínimas. No abre rutas
públicas ni se confunde con audit/historia. Errores de negocio 409 se distinguen de
5xx DB y timeout/proveedor; éxito de commit no cambia por fallo del sink.

## Evidencia para GO

| Caso sintético | Evidencia necesaria |
| --- | --- |
| Petición correcta y fallida | Localizar la operación por correlación y seguir spans hasta DB/dependencia, con revisión/servicio identificables. |
| DB caída, pool saturado o esquema incompatible | Señal/readiness y diagnóstico diferenciados; fallos acotados sin éxito aparente o fallback a archivos. |
| Conflicto Training y dependencia externa simulada | Distinguir resultados de negocio, latencia y fallo externo sin invocar cuentas/proveedores reales. |
| Backup fallido/restore de prueba | Estado y señal accionables; aplicación restaurada con acceso y diagnóstico operables. GO conserva los requisitos de recuperación de arquitectura §11. |
| Exportador no disponible | Peticiones y commits mantienen su contrato; timeout/buffers y fallo de exportación verificables. |
| Fixture sensible | Logs, métricas, spans y errores no contienen marcadores personales/secretos; inspeccionar también atributos automáticos. |

Registrar comandos/casos, revisión, entorno, configuración de muestreo/exportación, resultados y rutas de evidencia saneada. Demostrar en ensayo previo y verificar de nuevo tras corte según GO. Instalar un SDK, mostrar un dashboard o tener `/health` en verde no satisface EV-08.

La trazabilidad de entrega sigue requisito EV → escenario OpenSpec → prueba → evidencia; la trazabilidad histórica/audit sigue su contrato de seguridad/dominio. Las tres deben poder distinguirse al revisar una incidencia.

Referencias: [señales OpenTelemetry](https://opentelemetry.io/docs/concepts/signals/), [propagación de contexto](https://opentelemetry.io/docs/concepts/context-propagation/), [datos sensibles](https://opentelemetry.io/docs/security/handling-sensitive-data/). AI Tutor sirve como referencia de lifecycle/logging, no como evidencia de un despliegue completo de tracing en OpenGym.
