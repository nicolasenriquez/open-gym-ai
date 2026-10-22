# Instrucciones y skills de openGym

## Autoridad y lectura

- [AGENTS.md](../AGENTS.md) contiene las reglas comunes y los accesos por tarea.
- [docs/](docs/) contiene convenciones de agentes: [tickets](docs/issue-tracker.md), [triage](docs/triage-labels.md) y [dominio](docs/domain.md).
- [skills/](skills/) contiene una copia mantenida de cada skill. El [inventario](docs/skills-inventory.md) registra alcance, procedencia, problemas encontrados y evidencia de verificación.
- La documentación del producto sigue en [docs/](../docs/README.md), el vocabulario en [GLOSSARY.md](../GLOSSARY.md) y las decisiones en docs/adr/ cuando existan.
- OpenSpec conserva la autoridad de los cambios formalizados allí. Los tickets locales enlazan sus artefactos; no mantienen otra especificación del mismo cambio.

El runtime actual es Node/JSON. La dirección Python/FastAPI/PostgreSQL se consulta desde el índice de documentación y no se trata como implementación existente.

## Carga de instrucciones

AGENTS.md es el punto de entrada compartido; .agents/skills/ contiene las skills y .agents/docs/ sus referencias. Los enlaces Markdown son accesos para lectura por tarea, no imports automáticos. Cada cliente debe admitir estas convenciones o leerlas explícitamente. Los flujos del repositorio conservan estas fuentes únicas al generar o mantener instrucciones.

## Mantenimiento

1. Al cambiar reglas, rutas o arquitectura, ejecutar rules-check-drift sobre el rango pertinente; contrastar cada afirmación con archivos actuales.
2. Al cambiar instrucciones o skills, aplicar writing-for-agents: reglas breves, una autoridad por concepto y referencias condicionadas por tarea.
3. Al cambiar workflows cubiertos por verify-opengym, invocar explícitamente maintain-verification-skill para contrastar fuente y comportamiento real. Su auditoría completa requiere la pasada funcional; una revisión de enlaces no la sustituye.
4. Antes de actualizar skills externas, revisar [adaptaciones locales](docs/local-adaptations.md), conservarlas y actualizar el inventario. skills-lock.json registra procedencia de instalación; no certifica que el contenido adaptado siga idéntico al upstream.
5. Revisar el diff y ejecutar git diff --check. En una sesión nueva del cliente utilizado, comprobar las reglas cargadas y la presencia de verify-opengym sin ejecutar su flujo funcional.

No hay cambios de producto, APIs públicas ni dependencias de runtime en esta organización. Los secretos y datos permanecen excluidos de Git.

## Fuentes oficiales

Consultadas el 2026-10-22:

- [Codex: AGENTS.md](https://developers.openai.com/codex/guides/agents-md)
- [Codex: skills y descubrimiento](https://developers.openai.com/codex/skills)
