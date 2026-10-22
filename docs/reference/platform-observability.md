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

Definir acceso, almacenamiento, retención y eliminación por señal. El historial de negocio, audit requerido y recibos de guardado no dependen del muestreo ni de la disponibilidad de traces. Para pruebas de filtración, usar exclusivamente contenido sensible sintético reconocible y comprobar que no aparece en los artefactos emitidos.

## Ejecución y fallos

Evaluar instrumentación OpenTelemetry compatible con FastAPI y el cliente DB durante Foundation/port; fijar versiones y probar la configuración elegida. Backend de almacenamiento, collector y visualización se seleccionan según necesidad, como herramientas de ensayo o perfil opcional. Este contrato no impone Grafana/Tempo/Jaeger/Sentry ni altera por sí mismo los tres servicios de aplicación `web`/`api`/`db`.

Acotar buffers, exportación, timeouts y overhead. Un destino de telemetría caído no bloquea indefinidamente las peticiones ni cambia el resultado de un commit ya confirmado. Su fallo debe ser identificable sin un bucle ilimitado de logs. La política de fallo de audit se define separadamente en seguridad.

Concretar muestreo, cobertura de operaciones, retención, acceso y canal de alertas antes de GO. Las señales deben distinguir conflicto de negocio, indisponibilidad DB y fallo externo; los conflictos esperados no se clasifican todos como error interno. Acordar umbrales y objetivos de servicio con el entorno: esta documentación no inventa un SLA o garantía de recuperación.

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
