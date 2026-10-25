---
type: Reference
title: Recovery — contratos técnicos
description: Modelo, guardado y verificación técnica de la entrega posterior de Recovery.
---
# Recovery — contratos técnicos

**Estado:** referencia de la entrega posterior; requisitos funcionales en el [PRD Recovery](../open-gym-recovery.prd.md), dependencia de plataforma y gates en [arquitectura](../open-gym-evolution.architecture.md#12-gates-y-experimentos-antes-de-producción). Leer al especificar modelo, guardado, interfaz o aceptación Recovery después de cerrar plataforma. No es un esquema SQL ni evidencia de implementación. Las referencias numéricas § remiten a arquitectura.

## Modelo conceptual

**Recovery sigue sin DDL aprobado ni nomenclatura definitiva.** Identidad y Training tienen su [esquema de plataforma confirmado](platform-schema.md), enlazado desde [arquitectura §6](../open-gym-evolution.architecture.md#6-modelo-conceptual-postgresql). Esa aprobación no crea tablas Recovery ni acredita coherencia de propietario/RLS sin pruebas.

| Concepto | Relacional | JSONB selectivo |
| --- | --- | --- |
| Proceso Recovery | Propietario, ID, estado, fechas | Detalle opcional acotado |
| Indicación y revisión | Proceso, propietario, ID/revisión, vigencia, registro | Texto, ejercicios identificables y objetivos |
| Sesión | Proceso, propietario, estado, versión, fechas y asociación conocida | Trabajo registrado y snapshot contextual |
| Corrección | Objeto, propietario, operación y fecha | Anterior/nuevo o diferencias explícitas interpretables |
| Hito | Proceso, propietario, fecha efectiva y registro | Detalle del acontecimiento |
| Recibo idempotente | Propietario, operación única, huella, resultado y fecha | Respuesta compacta |
| Garmin futuro, sin crear todavía | Propietario, proveedor, ID externo y procedencia | Payload/métricas según necesidad |

Invariantes Recovery:

- Como máximo un proceso activo por propietario, con restricción de BD.
- Versiones para escritura condicional y estados de sesión limitados a en curso/completada.
- Fechas de calendario efectivas donde corresponda; instantes automáticos para registro/corrección. No convertir fechas retrospectivas indiscriminadamente a medianoche UTC.
- Revisiones conocidas de indicaciones preservadas y snapshots estables de sesiones. Cambios posteriores no los reescriben.
- Objetivos y resultados separados; ejercicios pendientes no se presentan como realizados.
- Contexto desconocido explícito; no asignar la indicación vigente por defecto a retrospectivas inciertas.
- Corrección y su antecedente se confirman en la misma transacción; no recalcular otras sesiones ni progresiones.
- Conservar nombres, instrucciones y unidades necesarios para interpretar la historia, aunque cambie el catálogo.

## Guardado, concurrencia e idempotencia

Comando autenticado con ID estable de operación, versión esperada, generación y contenido validado. El propietario procede de la sesión. Usar IDs estables en creaciones.

Dentro de la transacción y con serialización apropiada: comprobar generación, reconocer recibo existente, comparar contenido, comprobar versión/invariantes y guardar cambio/corrección/recibo. Una restricción única respalda la identidad de operación; un simple consultar-y-luego-insertar no resuelve carreras.

- Misma operación y contenido: devolver el recibo previo antes de rechazar por versión antigua.
- Misma operación y contenido distinto: rechazar.
- Conflicto de versión: conservar edición del cliente y solicitar revisión, sin last-write-wins ni merge automático.
- Confirmación de éxito solo después de commit y validación del recibo correcto.
- Timeout significa resultado no confirmado. Reintentar la misma operación; no inventar otra creación.
- Una confirmación no limpia cambios posteriores a la versión enviada. Un recibo antiguo no sustituye una lectura actual del recurso.
- Continuar una sesión consulta su versión guardada en servidor. No confundir sesión en curso con borrador no guardado.
- Sin colas offline Recovery ni promesa de recuperar contenido no confirmado tras cierre forzado.

Restauraciones renuevan la generación Recovery y rechazan contextos anteriores. La renovación evita sobrescrituras posteriores; no recupera por sí misma datos posteriores al backup.

## Reutilización e interfaz

Compartir catálogo y búsqueda (`frontend/src/lib/exercises.js`) y controles (`frontend/src/components/ui.jsx`). Reutilizar selectivamente componentes con props. No reutilizar íntegros `Workout.jsx`, `session-edit.js`, `finish-workout.js` o temporizadores conectados a `S.active`/`useUI.work`: contienen reglas de progresión, récords, filtrado o estado específico.

`registerCustom()` modifica el índice global. Las instrucciones y ejercicios personales Recovery permanecen dentro de su dominio; usar catálogo público de referencia sin registrar información de rehabilitación en ese índice. No crear otro catálogo general.

## Pruebas G4 y G5

- Escenarios A–D completos del PRD; correcciones sucesivas y ejercicios editados sin reescritura de snapshots.
- Atomicidad: fallo antes/después del commit y consistencia de cambio/corrección/recibo.
- Idempotencia concurrente: mismo ID/contenido, reutilización con otro contenido, reinicio, respuesta perdida y reintento tras otras escrituras.
- RLS Recovery: propietario distinto, contexto ausente, pool reutilizado y roles Training sin acceso; no filtración a coach, export/admin Training, sincronización global, cachés o logs.
- Restore con generación Recovery y clientes antiguos; recorrido responsive §12.1, separado de las tres sesiones reales de adopción.

## Validación web responsive

La entrega posterior de Recovery se acepta como web responsive mediante **Playwright CLI con Edge/Chromium**, después del cierre de plataforma. Esta matriz no exige construir Recovery para aceptar GP/GO; plataforma necesita sus propios casos de paridad de recorridos actuales. La matriz mínima Recovery usa viewports genéricos, sin perfiles de dispositivos:

| Vista | Viewport (ancho × alto, píxeles CSS) |
| --- | --- |
| Escritorio | 1440×900 |
| Intermedia | 768×1024 |
| Pequeña | 390×844 |
| Estrecha | 320×740 |

En cada tamaño, recorrer captura → organización → inicio de sesión de entrenamiento → guardado de avances → continuación → completado → historial. Verificar también autenticación y los escenarios A–D del PRD. Registrar caso, revisión probada, navegador, viewport, acciones, resultado y rutas de evidencia; los datos técnicos serán sintéticos y las sesiones de navegador aisladas.

- Conducir la interfaz con Playwright CLI, fijar el tamaño con `resize`, obtener snapshots y capturas y revisar visualmente las pantallas y estados relevantes. Una captura existente sin revisión no acredita aceptación visual.
- Comprobar controles etiquetados, acceso por teclado y foco visible, textos legibles y ausencia de solapamientos o recortes que impidan operar. El recorrido debe poder completarse en los cuatro tamaños.
- Para cada guardado, comprobar el resultado, recargar y continuar o consultar desde otra vista. Una confirmación visual aislada no acredita persistencia. El historial debe conservar resultados y contexto, sin prometer recuperación de ediciones no guardadas.
- Revisar consola y solicitudes fallidas; conservar evidencia sin credenciales, cookies ni datos personales. Cerrar únicamente las sesiones de navegador creadas para la prueba.

Reutilizar [verify-opengym](../../.agents/skills/verify-opengym/SKILL.md) para los recorridos invitados que ya cubre. Su helper actual no constituye una matriz responsive ni prueba autenticación o Recovery: estos recorridos necesitan casos dedicados cuando se implementen. Esta revisión no amplía ni modifica el harness. Playwright CLI es la superficie interactiva; no se presupone una suite Playwright Test nueva.

G5 requiere este recorrido visible completo y las garantías de datos/restauración de los gates anteriores antes de iniciar las tres sesiones reales. Estas últimas evalúan utilidad y fricciones desde cualquier navegador/tamaño admitido; las pruebas técnicas no prueban adopción. No se exige teléfono físico, emulación de dispositivo, apps nativas ni otros motores de navegador en esta entrega. HTTPS/origen/RP ID se verifican para publicación y autenticación según §10; localhost compatible puede utilizarse durante el ensayo local.

**Estado:** protocolo acordado, pendiente de ejecución para Recovery. Esta revisión documental no presenta capturas, pruebas visuales ni G5 como aprobados.

