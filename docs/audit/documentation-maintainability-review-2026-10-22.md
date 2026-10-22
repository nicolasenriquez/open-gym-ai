---
type: Audit
title: OpenGym — revisión de documentación, operación y seguridad
description: Revisión histórica de estructura documental, seguridad y operación previa a la migración OKF.
---
# OpenGym — revisión de documentación, operación y seguridad

## 1. Dictamen y alcance

**Fecha:** 2026-10-22. **Estado:** diagnóstico y propuesta; no se aplican cleanup, renombres ni cambios a los documentos canónicos. Se conserva el trabajo documental previo sin commit. Solo se añade este informe.

La dirección plataforma Python/FastAPI/PostgreSQL → Recovery → Garmin → ampliaciones de IA está alineada en los planes. La mejora necesaria ahora es facilitar su descubrimiento, reducir la carga de lectura y convertir observabilidad y seguridad en contratos verificables. No hace falta reconstruir toda la documentación ni copiar la estructura completa de AI Tutor.

**Fuentes:** checkout OpenGym `2cc7ee1fa110453b71f8790891603b06689c6d86` con ajustes documentales locales; AI Tutor `c28d4c36559218565845c447bcc64a89565881d9`, revisión Git revalidada en solo lectura; skill [writing-for-agents](../../.agents/skills/writing-for-agents/SKILL.md), leída durante esta revisión. Sus criterios aplicados son fuentes únicas, referencias condicionadas por tarea, carga de contexto, lectura progresiva, proximidad conceptual y condiciones de finalización comprobables.

La inspección comprende inventario, planes, instrucciones de agentes, índices, guías operativas y evidencia histórica pertinente, con comprobaciones estáticas de links/nombres y contraste con código de auth/audit y configuración. No se ejecutaron aplicaciones, pruebas funcionales, ataques, migraciones o telemetría; no se inspeccionaron secretos ni datos personales. Los hallazgos documentales no equivalen a vulnerabilidades reproducidas.

## 2. Hallazgos priorizados

| ID | Prioridad | Evidencia | Diagnóstico y corrección propuesta |
| --- | --- | --- | --- |
| DOC-01 | Alta | `AGENTS.md`, reglas/mapa; `CLAUDE.md`; `docs/agents/issue-tracker.md` | Falta un disparador explícito hacia Evolution y conviven instrucciones genéricas de especificación en `.scratch` con OpenSpec real. Añadir un pointer breve para modernización/migración y delimitar OpenSpec como fuente del cambio implementable; `.scratch` queda para notas/tickets que lo usen expresamente. Mantener un solo sistema de autoridad por cambio. |
| DOC-02 | Alta | Arquitectura §10 Observabilidad, una descripción general; PRD Evolution EV-03/EV-04 | Hay intención, pero falta un contrato aceptable de señales, correlación, tracing, acceso, retención y comportamiento ante fallos. Proponer resultado operativo explícito en PRD y evidencia técnica en GO. Una nueva sección o librería por sí sola no lo satisface. |
| DOC-03 | Alta | `api/server.js`: `sessionOf`, `requireAdmin`, audit; `SECURITY.md`; arquitectura §§9.1/10 | Autenticación, autorización y audit ya existen. Preservarlos/revalidarlos es parte de plataforma, no una mejora opcional que se pospone. Una ampliación posterior de identidad —p. ej. OIDC/SSO— sí requiere alcance independiente. |
| DOC-04 | Media | Arquitectura: 520 líneas/~8.043 palabras; Recovery PRD: ~4.308; discovery: ~2.293 | Arquitectura concentra dirección, inventario, snapshots históricos, contratos técnicos futuros Recovery y operación. Separar por necesidad de lectura, conservando un único plan técnico principal y enlaces con disparadores. Tamaño no implica que todo su contenido sobre. |
| DOC-05 | Media | Estado/alcance y autorizaciones repetidos en PRD, arquitectura, discovery, handoffs e informe previo | Mantener una nota clara de alcance por documento y las restricciones de datos/corte donde se aplican. Condensar recordatorios idénticos de aprobación/no implementación; conservar diferencias reales entre dato histórico, decisión y prueba. |
| DOC-06 | Media | `docs/README.md` enlaza planes, pero no presenta un mapa explícito de autoridad; `openspec/config.yaml` conserva plantilla | El lector debe distinguir producto, arquitectura, especificación, guía operativa y evidencia. Añadir esa ruta en el índice y un contexto mínimo en OpenSpec cuando se autorice editar configuración; evitar copiar PRD o reglas completas allí. |
| DOC-07 | Baja | `docs/NIX.md:210` apunta a `#passkeys-fail-even-though-rpid-looks-right`; encabezado destino usa `RP_ID` | Enlace roto confirmado: falta el guion bajo. Corregir a `SELF_HOSTING.md#passkeys-fail-even-though-rp_id-looks-right`. No se requiere retirar la guía Nix. |
| DOC-08 | Baja | Nombres de Markdown versionados; planes `open-gym-evolution.prd.md` / `.architecture.md` | No hay nombres inválidos detectados ni colisiones solo por mayúsculas. Los nombres actuales son válidos; renombrarlos únicamente por estética añade referencias que mantener sin resolver los problemas principales. |

El PRD Evolution tiene ~1.838 palabras y AGENTS ~595: no son los principales candidatos a fragmentación. El changelog, los archivos de catálogo y la evidencia histórica cumplen otras funciones; su longitud no justifica borrarlos. El modelo de fatiga Training de `frontend/src/lib/recovery.js` también debe distinguirse del dominio personal Recovery al orientar al lector.

## 3. Qué aporta AI Tutor y qué no debemos copiar

| Fuente observada en AI Tutor | Patrón aprovechable | Límite observado |
| --- | --- | --- |
| `CLAUDE.md` | Puente corto a `AGENTS.md`, sin una segunda fuente de instrucciones | OpenGym debe incluir rutas de lectura útiles también para agentes que solo cargan AGENTS. |
| `AGENTS.md`, sección On-Demand References | Referencias con condición: tests → testing; despliegue/integración → deployment; estructura → arquitectura | Su AGENTS mide ~3.304 palabras/378 líneas; copiarlo haría crecer el de OpenGym. También contiene repeticiones y tablas derivables de configuración. |
| `.claude/references/testing.md` y `deployment.md` | Referencias acotadas a una tarea, ejemplos operativos y fronteras de pruebas | Describen decisiones propias: DB simulada por defecto y despliegue blue/green. No trasladarlas como garantía de pruebas reales o necesidad de topología. |
| `docs/design/frontend-architecture.md` | Una responsabilidad documental explícita: estructura separada de lenguaje visual y comportamiento | Es la forma de delimitar autoridad la que se reutiliza, no la UI o stack de AI Tutor. |
| `app/backend/auth/dependencies.py`, rutas/repositorios | Identidad resuelta mediante dependencias y scoping del propietario; rutas sensibles identificadas en AGENTS | JWT, Google y admin por email son su contrato; OpenGym ya tiene passkeys, tokens firmados y roles que se deben preservar. |
| `main.py`, manifiesto backend y despliegue | Logging, lifecycle y operación explícita | La búsqueda focal no encontró instrumentación OpenTelemetry, `traceparent`, Prometheus o Sentry en los árboles de aplicación/despliegue examinados. No demuestra su ausencia en infraestructura externa no inspeccionada ni una solución completa de tracing. |

AI Tutor también tiene material de referencia de formato artículo con un enlace placeholder en `architecture-patterns.md`. Es evidencia de que el repositorio guía debe evaluarse por patrón y fuente, no copiarse como estándar íntegramente verificado.

## 4. Estructura recomendada para humanos y agentes

Mantener rutas existentes de los documentos canónicos. Introducir referencias solo al extraer contenido real o definir el contrato que falta; el árbol siguiente es una propuesta, no archivos creados:

```text
README.md                          producto actual y entrada
AGENTS.md                          reglas cortas + lectura según tarea
CLAUDE.md                          puente a AGENTS
docs/README.md                     índice humano y mapa de autoridad
docs/open-gym-evolution.prd.md      resultados de plataforma
docs/open-gym-evolution.architecture.md  dirección, límites y gates
docs/open-gym-recovery.prd.md       requisitos de Recovery
docs/reference/
  platform-security.md             contrato objetivo auth/authz/audit
  platform-observability.md        contrato objetivo de señales y operación
  recovery-contracts.md            detalle técnico Recovery extraído del plan
docs/dev/                          notas de implementación y discovery histórico
docs/research/                     investigación complementaria
docs/audit/                        evidencia fechada y diagnósticos
openspec/                          requisitos/cambios implementables y archivo
```

Las referencias bajo `docs/reference/` son compartidas entre humanos y agentes. No mantener una copia en `.claude/references` y otra en `.codex`; AGENTS y skills deben apuntar a la misma fuente. Tampoco se propone crear un `DESIGN.md` o una colección ADR vacía para imitar AI Tutor: incorporarlos cuando una decisión o trabajo concreto lo requiera.

**Mapa de autoridad del índice:** PRD = resultados; arquitectura = decisiones y gates; referencia técnica = un contrato especializado enlazado desde arquitectura; OpenSpec = cambio implementable; guías = operación actual; audit/research/discovery = evidencia/antecedentes. Los scripts/manifiestos describen comandos y dependencias existentes: documentar cómo usarlos y sus límites, sin mantener catálogos duplicados.

**Pointers propuestos para AGENTS**, en formato breve y condicionado por tarea:

- **Modernización o migración:** leer PRD Evolution y arquitectura, después el cambio OpenSpec seleccionado. Preservar Node/JSON como As-Is hasta el corte; la plataforma objetivo es Python/FastAPI/PostgreSQL antes de Recovery.
- **Auth, permisos o sesiones:** leer SELF_HOSTING, SECURITY y el contrato objetivo de seguridad cuando exista; verificar identidad, propietario y revocación.
- **Instrumentación u operación:** leer el contrato de observabilidad cuando exista; verificar correlación, fallos de dependencias y exclusión de datos sensibles.
- **Recovery:** leer su PRD y sus contratos específicos después de comprobar la dependencia de plataforma.

Solo activar los pointers a archivos nuevos cuando sus destinos existan. Mantener en AGENTS las invariantes que aplican siempre y enviar detalle por rama a las referencias; no cargar todos los PRD, auditorías o skills en cada turno.

La separación por necesidades de lectura es consistente con [Diátaxis](https://diataxis.fr/): explicación, referencia, tutorial y guía práctica tienen objetivos distintos. No hace falta renombrar todas las carpetas para adoptar esa distinción.

## 5. Observabilidad, tracing y tres formas de trazabilidad

Conviene separar tres contratos:

1. **Trazabilidad de entrega:** requisito EV → escenario OpenSpec → prueba → evidencia con revisión/entorno. Los planes ya la encaminan; las evidencias de ejecución aún faltan.
2. **Trazabilidad de datos y seguridad:** quién actuó, sobre qué recurso, cuándo, resultado y revisión/corrección. OpenGym tiene audit operativo; Recovery añadirá su historial de contexto y correcciones según su PRD. No confundirlo con un archivo de auditoría inmutable.
3. **Trazabilidad técnica:** correlacionar petición, operación de aplicación, DB y dependencia externa para explicar un fallo o latencia. Falta concretar su contrato objetivo.

[OpenTelemetry](https://opentelemetry.io/docs/concepts/signals/) distingue logs, métricas y traces; su [propagación de contexto](https://opentelemetry.io/docs/concepts/context-propagation/) permite correlacionar operaciones. Tener un monolito no elimina la utilidad de observar DB y proveedores externos.

**Base recomendada dentro de la modernización, pendiente de formalizar:**

| Área | Contrato propuesto | Evidencia mínima sugerida |
| --- | --- | --- |
| Logs operativos | Eventos estructurados en stdout/stderr, timestamp, servicio/revisión, severidad, código estable y correlación; límites de tamaño | Petición correcta/fallida deja eventos consultables sin payload personal. |
| Correlación/tracing | Contexto de petición y spans de aplicación/DB/dependencias; validar contexto entrante y mantener trazas legibles | Seguir una petición sintética hasta un fallo DB y distinguir fallo de conexión, conflicto de negocio y error externo simulado. |
| Métricas | Tasa/errores/duración por plantilla de ruta; saturación/espera del pool y resultado de procesos de backup | Fallo y saturación sintéticos reflejados con etiquetas de cardinalidad acotada. No usar usuario, URL cruda o texto libre como etiqueta. |
| Salud y recuperación | Liveness separado de readiness DB/esquema, estado de backup y señales accionables | DB indisponible o esquema incompatible se identifica; restore de prueba conserva operación y diagnóstico. |
| Privacidad y acceso | Allowlist de atributos, acceso y retención definidos; credenciales, cookies, notas, historial, SQL con valores y prompts fuera de telemetría | Inspeccionar logs/spans emitidos por app e instrumentación automática con fixtures sensibles sintéticas. |
| Fallos de observabilidad | Exportador opcional con fallos acotados; política explícita para audit y telemetría | Un destino de tracing caído no bloquea indefinidamente las peticiones ni modifica un commit de datos ya confirmado. |

Recomiendo evaluar instrumentación estándar OpenTelemetry en FastAPI/cliente DB durante Foundation/port. Collector, backend de almacenamiento y visualización se seleccionan por necesidad; no se fija Grafana/Tempo/Jaeger/Sentry ni se amplía el stack obligatorio por anticipación. Pueden ser herramientas de ensayo o un perfil opcional. Sampling, retención, acceso y objetivos de servicio requieren decisión, sin inventar un SLA.

`request_id`, `trace_id`, ID de operación idempotente y token de sesión tienen funciones distintas. Un identificador de tracing no autoriza al usuario ni sustituye un recibo de guardado. Tampoco enviar datos personales en baggage. [OpenTelemetry advierte](https://opentelemetry.io/docs/security/handling-sensitive-data/) que el implementador debe controlar lo que recogen las librerías; hashear un identificador no garantiza anonimato.

**Edición propuesta:** añadir a PRD Evolution un resultado EV-08 de diagnóstico operativo verificable, expresado como resultado y sin elegir tooling allí. Concretarlo en arquitectura/referencia y GO; conservar GP para paridad de seguridad y G3 para comprobación posterior a retirada. No hace falta inventar otro gate paralelo.

## 6. Autenticación y autorización: preservación y refuerzo

Autenticación responde quién accede; autorización, qué puede hacer sobre qué recurso. OpenGym ya implementa sesión firmada, passkeys, passwords opcionales, pairing/bearer, roles administrativos, ownership, deshabilitación y revocación. Evidencia: `api/server.js` (`sessionOf`, `requireAdmin`), `api/password.js`, `api/openapi.yaml` y `SECURITY.md`.

**Durante plataforma:** fijar una matriz de actor × recurso × acción: público/invitado, usuario propietario, otro usuario, administrador y consumidor MCP/coach. El invitado local y las rutas públicas legítimas conservan su contrato. Probar permisos de lectura/escritura/eliminación, acceso por ID ajeno, revocación durante espera, sesiones inválidas y límites de información expuesta. Roles DB/RLS complementan la autorización HTTP; no la reemplazan.

Reutilizar de AI Tutor las dependencias explícitas, ownership y fronteras de prueba. Mantener el contrato OpenGym de cookies/tokens, credenciales, origen/RP ID y clientes móviles; un cambio de lenguaje no autoriza sustituirlo por Google/JWT ni introducir un gestor de identidad completo. La [guía OWASP de autorización](https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html) respalda privilegio mínimo, permisos en cada petición y denegación por defecto para recursos protegidos.

**Después, si existe necesidad:** OIDC/SSO, MFA adicional, proveedores externos o una política más fina de permisos. Documentar resultado y compatibilidad antes de seleccionar producto. Estas ampliaciones no son condición inventada del port, pero la seguridad existente sí lo es.

**Audit separado de telemetría:** `api/server.js` registra eventos JSON en `audit.log`, con retención y opción de IP; `SECURITY.md` aclara que no es un archivo inmutable. Definir autoridad, acceso, integridad, retención y qué ocurre si falla la escritura al trasladarlo. No hacer depender el historial/audit requerido de traces muestreados. [OWASP Logging](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html) diferencia los propósitos de los registros y recomienda ajustar su alcance al riesgo.

## 7. Nombres, lint y cleanup propuesto

- `open-gym-evolution.prd.md` y `open-gym-evolution.architecture.md` son válidos. Varios puntos internos permiten distinguir propósito; `.md` sigue siendo la extensión. Mantenerlos evita una migración de enlaces innecesaria.
- El carácter literal `:` en un nombre, p. ej. `evolution:architecture.md`, es reservado en Windows. En títulos Markdown, `## Observabilidad: alcance` es válido. [Microsoft documenta](https://learn.microsoft.com/en-us/windows/win32/fileio/naming-a-file) los caracteres/nombres reservados y restricciones de punto o espacio final.
- Para archivos nuevos, usar nombres descriptivos, minúsculas y guiones, con sufijos `.prd.md`/`.architecture.md` cuando aporten significado. Conservar nombres convencionales `README.md`, `AGENTS.md`, `CLAUDE.md`, `SECURITY.md` y variantes upstream existentes; no hacer renombres masivos solo por uniformidad.
- Lint sintáctico y calidad editorial son revisiones distintas. No se encontró un linter Markdown dedicado en los manifiestos/workflows examinados. `git diff --check` solo verifica whitespace; no demuestra calidad, links o coherencia.

**Cleanup mínimo posterior, por orden:**

1. Corregir el ancla DOC-07; aclarar autoridad OpenSpec/`.scratch` y añadir pointers de lectura. Actualizar índice para humanos y agentes.
2. Condensar repeticiones de estado/autorización; mantener una ubicación canónica para orden de entrega, gates y cada contrato. Los resúmenes cortos con enlace sí ayudan a navegar y no son duplicación que deba borrarse automáticamente.
3. Dejar en arquitectura el objetivo, As-Is/To-Be, decisiones, fronteras, transición, riesgos y gates. Reubicar snapshots/huellas históricas hacia evidencia existente y contratos Recovery detallados hacia una referencia específica, preservando requisitos y enlaces.
4. Concretar seguridad/observabilidad como contratos objetivo enlazados, no runbooks de herramientas aún inexistentes. Mantener las guías actuales correctas hasta entregar el código correspondiente.
5. Verificar links/anchors, referencias en instrucciones/skills y equivalencia de requisitos al mover contenido. Mantener anchors estables o actualizar todos los consumidores. Conservar evidencia archivada, licencias, changelog, prompts runtime y catálogo.

No añadir una herramienta solo para cambiar el estilo de títulos/tablas existentes. Si se incorpora lint en CI, empezar por errores objetivos y reglas compatibles, sin reflow masivo. Las pruebas de enlaces deben reconocer IDs HTML, bloques de código y sintaxis Markdown real para evitar falsos positivos.

## 8. Doble comprobación y resultado

| Comprobación ejecutada | Resultado y límite |
| --- | --- |
| Links locales inline | 323 referencias en 48 Markdown de raíz/docs y README de módulos, sobre el estado previo a este informe. No incluye una validación completa de links externos, skills, prompts runtime, páginas del catálogo o todo OpenSpec. |
| Segunda pasada de anchors | Un fallo confirmado en NIX → SELF_HOSTING. El candidato `#systemd-hardening` sí existe como `<span id>` y fue descartado como falso positivo; no se recomienda tocarlo. |
| Nombres Markdown versionados | Sin caracteres Windows inválidos detectados ni colisiones de rutas solo por mayúsculas. No valida todos los límites de longitud/sistemas de archivos. |
| Cambios previos | `git diff --check` pasa. Se preservan sus archivos modificados y sin seguimiento. |
| Comparación AI Tutor | Revisión Git verificada; pointers, referencias, auth y límites de observabilidad contrastados con fuentes locales. Sin ejecución de su app o infraestructura. |
| Referencias oficiales | Consultadas Microsoft, Diátaxis, OpenTelemetry y OWASP el 2026-10-22; links en los apartados correspondientes. |

**Conclusión:** adoptar el patrón de referencias por tarea de AI Tutor, manteniendo AGENTS corto; preservar la separación producto/arquitectura/operación/evidencia; reforzar observabilidad y seguridad antes de aceptar plataforma. El cleanup prioritario es semántico y de navegación, no borrar historia o renombrar documentos válidos. Las propuestas anteriores siguen sin aplicar; este informe no instala tooling ni cambia el alcance canónico por sí solo.
