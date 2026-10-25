---
type: PRD
title: OpenGym Evolution — PRD de modernización de plataforma
description: Resultados y aceptación de plataforma antes de Recovery, Garmin e IA ampliada.
---
# OpenGym Evolution — PRD de modernización de plataforma

**Estado:** dirección y cleanup documental autorizados el 2026-10-22. Primera entrega: Python/FastAPI/PostgreSQL con paridad, seguridad y operación verificables. La presente revisión es documental; la ejecución de tareas, migración y despliegue se concretan por solicitudes separadas. El OpenSpec activo conserva su estado y evidencia de entrega.

**Ampliación documental:** el promotor solicita concretar una arquitectura modular por vertical slices inspirada en AI Tutor, con contratos y lógica localizados por funcionalidad y orden equivalente en frontend. Se conserva el frontend actual; esta revisión ajusta PRD, arquitectura y OpenSpec activo, sin implementar código ni ampliar permisos de ejecución anteriores.

**Diseño consolidado confirmado:** esquema compatible de las capacidades actuales y operación personal local con Compose, conservando el legado como referencia. [Esquema SQL](reference/platform-schema.md), [seguridad](reference/platform-security.md) y [operación local](reference/platform-operations.md) concretan tablas, relaciones, índices, roles y recuperación. La aprobación autoriza esta documentación y sus OpenSpecs, no implementación, instalaciones, migraciones ni corte. Foundation conserva su alcance sintético y el trabajo ya registrado.

**Fuentes:** solicitud del promotor, revisión del código y documentación recogida en el informe, [arquitectura](open-gym-evolution.architecture.md) y [PRD de Recovery](open-gym-recovery.prd.md). Este documento define intención, alcance y aceptación de plataforma; arquitectura define mecanismos y gates. Recovery conserva la autoridad sobre sus requisitos funcionales.

## Resumen ejecutivo

OpenGym Evolution busca una base mantenible y operable sobre la que ampliar la herramienta sin perder el acceso, los datos ni las capacidades actuales. La primera entrega sustituye la aplicación servidor heredada, preservando Training, autenticación, catálogo, medios, administración, notificaciones y coach dentro del alcance compatible expresamente acordado.

**Excepción aprobada Q6:** conservar coach local y proveedores HTTP actuales; Claude Agent SDK y Codex CLI quedan temporalmente no disponibles en la primera entrega Python, sin fallback Node ni cambio automático a otro proveedor. Conservar selección/configuración no secreta e historial, proteger originales y comunicar la limitación al cliente/administración; no anunciar paridad completa con esos proveedores. La evolución agéntica (incluido un eventual LangChain/LangGraph) se decide después, sin introducir dependencias anticipadas. El [diseño del port](../openspec/changes/port-compatible-platform/design.md#11-q6-migración-segura-antes-de-evolución-agéntica) concreta esta excepción.

Por decisión del promotor, la plataforma objetivo utiliza Python/FastAPI y PostgreSQL, con desarrollo y despliegue basados en contenedores. Es una restricción estratégica del proyecto, no una prueba de que ese stack sea por sí solo más seguro o de que Node sea inadecuado. La arquitectura desarrolla la transición y sus comprobaciones.

**Checkpoints de entrega:** port funcional → operación local recuperable → corte/retirada y aceptación en cambio operativo separado. El OpenSpec activo entrega los dos primeros y ensaya el tercero con fixtures; sus obligaciones reales se transfieren explícitamente antes de archive. Cerrar ese cambio no acepta la plataforma.

**Orden obligatorio:** plataforma completada y aceptada → Recovery → Garmin Connect → ampliaciones de IA. No se comienza la implementación funcional de las etapas posteriores mientras la plataforma siga incompleta. Sus alcances específicos se definirán cuando corresponda; no hay fechas comprometidas.

## 1. Problema

El promotor quiere ampliar OpenGym con seguimiento personal de recuperación, datos de Garmin y capacidades de IA. Actualmente las responsabilidades de datos y sus consumidores están acopladas a archivos y a módulos JavaScript compartidos. Añadir funciones mientras se sustituye esa base puede multiplicar contratos transitorios y dificultar distinguir una regresión de un cambio funcional.

La necesidad inmediata es conservar una herramienta utilizable y contar con una base común de desarrollo, verificación, despliegue y recuperación antes de extenderla. No se han medido pérdidas de productividad, fallos de datos o costes que permitan atribuir un beneficio cuantitativo a la migración.

## 2. Evidencia y límites

| Evidencia | Fuente y alcance |
| --- | --- |
| Prioridad explícita de completar Python/FastAPI/PostgreSQL antes de nuevas funcionalidades | Solicitud del usuario y autorización de estos ajustes documentales el 2026-10-22. |
| Identidad y Training servidor almacenados en archivos; consumidores adicionales leen esos datos | `api/server.js` y `api/coach/jobs.js`, inspeccionados en la revisión. Es evidencia de acoplamiento, no de pérdida de datos. |
| Cliente con persistencia local, sincronización y sesión activa propias | `frontend/src/store/useStore.js`; conservar pantallas no basta para preservar comportamiento. |
| PostgreSQL Foundation completada como ensayo separado en Node | [Tracker archivado](../openspec/changes/archive/2026-10-22-add-postgres-foundation/tasks.md) y [README Foundation](../api/foundation/README.md). No sustituye la aplicación ni demuestra el backend Python. |
| AI Tutor ofrece patrones de desarrollo y operación pertinentes | [Fuentes y límites](research/evolution-architecture-evidence.md#23-ai-tutor-como-referencia); no acredita que su topología o dominio deban copiarse. |

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
- **Al trabajar en una capacidad**, quiero encontrar juntos sus contratos, reglas y operaciones, reconocer sus componentes cliente y comprobar el recorrido sin reconstruir mentalmente toda la aplicación.
- **Al preparar una instalación**, quiero ejecutarla desde instrucciones reproducibles sin depender de la máquina original del desarrollador.
- **Al actualizar o recuperar la instancia**, quiero conservar los datos y saber cómo proceder ante un fallo, sin resultados silenciosamente incompletos.
- **Al terminar la transición**, quiero que el sistema nuevo sea suficiente para operar la app y que exista una condición clara para comenzar Recovery.

No se construye en esta entrega una plataforma clínica, un servicio comercial multiempresa ni una infraestructura distribuida de alta disponibilidad.

## 6. Entrega mínima completa

| ID | Resultado requerido |
| --- | --- |
| EV-01 | Preservar las capacidades actuales inventariadas: identidad/acceso, Training y sincronización/offline, catálogo, medios, administración, notificaciones, coach e import/export. Revalidar autenticación, permisos por propietario/acción, revocación y auditoría durante el traspaso; diferencias o limitaciones de compatibilidad se resuelven expresamente. |
| EV-02 | Conservar identidad, propiedad y significado del historial y configuración migrados; proteger los datos pendientes en clientes. Ninguna migración transforma objetivos o cálculos en resultados realizados ni altera el historial por accidente. |
| EV-03 | Construir, iniciar, detener y verificar el stack objetivo desde un checkout limpio con instrucciones reproducibles y runtime en contenedores. Distinguir desarrollo, ensayo/CI y operación; demostrar build correcto sin caché y reutilización de dependencias cuando no cambian, sin prometer tiempos no medidos. Las verificaciones necesarias tienen una superficie documentada y reproducible. |
| EV-04 | Disponer de procedimientos de respaldo, restauración y tratamiento de fallos comprobados para el alcance operativo acordado, incluyendo los elementos necesarios fuera de la base de datos. No prometer recuperación o plazos que no se hayan demostrado. |
| EV-05 | Completar la sustitución del backend y persistencia seleccionados: el destino funciona con una autoridad clara y los consumidores dejan de depender del almacenamiento retirado. Preservar como biblioteca neutral el código JavaScript que aún necesite el frontend, sin depender de la API Node retirada. Conservar una versión recuperable no equivale a mantener una dependencia activa del sistema anterior. |
| EV-06 | Mantener documentación y artefactos soportados coherentes con lo entregado; identificar expresamente alternativas legacy o fuera del soporte objetivo. |
| EV-07 | Comenzar la implementación de Recovery y las integraciones posteriores solo después de la aceptación de plataforma. La evolución funcional no se usa para compensar una migración incompleta. |
| EV-08 | Diagnosticar fallos y latencias mediante logs estándar estructurados, request_id y estado puntual de salud/DB/pool/backup, con acceso/retención verificados y sin datos privados. Fallo del sink no altera operaciones; auditoría e historial mantienen sus garantías. Tracing avanzado, OpenTelemetry, exporters propios e históricos métricos quedan diferidos. |
| EV-09 | Localizar cada capacidad portada en un módulo con contratos, reglas, operaciones y acceso a datos de propiedad explícita, y reconocer su recorrido en el frontend conservado. Demostrar dependencias controladas, responsabilidad transaccional entre operaciones y pruebas por caso de uso; reorganizar carpetas sin evidencia de comportamiento no satisface el resultado. |

**Restricciones confirmadas:** backend Python/FastAPI y PostgreSQL; conservar el frontend y las capacidades útiles existentes; desarrollo y despliegue con contenedores guiados por los patrones pertinentes de AI Tutor. Las versiones, bibliotecas auxiliares, esquema, contratos de transición y arquitectura de pruebas corresponden a arquitectura y a las especificaciones posteriores.

La organización objetivo es un monolito modular por funcionalidad. La [propuesta de módulos y vertical slices](reference/platform-modularity.md) concreta responsabilidades, contratos, componentes frontend, dependencias y slice piloto. Conservar el frontend permite mejoras internas acotadas al área intervenida, con pruebas; no exige trasladar todos sus archivos ni sustituir su estado local, estilos o herramientas.

La [responsabilidad por fase](reference/platform-modularity.md#responsabilidad-y-aceptación-por-fase) asigna biblioteca JS compartida, caché, imagen final, ambientes y transacciones a Foundation, port y operación. Foundation aporta evidencia sintética y handoff; port conserva capacidades; operación entrega imágenes/ambientes soportados y verifica corte/retirada. No se acredita el resultado final con una imagen de pruebas ni se retira soporte de clientes/plataformas silenciosamente.

La migración es costosa de revertir después de recibir datos nuevos. Concretar preservación y recuperación antes del uso real; un backend parcial no satisface la entrega completa.

### Decisiones de aceptación consolidadas

- EV-01/02/05: preservar IDs, alias y credenciales heredadas, Training completo y pendientes cliente. Conservar sesiones cuando sea seguro/compatible; excepción de reautenticación solo documentada y demostrada. El borrado conserva invitaciones consumidas/auditoría y verifica limpieza externa; diferencias no representables fielmente bloquean el corte.
- EV-03/06: primera operación personal en Compose, acceso desde el mismo computador, PostgreSQL privado y aceptación inicial Linux/amd64. Acceso LAN/remoto y arm64 requieren configuración/verificación propias; tratar expresamente clientes existentes antes de cortar.
- EV-04: objetivos RPO 6 h/RTO 24 h pendientes de prueba. Backup con pausa controlada de API/escritores, cada 3 h, al arranque si vencido y antes de migrar; cifrado, retención 30 días, disco independiente/clave separada y restore aislado mensual. Wrapper host requiere Docker/Compose y Node 22+, no Node en API. Medir pausa y preservar pendientes. Acceso restaurado por continuidad con evidencia o nueva vía local autorizada, sin rehabilitar credenciales dudosas ni elevar roles; definir autorización/entrega privada antes de implementarla. Conservar origen/release/configuración protegidos al menos 30 días tras corte, sin borrado automático.
- EV-08: diagnóstico privado, logs hasta 7 días/256 MiB con tooling estándar de rotación/retención seleccionado antes del slice. Correlación mínima, salud y estado backup; no exporter propio ni perfil de trazas/métricas. Audit conserva fallo observable sin invalidar éxito y no se confunde con logs.

Los detalles técnicos tienen un único propietario en las referencias enlazadas; este PRD no incorpora DDL ni acredita objetivos medidos. El [OpenSpec planificado de port y operación](../openspec/changes/port-compatible-platform/proposal.md) aporta requisitos, escenarios y tareas pendientes después de Foundation, manteniendo Recovery fuera.

## 7. Criterios de éxito y fracaso

| Resultado | Objetivo | Comprobación y referencia |
| --- | --- | --- |
| Continuidad funcional | Capacidades incluidas operativas con sus contratos o diferencias expresamente resueltas | Matriz y evidencias de paridad de arquitectura §§9 y 12; EV-01. |
| Seguridad conservada y comprobada | Acceso y acciones limitados al actor autorizado, revocación y eventos audit interpretables | Casos de seguridad antes del corte y tras retirada, referenciados desde arquitectura; EV-01. |
| Continuidad de datos | Datos interpretables y sin pérdida o sobrescritura silenciosa | Ensayo de migración, clientes pendientes y verificación tras corte; EV-02. |
| Instalación/operación reproducibles | La app funciona desde un checkout limpio conforme a las instrucciones, con ambientes explícitos e imagen entregable identificada | Matriz de build/caché, inventario runtime y combinaciones de ambientes verificadas en sus fases; EV-03/EV-06 y GO. |
| Recuperación comprobada | Se puede restaurar el alcance acordado y continuar con acceso y datos coherentes | Ensayo completo y límites documentados; EV-04. |
| Sustitución completa | El backend nuevo sirve la app y sus consumidores sin accesos activos al almacenamiento sustituido | Verificación después de retirada técnica; EV-05. |
| Secuencia respetada | Recovery no comienza con la plataforma pendiente | Aceptación de plataforma registrada antes del primer cambio funcional; EV-07. |
| Diagnóstico operativo | Correlacionar registros y distinguir fallo interno/dependencia, conflicto, saturación y antigüedad del backup sin datos privados; sin exigir spans | Casos sintéticos, retención de todas las copias y verificación tras corte conforme a GO; EV-08. |
| Modularidad verificable | Cada capacidad portada tiene propietario y contrato localizables, dependencias explícitas y recorrido cliente probado cuando corresponde | Slice piloto Training y revisión de los módulos portados según la propuesta modular, dentro de GP/GO/G3; EV-09. |

El cierre requiere **todos** estos resultados. No exige ausencia de toda deuda histórica: identificar la base y demostrar que el cambio no introduce regresiones dentro del alcance. Levantar contenedores o importar filas por sí solos no acredita aceptación.

**Fracaso/revisión:** pérdida de acceso/datos, acciones no autorizadas, filtración por telemetría, contratos rotos, dependencia permanente del backend anterior u operación, diagnóstico o restauración no demostrados. La [arquitectura §12](open-gym-evolution.architecture.md#12-gates-y-experimentos-antes-de-producción) contiene las condiciones técnicas de cierre.

## 8. Exclusiones y entregas posteriores

- Nuevas funciones de Recovery/kinesiología, Garmin Connect y ampliaciones del coach o IA. Preservar el coach local/HTTP actual y hacer explícita la indisponibilidad SDK/CLI aprobada en Q6 sí pertenece a EV-01.
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
| Correspondencia de módulos, contratos y componentes por recorrido | Propuesta modular y OpenSpecs de Foundation/port; evidencia del slice piloto | EV-09; Foundation aporta estructura parcial, no aceptación de módulos funcionales. |
| Biblioteca JS neutral, transacciones colaborativas y entrega operativa | Responsabilidad por fase de la propuesta modular; escenarios Foundation y posteriores OpenSpecs de port/operación | EV-01/02/03/05/06/09; no retirar fuentes compartidas ni aceptar operación sin verificar sus imágenes, ambientes y soporte. |
| Validar el esquema y continuidad de acceso ya diseñados | Esquema SQL aprobado, seguridad y OpenSpec de port; DDL y pruebas pendientes | Alias/credenciales compatibles, proyecciones Training, RLS demostrados; no solo tablas dibujadas. |
| Compatibilidad del coach local/HTTP y excepción SDK/CLI Q6 | Arquitectura, port y ensayos acotados | Retirada completa con contratos admitidos verificados y proveedores diferidos explícitamente no disponibles. |
| Inventario real y demostrar operación/recuperación aceptadas | Operación local y OpenSpec de port/operación; destino físico y ensayo previos al corte | Migración real y EV-02/04: objetivos acordados no equivalen a garantías; bloqueos de reconciliación y clientes resueltos. |
| Implementar/verificar diagnóstico privado y su retención | Contrato de observabilidad y operación | EV-08/GO: instrumentación, cotas y eliminación real pendientes; sin elegir herramientas en este PRD. |

**Handoff:** la [arquitectura](open-gym-evolution.architecture.md) desarrolla esta dirección y conserva los requisitos funcionales del [PRD Recovery](open-gym-recovery.prd.md) para la entrega posterior. [Foundation archivada](../openspec/changes/archive/2026-10-22-add-postgres-foundation/proposal.md) es evidencia sintética histórica de Node; no acredita el stack Python ni cierra esta entrega.

Las especificaciones posteriores deben aportar evidencia de cada resultado; este PRD no constituye una validación ejecutada.
