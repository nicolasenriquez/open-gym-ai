---
type: PRD
title: OpenGym Evolution — PRD de modernización de plataforma
description: Resultados y aceptación de plataforma antes de Recovery, Garmin e IA ampliada.
---
# OpenGym Evolution — PRD de modernización de plataforma

**Estado:** dirección y cleanup documental autorizados el 2026-10-22. Primera entrega: Python/FastAPI/PostgreSQL con paridad, seguridad y operación verificables. La autorización actual es documental; implementación, OpenSpecs, migración y despliegue se concretan por solicitudes posteriores.

**Fuentes:** solicitud del promotor, revisión del código y documentación recogida en el informe, [arquitectura](open-gym-evolution.architecture.md) y [PRD de Recovery](open-gym-recovery.prd.md). Este documento define intención, alcance y aceptación de plataforma; arquitectura define mecanismos y gates. Recovery conserva la autoridad sobre sus requisitos funcionales.

## Resumen ejecutivo

OpenGym Evolution busca una base mantenible y operable sobre la que ampliar la herramienta sin perder el acceso, los datos ni las capacidades actuales. La primera entrega sustituye la aplicación servidor heredada, preservando Training, autenticación, catálogo, medios, administración, notificaciones, coach y MCP dentro de sus contratos vigentes.

Por decisión del promotor, la plataforma objetivo utiliza Python/FastAPI y PostgreSQL, con desarrollo y despliegue basados en contenedores. Es una restricción estratégica del proyecto, no una prueba de que ese stack sea por sí solo más seguro o de que Node sea inadecuado. La arquitectura desarrolla la transición y sus comprobaciones.

**Orden obligatorio:** plataforma completada y aceptada → Recovery → Garmin Connect → ampliaciones de IA. No se comienza la implementación funcional de las etapas posteriores mientras la plataforma siga incompleta. Sus alcances específicos se definirán cuando corresponda; no hay fechas comprometidas.

## 1. Problema

El promotor quiere ampliar OpenGym con seguimiento personal de recuperación, datos de Garmin y capacidades de IA. Actualmente las responsabilidades de datos y sus consumidores están acopladas a archivos y a módulos JavaScript compartidos. Añadir funciones mientras se sustituye esa base puede multiplicar contratos transitorios y dificultar distinguir una regresión de un cambio funcional.

La necesidad inmediata es conservar una herramienta utilizable y contar con una base común de desarrollo, verificación, despliegue y recuperación antes de extenderla. No se han medido pérdidas de productividad, fallos de datos o costes que permitan atribuir un beneficio cuantitativo a la migración.

## 2. Evidencia y límites

| Evidencia | Fuente y alcance |
| --- | --- |
| Prioridad explícita de completar Python/FastAPI/PostgreSQL antes de nuevas funcionalidades | Solicitud del usuario y autorización de estos ajustes documentales el 2026-10-22. |
| Identidad y Training servidor almacenados en archivos; consumidores adicionales leen esos datos | `api/server.js`, `api/coach/jobs.js` y `mcp/src/state.js`, inspeccionados en la revisión. Es evidencia de acoplamiento, no de pérdida de datos. |
| Cliente con persistencia local, sincronización y sesión activa propias | `frontend/src/store/useStore.js`; conservar pantallas no basta para preservar comportamiento. |
| PostgreSQL Foundation completada como ensayo separado en Node | [Tracker archivado](../openspec/changes/archive/2026-10-22-add-postgres-foundation/tasks.md) y [README Foundation](../api/foundation/README.md). No sustituye la aplicación ni demuestra el backend Python. |
| AI Tutor ofrece patrones de desarrollo y operación pertinentes | [Fuentes y límites](audit/evolution-architecture-evidence-2026-10-22.md#23-ai-tutor-como-referencia); no acredita que su topología o dominio deban copiarse. |

**Hipótesis:** una plataforma modular y reproducible facilitará las ampliaciones posteriores. La aceptación inicial solo puede demostrar continuidad funcional, recuperación y operabilidad; una mejora de productividad exige observación posterior. No se presenta como demanda comercial validada.

## 3. Tesis: por qué hacerlo primero

La transición es una inversión deliberada del promotor antes de ampliar el producto. Hacerla con las capacidades actuales permite fijar una referencia de compatibilidad y un cierre verificable sin mezclar el port con funcionalidades todavía no implementadas.

La alternativa de mantener el sistema actual continúa siendo técnicamente posible. La prioridad elegida cambia el orden de inversión; no demuestra un defecto intrínseco de Node ni reemplaza la validación posterior de utilidad de Recovery.

## 4. Hipótesis falsable

**Creemos que** completar una base de plataforma común, preservando los contratos actuales y con procedimientos reproducibles, permitirá al promotor operar OpenGym y comenzar nuevas capacidades sin depender del backend sustituido ni de preparaciones manuales no documentadas.

**Sabremos que se cumple la aceptación inicial si**, durante el ensayo de transición y la verificación posterior al corte, los recorridos inventariados siguen funcionando, los datos conservan su significado, otra instalación limpia puede ejecutarse con las instrucciones y la recuperación se demuestra en el entorno acordado.

**La hipótesis queda cuestionada si** la app requiere volver al backend sustituido para una capacidad incluida, hay pérdidas o cambios históricos no autorizados, se depende de datos/carpetas personales no documentados o no se puede restaurar y continuar de forma controlada. Cambiar de lenguaje sin resolver esas condiciones no completa la entrega.

La ventana es la aceptación de esta entrega, sin plazo de calendario inventado. No se exige implementar Recovery para demostrar la plataforma.

## 5. Usuario objetivo y Jobs to Be Done

El usuario principal es el promotor que desarrolla, mantiene y opera su instancia; las personas y clientes existentes deben conservar el acceso a sus datos y entrenamiento.

- **Al modificar la herramienta**, quiero comprobar que las capacidades actuales conservan su comportamiento antes de añadir otras.
- **Al preparar una instalación**, quiero ejecutarla desde instrucciones reproducibles sin depender de la máquina original del desarrollador.
- **Al actualizar o recuperar la instancia**, quiero conservar los datos y saber cómo proceder ante un fallo, sin resultados silenciosamente incompletos.
- **Al terminar la transición**, quiero que el sistema nuevo sea suficiente para operar la app y que exista una condición clara para comenzar Recovery.

No se construye en esta entrega una plataforma clínica, un servicio comercial multiempresa ni una infraestructura distribuida de alta disponibilidad.

## 6. Entrega mínima completa

| ID | Resultado requerido |
| --- | --- |
| EV-01 | Preservar las capacidades actuales inventariadas: identidad/acceso, Training y sincronización/offline, catálogo, medios, administración, notificaciones, coach, MCP e import/export. Revalidar autenticación, permisos por propietario/acción, revocación y auditoría durante el traspaso; diferencias o limitaciones de compatibilidad se resuelven expresamente. |
| EV-02 | Conservar identidad, propiedad y significado del historial y configuración migrados; proteger los datos pendientes en clientes. Ninguna migración transforma objetivos o cálculos en resultados realizados ni altera el historial por accidente. |
| EV-03 | Construir, iniciar, detener y verificar el stack objetivo desde un checkout limpio con instrucciones reproducibles y runtime en contenedores. Las verificaciones necesarias tienen una superficie documentada y reproducible. |
| EV-04 | Disponer de procedimientos de respaldo, restauración y tratamiento de fallos comprobados para el alcance operativo acordado, incluyendo los elementos necesarios fuera de la base de datos. No prometer recuperación o plazos que no se hayan demostrado. |
| EV-05 | Completar la sustitución del backend y persistencia seleccionados: el destino funciona con una autoridad clara y los consumidores dejan de depender del almacenamiento retirado. Conservar una versión recuperable no equivale a mantener una dependencia activa del sistema anterior. |
| EV-06 | Mantener documentación y artefactos soportados coherentes con lo entregado; identificar expresamente alternativas legacy o fuera del soporte objetivo. |
| EV-07 | Comenzar la implementación de Recovery y las integraciones posteriores solo después de la aceptación de plataforma. La evolución funcional no se usa para compensar una migración incompleta. |
| EV-08 | Poder diagnosticar fallos y latencias, correlacionar operaciones y reconocer indisponibilidad o saturación con señales verificables, acceso/retención definidos y sin exponer datos privados. Un fallo del destino de telemetría mantiene el contrato de las operaciones; auditoría e historial conservan sus garantías propias. |

**Restricciones confirmadas:** backend Python/FastAPI y PostgreSQL; conservar el frontend y las capacidades útiles existentes; desarrollo y despliegue con contenedores guiados por los patrones pertinentes de AI Tutor. Las versiones, bibliotecas auxiliares, esquema, contratos de transición y arquitectura de pruebas corresponden a arquitectura y a las especificaciones posteriores.

La migración es costosa de revertir después de recibir datos nuevos. Concretar preservación y recuperación antes del uso real; un backend parcial no satisface la entrega completa.

## 7. Criterios de éxito y fracaso

| Resultado | Objetivo | Comprobación y referencia |
| --- | --- | --- |
| Continuidad funcional | Capacidades incluidas operativas con sus contratos o diferencias expresamente resueltas | Matriz y evidencias de paridad de arquitectura §§9 y 12; EV-01. |
| Seguridad conservada y comprobada | Acceso y acciones limitados al actor autorizado, revocación y eventos audit interpretables | Casos de seguridad antes del corte y tras retirada, referenciados desde arquitectura; EV-01. |
| Continuidad de datos | Datos interpretables y sin pérdida o sobrescritura silenciosa | Ensayo de migración, clientes pendientes y verificación tras corte; EV-02. |
| Instalación/operación reproducibles | La app funciona desde un checkout limpio conforme a las instrucciones | Evidencia de operación independiente de la máquina original; EV-03/EV-06. |
| Recuperación comprobada | Se puede restaurar el alcance acordado y continuar con acceso y datos coherentes | Ensayo completo y límites documentados; EV-04. |
| Sustitución completa | El backend nuevo sirve la app y sus consumidores sin accesos activos al almacenamiento sustituido | Verificación después de retirada técnica; EV-05. |
| Secuencia respetada | Recovery no comienza con la plataforma pendiente | Aceptación de plataforma registrada antes del primer cambio funcional; EV-07. |
| Diagnóstico operativo | Se puede localizar una operación y distinguir fallo interno/dependencia, conflicto y saturación sin revelar datos privados | Casos sintéticos y verificación posterior al corte conforme a GO; EV-08. |

El cierre requiere **todos** estos resultados. No exige ausencia de toda deuda histórica: identificar la base y demostrar que el cambio no introduce regresiones dentro del alcance. Levantar contenedores o importar filas por sí solos no acredita aceptación.

**Fracaso/revisión:** pérdida de acceso/datos, acciones no autorizadas, filtración por telemetría, contratos rotos, dependencia permanente del backend anterior u operación, diagnóstico o restauración no demostrados. La [arquitectura §12](open-gym-evolution.architecture.md#12-gates-y-experimentos-antes-de-producción) contiene las condiciones técnicas de cierre.

## 8. Exclusiones y entregas posteriores

- Nuevas funciones de Recovery/kinesiología, Garmin Connect y ampliaciones del coach o IA. Preservar el coach actual sí pertenece a EV-01.
- Rediseño o sustitución del frontend, conversión general a TypeScript, cambio de gestor frontend o modificación de reglas de progresión sin una necesidad independiente.
- Normalización completa de Training, microservicios, sistemas de colas, búsqueda vectorial o frameworks de agentes por anticipación.
- Nuevos builds nativos, publicación en tiendas o despliegue definitivo en VPS como requisito del primer ensayo local. La compatibilidad de clientes existentes debe tratarse expresamente.
- Garantías clínicas, de alta disponibilidad, rendimiento o RPO/RTO no acordadas y verificadas.

**Secuencia posterior:** Recovery conforme a su PRD y validación de utilidad; después Garmin con alcance/acceso a datos verificados; posteriormente ampliaciones de IA con casos de uso, consentimiento y evaluación. Voz, análisis avanzado y offline de Recovery se evaluarán cuando exista necesidad. No se activan por preparar la plataforma.

## 9. Pendientes y handoff

| Pendiente | Dónde se resuelve | Condiciona |
| --- | --- | --- |
| Versiones/entorno objetivo y herramientas auxiliares | Arquitectura y especificación de Foundation Python | Evidencia técnica reproducible y operación objetivo. |
| Matriz exacta de capacidades y clientes compatibles | Caracterización del sistema y handoff de migración | Aceptación de paridad y alcance de EV-01. |
| Conservación de sesiones, adaptación de credenciales y acceso de consumidores | Arquitectura y pruebas de transición | Continuidad de acceso; no autoriza sustituir la experiencia de autenticación automáticamente. |
| Viabilidad de cada proveedor/runtime del coach y contrato MCP | Arquitectura y ensayos acotados | Retirada completa sin pérdida de capacidades. |
| Inventario real, mantenimiento, recuperación y plazos aceptables | Plan operativo previo al corte | Migración de datos reales y aceptación EV-02/EV-04. |
| Señales, cobertura, acceso, retención y tratamiento de fallos de diagnóstico | Arquitectura y contrato de observabilidad | Aceptación EV-08/GO, sin seleccionar herramientas en este PRD. |

**Handoff:** la [arquitectura](open-gym-evolution.architecture.md) desarrolla esta dirección y conserva los requisitos funcionales del [PRD Recovery](open-gym-recovery.prd.md) para la entrega posterior. [Foundation archivada](../openspec/changes/archive/2026-10-22-add-postgres-foundation/proposal.md) es evidencia sintética histórica de Node; no acredita el stack Python ni cierra esta entrega.

Las especificaciones posteriores deben aportar evidencia de cada resultado; este PRD no constituye una validación ejecutada.
