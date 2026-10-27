# Adaptaciones locales de skills

Fecha: 2026-10-27. Revisar estas adaptaciones antes de reinstalar desde upstream.

| Skills | Adaptación local |
|---|---|
| caveman-commit | El README enlaza al repositorio upstream; SKILL.md se conserva sin cambios. |
| setup-matt-pocock-skills / rules-create-global / codebase-onboarding | Mantener reglas solo en AGENTS.md y referencias en .agents/docs/, sin crear adaptadores de herramientas. |
| create-verification-skill | Instalar una única copia en .agents/skills/, sin generar adaptadores. |
| inherit-legacy-style | Guardar reglas de estilo en .agents/docs/ y un pointer condicionado en AGENTS.md. |
| prime-codebase / prime-backend / prime-frontend / retro | Leer o mantener AGENTS.md; buscar referencias de agentes en .agents/docs/. |
| rules-check-drift / writing-for-agents / opsx-delivery-workflow | Usar AGENTS.md como autoridad compartida. |
| ponytail-help | Ayuda portable; retirar instalación, actualizaciones y comandos exclusivos de un cliente no utilizado. |
| react-testing | Enlaces a frontend-a11y, frontend-patterns y tdd; marcar reglas, agentes y comandos upstream no instalados. |

El [inventario](skills-inventory.md) registra procedencia y límites de la revisión. skills-lock.json conserva las fuentes y hashes originales de instalación; no se recalculan con un algoritmo supuesto ni se presentan como checksum del contenido adaptado. Los paths del lock pertenecen al repositorio de origen, no son destinos locales.

El diff de Git muestra las adaptaciones de esta intervención. Los informes históricos conservan sus hechos y rutas originales; no gobiernan las instrucciones actuales. Las referencias opcionales de los primers no obligan a crear documentos vacíos.
