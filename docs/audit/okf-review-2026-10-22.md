---
type: Audit
title: Revisión final de OKF y su herramienta local
description: Hallazgos reproducidos, correcciones y límites de la revisión posterior a la migración OKF.
---
# Revisión final de OKF y su herramienta local

Revisión posterior a la [migración del 2026-10-22](okf-migration-2026-10-22.md). El alcance es la documentación y su herramienta local, para una persona o agente por ejecución. La entrada continúa siendo `AGENTS.md`; no se cambia código de aplicación ni se modifica el cuerpo de la evidencia previa.

## Hallazgos corregidos

| Caso reproducido | Problema anterior | Corrección |
| --- | --- | --- |
| Texto YAML con `!important`, `*literal*`, `&write` o comentarios equivalentes | Se rechazaba como alias o tag incluso dentro de una cadena o bloque literal. | Inspeccionar nodos YAML; rechazar anchors reales y tags fuera del esquema permitido. |
| Fecha `2026-02-30` | `Date.parse` la normalizaba y el validador la aceptaba. | Comprobar calendario, mes, día y año bisiesto antes de aceptar timestamps o fechas de logs. |
| HTML comentado | Un ejemplo comentado producía un enlace roto o un ancla inexistente aparentemente válida. | Excluir comentarios al extraer etiquetas y atributos. |
| HTML sin comillas o con entidades | Se omitían enlaces activos sin comillas y no se resolvían correctamente entidades en fragmentos. | Leer atributos de las etiquetas y decodificar sus valores; no tratar el texto de otro atributo como un enlace. |
| Salida `plan --out` mediante una junction externa que apunta al repositorio | La comprobación de ruta textual permitía escribir un informe dentro del repositorio. | Resolver el padre real del destino antes de aplicar la restricción de salida. |
| Opciones CLI de otro comando o repetidas | Se ignoraban opciones o se sustituía silenciosamente su valor. | Validar opciones por comando y rechazar duplicaciones antes de operar. |
| Configuración de carpeta sin título | Podía generar un índice con `undefined` como encabezado. | Validar título, descripción y propiedad explícita de cada carpeta. |

Los siete casos se añadieron primero como pruebas: fallaron con el comportamiento anterior y pasaron tras corregirlo. También se reforzó la portabilidad de nombres de Windows y la comprobación del documento elegido para un enlace a directorio. Se retiró un helper sin uso. Los hashes históricos no se regeneraron.

## Verificación y límites

La suite incluye además la aceptación de un día bisiesto válido, preservación de bytes y comentarios, planes obsoletos/alterados, recuperación ante fallos simulados y repetición sin escrituras documentales. El índice de auditoría se regenera para incorporar únicamente esta nueva página.

Resultado de la revisión: 39 pruebas aprobadas en Node 22 y 24; 43 conceptos, 12 índices y 425 enlaces locales comprobados sin hallazgos pendientes. La evidencia anterior conserva sus cuerpos y el mantenimiento sigue siendo idempotente. Los dos avisos previos de whitespace registrados por la migración conservan su tratamiento histórico.

Los resultados actuales se obtienen con `node scripts/docs/okf.mjs check` y `node --test scripts/docs/okf.test.mjs`. El [perfil](../standards/okf-profile.md) y la [guía](../operations/okf-authoring-guide.md) delimitan lo que se comprueba: estructura, navegación local, política y preservación. No se certifica la veracidad de requisitos ni se consultan enlaces externos durante el check. La revisión no acredita aceptación de la plataforma Python/FastAPI/PostgreSQL.
