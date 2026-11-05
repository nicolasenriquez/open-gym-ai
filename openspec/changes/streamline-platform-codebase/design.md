## Context

Auditoría del 2026-11-04 sobre `docs/opengym-evolution-discovery`, HEAD `13a1b6fde7a219640ddae34338bef8608def8ffb`, con cambios locales ajenos, incluidos staged y traslado/edición del port archivado. HEAD no identifica todos los bytes auditados. Esta intervención solo modifica la OpenSpec seleccionada.

### Prime-codebase: estado observado

- Producto self-hosted de entrenamiento: PWA React 19/Vite 8/Zustand 5, shells Capacitor; frontend 1.4.1. Python 3.14/FastAPI/PostgreSQL en monolito modular; HTTP exclusivamente `/api/v1`.
- `frontend/src/main.jsx` arranca React/medios; `App.jsx` compone rutas; `store/useStore.js` posee documento/sync y `useUI.js`, estado efímero. `shared/coach-core/` es JS neutral para cliente, no otro servidor API.
- `backend/src/opengym_platform/application.py` compone routers/lifespan. Capacidades con lógica/persistencia propias; migraciones en `platform_migrations/`, comandos operativos separados del runtime.
- CI usa Node 22, pnpm 10.34.8 y locks; Vitest 4, pytest, Ruff y mypy. `scripts/platform.mjs` selecciona `backend/platform-suites.json` y recursos sintéticos propios. No hace falta otro runner.
- `AGENTS.md` y `.agents/README.md` enrutan instrucciones; OpenSpec posee el cambio y docs OKF, el conocimiento de producto. Helpers de entrenamiento/sesión puros con tests adyacentes; locales y contratos preservados.
- Inventario de 21.155 rutas Git, 19.693 bajo catálogo; cantidad de archivos no equivale a complejidad. Se profundizó en composición, guardado, sync, verificadores, CI y documentación. No se leyó cada asset ni se certificó seguridad/rendimiento de todo el producto.
- Sin archivos versionados en `api/` o `backend/contracts/`; quedan residuos locales ignorados en `api/` y contracts está vacío. No se confunden con código entregado ni se borran automáticamente.

### Auditoría de la propuesta original

**68/100** para la especificación anterior a esta revisión. Rúbrica de juicio técnico, no benchmark de agentes ni score de seguridad. Cada dimensión valora evidencia actual, decisión concreta y aceptación comprobable; no se otorga una nota mejorada solo por escribir requisitos.

| Dimensión | Peso | Puntos | Fundamento |
| --- | ---: | ---: | --- |
| Correspondencia con checkout actual | 15 | 8 | Revisión antigua, port 47/57 y artefactos retirados descritos como activos |
| Propiedad y arquitectura | 20 | 18 | Monolito modular, interfaces, TX compartida y una persistencia frontend |
| Reglas ejecutables y CI | 20 | 13 | Buen diseño de negativos; falta entrega y política completa de formato/comentarios |
| Navegación y portabilidad | 15 | 9 | Autoridades identificadas; falta probar descubrimiento con clientes distintos |
| Limpieza y comentarios | 15 | 7 | Selección segura, pero preservación de prosa interna contraria al nuevo objetivo |
| Pruebas y entrega acotada | 15 | 13 | Casos HTTP/PG/browser precisos; diagnóstico no equivale a ejecución completa |
| **Total** | **100** | **68** | Buena base; rebasar y cerrar decisiones antes de ejecución |

| Hallazgo comprobado | Evidencia y caso concreto | Corrección propuesta |
| --- | --- | --- |
| Plan desactualizado | Diseño anterior basado en `5f8f70519`, contratos JSON, `api/Dockerfile` y Compose raíz; Git ya no los contiene | Actualizar baseline/propietarios; no recrear lo retirado para satisfacer una matriz antigua |
| Dependencia hacia composición | `administration/cleanup.py:58,73` y `backup.py:240` importan `SCHEMA_REVISION` de `application`, que importa capacidades | Metadata pura, import independiente y rechazo de esquema incompatible |
| Training conoce Coach | `training/service.py:69-186` abre TX, escribe, llama `coach.training_changed` y cancela después; router obtiene Jobs de composición | Un iniciador y pruebas del handle/orden; no se diagnosticó pérdida de atomicidad |
| Lint no impone ownership | `.oxlintrc.json` activa cinco reglas y desactiva categorías; ejecución: 737 archivos, cinco reglas, cero errores | Entregar reglas de dependencias/exports y negativos; no atribuir estas garantías al lint actual |
| Referencias activas falsas | `.agents/docs/skills-inventory.md:82` llama actual a Node/JSON; `frontend/vite.config.js:11-15` cita `api/server.js`; `useStore.js:716-718` cita `api/sync-stamps.js` | Reconciliar routing y retirar prosa obsoleta antes de extender esos patrones |
| Inventario Compose contradictorio | `backend/README.md:13` anuncia exactamente cuatro entradas; luego documenta maintenance y restore, también versionados | Distinguir cuatro entradas ordinarias y dos operativas; comprobar las seis |
| Sync concentra responsabilidades | `useStore.js`, 1.984 líneas: owner, stashes, revisiones, push/pull, timers y móvil; `sheets.jsx`, 3.423 líneas, mezcla UI | Extraer por responsabilidad/caller; longitud orienta lectura, no obliga a dividir |
| Legacy activo no es código muerto | `useStore` importa/ejecuta `liftLegacy`; `sync-legacy.js` interpreta datos offline v1.3.9, con tests activos | Decidir fin de soporte/tratamiento de pendientes antes de borrar |
| Descripción móvil desactualizada | `build:mobile` ejecuta `cap sync`; `shared_client/formats_and_bundles` ya es prueba portable vigente | Reutilizarla, sin llamarla comparador transitorio ni acreditar dispositivo |

Checks ejecutados y límites: [plan de verificación](verification-plan.md#auditoría-local-ejecutada-el-2026-11-04). Los hallazgos de fuente no acreditan un fallo funcional reproducido en producción.

## Goals / Non-Goals

**Goals:** propietarios visibles, interfaces pequeñas, errores accionables en CI, retirada de implementaciones sustituidas, cero comentarios narrativos propios y prueba de que agentes nuevos encuentran dónde intervenir/verificar. Seis capacidades, recorridos independientes.

**Non-Goals:** operar instancias/datos/secretos reales; corte o Recovery; cambiar UX/HTTP/RLS/DDL/formatos/offline sin decisión de alcance; añadir stores por feature, event bus, repositorios genéricos, `apps/packages`, Nx/Turborepo, limpiador o runtime multiagente. No instalar P-stack ni copiar su automatización de merge/publicación.

## Decisions

### D1. Baseline independiente y primera retirada

Registrar revisión, dirty state, contratos/consumidores, comandos y recursos por slice. No exigir cierre de otras OpenSpec ni confundir retirada de fuentes con migración real. Corregir navegación falsa y retirar código sustituido antes de usarlo como patrón. No determinar consumidores mediante una búsqueda de palabras solamente.

Alternativa descartada: esperar corte real o repetir retirada Node. Ya existe entrega del repositorio; corte queda fuera de alcance.

### D2. Metadata y colaboración backend

Autoridad única `core/schema.py:SCHEMA_REVISION`, stdlib solamente, compartida por composición/cleanup/backup. Exponer `core.platform_settings.load_secret` renombrando helper privado y migrando consumidores, sin cambiar validación/formato/permisos.

`training_save.save(database, session, body, note_state, *, coach)` recibe el colaborador obligatorio de composición, autoriza y abre TX. `training.service.write_participant(handle, session, body)` posee documento/linaje y devuelve estado/resultado; no conoce Coach ni abre pool/commit. Iniciador llama `Jobs.training_changed` con el mismo handle y `Jobs.cancel` tras commit. Mantener semántica postcommit de note_state. Coach posee consentimiento/jobs/cuotas y consulta proyecciones públicas Training.

Conservar `test_failed_withdrawal_rolls_back_training_and_does_not_cancel_authorized_work`; probar éxito, revocación durante espera, commit fallido, identidad del colaborador y respuesta tardía. No inferir atomicidad de imports.

Alternativa descartada: event bus o fachada que reenvía al servicio todavía acoplado. La interface debe ocultar coordinación real.

### D3. Navegación por propietario

Planificación, tareas y resultados necesarios quedan autocontenidos en el cambio OpenSpec. `.agents/docs/issue-tracker.md` adapta las skills de tickets a esa autoridad; no se crea `.scratch/`, `docs/scratch` ni otro tracker. Ensayos/verificadores usan temporales exclusivos del sistema, consolidan lo útil y descartan el resto. Los comandos de reproducción y límites deben entenderse sin esos temporales.

AGENTS raíz para reglas comunes; `.agents/docs/` para detalle condicionado; OpenSpec para cambio/tareas; guías de módulos para contratos/uso. Instrucciones locales solo con reglas exclusivas. Cada capacidad conduce a entrada, interface pública, colaboradores, estado y pruebas. Actualizar código→regla→comando al mover código/tests, sin clonar todo el mapa en cada README.

Revisar activación, dependencias y solapamientos de skills. Lock acredita procedencia, no contenido idéntico. No copiar P-stack completo sobre skills locales. Declarar herramientas requeridas y degradaciones por cliente.

### D4. Frontend por capacidades

`useStore` sigue como única autoridad persistente; `useUI`, efímera. Extraer coordinación sin duplicar ownership/revisiones/pendientes/transacciones locales. Helpers puros de entrenamiento/sesión permanecen en `lib/` con test adyacente. UI/hooks/clientes pueden ir a `features/<area>/` si reduce dispersión; views compone, transporte común único y UI compartida sin dependencia de features.

| Recorrido | Invariantes |
| --- | --- |
| Training/sync | owner, revisión/linaje, pendientes, sesión en curso, pestañas, 401/409, respuesta perdida |
| Identity | password/passkey/pairing, rechazo/revocación, cambio de perfil con pendientes |
| Coach | local/demo/HTTP, consentimiento, jobs/propuestas, aplicación autorizada, Q6 sin fallback |
| Media | cola offline, referencias, bytes/owner conservados ante fallos |
| Administration | actor/target, facultades, borrado/cleanup, invitaciones/reset/audit |
| Notifications | dispositivos, presencia/timers efímeros, opt-out, web/móvil y límites de entrega |

No mover áreas ya cohesionadas por cumplir topología. Caracterización→cambio→prueba por recorrido; callers/mocks/generadores/bundles juntos.

### D5. Limpieza y comentarios

Objetivo: cero comentarios narrativos en fuente propia mantenida, incluidos banners, código comentado y docstrings puramente explicativos. Nombres/interfaces y pruebas expresan comportamiento propio. Contratos textuales y restricciones externas no codificables viven en su documento propietario, accesible desde el mapa. No trasladar toda la prosa a otra carpeta: conservar solo conocimiento necesario.

Antes de retirar explicación de un invariante, identificar o añadir la prueba que distingue el fallo; sin ella, retirada pendiente. Ejemplo postcommit: fallo de bookkeeping no cambia éxito reconocido. Deuda vigente se resuelve o pasa al tracker existente; no desaparece con el TODO.

Alcance exacto de fuente mantenida y exclusiones por generador en [V11](verification-plan.md#v11-formato-comentarios-y-retirada-de-implementaciones). La limpieza cubre toda esa fuente por lotes, no solamente módulos que se muevan. Hasta completarla, el checker se aplica a archivos aceptados y el resto sigue pendiente; aceptación final exige revisar el alcance completo sin una excepción permanente para comentarios antiguos.

Licencia/atribución y directivas efectivas se clasifican aparte: `@vitest-environment`, shebang/encoding, parser directives Docker, anotaciones de pureza, pragmas build/lint/tipos/coverage y docstrings que forman contrato/salida observable. Reemplazar por configuración/API equivalente cuando exista y probarla. Si no, excepción exacta con consumidor/motivo. Supresión de corrección: resolver diagnóstico o demostrar falso positivo, sin aceptarla por antigüedad. No prometer eliminación literal de toda sintaxis con forma de comentario.

Inventario de retirada en tarea/review: ruta, dueño, finalidad, consumidores, decisión, prueba sustituta y obligación pendiente. Tests/fixtures independientes no son basura. Históricos protegidos: revisar finalidad, preservar conocimiento y actualizar enlaces/índices/config/manifiesto juntos; no reescribir y rehashear para ocultarlo. OpenSpec archivado conserva decisiones, no un runtime duplicado.

Comprobar rutas absolutas reales, enlaces/junctions, pertenencia y escritores detenidos. Preservar trabajo concurrente, datos, secretos, backups y journals. Copia privada externa para retirada amplia, incluido untracked propio necesario. Sin `git clean`, borrado global o prune Docker; usar verificador propietario. No construir un limpiador genérico.

### D6. Grafo y exportaciones verificables

Mapa concreto en [verification-plan.md](verification-plan.md#exportaciones-e-interfaces-decisión-concreta). Público significa declarado, no simplemente exportado.

| Origen | Permitido | Rechazado |
| --- | --- | --- |
| Composición | capacidades/core | import inverso para metadata |
| core/metadata | infraestructura requerida; schema solo stdlib | funcionalidad/composición |
| Guardado coordinado | identidad, operaciones públicas Training/Coach/core | privados ajenos, otro pool/commit, cancelación precommit |
| Training participante | core/contexto autorizado | objeto/import Coach |
| Coach/Media/Notifications | proyecciones Training declaradas | repositorios/SQL privados Training, owner arbitrario |
| Feature frontend | store/transporte/helpers/UI comunes | internos de otra feature |
| UI compartida | primitivas comunes | features |

Integrar en checks/toolchain: imports estáticos/locales Python, dinámicos literales, JS/JSX y exports acordados. Computados no resueltos requieren revisión, sin pase automático. Preferir parser/AST y tooling existente a lector ad hoc; regex no prueba completa de JS. Fixtures positivas/negativas y diagnóstico ruta/regla/origen/destino/reparación, misma invocación local/CI. Sin allowlist global permanente ni promesa de análisis general de flujo. Colaboración por objetos requiere prueba de operación.

### D7. Pruebas y entrega

Cada tarea declara requisito/escenario, comando exacto, entorno, observador y expectativas. Regla nueva rechaza fixture negativa; refactor pasa caracterización antes/después. No inventar RED de producto en limpieza editorial. Browser requiere acción UI y observación independiente, no solo captura/nombre. Fake no acredita proveedor/hardware. Añadir cobertura faltante al harness vigente.

Checks del slice primero; integración al final. No repetir sin cambio/fallo/riesgo nuevo. Checkpoint pendiente bloquea recorridos solapados. Resultados en tarea/CI, sin segundo tracker o informe perpetuo.

### D8. Cero implementaciones sustituidas y compatibilidad activa

Prohibir copias de implementaciones retiradas en fuente/build/distribución, incluso renombradas legacy/archive. Git conserva su historia. Node herramienta de build, JS neutral, JSON runtime y fixtures independientes no son backend retirado.

| Artefacto actual | Decisión propuesta |
| --- | --- |
| `api/`, `backend/contracts/` | Sin fuente versionada; no recrear. Residuos locales requieren identificar contenido/propiedad |
| `coach/assets.json`, `notifications/copy.json` | Runtime generado; conservar fuentes/generadores/checks |
| Fixtures identity/WebAuthn/stamps/Coach | Expectativas independientes legibles, sin ejecutar servidor retirado |
| `sync-legacy.js` y callers/tests | Soporte activo v1.3.9; decidir fin de soporte y pendientes antiguos |
| `importer.py`, `scripts/platform-node-*.mjs` | Importación/captura congelada con consumidores sintéticos; no segunda API. Retirada requiere decisión de contrato |

Decisión explícita del promotor el 2026-11-04: eliminar sustituidos y decidir aparte las compatibilidades activas. Este cambio conserva soporte offline v1.3.9 e importación/captura Node mientras tengan consumidores. Retirarlos requiere una fase específica con requisitos afectados, evaluación BREAKING y migración/rechazo de datos definidos. Renombrar un runtime sustituido como adapter no satisface la retirada. Ningún borrado de datos/corte real queda autorizado.

### D9. Documentación final

Etapa 9 después de aceptación técnica: raíz/paquetes, agentes, arquitectura/API, operación/recuperación y deploy. Contrastar afirmaciones con fuente; ejemplos soportados/pendientes/históricos. Comandos en checkout aislado con datos sintéticos y límites de hardware/proveedor. OKF valida estructura, no verdad semántica. Cambios posteriores revalidan lo afectado. Resultado en tarea/PR.

### D10. Docker por propietario

Actual: seis Dockerfiles y seis Compose versionados, contando maintenance/restore. Conservar backend/Dockerfile con runtime/dev/test/migrate/ops y web/Dockerfile. Cliente neutral separado. Proponer browser/security bajo deploy/images y diagnóstico bajo deploy/diagnostics solo con beneficio de propiedad y consumidores/ignores actualizados juntos. No renombrar por estética.

Retirados: api/Dockerfile, backend/Dockerfile.contracts y Compose raíz. AI Tutor es contexto histórico, no dependencia/patrón normativo; esta auditoría no lo releyó ni validó.

Preservar COPY/contextos completos, ignore efectivo, locks, caché, no-root, privilegios y secretos por servicio. Ignore específico tiene precedencia sobre raíz [S10]. Bases web mutables: fijar identidad revisada/política de actualización sin prometer identidad bit a bit por FROM. Comparar renders dev/prod/test/prod+maintenance y restore pertinente con env sintético/directorio canónico; sin cambiar nombres de recursos, volúmenes o journals por mover recetas. API/DB privadas, prod sin build/reload, migración explícita/readiness real.

Etapa 10 antes de 8/9; daemon/Buildx autorizado para contexto/builds. Permiso faltante no prueba defecto ni build correcto. Sin instancias reales ni instalar tooling por inferencia.

### D11. Estado y gate de planificación

**Implementation Ready de planificación**. D8 resuelta por el promotor y D12 cerrada mediante ensayo aislado con versión/configuración exactas. Alcance, interfaces, seams de verificación, casos, comandos, escenarios, trazabilidad y orden de entrega definidos; no hay decisiones materiales abiertas. Validación CLI y revisión semántica se comprueban por separado. Las 60 tareas siguen pendientes y ninguna se marca por preparar la especificación. El encargo actual autoriza ensayo y preparación, no comenzar el refactor ni instalar la herramienta en el proyecto.

Los seams públicos HTTP/PG/browser, pruebas de operación/transacción, fixtures negativas y formatter están propuestos y documentados; no se afirma permiso de ejecución real ni aprobación adicional de TDD. Docker y sesiones nuevas de clientes son preflight/pruebas de sus tareas de entrega, no decisiones de diseño pendientes. Faltantes de entorno bloquean el slice que los requiere y su aceptación, sin convertirlos en PASS.

### D12. CI y formateo

Decisión: **oxfmt 0.76.0**, única nueva dependencia dev, sin rangos ni plugins. Conservar Ruff check/format y mypy fijados. Instalar en package.json/lock raíz únicamente durante 3.5, mediante pnpm add --save-dev --save-exact oxfmt@0.76.0. No añadir Prettier ni cambiar Oxlint. El ensayo no modificó dependencias, CI o fuentes originales.

La [plantilla exacta](formatter.config.json) es la autoridad de opciones/exclusiones; en 3.5 se traslada a .oxfmtrc.json raíz, sin mantener dos copias editables. Define 100 columnas orientativas, dos espacios, LF, comillas JS simples, sin semicolons finales, sin trailing commas, arrowParens=avoid, embeddedLanguageFormatting=off y objectWrap=collapse. Mantiene defaults fijados para JSX con comillas dobles y sorting de imports/clases desactivado, sin plugins; JSON no está en la selección del comando. Semicolons preventivos de ASI siguen siendo válidos. No formatear lenguaje embebido preserva templates/prompts/SQL como datos.

objectWrap=collapse evita que el layout previo de objetos cambie el resultado de la siguiente pasada. Con preserve, Oxfmt 0.76.0 no estabiliza seis de 716 archivos a ancho 100 y cuatro a 120. Prettier 3.9.10 reproduce los mismos casos al comparar esos seis archivos; cambiar de herramienta no resuelve esa causa. Ambas estabilizan esos seis con collapse; Oxfmt pasa además el alcance completo de 716 con la configuración final. Elegimos una herramienta coherente con el tooling Oxc existente; no se atribuye una ventaja de rendimiento no medida.

Fuente npm oficial: engines ^20.19.0 || >=22.12.0; paquete y binding Windows ensayados en 0.76.0. Identidad npm oxfmt: sha512-Yo9RIn9lRWTm/U8obHbXUWc39lCpEFXlEggFoPx01zS18OCFi7mAwMmL05+p1AunuJgSkONffWyBHJzpMMCRuQ==. Pin y fuente de versión en [release oficial](https://github.com/oxc-project/oxc/releases/tag/oxfmt_v0.76.0) y [package.json del tag](https://github.com/oxc-project/oxc/blob/oxfmt_v0.76.0/npm/oxfmt/package.json). Al actualizar, repetir el ensayo; no seguir latest ni actualizarlo automáticamente con el lint.

Comando fijo local/CI y configuración sin descubrimiento anidado, desde raíz:

```sh
pnpm exec oxfmt --config .oxfmtrc.json --disable-nested-config --check "frontend/**/*.{js,jsx,mjs,css}" "scripts/**/*.{js,mjs}" "shared/**/*.js"
```

3.5 añade fmt:check con esa invocación y fmt con --write en su lugar, al package.json raíz; quality ejecuta pnpm run fmt:check tras instalación frozen. Paths entre comillas se expanden por la herramienta en Windows/Linux. No usar oxfmt . ni un wrapper nuevo. Ignorados: generados identificados, catálogo/media, shells, dependencias/outputs, Markdown/históricos, locks y website separado. Diff mecánico separable y revalidación de idempotencia/fixtures en entrega.

El [ensayo](verification-plan.md#ensayo-del-formatter-completado-el-2026-11-04) corrió CLI y regresiones en Windows x64/Node 22.23.2: 716 archivos, 660 tests, 38 generados/ocho sentinelas intactos y 999 originales sin cambios por hash. La comparación estructural normaliza representaciones equivalentes JS/JSX y trivia CSS; no es prueba formal. No se ejecutó el binding Linux, CI remoto, navegador ni hardware. 3.5 debe verificar Linux/CI antes de aceptar la integración; esto no deja abierta la elección del formatter.

Comentarios: tokens/AST, sin regex que confunda URLs/strings/regex JS/prompts. Python tokenize y docstrings clasificados aparte; JS/JSX con parser disponible o dependencia justificada. Otros formatos tocados: revisión contextual hasta tener parser, sin acreditar cobertura universal. Integrar en comandos existentes. Directivas efectivas según D5.

CI ejecuta primero controles baratos y después tests de capacidad/integración/build/browser exigidos. Diagnósticos accionables y resultados/límites explícitos; selección desconocida u omisión no recibe éxito. Manifest/runner actuales siguen como autoridad.

### D13. Utilidad comprobada para agentes

Soporte inicial propuesto: Codex y Cursor; no se ensayó onboarding nuevo de ninguno aquí. Sesión nueva/checkout aislado por cliente: seis briefs, uno por capacidad, para ubicar propietario, interface, estado, regla y comando, e identificar violación/diagnóstico. Sin suministro manual de rutas ni datos reales. Navegación y resolución de bugs se evalúan por separado.

Criterio: seis de seis respuestas correctas por cliente, cero accesos privados/comandos inventados y evidencia de instrucciones cargadas. Medir tiempo, documentos abiertos y correcciones humanas antes/después; no fijar mejora porcentual sin baseline. Resultados en tarea/CI, sin plataforma de evaluación nueva.

AGENTS/Agent Skills aportan formato común [S6,S7,S11]; carga depende del cliente. Declarar solo clientes ensayados; adapters mínimos apuntan a una autoridad sin duplicar política. P-stack se estudió como referencia: no se ejecutaron arena/interrogate/no-comments ni sus subagentes/modelos/harness particulares.

## Fuentes y lectura crítica

Primarias consultadas el 2026-11-04. P-stack leído en main mutable, sin pin de commit confirmado: acredita contenido consultado, no versión instalada. Incorporarlo exige pin/procedencia/adaptación. Son referencias de diseño, no prueba de efectividad en OpenGym ni estándares que obliguen a copiar toda su arquitectura.

- **[S1]** [Cursor, P-stack README](https://github.com/cursor/plugins/blob/main/pstack/README.md): workflows y adapters por harness. Adoptar investigación/verificación según tarea; no importar merge ni selección de modelos como política de producto.
- **[S2]** [P-stack architect](https://github.com/cursor/plugins/blob/main/pstack/skills/architect/SKILL.md): callers/interfaces y diseños alternativos. Aquí: monolito modular frente a reorganización global y coordinación explícita frente a event bus.
- **[S3]** [No-comments](https://github.com/cursor/plugins/blob/main/pstack/skills/no-comments/SKILL.md) y [comment-sicko](https://github.com/cursor/plugins/blob/main/pstack/agents/comment-sicko.md): retirada de prosa con excepciones explícitas, incluidas licencias, contrato público y restricciones externas. No equivale a borrar cualquier sintaxis de comentario. Adaptación: codificar/verificar garantía antes de retirar explicación.
- **[S4]** [Subtract before you add](https://github.com/cursor/plugins/blob/main/pstack/skills/principle-subtract-before-you-add/SKILL.md): quitar complejidad sustituida antes de extender patrones; no borrar fixtures que protegen contratos vigentes.
- **[S5]** [OpenAI, Harness engineering, 2026-02-11](https://openai.com/index/harness-engineering/): repositorio como conocimiento, instrucciones como mapa y restricciones mecánicas. Sus métricas no predicen OpenGym ni justifican relajar nuestros gates.
- **[S6]** [Official OpenAI documentation, AGENTS.md](https://developers.openai.com/codex/guides/agents-md/): carga jerárquica/límites de contexto y prueba de instrucciones cargadas; enlaces Markdown no implican carga automática.
- **[S7]** [Agent Skills specification](https://agentskills.io/specification): metadatos, compatibilidad y carga progresiva. Formato válido no prueba ejecución correcta.
- **[S8]** [Oxfmt, release 0.76.0](https://github.com/oxc-project/oxc/releases/tag/oxfmt_v0.76.0), [configuración](https://oxc.rs/docs/guide/usage/formatter/config-file-reference.html) y [exclusiones](https://oxc.rs/docs/guide/usage/formatter/ignore-files.html): versión y opciones contrastadas también con el schema del paquete instalado. [Prettier, opciones](https://prettier.io/docs/options) orientó la comparación; la decisión final se apoya en el ensayo local, no en benchmarks del proveedor.
- **[S9]** [Oxlint no-cycle](https://oxc.rs/docs/guide/usage/linter/rules/import/no-cycle) y [Ruff formatter](https://docs.astral.sh/ruff/formatter/): checks mecánicos; prohibir ciclos no valida ownership ni transacciones.
- **[S10]** [Docker build context](https://docs.docker.com/build/concepts/context/): inputs e ignore efectivos; mover recetas requiere probar qué entra al build, además del YAML.
- **[S11]** [GitHub Copilot instructions](https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/add-custom-instructions/add-repository-instructions): soporte de instrucciones depende de cliente/función; no prometer compatibilidad universal.

Transcripción aportada: 9:16–12:22 (CLI reproducible y feature map), 14:57–18:51 (arquitectura→análisis estático→reglas/skills), 20:46–25:00 (workarounds/comentarios), 26:56–30:28 (colocación/imports y código como memoria). Fuente primaria aportada con errores de transcripción y sin URL/fecha del video verificadas. No se usan cifras de PR/nombres empresariales como hechos comprobados. Dune/Electron ilustra enforcement, no una arquitectura que portar a esta PWA.

## Risks / Trade-offs

- [Retirada de compatibilidad consumida causa pérdida/rechazo de datos] → decisión de soporte y pruebas de pendientes/contratos antes de borrar.
- [Retirar prosa pierde garantía/directiva] → codificar/probar primero, clasificar tokens y verificar consumidores.
- [Formatter oculta refactor con churn] → diff mecánico separable, sin ordenar imports con efectos.
- [Imports pasan con colaboración indebida por objetos] → pruebas de handle/commit y revisión de interface.
- [Documentación compite con código] → una autoridad, routing breve y retiro de textos sustituidos.
- [Score produce confianza excesiva] → distinguir juicio de diseño, checks y prueba de comportamiento; sin corrección universal prometida.

## Migration Plan

Baseline/decisiones → navegación falsa/sustituidos demostrados → backend/controles/formato → Docker → sync/seis capacidades → higiene residual → aceptación técnica → onboarding final → etapa 9 documental. IDs existentes conservados; tareas nuevas insertadas por dependencia.

Reversión mediante diffs/archivos propios separables; no reset global, datos ni restauración del runtime retirado. Sin DDL/operación real. No commit/push, archive o sync en esta fase.

## Open Questions

Ninguna decisión material abierta de planificación. D8 conserva compatibilidades activas y D12 fija Oxfmt 0.76.0/configuración ensayada. Los preflight y pruebas de entrega siguen pendientes y no se acreditan como ejecutados por declarar Implementation Ready.
