---
type: Reference
title: Perfil documental OKF de OpenGym
description: Alcance, autoridad y reglas locales del bundle documental OKF v0.2.
---
# Perfil documental OKF de OpenGym

## Especificación fijada

Base: [OKF v0.2, revisión 0b87c52](https://github.com/GoogleCloudPlatform/open-knowledge-format/blob/0b87c52c6ef999286c745e19998fdfcd03d5dbee/SPEC.md). SHA-256 de `SPEC.md`: `26aa5da029278939f914e578107242d9607d4f2dc5fe153272b82f9ed1030101`. El pin también está en [la configuración](../../scripts/docs/okf.config.json); actualizarlo requiere revisar reglas y pruebas.

La especificación define conceptos con YAML y `type`; reserva `index.md` y `log.md`. Permite extensiones y tipos desconocidos. Los campos opcionales tienen requisitos propios cuando se usan. Los índices y registros son opcionales en el estándar; este perfil exige índices locales. La semántica normativa completa pertenece a la especificación enlazada.

## Alcance local

El bundle es **todo `docs/`**. Todo `.md` salvo los dos nombres reservados es un concepto, también los README y la evidencia histórica. Los índices describen su carpeta y enlazan a las subcarpetas documentales. `docs/index.md` declara `okf_version: "0.2"`; los índices hijos no tienen frontmatter.

`AGENTS.md` es la entrada central del repositorio. Raíz, `.agents/`, `openspec/`, catálogo, documentación de paquetes y prompts del runtime quedan fuera del bundle. Se comprueban las rutas de los controles enumerados en la configuración, sin reformatearlos ni convertir sus destinos. Los artefactos no Markdown de `docs/` siguen siendo recursos enlazables.

## Reglas locales comprobables

- Cada concepto incluye `type`, `title` y `description` como cadenas no vacías; título y descripción ocupan una línea. Los dos últimos son una exigencia de este perfil.
- Taxonomía recomendada: PRD, Architecture, Guide, Reference, Research, Audit e Implementation Plan. Otros tipos se admiten; no existe lista cerrada obligatoria.
- Metadatos existentes y extensiones se conservan. La herramienta inserta frontmatter ausente solo con una propuesta explícita; editar frontmatter existente es una acción manual revisable.
- YAML debe poder leerse de forma segura. Anchors y aliases requieren revisión manual; los tags personalizados quedan fuera del esquema permitido. La puntuación dentro de cadenas, comentarios o bloques es texto, no sintaxis de alias. Esta restricción es una política local.
- UTF-8 sin BOM y finales de línea uniformes por archivo. Se conserva LF o CRLF y el cuerpo original en las inserciones; no se aplica formateo global.
- Toda carpeta con Markdown, o que conduzca a él, tiene un índice. La propiedad de los índices generados se declara en la configuración. Las agrupaciones de raíz son locales.
- Los enlaces activos locales deben resolver con mayúsculas exactas. Preferir rutas relativas, compatibles con GitHub. Un enlace que empieza por `/` dentro del bundle se interpreta desde `docs/`, según su contexto OKF; evitarlo si produciría una navegación distinta en GitHub.
- Los nombres nuevos son portables entre Windows/Linux. Mantener nombres y anclas vigentes salvo necesidad demostrada; revisar referencias entrantes antes de mover o retirar contenido.

## Procedencia, confianza y evidencia

No añadir fechas, `sources`, `generated` o `verified` por rutina. Registrar únicamente hechos conocidos; una validación de sintaxis no acredita la exactitud del contenido. Un documento estable puede describir una arquitectura todavía pendiente. El texto debe distinguir sistema actual, objetivo, recomendación y evidencia.

Las fuentes de verdad están en [la entrada documental](../README.md#documentation-authority). El perfil no modifica requisitos de plataforma ni autoriza trabajo de producto.

Los cuerpos protegidos están identificados en [el manifiesto histórico](../../scripts/docs/historical-bodies.json), con SHA-256 calculado antes de la conversión. El hash excluye únicamente el frontmatter; incluye saltos de línea y todo el cuerpo. También se conservan los recursos asociados. Para corregir una conclusión histórica, crear una nota nueva y enlazarla desde documentación vigente. No actualizar un hash para ocultar una reescritura. Los enlaces obsoletos de esos cuerpos se reportan como avisos; no se arreglan retroactivamente.

Las reglas documentales de `.gitattributes` mantienen LF en esas superficies, que ya usaban LF antes de migrar. Así los hashes conservan su significado después de un checkout en Windows o Linux. Las demás guías mantienen sus finales de línea actuales.

El plan original de migración está protegido como registro de intención. El [informe de ejecución](../audit/okf-migration-2026-10-22.md) indica el resultado; sus tiempos verbales no convierten el plan original en un runbook vigente.

## Comprobación y límites

La [herramienta local](../../scripts/docs/okf.mjs) distingue hallazgos `official` y `local`, con severidad requerida o aviso histórico. Comprueba metadatos usados por este bundle, estructura de reservas, inventario, índices, enlaces y preservación. No certifica semánticamente la documentación, no ejecuta computaciones atestadas y no consulta enlaces externos. Un tipo de computación exige revisión adicional de su contrato y pruebas específicas antes de introducirlo.

Git registra el historial; no se añade un `log.md` duplicado. El mantenimiento y la recuperación se describen en [la guía de autoría](../operations/okf-authoring-guide.md).
