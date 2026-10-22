---
type: Audit
title: OpenGym Evolution — revisión documental y propuesta de nueva base arquitectónica
description: Diagnóstico histórico y propuesta para priorizar la modernización de plataforma.
---
# OpenGym Evolution — revisión documental y propuesta de nueva base arquitectónica

## 1. Estado, alcance y dictamen

**Estado:** investigación y propuesta documental del 2026-10-22. La nueva prioridad procede de la solicitud del usuario: completar primero la transición a Python/FastAPI/PostgreSQL y profesionalizar desarrollo y operación mediante contenedores; después incorporar Recovery, Garmin y ampliaciones de IA. Las recomendaciones concretas de este informe no se presentan como arquitectura implementada ni como decisiones históricamente aprobadas.

**Dictamen:** la documentación vigente es razonablemente coherente con la decisión anterior —Node y PostgreSQL para llegar a Recovery—, pero ya no expresa la prioridad solicitada. Hay que revisar su objetivo, dependencias, herramientas y condiciones de cierre. Añadir FastAPI al roadmap sin reemplazar esas decisiones dejaría dos instrucciones incompatibles.

**Propuesta principal:** establecer una entrega independiente de modernización con paridad funcional de OpenGym, un backend modular Python/FastAPI y PostgreSQL como autoridad del estado servidor migrado. Recovery conserva su PRD funcional, pero su implementación queda después de la aceptación de esa plataforma. Mantener React/Vite/Zustand, catálogo, funcionamiento invitado y offline de Training.

**Alcance ejecutado:** inspección documental y de código; referencia AI Tutor en solo lectura; consulta de documentación oficial. No se ejecutaron suites, contenedores, migraciones, restauraciones ni pruebas de navegador. No se inspeccionaron datos o perfiles personales. Solo se añade este informe; los documentos canónicos conservan su contenido para que la propuesta sea revisable.

## 2. Evidencia y estado actual

### 2.1 Checkout y arquitectura real

- Rama: `docs/opengym-evolution-discovery`.
- Revisión inspeccionada: `2cc7ee1fa110453b71f8790891603b06689c6d86`.
- Árbol limpio al comenzar. Frontend y API declaran `1.4.1`; no se comprobó versión upstream ni identidad de las imágenes actualmente desplegadas.
- React 19, Vite, React Router y Zustand en `frontend/`; Vitest para frontend y MCP. API Node `node:http`, pruebas `node:test`; Node 22 en CI.
- `docker-compose.yml` levanta `api` y `web`; nginx sirve el frontend y mantiene `/api` bajo el mismo origen. No incorpora PostgreSQL al funcionamiento normal.
- `api/server.js` mantiene identidad y datos auxiliares en `db.json`, Training en `state-<uid>.json`, sesiones firmadas y acceso a medios. No importa Foundation.
- `frontend/src/store/useStore.js` mantiene datos locales, propietario, sincronización, copias apartadas y sesión activa. PostgreSQL no debe eliminar estas responsabilidades del cliente.
- `mcp/src/state.js` lee archivos y usa watcher/mtime; `mcp/src/tools.js` importa helpers de dominio del frontend. `api/coach/jobs.js` enumera y lee documentos Training y tiene persistencia propia. Cambiar únicamente las rutas `/api/data` dejaría consumidores obsoletos.
- No se encontraron archivos Python, `pyproject.toml`, `uv.lock` ni Alembic entre los archivos versionados de este checkout.

La actividad reciente implementó y archivó Foundation PostgreSQL sintética: entorno aislado, pool, migraciones, aislamiento, backup/restore y CI. No fue una migración de la aplicación.

### 2.2 Qué acredita Foundation

`api/foundation/README.md`, el diseño archivado y el tracker registran 18/18 tareas, 55 pruebas sintéticas y 9 del harness; también registran resultados históricos de compatibilidad de API/frontend/MCP. **Son resultados documentados de ejecuciones anteriores, no pruebas repetidas durante esta revisión.**

Su stack fija Node 22.23.2, `pg` 8.23.1, `node-pg-migrate` 9.0.0 y PostgreSQL 18.6. Está separado de `api/server.js` y de la imagen normal. El restore usa fixtures pequeñas dentro del entorno de ensayo; no acredita recuperación externa completa, PITR ni RPO/RTO de producción. G1 operativo y G0/G2–G5 siguen pendientes.

Reutilizable: requisitos, escenarios, controles de aislamiento, conocimiento de PostgreSQL y evidencia histórica. Debe probarse de nuevo en Python: lifecycle del pool, transacciones, cancelaciones, contexto RLS, migrador, errores, concurrencia y recuperación. Un pool JavaScript aprobado no valida `asyncpg`; el locking de `node-pg-migrate` no acredita el de Alembic.

## 3. Hallazgos y ajustes necesarios

| ID | Prioridad | Evidencia vigente | Consecuencia y ajuste propuesto |
| --- | --- | --- | --- |
| D1 | Alta | Arquitectura §§1, 3 y 14: Recovery primera entrega, API Node y FastAPI posterior | Contradice la nueva prioridad. Reemplazar la dirección y la secuencia por modernización completa antes de Recovery. Registrar que el motivo es un cambio de objetivo del usuario, no un fallo demostrado de Node. |
| D2 | Alta | PRD: resumen, §8 y §9.3; discovery §§5, 7 y 9 excluyen modernización como prerrequisito | Conservar los requisitos funcionales y actualizar la dependencia de entrega. Separar necesidad de producto de orden de inversión: la arquitectura no demuestra el valor de Recovery, pero ahora sí condiciona su implementación. |
| D3 | Alta | Arquitectura §§3 y 8 seleccionan `pg`/`node-pg-migrate`; §15 ya registra versiones verificadas | Separar selección histórica de Node, evidencia sintética y nueva selección Python. Proponer `asyncpg`/Alembic y una sola autoridad de migraciones para el esquema objetivo. No ejecutar ambos migradores sobre las mismas tablas. |
| D4 | Alta | Secuencia actual: Foundation → migración de persistencia Node → Recovery | Ejecutarla literalmente añade un backend intermedio destinado a ser sustituido. Preparar Python/PostgreSQL con datos sintéticos antes del corte real; conservar Node como referencia hasta demostrar paridad. |
| D5 | Alta | “Monolito” no está definido; AI Tutor reúne estáticos y FastAPI en una imagen, con PostgreSQL separado | Definir monolito modular de aplicación y topología de contenedores por separado. Recomendar inicialmente `web` + `api` Python + `db`, mismo origen y una unidad de release. No incluir PostgreSQL en el contenedor de aplicación. |
| D6 | Alta | Arquitectura §9 ya inventaría consumidores, pero no existe contrato de portabilidad Python | Extender la matriz a todas las capacidades actuales y fijar su destino, pruebas y condición de retirada. Autenticación, coach, notificaciones, MCP y medios forman parte del traspaso. |
| D7 | Media | Gates G0–G5 son de la secuencia anterior; falta aceptación específica del backend Python | Mantener su trazabilidad y añadir una condición explícita de paridad Python y otra de operación reproducible. No reutilizar G4/G5 como cierre de plataforma: corresponden a Recovery. |
| D8 | Media | `ROADMAP.md` deja database storage para después y contempla base embebida; README también contiene calendario upstream | Distinguir roadmap upstream de la evolución de este checkout. Añadir una ruta local inequívoca sin reescribir compromisos upstream como si fueran propios. |
| D9 | Media | Discovery, última línea: Foundation con “implementación parcial”; tracker e índice: completa y archivada | Corregir el estado de entrega sin transformar el discovery en registro técnico vivo. Enlazar la evidencia y dejar el estado actual en un único lugar. |
| D10 | Media | Arquitectura §3/§8 dice versiones pendientes; §15 y README Foundation ya registran las ensayadas | Etiquetar las referencias anteriores como históricas y distinguir “versión ensayada” de “versión objetivo operativa”. Evitar instrucciones presentes contradictorias. |
| D11 | Media | `openspec/config.yaml` solo contiene plantilla; documentos repiten restricciones y estados | Añadir contexto mínimo con enlaces a fuentes canónicas y orden de entregas cuando se aplique la revisión. No copiar el PRD o la arquitectura completos al config. |
| D12 | Media | Guías actuales explican Node/JSON, backup de `data/`, MCP sin red y despliegues Nix/Kubernetes/Helm | Son correctas para el sistema actual; deberán actualizarse junto a la migración o marcarse como legacy fuera del soporte objetivo. No prometer soporte de artefactos que sigan arrancando Node. |

No se encontró un documento denominado PDD en el inventario revisado. Los artefactos equivalentes son el discovery, `docs/open-gym-recovery.prd.md` y `docs/open-gym-evolution.architecture.md`.

## 4. Organización documental propuesta

Mantener el estilo existente: Markdown en español para planificación local, estado y alcance explícitos, evidencia separada de hipótesis, tablas de decisiones, exclusiones, escenarios Dado/Cuando/Entonces y handoffs hacia OpenSpec. Conservar el idioma propio de las guías upstream.

| Documento | Autoridad propuesta | Cambio |
| --- | --- | --- |
| `docs/open-gym-evolution.prd.md` — nuevo | Intención y aceptación de la entrega de modernización | Problema, usuario, hipótesis, paridad, operabilidad, criterios de éxito, exclusiones y dependencia de Recovery. Python/FastAPI/PostgreSQL como restricción estratégica del promotor, desarrollada técnicamente en arquitectura. |
| `docs/open-gym-evolution.architecture.md` | Cómo se ejecuta la dirección objetivo | Revisar en el mismo archivo; conservar antecedentes y marcar qué decisiones quedan sustituidas. To-Be Python, límites, tooling, datos, paridad, transición, operación y gates. |
| `docs/open-gym-recovery.prd.md` | Qué necesita Recovery y cómo se evalúa su utilidad | Mantener §§1–7 y escenarios A–D; actualizar resumen, exclusiones y handoff para depender de la plataforma aceptada. Las tres sesiones reales siguen evaluando Recovery. |
| `docs/dev/personal-recovery-discovery.md` | Antecedente de decisiones de producto | Añadir revisión de prioridad fechada y corregir estado obsoleto. Conservar testimonio e hipótesis originales. |
| `docs/README.md` | Entrada y orden de lectura | Evolution PRD → arquitectura → evidencia Foundation → transición Python/PG → Recovery PRD → cambios funcionales. Un resumen del estado con enlaces, sin otra matriz de gates duplicada. |
| `ROADMAP.md` / sección roadmap de README | Roadmap upstream y referencia a la línea local | Identificar expresamente los ámbitos. Prioridad local: plataforma → Recovery → Garmin → ampliaciones IA, sin fechas inventadas. |
| `GLOSSARY.md` | Términos de producto | Mantener indicación/sesión/corrección/hito. Aclarar que el cálculo de fatiga Training de `lib/recovery.js` no es el dominio personal Recovery. Definir monolito y autoridad de datos en arquitectura. |
| `docs/research/recovery-reference-benchmark.md` | Investigación complementaria de Recovery | Mantener hallazgos y revisiones. Anotar que su dictamen corresponde a la base anterior y enlazar el nuevo orden; no convertir patrones externos en requisitos nuevos. |
| `openspec/specs/postgres-foundation/spec.md` | Contrato entregado por Foundation | Preservar alcance sintético. Un nuevo cambio deberá especificar cualquier evolución/sustitución; no reetiquetar pruebas Node como Python. |
| `openspec/changes/archive/2026-10-22-add-postgres-foundation/` | Historia de entrega | No reescribir el archivo histórico para acomodarlo al stack futuro. Referenciarlo desde la nueva arquitectura. |
| `openspec/config.yaml` | Contexto breve para nuevas especificaciones | Fuentes canónicas, estado actual/objetivo y dependencia de plataforma antes de Recovery. |
| README, CONTRIBUTING, AGENTS, SELF_HOSTING, API, AI_COACH y MCP | Contrato operativo/de contribución del código existente | Mantener As-Is hasta implementar. Al entregar cada cambio, actualizar comandos, configuración, dependencias, soporte, API y recuperación afectados. |
| MOBILE, NIX, Kubernetes, Helm, website y diagramas | Superficies derivadas y alternativas de distribución | Inventariar compatibilidad; mantener, adaptar o marcar legacy. La primera entrega sigue siendo web/Compose; excluir publicación nativa no autoriza romper clientes existentes silenciosamente. |
| DATA_IMPORTS, catálogo y notas de dominio | Semántica de datos y entrenamiento a preservar | Reutilizar para paridad, sin normalización masiva ni rediseño de Training como consecuencia automática del port. |
| Auditorías y `docs/dev/ui-accessibility-fixes.md` | Evidencia histórica y correcciones | No declarar vigentes todos los fallos de la auditoría original: existen correcciones posteriores documentadas y código con `<dialog>`. Revalidar la nueva revisión antes de convertir hallazgos históricos en bloqueantes actuales. |

No se propone un segundo architecture plan con autoridad paralela. El PRD Evolution nuevo separa dos entregas distintas; la arquitectura existente sigue siendo el documento técnico principal.

## 5. Borradores concretos de redacción

Los siguientes textos son propuestas para la futura edición de los documentos, no sustituciones ya aplicadas.

### 5.1 Resumen del nuevo PRD Evolution

> OpenGym Evolution tiene como primera entrega establecer una plataforma mantenible y operable para las capacidades actuales de OpenGym. La transición debe preservar el acceso, los datos, el historial y los recorridos de Training, así como sus integraciones actuales, antes de incorporar funcionalidades nuevas.
>
> Por decisión del promotor, la plataforma objetivo utiliza un backend Python/FastAPI y PostgreSQL, con desarrollo y despliegue basados en contenedores. La arquitectura concreta los mecanismos y las pruebas necesarias. La elección de stack no constituye por sí sola evidencia de mejor calidad, seguridad o utilidad.
>
> La entrega se considera satisfactoria cuando un checkout limpio puede construir y ejecutar el stack, las capacidades inventariadas cumplen su contrato de compatibilidad, la migración y restauración han sido ensayadas y el backend sustituido deja de ser necesario para servir la aplicación. Recovery, Garmin y las ampliaciones de IA comienzan después de esa aceptación.

**Problema respaldado por código:** el estado servidor y sus consumidores dependen de archivos, y varios contratos se comparten mediante JavaScript. Llevar esa base a Python exige una transición explícita y comprobable. No se afirma que Node sea intrínsecamente poco profesional ni que el sistema actual haya perdido datos.

**Hipótesis:** una base modular y reproducible permitirá añadir capacidades con contratos claros, pruebas y procedimientos operativos comunes. La aceptación inicial demuestra paridad y operabilidad; una mejora futura de productividad requiere observación posterior, no una métrica inventada ahora.

**Exclusiones:** nuevas funcionalidades Recovery/Garmin/IA, rediseño del frontend, cambio a TypeScript/Bun por imitación, normalización integral de Training, microservicios, Redis, Kubernetes, pgvector y frameworks de agentes sin caso concreto. No excluir las capacidades existentes de coach/MCP/notificaciones sin una decisión explícita de alcance.

### 5.2 Sustitución del objetivo de arquitectura

> Completar la transición de la aplicación servidor a un monolito modular Python/FastAPI, con PostgreSQL como autoridad del estado duradero migrado, preservando la experiencia React/Vite/Zustand y los contratos actuales de OpenGym. La base se entrega y verifica antes de implementar Recovery, Garmin Connect o ampliaciones de IA. La ejecución será incremental; el destino no incluye una segunda API Node permanente.

**Topología recomendada:**

```text
Navegador / PWA: React + Vite + Zustand
           │ mismo origen
     web: nginx + catálogo/estáticos
           │ /api
     api: Python / FastAPI
     ├─ identidad y autenticación
     ├─ Training y sincronización compatible
     ├─ medios, administración y notificaciones
     └─ coach actual y contratos para consumidores
           │
     db: PostgreSQL privado + volumen persistente

Migraciones: proceso puntual con rol separado, previo al API compatible.
Medios/secretos: almacenamiento protegido con respaldo coordinado.
MCP: cliente opcional de solo lectura mediante contrato Training restringido.
Recovery/Garmin/IA ampliada: módulos posteriores, todavía no implementados.
```

Tres servicios Compose no implican tres microservicios de negocio. La propuesta mantiene un solo backend de aplicación. No es necesario reunir estáticos y API en una imagen para conseguirlo; conservar nginx reduce el cambio sobre catálogo, subpaths y origen.

### 5.3 Dependencia del PRD Recovery

> Los requisitos funcionales y escenarios A–D de este PRD se conservan. Por la revisión de prioridad del 2026-10-22, su implementación comienza después de aceptar la entrega de modernización de OpenGym Evolution. Las tres sesiones reales de kinesiología se realizan tras completar la experiencia Recovery y sus comprobaciones técnicas; no evalúan la migración arquitectónica.

Reemplazar las frases “no es condición”/“no es prerrequisito” por esta dependencia. Mantener la distinción: FastAPI no es una necesidad clínica del usuario de Recovery; sí es una restricción y prioridad del proyecto que lo construye.

## 6. Qué significa completar el traspaso

### 6.1 Matriz mínima de compatibilidad

| Área | Contrato que debe conservarse o cambiarse expresamente | Evidencia requerida |
| --- | --- | --- |
| Identidad | IDs, credenciales WebAuthn, contadores, roles, deshabilitación y eliminación | Fixtures migradas, dos propietarios, permisos y revocación, incluyendo espera concurrente. |
| Autenticación | Cookies/tokens firmados, expiración y sesión revocable; passwords opcionales, pairing y device links | Vectores Node/Python y pruebas HTTP. No reemplazar cookies por JWT/OAuth de AI Tutor automáticamente. Compatibilidad de sesiones o invalidación controlada explícita. |
| Passwords | Formato scrypt y normalización NFKC de `api/password.js`; límites de coste y concurrencia | Passwords sintéticas conocidas y casos Unicode, hashes heredados y abuso. No importar bcrypt como reemplazo automático. |
| Training | `GET/PUT /api/data`, `/api/data/rev`, envoltorios, errores, `409`, stamps, `_rev`, `_wid`, `_wids`, `baseRev/baseWid`, reset y escrituras legacy admitidas | Caracterización Node y misma batería contra Python/PG; dos clientes, primera escritura concurrente, respuesta perdida y restore. |
| Cliente local | Invitado, offline, sesión activa local, propietario, cambios pendientes y reconciliación | Recorridos reales con perfiles sintéticos aislados. No migrar `active` al servidor por accidente ni borrar localStorage para facilitar el corte. |
| Contrato HTTP | Cuerpos, códigos, headers/cookies, CSRF/origen, subpaths, límites y uploads | Matriz de rutas/métodos desde OpenAPI y handlers. Adaptar validación FastAPI: su respuesta predeterminada no equivale al contrato Node. |
| Medios | Permisos por usuario, referencias, deduplicación y GC conservador | Fallos de DB no disparan borrado; backup/restore coordinado de archivos y referencias. |
| Administración y push | Usuarios, invitaciones, audit, suscripciones, recordatorios y rest timers | Casos habilitados/deshabilitados y aislamiento; inventario del estado en memoria y persistente. |
| Coach actual | Consentimiento, proveedores, propuestas, aprobación, configuración, credenciales, jobs y límites/sandbox | Adaptadores y fixtures sin llamadas reales; lectura de Training autoritativo. Inventariar cada almacén y tratamiento. |
| MCP | Resultados actuales, solo lectura, selección de propietario y números consistentes con Training | Fuente autoritativa nueva, permisos y paridad de helpers compartidos; sin espejos JSON ni acceso Recovery implícito. |
| Catálogo/import/export | IDs históricos, nombres/unidades, archivos generados, formatos e interpretación del historial | Fixtures representativas y suites existentes; equivalencia semántica, no bytes idénticos de JSONB. |

**Trampa específica de Python:** Pydantic, coerciones, valores ausentes/null y serialización no deben endurecer ni transformar el contrato Training por defecto. Las fixtures deben fijar también fechas, Unicode, números y campos internos. No utilizar solo el documento filtrado por `forClient` como origen de migración.

### 6.2 Límite de Node después del port

Propuesta: retirar Node como servidor HTTP de negocio; conservar herramientas Node de build/frontend y, inicialmente, el cliente MCP stdio con transporte Training autenticado de privilegio mínimo. El contrato MCP deberá definir provisionamiento/revocación de credencial, propietario, disponibilidad y errores; aún no está diseñado.

Los helpers JavaScript compartidos por frontend/MCP pueden mantenerse. El comportamiento que deba ejecutarse en Python —por ejemplo, stamps del servidor— necesita pruebas de equivalencia. No hace falta portar la UI o todos sus cálculos a Python.

El coach exige una decisión técnica específica: los adapters actuales usan SDK/CLI y aislamiento de procesos. Un backend FastAPI no garantiza que esos proveedores y la bajada de privilegios puedan trasladarse literalmente. Antes de declarar paridad completa, demostrar el reemplazo o documentar una excepción acotada para un runtime auxiliar opcional. No esconder una API Node permanente bajo la etiqueta “monolito Python”, ni retirar el coach silenciosamente.

### 6.3 Datos y autoridad

Mantener Training como documento JSONB compatible inicialmente; no rediseñar al mismo tiempo todas sus entidades. Identidad y relaciones relevantes pueden ser relacionales. Cada almacén servidor se clasifica como migrado, conservado con justificación o retirado, incluyendo configuración/jobs del coach, audit, suscripciones y metadatos de GC.

PostgreSQL almacena el estado duradero servidor seleccionado; no absorbe necesariamente archivos multimedia, secretos, catálogo estático ni almacenamiento local del invitado/offline. Una autoridad por dominio, sin dual-write permanente ni fallback silencioso a archivos.

## 7. Secuencia recomendada y condiciones de salida

| Etapa | Trabajo y límite | Condición para avanzar |
| --- | --- | --- |
| 0. Revisar la base documental | PRD Evolution, arquitectura, dependencia Recovery y mapa de consumidores; registrar decisiones sustituidas | Documentos coherentes con la nueva prioridad y alcance explícito de compatibilidad. No editar el archivo histórico Foundation. |
| 1. Caracterizar OpenGym actual | Matriz de capacidades/rutas, fixtures sintéticas, contratos auth/sync y procedencia de la versión de referencia | Se puede distinguir comportamiento obligatorio, deuda conocida y cambio intencional. Inventario real de clientes antes del corte, no antes de todo ensayo aislado. |
| 2. Foundation Python/PG | Entorno descartable, pool/lifespan, roles, migraciones Alembic, recuperación y CI | Evidencia equivalente sobre el stack nuevo; PostgreSQL ausente hace fallar las pruebas obligatorias. Sin acceso a datos reales. |
| 3. Port y migración ensayados | Identidad/Training, contratos HTTP, consumidores, coach, medios y notificaciones; frontend actual conectado a la API nueva en entorno aislado | Paridad Python demostrada, equivalencia de importación y comportamiento concurrente, operaciones y despliegue reproducibles. |
| 4. Corte y retirada | G0, G1 operativo, ensayo representativo, pausa de escritores, importación, verificación, cambio de autoridad y retirada del código sustituido | G2/G3 y condiciones nuevas de paridad/operación satisfechas; restauración y tratamiento de clientes offline demostrados. Sin Node HTTP ni lectores activos del estado sustituido. |
| 5. Recovery | Dominio y experiencia completa según PRD y benchmark | G4/G5; después tres sesiones reales para evaluar utilidad. |
| 6. Garmin | Discovery concreto de datos, acceso, permisos, procedencia y deduplicación | Fuente y autenticación verificadas; sin sesiones Recovery creadas por inferencia ni métricas inventadas. |
| 7. IA ampliada | Casos de uso, consentimiento, datos permitidos, evaluación y revisión humana | Capacidad útil demostrada y límites verificables. Python facilita integración, pero no exige LangChain/LangGraph/pgvector. |

La prioridad entre nuevas integraciones podrá revisarse después de la plataforma; no hay fechas ni acceso a proveedores comprometidos. No se propone generar ahora todos los OpenSpecs futuros. La siguiente especificación debe cubrir un tramo implementable y verificable del nuevo orden.

**Alternativas consideradas:**

- **Recomendada:** preparar directamente Python/PostgreSQL, validar con fixtures y realizar un corte controlado cuando exista paridad. Hay una transición productiva de autoridad; Node se conserva como referencia/versión recuperable durante la preparación.
- **Intermedia:** migrar primero Node a PostgreSQL y portar Python después. Solo justificar si reduce un riesgo concreto o existe una necesidad operativa inmediata. Añade adaptadores, convivencia de herramientas y trabajo potencialmente descartable.
- **Descartada como punto de partida:** sustituir frontend, auth, backend y modelo completo de Training en un mismo salto. Multiplica incertidumbre sin ser requisito del objetivo.

Un corte único concentra riesgo: exige ensayos completos, ventana de mantenimiento y regla de abortar antes de habilitar escrituras. “Una transición productiva” no significa implementar todo en un PR ni convertir un big bang sin pruebas en estrategia.

### Aceptación de plataforma independiente de Recovery

Conservar G0–G3 con su significado y añadir explícitamente condiciones de **paridad del backend Python** y **operación reproducible** en arquitectura. La entrega se cierra cuando:

1. Un checkout limpio construye y levanta la aplicación objetivo mediante comandos documentados, sin instalaciones manuales de Python/PostgreSQL para el runtime ni dependencia de carpetas personales.
2. API Python y PostgreSQL superan pruebas reales de esquema, permisos, transacciones y concurrencia, además de los contratos funcionales inventariados. Las suites JavaScript que correspondan siguen pasando.
3. Auth, Training, offline, coach, MCP, medios, administración e import/export conservan sus contratos; diferencias y deuda previa quedan identificadas. No se exige “cero bugs históricos” como condición imposible de medir.
4. Backup/restauración incluyen DB, roles necesarios, medios, configuración y secretos protegidos. Entorno, retención, destino externo, alertas y objetivos de recuperación están definidos y ensayados; los RPO/RTO candidatos anteriores no se convierten en garantías por copia.
5. La nueva autoridad está activa y el código exclusivo de la persistencia/HTTP sustituido se ha retirado y verificado. La versión anterior recuperable, su configuración y origen congelado quedan protegidos durante una ventana definida.
6. Las guías y artefactos soportados describen lo entregado. Artefactos Nix/Helm/Kubernetes no adaptados tienen estado legacy explícito y no se anuncian como despliegue Python compatible.

El rollback antes de nuevas escrituras y la recuperación después de ellas son procedimientos distintos. Restaurar el backup anterior tras recibir nuevas escrituras puede perderlas. La retirada de código no autoriza borrar datos originales o secretos.

## 8. AI Tutor: patrones transferibles y límites

Repositorio local inspeccionado en solo lectura: `C:/Users/nenri/OneDrive/Desktop/proyectos/pry-ai-evaluator/ai-tutor`, revisión `c28d4c36559218565845c447bcc64a89565881d9`, revalidada en esta investigación. La revisión no certifica su ejecución ni su adecuación completa a OpenGym.

| Fuente AI Tutor | Aprovechar | Adaptación necesaria |
| --- | --- | --- |
| `app/backend/pyproject.toml`, `uv.lock` | `uv`, dependencias bloqueadas, Ruff, mypy, pytest y configuración común | Elegir versión Python y dependencias compatibles durante la especificación; no copiar versiones antiguas ni dependencias de RAG/dental. |
| `app/backend/db/postgres.py` | Pool asyncpg y apertura/cierre explícitos | Añadir límites/timeouts y pruebas propias; no trasladar `hnsw.iterative_scan` ni el tamaño de pool como estándar. |
| `app/backend/alembic/env.py` | Alembic con SQLAlchemy para ejecutar migraciones y asyncpg para la aplicación | No obliga a usar ORM. Definir locking, migrador separado, fallos y recuperación con prueba real; copiar el archivo no aporta esas garantías. |
| `app/backend/main.py` | Lifecycle y módulos de rutas | AI Tutor ejecuta Alembic al arrancar. Recomendar migración controlada previa al API; readiness comprueba esquema compatible. |
| `deploy/Dockerfile` | Build por etapas, lockfile, runtime no root, healthcheck y rutas/imports reproducibles | Mantener nginx si reduce cambios; no imponer imagen conjunta ni confiar en headers de proxy desde cualquier cliente. |
| `deploy/docker-compose.yml` / override local | Red de aplicación, DB persistente y espera por healthcheck | No copiar blue/green, Caddy, pgvector o Whisper sin necesidad. La configuración local abre un puerto que cambia la frontera de confianza del proxy. |
| `justfile` | Superficie corta y repetible para subir, bajar, logs y verificación | En OpenGym proponer también verificación ejecutable en contenedores. AI Tutor permite excepciones de tooling en host; no atribuirle un enfoque exclusivamente containerizado. |
| `.github/workflows/ci.yml` | Lockfiles, formato/lint/tipos/tests/build | Añadir job obligatorio con PostgreSQL real: el CI inspeccionado no muestra servicio PostgreSQL para las pruebas backend. |
| `app/backend/tests/conftest.py` | Fixtures y sustitución de servicios externos en sus límites | PostgreSQL se sustituye por defecto y ciertas pruebas reales son opt-in. Mantener en OpenGym pruebas reales obligatorias de DB, RLS, migraciones y restore. |
| Repositorios/servicios por dominio | SQL fuera de handlers, ownership y transacciones | Copiar las fronteras de responsabilidad, sin modelo clínico dental, OAuth/JWT, Bun o UI ajena como requisitos de OpenGym. |

**Stack recomendado, pendiente de versiones y comprobación:** FastAPI/Pydantic + Uvicorn, asyncpg, Alembic, uv, pytest/httpx, Ruff y mypy. SQL explícito inicialmente; SQLAlchemy puede limitarse al migrador. Mantener npm y herramientas frontend actuales. Un único proceso API inicial hasta resolver expresamente estado en memoria, jobs y límites antes de añadir workers/réplicas.

## 9. Reglas editoriales para evitar ambigüedad

- **As-Is, To-Be y evidencia histórica** siempre separados, con revisión/fecha cuando se afirma una observación de ejecución.
- **Decidido por el usuario, recomendado y pendiente** no son sinónimos. La nueva prioridad permite revisar la decisión anterior; no requiere demostrar que Node sea defectuoso.
- **Una fuente por tipo de decisión:** PRD para resultados, arquitectura para mecanismos, OpenSpec para requisitos/cambio acotado, guías para operación actual y archivo para evidencia histórica.
- Cada requisito de paridad y aceptación recibe un ID estable al formalizar el PRD/arquitectura. Cada escenario OpenSpec apunta a ese requisito y cada prueba registra qué demuestra.
- “Migrado” exige consumidores operativos, autoridad única, compatibilidad tras retirada y recuperación ensayada. “Levanta el contenedor” o “importó filas” no bastan.
- Separar plataforma aceptada, Recovery funcional y utilidad en tres sesiones. Ninguna de esas evidencias sustituye a las otras.
- Versiones ensayadas no son automáticamente versiones objetivo. Proveedor PostgreSQL, host Compose local, VPS y despliegue final necesitan un contrato propio; validar localmente no obliga a adelantar el VPS.
- Referencias y benchmarks justifican decisiones concretas; no deben convertirse en un segundo PRD ni en una lista de dependencias obligatorias.

### Decisiones que la especificación siguiente debe concretar

La dirección Python/FastAPI/PostgreSQL y plataforma primero proviene de esta solicitud. Quedan por precisar: versiones y objetivo PostgreSQL; alcance de compatibilidad de clientes nativos sin asumir nuevos builds; sesiones existentes o reautenticación controlada; mecanismo WebAuthn Python; contrato MCP; viabilidad de cada proveedor/sandbox del coach; inventario de almacenes; entorno operativo; backups, ventana de corte y RPO/RTO aceptables. Estos puntos no impiden proponer la revisión documental; sí condicionan cerrar la especificación de migración y ejecutarla con datos reales.

## 10. Fuentes oficiales consultadas

Consulta del 2026-10-22. Respaldan mecanismos; no demuestran que este repositorio ya los implemente.

| Fuente | Aplicación y límite |
| --- | --- |
| [FastAPI: contenedores Docker](https://fastapi.tiangolo.com/deployment/docker/) | Imagen de aplicación, proxy, procesos y pasos previos al arranque. La topología de tres servicios es recomendación para OpenGym, no mandato del framework. |
| [FastAPI: lifespan](https://fastapi.tiangolo.com/advanced/events/) | Inicializar y cerrar recursos compartidos. No resuelve automáticamente transacciones o aislamiento. |
| [FastAPI: errores y excepciones de validación](https://fastapi.tiangolo.com/tutorial/handling-errors/) | Permite adaptar errores; comparar explícitamente el contrato legacy durante el port. |
| [Alembic: asyncio y migraciones de datos](https://alembic.sqlalchemy.org/en/latest/cookbook.html#using-asyncio-with-alembic) | Uso de engine async de SQLAlchemy y separación del problema de migración de datos. No acredita locking/concurrencia del despliegue. |
| [Docker Compose: orden de arranque](https://docs.docker.com/compose/how-tos/startup-order/) | Distingue servicio arrancado, saludable y proceso previo completado. No sustituye recuperación ante fallos posteriores. |
| [uv: integración con Docker](https://docs.astral.sh/uv/guides/integration/docker/) | Lockfile, capas e instalación reproducible. Usar verificación de lock coherente con la configuración elegida, no resolver dependencias al iniciar el runtime. |
| [PostgreSQL: RLS](https://www.postgresql.org/docs/current/ddl-rowsecurity.html) | Permisos y políticas como protección adicional; probar con roles reales y contexto correcto. |
| [PostgreSQL: backup y restore](https://www.postgresql.org/docs/current/backup.html) | Distingue dumps, backups de filesystem y archivado continuo; un dump no constituye PITR. |
| [Garmin Connect Developer Program](https://developer.garmin.com/gc-developer-program/overview/) | La página consultada distingue acceso Personal y Business, y anuncia acceso Personal a datos propios por pull. Investigar la opción oficial aplicable cuando llegue esa etapa; no asumir scraping ni limitar el análisis a acceso empresarial. No se probó elegibilidad, credenciales, límites o funcionamiento. |

## 11. Cobertura y límites de la revisión

Inventario obtenido con `git ls-files`: 21.206 archivos versionados y 51 Markdown bajo el filtro de documentación de proyecto, planificación, auditorías y Foundation; excluye skills y páginas del catálogo por ejercicio. Se realizó lectura profunda de PRD, arquitectura, discovery, estado Foundation e índice, y lectura focal de guías, configuración, entrypoints y consumidores para determinar impacto. El inventario no significa validación línea por línea de toda la documentación ni de cada afirmación histórica.

Fuentes técnicas inspeccionadas: manifiestos frontend/API/MCP/Foundation, Compose normal y sintético, CI, API/OpenAPI, estado cliente, lectores MCP/coach, medios, passwords, helpers compartidos y código de correcciones UI. Las auditorías previas son evidencia fechada; esta investigación no reejecutó sus recorridos ni los resultados Foundation.

**Próximo trabajo recomendado:** aplicar una revisión documental coherente como un solo conjunto —PRD Evolution nuevo, arquitectura actualizada, dependencia Recovery y referencias/índice— y después especificar el primer tramo Python/PostgreSQL verificable. El resultado esperado de esa revisión es una dirección y condiciones de aceptación inequívocas; no una declaración de migración completada.
