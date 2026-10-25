---
type: Reference
title: Plataforma — observabilidad y tracing
description: Contrato objetivo de señales, tracing, privacidad y evidencia de operación para GO.
---
# Plataforma — observabilidad y tracing

**Estado:** contrato objetivo revisado de EV-08 para operación personal local.
No describe tooling entregado ni resultados ejecutados. La revisión sustituye el
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
implementar S9 seleccionar y fijar la herramienta, su configuración de cuota/edad
y su política para archivos activos; es un prerrequisito pendiente, no una selección
ni una prueba acreditada por este documento. Si no satisface la política, detener
ese slice y revisar la decisión, no añadir silenciosamente un subsistema propio.

Los límites se verifican con archivos activos y rotados, reinicio, API detenida y
espacio agotado. La tarea horaria de retención usa el mismo mecanismo. Host apagado
no puede borrar físicamente: limpiar expirados antes de reanudar acceso diagnóstico.
No reemplazar `compose logs` por un sink propio sin declarar cómo se diagnostican
también nginx y PostgreSQL; resolver sus copias y posibles datos sensibles en S9.

### Configuración cerrada y límites iniciales

- Logs <= 256 MiB/siete días, registro <= 8 KiB; salida estructurada saneada.
- I/O y buffers acotados, fuera del event loop cuando puedan bloquear; cierre <= 5 s.
- Sink lleno/no disponible no cambia commits ni bloquea indefinidamente HTTP.
- Fallo visible mediante estado/código seguro; no reintento ni bucle de logs ilimitado.
- Archivos privados y acceso solo de API/tooling operador; sin puertos diagnósticos públicos.

Comando futuro `ops diagnose --config /run/operator/config.json`, con el prefijo
Compose del [plan ejecutable](../../openspec/changes/port-compatible-platform/execution-plan.md#commands-and-safety-contract),
reporta salud diferenciada, pool, audit_degraded y último backup verificado.
`--request <hex32>` consulta registros saneados de una operación, nunca owner/nombre.
Sale 0 saludable, 1 degradado, 2 configuración/uso inválido. Backup ausente/fallido
o edad > 3 h advierte; > 6 h marca objetivo RPO incumplido. No depende de sampling,
perfil opcional ni un exporter. Distingue 409 de negocio, 5xx DB y timeout externo.

## Evidencia para GO

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
