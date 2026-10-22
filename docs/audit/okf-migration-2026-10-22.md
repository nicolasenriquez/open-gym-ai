---
type: Audit
title: Ejecución de la migración documental OKF v0.2
description: Alcance, preservación y verificaciones de la conversión documental completa del 2026-10-22.
---
# Ejecución de la migración documental OKF v0.2

## Alcance y base

Solicitud: ejecutar el [plan completo](../plans/okf-v0.2-documentation-migration.plan.md), mantener `AGENTS.md` central y preservar evidencia sin cambiar aplicación. La base fue `docs/opengym-evolution-discovery`, HEAD `2cc7ee1fa110453b71f8790891603b06689c6d86`, con modificaciones previas. No se hizo reset, stash, commit ni despliegue.

Se capturaron hashes de 21.216 archivos existentes seguidos o no ignorados y copias de la documentación y controles que podían cambiar. El inventario inicial tenía 37 Markdown de `docs/`. Durante el trabajo reaparecieron dos controles en `docs/agents/`; el usuario confirmó integrar el estado actual. Se respaldaron antes de transformarlos y se verificó que eran idénticos a sus fuentes en `.agents/docs/`.

La copia de esta ejecución está fuera del repositorio, en `C:/Users/nenri/.codex/visualizations/2026/10/22/01a1649a-d54b-7d11-9f1b-cb6b275060ed/okf-backup/`. Contiene `manifest.json`, estado inicial, archivos originales, especificación fijada y propuestas mecánicas. Es respaldo local de la sesión, no una dependencia para usar la herramienta.

La [revisión oficial fijada](https://github.com/GoogleCloudPlatform/open-knowledge-format/blob/0b87c52c6ef999286c745e19998fdfcd03d5dbee/SPEC.md) y su hash se registran en el [perfil](../standards/okf-profile.md). El patrón de auditoría y sincronización de AI Tutor se adaptó al alcance de OpenGym; no se importaron sus rutas personales ni reglas como si fueran requisitos oficiales.

## Transformaciones y propietarios

| Superficie | Transformación | Autoridad o preservación |
| --- | --- | --- |
| Conceptos existentes de `docs/` | Frontmatter aditivo con tipo, título y descripción | Cuerpo exacto, salvo las tres páginas de navegación/control descritas abajo. |
| Auditorías previas, discovery, investigación y plan original | Solo metadatos cuando faltaban | 16 cuerpos sellados en el manifiesto histórico; imágenes y recursos intactos. |
| Índices de carpetas | Generación determinista y navegación por necesidad | Propiedad explícita en configuración; sin repetir requisitos. |
| `docs/README.md` | Entrada breve y tabla de fuentes de verdad | El inventario duplicado pasa a `docs/index.md`; se mantienen sus secciones de entrada. |
| `docs/agents/domain.md`, `triage-labels.md` | Rutas de compatibilidad, sin duplicar reglas | Mismo contenido original en `.agents/docs/`; URL antigua conservada. |
| README raíz | Ruta al índice y retirada del enlace a `CLAUDE.md` eliminado | `AGENTS.md` conserva la entrada común; contexto histórico del autor preservado. |
| AGENTS y CONTRIBUTING | Accesos al índice y guía por tarea | Reglas detalladas en perfil y guía, no copiadas al contexto global. |
| Herramienta local | `check`, `plan` y `apply`, más fixtures y configuración | Solo desarrollo documental; sin imports ni cambios de runtime. |
| `.gitattributes` | LF para evidencia protegida y herramientas documentales | Evita invalidar hashes por conversión de checkout; los cuerpos afectados ya eran LF. |

Los PRDs, arquitectura, referencias de seguridad/observabilidad, roadmap y OpenSpec mantienen sus decisiones. La plataforma Python/FastAPI/PostgreSQL sigue pendiente de aceptación antes de Recovery, Garmin e IA ampliada; esta conversión no satisface gates de producto o ingeniería.

## Registro de recortes y enlaces

| Origen | Motivo comprobado | Sustitución y referencias |
| --- | --- | --- |
| Inventarios repetidos en `docs/README.md` | El índice es ahora la navegación generada única | Índice central y sus índices hijos; se conservaron las secciones antiguas como entradas breves. |
| Dos controles de `docs/agents/` | Duplicados byte por byte de `.agents/docs/` | Páginas de compatibilidad enlazan directamente a las fuentes centrales; ningún archivo eliminado. |
| README raíz → `CLAUDE.md` | Destino eliminado por la centralización previa | Párrafo enlaza al `AGENTS.md` existente. |
| Arquitectura → `README.md#documentation-authority` | Ancla ausente en la base | Se añadió la tabla de autoridad en ese destino; enlace existente conservado. |

No se retiraron requisitos, decisiones ni evidencia histórica. Los informes anteriores que proponen adopción gradual conservan su texto; el plan aprobado y esta ejecución documentan su sustitución por conversión completa.

## Verificación

Resultados de ejecución:

- 42 conceptos y 12 índices; 421 enlaces locales comprobados, sin hallazgos requeridos ni avisos históricos pendientes.
- 31 pruebas del tooling aprobadas en Node 22 y Node 24.14.0. Cubren preservación, repetición, YAML inválido, enlaces, rutas Windows, locks, planes alterados/obsoletos y recuperación de fallos simulados EBUSY/ENOSPC.
- 16 cuerpos protegidos idénticos a su base. De los 37 Markdown iniciales, 36 conservan el cuerpo exacto; el único cuerpo reorganizado es `docs/README.md`, conforme al registro de recortes. Las dos páginas de compatibilidad posteriores conservan su contenido original en las fuentes centrales y el respaldo.
- 168 recursos documentales no Markdown intactos; ningún archivo del inventario inicial eliminado ni archivo de aplicación alterado. El cambio adicional de `.gitattributes` afecta únicamente documentación y sus herramientas.
- La segunda propuesta contiene cero transformaciones y su aplicación devuelve `written: 0`; bytes y mtimes de los 54 Markdown permanecen intactos.

El control de whitespace de los cambios de esta ejecución y los archivos nuevos se revisó por separado. La comparación completa contra HEAD conserva dos avisos previos de línea vacía final: `evolution-architecture-evidence-2026-10-22.md` y `reference/recovery-contracts.md`. Ya estaban en las copias iniciales; no se modifican para maquillar el resultado. En particular, el primero tiene el cuerpo protegido. Son excepciones de lint de la base, no hallazgos nuevos ni incumplimientos OKF.

Las suites de aplicación no se ejecutaron: esta entrega no cambia su código. Las pruebas del tooling no acreditan paridad Python, migraciones reales, seguridad de plataforma ni utilidad de Recovery. Se añadieron solo dependencias de desarrollo raíz; la auditoría de dependencias al instalarlas terminó con cero vulnerabilidades conocidas.

La validación local es una comprobación estructural contra el estándar fijado y este perfil, no una certificación externa ni prueba de veracidad de cada afirmación. No se consultan enlaces externos durante el mantenimiento ordinario.
