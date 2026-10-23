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

Implementar instrumentación OpenTelemetry compatible con FastAPI y cliente DB durante port/operación; fijar versiones y probar configuración. Foundation aporta salud/logs sintéticos y handoff, sin acreditar EV-08 ni añadir SDK/exportadores por esta revisión. Backend de almacenamiento, collector y visualización se eligen para el perfil local opcional, sin imponer Grafana/Tempo/Jaeger/Sentry o alterar los tres servicios de negocio web/api/db. Probes y métricas internos; interfaces de diagnóstico solo privadas/loopback según operación local.

Acotar buffers, exportación, timeouts y overhead. Un destino de telemetría caído no bloquea indefinidamente las peticiones ni cambia el resultado de un commit ya confirmado. Su fallo debe ser identificable sin un bucle ilimitado de logs. La política de fallo de audit se define separadamente en seguridad.

Concretar muestreo, cobertura, cotas, herramientas y superficie local de avisos antes de GO; acceso y máximos de retención quedan fijados arriba. Distinguir conflicto de negocio, indisponibilidad DB y fallo externo; conflictos esperados no son todos error interno. Exponer degradación de audit y respaldo fallido/antigüedad frente a objetivos de recuperación según [operación local](platform-operations.md#respaldo-coordinado), sin servicios externos ni SLA inventado.

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
