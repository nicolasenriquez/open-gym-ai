---
type: Implementation Plan
title: Migración documental completa a OKF v0.2
description: Plan de conversión segura, navegación y mantenimiento idempotente de la documentación de OpenGym.
status: draft
---
# Migración documental completa a OKF v0.2

Propuesta del 2026-10-22. Este archivo es planificación: no ejecuta la conversión ni implementa el script. La entrega propuesta completa todo el alcance acordado en una misma iniciativa; sus pasos son controles de ejecución, no una adopción gradual.

## Decisión y fuentes

La especificación oficial consultada publica **v0.2**, no v2.0. Se propone adoptar esa versión, fijando su revisión antes de ejecutar. Un bundle puede ocupar una subcarpeta. Dentro de él, todos los `.md` excepto `index.md` y `log.md` son conceptos con frontmatter YAML; `type` es la única clave siempre obligatoria. Existen requisitos condicionales cuando se usan otras familias de metadatos. Los índices y logs son opcionales; el índice raíz admite `okf_version`. Procedencia, verificación y ciclo de vida tienen semánticas distintas. Estas reglas proceden de la [especificación oficial, §§3–5 y 8–12](https://github.com/GoogleCloudPlatform/open-knowledge-format/blob/main/SPEC.md).

El perfil, las rutas, los controles de seguridad y el script que siguen son **decisiones propuestas para OpenGym**, no obligaciones adicionales atribuidas al estándar. El [repositorio oficial](https://github.com/GoogleCloudPlatform/open-knowledge-format) es el punto de consulta para futuras revisiones.

Referencias locales examinadas:

- `AGENTS.md`, `.agents/README.md` y `.agents/docs/issue-tracker.md`: entrada central, organización y relación con OpenSpec.
- `.agents/skills/prime-codebase/SKILL.md` y `.agents/skills/writing-for-agents/SKILL.md`: contexto, fuentes únicas y lectura por necesidad.
- AI Tutor: `C:/Users/nenri/OneDrive/Desktop/proyectos/pry-ai-evaluator/ai-tutor/.agents/skills/okf-docs-sync/SKILL.md`.

De AI Tutor se adopta el proceso de snapshot → clasificación → registro de hallazgos → sincronización aditiva → retiro fundamentado → verificación. Su skill referencia `index.md`, `.agents/skills/prime/SKILL.md`, `docs/standards/okf-standard.md` y `docs/operations/okf-authoring-guide.md`, ausentes en el checkout examinado. No es un script ejecutable que podamos copiar sin adaptación. Su clasificación de controles no exime de metadatos a los README que queden dentro del bundle elegido.

## Diagnóstico de OpenGym

Snapshot: rama `docs/opengym-evolution-discovery`, HEAD `2cc7ee1fa110453b71f8790891603b06689c6d86`; árbol con cambios previos y archivos sin seguimiento. Actualizar este snapshot antes de ejecutar.

| Superficie examinada | Situación y consecuencia |
| --- | --- |
| `docs/` | 36 Markdown existentes: 13 en raíz, 13 de auditoría, 6 de desarrollo, 3 referencias y 1 investigación. No tienen frontmatter ni índices OKF. El inventario deberá incorporar este plan y cualquier archivo posterior. |
| Codificación | En esos 36 archivos: 23 LF, 13 CRLF, sin BOM ni finales mixtos detectados. La conversión debe conservarlos por archivo. |
| Entrada para agentes | `AGENTS.md` centraliza instrucciones; `CLAUDE.md` está eliminado. `.agents/` conserva su propio formato. |
| Navegación pendiente | `README.md` todavía enlaza `CLAUDE.md`; arquitectura apunta a `README.md#documentation-authority`, sección ausente del índice documental. |
| Arquitectura real | React/Vite, API Node con JSON y MCP opcional; Compose actual `api` + `web`. Python/FastAPI/PostgreSQL sigue siendo un objetivo pendiente de aceptación. |
| Planificación vigente | Evolution precede a Recovery, Garmin y ampliaciones de IA. Seguridad y observabilidad ya tienen referencias separadas; deben conservarse en aceptación. |
| Herramientas | Node 22 en CI; `scripts/build-api-docs.mjs` ya demuestra generación determinista y comprobación sin escritura. `js-yaml` existe como dependencia de desarrollo raíz. |

La mejora esperada es poder descubrir documentación y comprobar su estructura sin duplicar reglas, confundir evidencia con requisitos actuales o reescribir contenido por cada ejecución. El formato, por sí solo, no prueba la exactitud de una arquitectura ni la seguridad del producto.

## Alcance y fuentes de verdad

**Bundle completo:** `docs/`, incluidos README, auditorías y este plan. Los índices cubren todas las carpetas con documentos o subcarpetas documentales. Los directorios exclusivos de imágenes no necesitan índices vacíos.

**Fuera del bundle:** raíz del repositorio, `.agents/`, `openspec/`, README de paquetes, catálogo, plantillas y Markdown consumido por el runtime, especialmente `api/coach/prompts/`. Permanecen en sus formatos actuales. Se permiten correcciones puntuales de rutas en `AGENTS.md`, README y CONTRIBUTING; no convertir esas superficies en bundles implícitos.

No se modifica aplicación, API, DB, contenedores, despliegue ni artefactos generados. El futuro script y sus tests serán herramientas locales de documentación, separadas del runtime. Esta etapa de planificación solo añade este documento.

| Autoridad | Contenido que conserva |
| --- | --- |
| `AGENTS.md` | Reglas compartidas y desencadenantes de lectura; entrada central. |
| `docs/index.md` | Mapa documental, con enlaces y descripciones breves. |
| PRD Evolution | Qué se acepta de plataforma y por qué. |
| Arquitectura y referencias de plataforma | Cómo se transiciona; contratos y gates técnicos. |
| PRD Recovery | Requisitos funcionales posteriores a la aceptación de plataforma. |
| OpenSpec | Especificaciones y tareas del cambio seleccionado; archivos archivados preservados. |
| Auditoría y discovery | Evidencia, contexto y decisiones históricas, identificados como tales. |
| Perfil OKF local | Alcance y reglas documentales comprobables. |
| Guía de autoría | Cómo crear, actualizar y comprobar documentos. |

Ruta propuesta: `AGENTS.md` → `docs/index.md` → documento pertinente → OpenSpec seleccionado, cuando exista. `docs/README.md` conserva su URL como guía de entrada breve y enlaza al índice; deja de repetir el inventario completo. No crear un segundo índice raíz ni `.scratch/` para sostener esta migración.

## Secuencia de ejecución

### 1. Capturar una base recuperable

1. Registrar rama, HEAD, estado y listado de archivos existentes, incluidos los no seguidos por Git. No exigir limpiar el árbol mediante reset o stash.
2. Crear un manifiesto temporal con ruta, SHA-256, tamaño, codificación, finales de línea, cuerpo y clasificación inicial. Registrar también los archivos fuera del alcance cuya integridad se verificará al terminar.
3. Guardar una copia recuperable de los archivos que se transformarán, incluidos los no seguidos, fuera del bundle. Git HEAD no respalda estos últimos ni las modificaciones locales actuales.
4. Delimitar la lista de escrituras; rechazar rutas que escapen de ella y detectar cambios concurrentes durante el trabajo.

**Cierre:** todos los archivos de entrada quedan identificados y recuperables sin perder trabajo anterior. Una discrepancia de hash obliga a recalcular el plan del archivo afectado.

### 2. Fijar la especificación y el perfil local

1. Registrar URL oficial, versión, commit y hash del texto consultado. Las ejecuciones ordinarias no seguirán automáticamente `main` ni necesitarán red.
2. Crear `docs/standards/okf-profile.md`: separar requisitos oficiales, reglas locales y recomendaciones. Incluir alcance, reservas, metadatos opcionales y tratamiento histórico.
3. Usar una taxonomía inicial pequeña: PRD, Architecture, Guide, Reference, Research, Audit e Implementation Plan. La elección es local; un tipo desconocido no se declarará infracción oficial por ser desconocido.
4. Proponer `title` y `description` como requisitos locales para nuevos conceptos y para esta conversión, de modo que alimenten los índices. Etiquetas solo cuando ayuden a encontrar contenido.
5. Definir reglas condicionales para campos presentes. No inventar fuentes, autores, revisiones humanas, fechas ni pruebas. `status` describe el documento, no el grado de implementación del producto.

**Cierre:** cada regla tiene origen y severidad identificables; no existen excepciones locales que pretendan invalidar una obligación oficial mientras se proclama conformidad completa.

### 3. Clasificar todo y proteger la evidencia

1. Registrar por archivo: clase, autoridad, tipo propuesto, hallazgo, evidencia, transformación y estado. Distinguir hallazgos requeridos, recomendaciones, diferidos y excepciones justificadas.
2. Clasificar los 13 Markdown históricos de auditoría y cualquier evidencia adicional. Su conversión añade exclusivamente metadatos; el cuerpo se conserva byte por byte. Imágenes y artefactos asociados permanecen intactos.
3. Conservar las afirmaciones históricas aunque hayan quedado obsoletas; explicar su alcance temporal mediante metadatos o enlaces desde documentación vigente. No corregir retroactivamente sus resultados.
4. Separar referencias rotas históricas de rutas activas: las primeras quedan registradas como tales; las segundas se reparan en la documentación vigente.

**Cierre:** todo Markdown del bundle tiene destino y política. Si se exige inmutabilidad del archivo histórico entero, en vez de solo del cuerpo, detener esa parte y resolver el alcance: excluirlo silenciosamente del validador no hace conforme a todo `docs/`.

### 4. Preparar y probar la herramienta en fixtures

Implementar la herramienta propuesta en la sección siguiente antes de aplicarla a documentos reales. Utilizar fixtures temporales para probar transformaciones, fallos y recuperación; no usar datos de entrenamiento ni secretos reales.

**Cierre:** las pruebas cubren la matriz de casos límite, rechazo de escrituras fuera de alcance y conservación del contenido. El script no incluye reescritura de prosa mediante un LLM.

### 5. Producir y revisar el plan de transformación

1. Ejecutar comprobación y simulación de todo el bundle. El resultado contiene ruta, hash esperado, regla, diferencia propuesta y motivo.
2. Revisar títulos, descripciones y clasificación manualmente; no inferir decisiones aprobadas desde un nombre de archivo.
3. Resolver colisiones con índices o metadatos añadidos por otros cambios. Conservar claves desconocidas; evitar serializaciones que pierdan comentarios o estructuras YAML.
4. Separar los cambios mecánicos de las correcciones editoriales. Los primeros deben conservar el hash del cuerpo; las segundas requieren una diferencia revisable con sustitución identificada.

**Cierre:** todas las escrituras están explicadas y acotadas; cualquier caso ambiguo queda resuelto antes de aplicar, sin saltar archivos obligatorios.

### 6. Convertir los conceptos y construir los índices

1. Añadir o ajustar el frontmatter de todos los conceptos incluidos. Preservar idioma, títulos del cuerpo, anclas, bloques, enlaces y finales de línea.
2. Crear `docs/index.md` con `okf_version: "0.2"` y entradas por intención: uso, operación actual, evolución, desarrollo, referencias y evidencia.
3. Crear índices en las carpetas documentales, incluidas las subcarpetas de auditoría con Markdown. Cada índice enumera sus documentos y delega las subcarpetas mediante enlaces.
4. Mantener el índice determinista, derivado de metadatos y agrupaciones explícitas. No duplicar párrafos de requisitos ni la tabla de aceptación en él.
5. Conservar los nombres de archivo y enlaces existentes siempre que sea posible. En Windows, usar nombres portables sin `:`, nombres reservados o puntos/espacios terminales. No emprender un renombrado masivo por estética.

**Cierre:** todos los conceptos tienen metadatos válidos, todos son descubribles desde los índices y la evidencia conserva sus hashes de cuerpo.

### 7. Reparar rutas y completar el cleanup pendiente

1. Actualizar los pointers pertinentes de `AGENTS.md`, README y CONTRIBUTING hacia la ruta central. Eliminar de las instrucciones activas la dependencia de `CLAUDE.md` eliminado.
2. Resolver el enlace `documentation-authority`: ubicar esa explicación en la fuente elegida y actualizar todos sus consumidores. Registrar las anclas antiguas cuando existan enlaces externos conocidos.
3. Mantener en `docs/README.md` una introducción breve con acceso al índice y al FAQ; trasladar el inventario a un único propietario.
4. Revisar duplicaciones entre Evolution, arquitectura, Recovery, discovery, roadmap y referencias. Para cada recorte registrar sección, duplicación demostrada, propietario, sustitución y referencias entrantes.
5. Conservar los identificadores de requisitos y gates, seguridad, autenticación/autorización, audit y observabilidad/tracing. El orden continúa siendo plataforma aceptada → Recovery → Garmin → ampliaciones de IA.
6. Mantener Node/JSON como estado actual y Foundation como evidencia sintética archivada. Reformatear documentación no satisface gates técnicos ni autoriza implementación.

**Cierre:** una regla tiene un propietario, el resto enlaza a él; no se borra evidencia ni se debilita un contrato operativo. Los cambios editoriales están separados de las inserciones de metadatos.

### 8. Verificar la entrega completa

1. Validar por separado conformidad oficial y política local, incluidos requisitos condicionales de campos opcionales presentes.
2. Comprobar enlaces activos, anclas, referencias por etiqueta, imágenes, rutas centrales y cobertura de índices. Revisar enlaces entrantes desde fuera del bundle.
3. Comparar cuerpos históricos y artefactos con el manifiesto; comprobar que no hay cambios de runtime, prompts ni archivos excluidos respecto de la base capturada.
4. Ejecutar `git diff --check` y revisar también archivos nuevos, que ese comando no cubre. Distinguir problemas previos de los introducidos.
5. Ejecutar una segunda simulación y aplicación: cero diferencias, cero escrituras y mtimes intactos. La comprobación sola tampoco escribe archivos.
6. Revisar manualmente recorridos de lectura: operar la app actual, comenzar Evolution, evaluar seguridad/observabilidad, consultar evidencia y crear un documento nuevo.

**Cierre:** cero hallazgos requeridos abiertos; excepciones y avisos históricos documentados. La entrega no se declara completa con conceptos omitidos ni validaciones no ejecutadas. No son necesarias las suites de aplicación para una conversión documental aislada; sí las pruebas de la herramienta si se implementa.

### 9. Dejar mantenimiento reproducible

Crear `docs/operations/okf-authoring-guide.md` con las acciones para añadir, editar, mover, deprecar y comprobar documentos. Remitir al perfil para las reglas, sin copiarlas. Añadir un pointer breve en `AGENTS.md` que se active al modificar documentación.

No crear `log.md` por obligación inexistente: Git y el informe de migración pueden bastar. Si se decide mantenerlo, definir un único propietario y evitar entradas automáticas por ejecuciones sin cambios. Cambiar la versión del perfil exigirá una actualización explícita con nuevas pruebas.

**Cierre:** otra persona o agente puede repetir los comandos y obtener el mismo diagnóstico sin depender del contexto de esta conversación. La integración en CI queda como reutilización posterior del modo de comprobación; esta propuesta pide mantenimiento local.

## Contrato propuesto para el script local

Rutas: `scripts/docs/okf.mjs`, `scripts/docs/okf.config.json` y `scripts/docs/okf.test.mjs`. Node 22 ESM aprovecha el entorno existente. Reutilizar `js-yaml` para YAML; evaluar un parser Markdown mantenido para enlaces y bloques, justificando cualquier dependencia exclusivamente de desarrollo. No extender el regex limitado del generador de API a un validador general.

Comandos **propuestos, todavía no disponibles**:

```text
node scripts/docs/okf.mjs check
node scripts/docs/okf.mjs plan --out <ruta-temporal-del-plan.json>
node scripts/docs/okf.mjs apply --plan <ruta-del-plan-revisado.json>
node --test scripts/docs/okf.test.mjs
```

| Operación | Contrato |
| --- | --- |
| `check` | Solo lectura; salida humana y opción JSON estable. Código 0 conforme, 1 hallazgos bloqueantes y 2 error operativo/configuración. Separar infracciones oficiales de política local. |
| `plan` | Calcula cambios sin editar documentos; escribe el informe únicamente en la ruta indicada. Incluye hashes de contenido y configuración. |
| `apply` | Aplica exclusivamente cambios mecánicos revisados; verifica hashes antes de escribir. Acepta metadatos e índices; rechaza borrados, movimientos y cambios de prosa no contemplados. |
| Configuración | Bundle, reglas locales, clasificación histórica y propiedad de índices. Sin exclusiones ocultas de conceptos internos ni dependencia de rutas personales de AI Tutor. |
| Idempotencia | Orden estable independiente del locale; sin timestamps nuevos, reflujo, normalización global o cambios de verificación por cada ejecución. Segunda aplicación sin escritura. |
| Seguridad | Sin red ni ejecución de comandos documentados. Contenido y enlaces son datos; no evalúan código, templates ni instrucciones incrustadas. |
| Escritura | Preparar resultados antes de mutar, comprobar concurrencia y reemplazar por archivo con temporal en el mismo volumen. Fallos y permisos se reportan; no forzar sobrescrituras. |
| Recuperación | Registro de cambios propios y recuperación condicionada a hashes. Atomicidad por archivo no equivale a una transacción de todo el repositorio; una interrupción debe poder diagnosticarse y reanudarse. |

Para índices existentes con contenido manual, el primer plan exige una fusión revisada y asigna su propiedad. El mantenimiento posterior solo regenera los índices declarados como propios; una edición concurrente invalida el plan. Para YAML complejo que no pueda preservarse de forma fiable, emitir una transformación manual pendiente en lugar de descartar comentarios o campos desconocidos.

## Matriz de casos límite y pruebas

| Área | Casos a cubrir y resultado esperado |
| --- | --- |
| Inventario | Archivos seguidos/no seguidos, borrados previos, altas concurrentes y carpetas vacías: recuento exhaustivo sin resucitar archivos ni omitir documentos nuevos. |
| Codificación | UTF-8, BOM, LF/CRLF, mezcla, falta de salto final, UTF-8 inválido: preservar bytes cuando sea seguro; los casos ambiguos bloquean la transformación automática. |
| Frontmatter | Ausente, vacío, sin cierre, `---` como separador Markdown, claves duplicadas, multidocumento, tags YAML y aliases abusivos: parsing acotado y rechazo explícito de entradas no seguras. |
| Tipos y extensiones | `type` vacío/null/lista/número y tipos desconocidos; claves anidadas y comentarios: validar la forma, conservar extensiones y no confundir taxonomía local con estándar. |
| Familias opcionales | Fuentes, actores, fechas con zona, eventos de verificación y computaciones atestadas: comprobar reglas aplicables si existen; nunca rellenarlas con afirmaciones fabricadas. No introducir computaciones atestadas para decorar documentación. |
| Reservas | `index.md`, índice raíz y `log.md`: validar su estructura específica; detectar colisiones de mayúsculas y bundles anidados antes de generar contenido. |
| Markdown | Bloques cercados con backticks o tildes, código inline, enlaces inline/por referencia, imágenes, autolinks y HTML: no interpretar ejemplos como enlaces activos. |
| Anclas | Encabezados repetidos, acentos, puntuación, HTML `id` y slugs reales del renderer: no marcar como roto un ancla explícita válida. |
| Rutas | Espacios, Unicode, paréntesis, `#`, escapes, queries, URL encoding y diferencias de mayúsculas: resolver sin confundir fragmento con nombre ni decodificar reiteradamente. |
| Fronteras | Enlaces relativos fuera del bundle pueden apuntar legítimamente al código o a OpenSpec; validarlos sin convertir el destino. Distinguir rutas raíz del bundle de la resolución del renderer GitHub. |
| Windows | Drives, UNC, rutas largas, junctions, symlinks, hardlinks y `..`: resolver rutas reales y rechazar escrituras fuera del alcance o alias peligrosos. No seguir enlaces de directorio de forma implícita. |
| Evidencia | Hash del cuerpo antes/después, imágenes intactas y enlaces históricos obsoletos registrados: no reinterpretar hallazgos antiguos ni inventar revisiones humanas. |
| Fallos | Plan obsoleto, edición concurrente, bloqueo OneDrive/EBUSY, falta de permisos/espacio e interrupción: error acotado, sin reset global ni eliminación del trabajo ajeno. |
| Repetición | Aplicación inicial, segunda simulación vacía y segunda aplicación sin escrituras; el modo check mantiene los bytes y mtimes de todos los documentos. |
| Privacidad | Informes y fixtures sin credenciales, datos personales ni URLs con tokens. Los enlaces externos no se consultan automáticamente durante check/apply. |

La sintaxis Markdown se contrastará con la [especificación GFM oficial](https://github.github.com/gfm/); los detalles de anclas del renderer necesitan casos de prueba propios. Esta matriz cubre riesgos identificados y define paradas seguras; no promete anticipar todos los archivos o fallos posibles.

## Entrega y aceptación final

La implementación futura entrega el bundle completo convertido, índices, perfil, guía, script probado e informe con inventario, transformaciones, hashes de preservación, recortes justificados, avisos históricos y resultados reales de comprobación.

Se acepta cuando todos los conceptos del alcance cumplen el estándar fijado y el perfil local, la navegación es coherente, los cuerpos históricos y artefactos permanecen preservados, los contratos de plataforma siguen íntegros y la segunda ejecución no cambia nada. El mantenimiento automático comprueba estructura y consistencia; la corrección de las afirmaciones y los cambios de requisitos siguen exigiendo revisión humana o técnica explícita.
