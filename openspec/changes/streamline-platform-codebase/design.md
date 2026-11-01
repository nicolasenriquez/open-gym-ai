## Context

Este diseño se prepara sobre la rama `docs/opengym-evolution-discovery`, revisión explorada `5f8f70519`. El port registra 47/57 tareas; no se asume aceptación real. Se reexplora el checkout actual porque rutas/hallazgos cambian; comenzar después del port es una preferencia no vinculante, sin dependencia de finalización/aceptación de otra OpenSpec.

### Evidencia de prime-codebase y triage

OpenGym conserva React/Vite/Zustand y shells Capacitor; el backend objetivo es un monolito modular Python/FastAPI/PostgreSQL, con JSONB Training compatible y biblioteca neutral `shared/coach-core/`. Python usa uv, pytest, Ruff y mypy; frontend usa pnpm y Vitest; el harness existente selecciona suites/casos e integra HTTP/PG/browser sintéticos. No hace falta otro gestor de monorepo.

| Hallazgo de exploración | Fuente actual | Tratamiento |
| --- | --- | --- |
| La composición posee la revisión SQL, pero Cleanup y backup importan esa composición para leerla | `backend/src/opengym_platform/application.py`, `administration/cleanup.py`, `backup.py` | P1: metadata pura, sin invertir dependencias hacia HTTP |
| Training invoca Coach dentro de TX y cancela después; Coach consume proyecciones Training | `training/service.py`, `training/router.py`, `coach/jobs.py` | P1: explicitar colaboración y conservar rollback; no es prueba de bug transaccional |
| Existe cobertura de rollback ante retirada de consentimiento fallida | `backend/tests/platform/test_coach_lifecycle.py` | Conservar garantía y probar también éxito, revocación y cancelación posterior al commit |
| Sync mantiene coordinación, ownership y efectos móviles dentro de una clausura grande | `frontend/src/store/useStore.js`, `lib/sync-*`, `lib/remote.js` | P2: profundizar coordinación, sin dividir el documento en stores independientes |
| Guías contienen afirmaciones históricas ya superadas y reglas sin control general | `.agents/README.md`, `docs/reference/platform-modularity.md`, `.oxlintrc.json` | P1: corregir autoridad y controles focalizados, no solo enlaces |
| Runtime, migrador y ops ya tienen targets separados | `backend/Dockerfile` | Conservar separación; no crear infraestructura duplicada |
| Existe trabajo externo de retirada Node/contratos | Contexto histórico de exploración, no dependencia | Preservar consumidores actuales; no exigir finalización ajena |
| El perfil OKF ya permite retirada revisada de históricos y el tracker define closeout de scratch | `docs/standards/okf-profile.md`, `docs/operations/okf-authoring-guide.md`, `.agents/docs/issue-tracker.md` | Reutilizar esas políticas; inventario por finalidad, no GC por antigüedad |

Las rutas son puntos de partida, no una lista cerrada de archivos a mover. La comprobación de redundancia encontró shared/OpenAPI/diagnóstico ya entregados: no se vuelven a implementar. No había registros de rechazo en `.out-of-scope/` al preparar el cambio. Las capacidades nuevas son garantías de mantenimiento, no cambios a contratos de producto existentes.

## Goals / Non-Goals

**Goals:**

- Concentrar conocimiento, cambios y pruebas en sus módulos propietarios, con interfaces pequeñas y colaboraciones explícitas.
- Organizar seis capacidades frontend mediante slices aceptables por separado: Training, Identity, Coach, Media, Administration y Notifications.
- Hacer comprobables unas pocas reglas de dependencia y ofrecer navegación código → regla → prueba.
- Retirar texto y evidencia sustituidos sin destruir conocimiento vigente, pruebas reproducibles o material ajeno/protegido necesario.

**Non-Goals:**

- Ejecutar o repetir el corte, restaurar datos reales, ejecutar retirada operativa de Node o aceptar operativamente la plataforma.
- Cambiar UX, contratos HTTP, coerciones, permisos/RLS, esquema SQL, formatos o reglas de entrenamiento; normalizar JSONB; cambiar el comportamiento offline.
- Reorganizar toda la raíz como `apps/packages`, añadir stores por feature, repositorios genéricos, event bus, framework de orquestación, Nx/Turborepo o conversión general a TypeScript.
- Recovery, nuevos proveedores/agentes o habilitación SDK/CLI por Q6; borrar backups, secretos, perfiles, catálogo, prompts o datos de usuario.
- Reescribir Git, compactar historial, crear informes permanentes de limpieza o borrar comentarios por cuota, edad, longitud o nombre de directorio.

## Decisions

### D1. Ejecución independiente y baseline propio — P0

Esta propuesta es independiente de todas las demás OpenSpec. Empezar después del port es preferencia no vinculante: no se exige cierre, aceptación, corte ni retirada ajenos para ejecutar o aceptar este cambio. Antes de un slice autorizado se registran revisión, estado local, runtimes/contratos activos, comandos y permisos propios. Si conviven Node/Python y herramientas transitorias, se preservan sus consumidores. Una prueba o permiso propio faltante bloquea la acción afectada; no todo el cambio por el estado de otro. El corte de instancias reales queda fuera de alcance. Preparar documentos no autoriza implementar.

### D2. Metadata y colaboración backend — P1

Extraer únicamente metadata pura de compatibilidad fuera de la composición, con una autoridad compartida para HTTP y comandos operativos. Ningún módulo funcional ni comando importa la aplicación para obtener constantes. No crear un registro genérico.

Revisar el caso completo de guardado Training–Coach: iniciador, participantes, permisos, handle compartido, resultado y efectos posteriores al commit. Preferir la menor modificación que haga explícita la colaboración y elimine el conocimiento recíproco innecesario; extraer una operación coordinada solo si concentra complejidad real. No prescribir nueva carpeta global ni event bus. Documentar y comprobar el grafo aceptado, incluida la colaboración pasada como objeto que un control de imports no ve.

El module debe ganar depth mediante una interface que oculte coordinación; el seam conserva autorización/atomicidad. Cada adapter responde a variación real; locality y leverage se justifican con consumidores y pruebas, no por número de archivos. Aplicar el deletion test: una fachada que solo delega y deja el conocimiento disperso se descarta.

### D3. Navegación y controles — P1

Actualizar propietarios existentes: AGENTS raíz para reglas comunes, referencias para detalle condicionado, OpenSpec para cambio y tareas, guías de módulos para uso vigente. No clonar reglas en cada README. Añadir instrucciones locales solo si hay reglas exclusivas que no se explican mejor por referencia. Revisar solapamientos de skills por responsabilidades y activación; no eliminarlas por cantidad.

Integrar en verificación/CI existente controles para imports hacia composición, dependencias funcionales desde core y acceso a internos ajenos según interfaces acordadas; tratar imports locales/dinámicos explícitamente. Fixtures negativas deben demostrar rechazo sin contaminar producción. Excepciones, si son necesarias, llevan razón y condición de retirada; no una allowlist global indefinida. El análisis estático no acredita atomicidad ni detecta toda colaboración indirecta.

El module de verificación conserva una interface breve para seleccionar suites/casos, con adapter por herramienta existente. Su seam no crea un segundo runner; depth, locality y leverage reducen decisiones repetidas. Un agente debe encontrar, para cada capacidad, propietario, contratos, colaboradores y comandos sin leer toda la documentación.

### D4. Frontend por capacidades, sin nueva autoridad — P2

Mantener `useStore` como autoridad persistente y `useUI` efímera. La coordinación extraída de sync comparte esa autoridad y no duplica ownership, revisiones, pendientes ni transacciones locales. Helpers puros que leen sesiones o deciden entrenamiento permanecen en `lib/` con sus pruebas, conforme AGENTS.

Tras caracterizar sync, intervenir las seis capacidades una a una. Cada slice declara recorrido observable, archivos/consumidores, interface, colaboradores, almacenamiento, fallos y pruebas. Ubicar UI/hooks/cliente propios bajo `features/<area>/` cuando reduzca dispersión; `views/` compone, transporte común sigue único y UI compartida no importa internals de features. No exigir carpetas vacías ni un archivo por capa. Mover código y pruebas juntos cuando corresponda; actualizar imports, mocks, tests, bundles y generadores consumidores.

| Orden sugerido | Capacidad | Invariantes a preservar |
| --- | --- | --- |
| 1 | Training/sync | ownership, revisión/linaje, pendientes, sesión en curso, pestañas, 401/409, respuesta perdida y reanudación |
| 2 | Identity | login/password/passkey/pairing vigentes, rechazo/revocación y decisión sobre datos locales al cambiar perfil |
| 3 | Coach | local/demo/HTTP, consentimiento, jobs/propuestas, aplicación autorizada y Q6 sin fallback |
| 4 | Media | cola offline, referencias, bytes/ownership y no pérdida de archivos ante error |
| 5 | Administration | actor/target, facultades vigentes, borrado y limpieza pendiente, invitaciones/reset/audit según contratos |
| 6 | Notifications | web/móvil, dispositivo, presencia/timers efímeros, opt-out y ausencia de promesa exactly-once |

La interface de cada module oculta coordinación propia; un seam y sus adapters se introducen solo donde existe variación. El beneficio de depth se verifica como locality y leverage: una corrección representativa se concentra en su capacidad sin replicarse en pantallas. No hay un objetivo artificial de líneas o archivos.

### D5. Limpieza por finalidad y consumidores — P2 transversal

Se acuerda incluir texto y evidencia históricos protegidos, revisando cada retirada. Crear inventario acotado en la tarea/PR con ruta exacta, propietario, finalidad, consumidores y decisión: conservar, condensar en propietario vigente o retirar. Para evidencias retenidas, incluir obligación pendiente y condición de eliminación; la antigüedad no basta.

Separar tres clases:

1. **Textos:** README, guías e instrucciones duplicadas, cronología de implementación y referencias obsoletas. Integrar conocimiento útil en su fuente propietaria y retirar repetición; mantener contexto temporal de investigación necesaria. No crear `archive/`, `log.md` o auditoría perpetua por rutina.
2. **Evidencias de ejecuciones:** logs, capturas, exports sintéticos, helpers temporales y copias locales propias bajo `.scratch/<tarea>/`, `.playwright-cli/` o temporales identificados. Conservar lo exigido por revisiones abiertas, aceptación, regresiones no reproducibles o retención vigente. Los tests ejecutables, fixtures independientes y pruebas de garantías no son basura por haber sido escritos en el pasado.
3. **Comentarios:** retirar los que narran literalmente el código, rutas/estados falsos y cronología ya irrelevante. Conservar explicación del porqué, invariantes, condiciones de carrera, seguridad, compatibilidad y regresiones todavía posibles. Reducir contexto histórico a la razón vigente cuando aporte más claridad. Preservar licencias/atribución, directivas de lint/types/build/coverage y TODO/shortcut con obligación vigente; no esconder deuda.

Ejemplo que se conserva por su razón vigente: la advertencia de que bookkeeping postcommit no puede cambiar el éxito reconocido en Training. Una nota QA antigua sobre pérdida de datos no se borra solo por su fecha: se conserva o condensa si explica un riesgo actual.

Para borrar archivos locales: comprobar que escritores terminaron, revisar rutas absolutas y destino real a través de enlaces/junctions, limitarse a artefactos propios y preservar cambios/untracked ajenos. Antes de una retirada amplia, copia privada fuera del repo con rutas/hashes de lo necesario, incluyendo trabajo local; sin secretos en logs/inventarios públicos. No enumerar datos personales ni credenciales como candidatos. No usar borrado recursivo global, `git clean`, prune global ni GC programado nuevo. Docker se limpia mediante el verificador propietario, no borrando directorios.

Los históricos del manifiesto OKF no se reescriben y se rehashean para hacer pasar un check. Una retirada/traslado justificado revisa consumidores y conocimiento, actualiza enlaces, índices, configuración y manifiesto juntos; un traslado sin reescritura conserva el hash. Los OpenSpec archivados y tickets con decisiones/obligaciones se preservan como trazabilidad; no se vacían por cuotas. Esta propuesta y su ticket no se autoeliminan durante la ejecución.

El module de higiene usa una interface de selección revisada, no un demonio; su seam valida pertenencia/finalidad y los adapters de archivos/documentación existentes realizan solo la operación acotada. Depth concentra las comprobaciones, locality vincula decisión y tarea, leverage evita repetir criterios. No se crea un limpiador genérico sin una necesidad real.

### D6. Precisiones de la auditoría: resultado y control de dependencias

Esta sección precisa D2–D5 sin ampliar contratos de producto. La terminología de D5 describe responsabilidades de revisión, no autoriza implementar un módulo/framework de higiene ni adapters nuevos. Usar revisión del diff, herramientas de archivos y controles documentales existentes.

El resultado backend elegido es una sola operación iniciadora de guardado coordinado: autoriza, abre TX, llama participantes Training y Coach con el mismo handle, decide commit y solicita cancelación después. Training posee documento/linaje y no recibe un objeto Coach ni decide su política; Coach posee consentimiento/jobs/cuotas y puede consultar proyecciones públicas Training. Ningún participante abre commit/pool propio. Reutilizar una operación existente si ya cumple; no añadir una fachada para mantener la coordinación dispersa. El nombre/archivo exacto se confirma tras 1.2 sin cambiar este contrato ni crear un framework de orquestación.

| Origen | Dependencias permitidas | Rechazo verificable |
| --- | --- | --- |
| Composición HTTP | módulos funcionales y core | un módulo funcional/comando importando composición para metadata, incluso dentro de una función |
| core/metadata | stdlib y dependencias de infraestructura ya necesarias | import de Training, Identity, Coach, Media, Administration, Notifications o composición |
| Guardado coordinado | identidad autorizada y operaciones públicas Training/Coach, core | SQL ajeno, acceso a privados, otro pool/commit o cancelación previa a commit |
| Training participante | core e identidad/contexto autorizado | dependencia funcional Coach, incluso un objeto Coach pasado como argumento |
| Coach, Media, Notifications | consultas públicas Training y colaboradores autorizados en el mapa | tablas/repositorios privados Training o acceso con owner arbitrario |
| Feature frontend | store/transportes comunes, helpers puros y UI compartida | imports a internos de otra feature; UI compartida importando una feature |

Antes de 3.2, 3.4 registra en la guía propietaria las exportaciones consumidas realmente y el mapa concreto de módulos/archivos. Exportado no equivale automáticamente a público: es público si se declara como operación permitida con consumidor, permisos y pruebas. Nombres con prefijo `_`, repositorios/tablas privados y estado interno ajenos están prohibidos; un uso existente se migra, no se blanquea mediante una allowlist general. Una excepción específica requiere consumidor, razón, prueba y condición de retirada, revisada explícitamente.

El control cubre imports estáticos Python/JS y locales Python. Imports dinámicos con destino literal se resuelven; un destino computado que impida decidir se señala como no verificado y requiere revisión explícita, no pase silencioso. No construir un intérprete general ni prometer análisis completo de flujo. Fixtures positivas/negativas prueban estas categorías; colaboración por objetos/handles se comprueba también mediante pruebas de la operación.

### D7. Contratos de prueba y recorridos acotados

Cada tarea tiene Traceability y Proof/Check adyacentes. La matriz de comandos V0–V9 de tasks es referencia inicial al checkout explorado, no prueba ejecutada ni dependencia eterna del harness del port. En 1.3 se registran comandos exactos, casos seleccionados, entorno, observador y resultado esperado actuales. Un comando retirado no se resucita: identificar su reemplazo nativo, o bloquear el slice hasta definirlo. No cerrar tareas con marcadores sin resolver.

Para refactors sin cambio de comportamiento, la caracterización debe pasar antes y después; no se inventa un RED de producto. Las reglas nuevas se prueban con fixture negativa que falla sin la regla y es rechazada con ella. Añadir regresión fail-first solo si aparece una garantía ausente o fallo real dentro del alcance. Las pruebas HTTP/PG observan estado/rollback independientemente; Vitest prueba coordinación pública y efectos de transporte/almacenamiento; browser conduce acciones UI reales, sin fabricar éxito ni mutar internals para acreditar el recorrido. Un fake de transporte no acredita proveedor, push o dispositivo reales.

Estado de los seams: propuestos para entrega futura, no implementados ni verificados por esta actualización documental. La aprobación de redactar el diseño no autoriza nuevos hooks de producto ni cambios de permisos. Reutilizar los seams públicos y sintéticos ya aceptados; una necesidad materialmente distinta se revisa antes de entrega.

Las tareas existentes 5.2, 5.4, 6.2, 6.4 y 6.6 son checkpoints de aceptación de sus recorridos nuevos, no mandatos de mover una capacidad completa en una sesión. Cada recorrido nuevo caracteriza → reorganiza lo necesario → verifica antes del siguiente. Si una responsabilidad ya está bien localizada, conservarla y acreditar interface/consumidores/pruebas satisface el slice; no exigir movimientos por cuota. Las seis capacidades siguen dentro del alcance.

### D8. Clasificación de JSON y obligación heredada

Observaciones de auditoría, a revalidar en 1.2:

| Artefacto | Tamaño observado aproximado | Finalidad / decisión |
| --- | --- | --- |
| `backend/src/opengym_platform/coach/assets.json` | 559 KiB | Datos runtime generados: catálogo reducido de 5.632 ejercicios, prompts y esquemas; conservar autoridad/generador y check, no tratar como proof antiguo |
| `backend/src/opengym_platform/notifications/copy.json` | 20 KiB | Copy runtime generada; conservar mientras tenga consumidores |
| `backend/contracts/training-stamps.v1.json` | 137 KiB / 40 vectores | Contrato transitorio: conservar mientras tenga consumidores; su retirada externa no es prerrequisito |
| `backend/contracts/identity-passkeys.v1.json` | 61 KiB / 51 casos | Igual tratamiento transitorio, preservando garantías WebAuthn independientes |
| `backend/tests/platform/fixtures/coach-vectors.json` | 49,5 KiB | Referencia independiente consumida por pytest; revisar minimalidad/legibilidad y cobertura sin borrar por origen Node ni regenerar expected desde Python |

La auditoría observó guía contradictoria sobre retener/retirar contratos. Resolverla según finalidad, consumidores y garantías actuales, sin exigir evidencia de otra OpenSpec. Una eliminación sin prueba sustituta o con lectores activos se bloquea individualmente, conservando el artefacto, sin impedir trabajo independiente.

El resultado es cero eliminaciones sin justificación ni contradicciones activas de retención, no cero contratos, cero JSON ni cero trazas históricas. Los fixtures mínimos conservan procedencia/garantía explícita y no copian dumps íntegros. Los datos runtime nunca se editan o eliminan como limpieza de evidencia; si se cambia una fuente canónica necesaria, regenerar únicamente mediante su generador y verificar consumidores.

### D9. Documentación final sobre el árbol resultante

La documentación acompaña cada slice; 3.1 ofrece navegación inicial y 7 retira material redundante. La nueva etapa 9 vuelve a reconciliar el conjunto después de 8: la aceptación de 8 es técnica y revisable, no cierre final. Ninguna tarea previa completa esta fase por haber ejecutado OKF.

Inventariar al menos README/CONTRIBUTING/AGENTS raíz, `.agents/README.md` y referencias afectadas, guías frontend/backend, arquitectura/modularidad, API/OpenAPI, self-hosting, operación/backup/restore/diagnóstico, índices y ejemplos Compose/Helm/Kubernetes existentes. Cada entrada indica propietario, afirmaciones/commands afectados y estado soportado/pendiente/histórico. No ampliar soporte a Helm/Kubernetes por documentarlos; corregir o retirar referencias activas según soporte real.

Cada afirmación relevante de runtime, ruta, interface, privilegio, imagen, configuración o comando enlaza a fuente/contrato o evidencia de la revisión final. Ejecutar en checkout limpio aislado los comandos de onboarding/build/test/diagnóstico documentados aplicables; comandos operativos se ensayan solo sobre fixtures/datos sintéticos y sin tocar una instancia real. Comandos destructivos o dependientes de hardware/proveedor no se ejecutan sobre producción: registrar revisión/ensayo disponible y límite; si su validación es requisito de aceptación, pendiente bloquea, no se omite como éxito.

Registrar en 9.5 revisión final y árbol limpio, matriz afirmación→fuente/comando→resultado/límite, discrepancias cerradas, evidencia retenida y condiciones de retirada. Solo metadata de revisión necesaria, sin nuevo informe perpetuo ni fechas de verificación inventadas. Si el código cambia después de la comprobación, revalidar superficies afectadas. Cierre bloqueado por comandos rotos, contradicciones activas, enlaces a artefactos retirados o afirmaciones de soporte no demostradas.

### D10. Segunda auditoría y organización Docker aditiva

Los findings anteriores quedan cubiertos documentalmente por D6–D9: iniciador y grafo, pruebas por tarea, recorridos menores, clasificación JSON, limpieza sin subsistema y documentación final. La etapa 9 está definida por inventario, reconciliación, retirada residual, comandos aislados y aceptación; no está ejecutada. Se concretan comandos/casos/exportaciones del checkout actual, sin gate operativo externo. Validación CLI completa no implica Implementation Ready.

Precisiones de dependencias de prueba: el V3 nuevo se entrega en 3.2–3.3. En 2.3 se hace revisión manual del grafo y las pruebas V2, con repetición automática V3 en 8.2; 3.4 diseña y registra fixtures/comando, no exige haber implementado el check. No hay dependencia circular de 2.3/3.4 hacia una prueba futura para poder definirla. El mismo criterio aplica a V10: primero diseño/fixture y después comprobación implementada. Un caso pendiente nunca se registra como PASS.

#### Inventario y evaluación de openGym

Inventario explorado: siete Dockerfiles activos versionados y seis Compose, sin contar recetas de prototipos locales en scratch. Revalidar tras retirada: API Node y contratos transitorios no deben mantenerse solo para completar esta lista.

| Receta o familia actual | Propiedad y evaluación | Acción prevista |
| --- | --- | --- |
| `backend/Dockerfile` | Targets dependencies/test/runtime/dev/migrate/ops/default; runtime no-root, sin Node/pytest/importador/backup y roles separados | Conservar junto al backend y mantener default=runtime; no unificar todo en una imagen |
| `web/Dockerfile` | Build Vite y runtime nginx no-root, contexto raíz por shared/catalogue; usa tags base mutables y `apk upgrade` | Conservar junto a web; fijar inputs base de la cadena y explicitar límites de reproducibilidad de paquetes/repositorios |
| `backend/Dockerfile.browser` | Verificación transversal frontend/Playwright, no módulo backend | Trasladar, si sigue activo, a `deploy/images/browser.Dockerfile` con ignore específico y contexto raíz explícito |
| `backend/Dockerfile.security` | Herramientas de auditoría y locks propios, contexto raíz | Trasladar, si sigue activo, a `deploy/images/security.Dockerfile` con ignore específico; no mezclar herramientas con runtime |
| `backend/diagnostics/` | Servicio auxiliar propio con rsyslog/logrotate/config/runner y contexto pequeño | Reubicar como unidad en `deploy/diagnostics/`, preservando contexto autocontenido y contrato de logging |
| `api/Dockerfile`, `backend/Dockerfile.contracts` | Runtime Node y comparación transitoria | Conservar consumidores activos; retirada operativa fuera de alcance, no prerrequisito |
| Compose raíz Node | Runtime todavía vigente antes de corte | Documentar selector/runtime vigente sin exigir retirada ni alterar instancia real |
| `deploy/docker-compose.yml` + dev/prod | Base con controles comunes y overlays explícitos; prod usa IDs locales verificados y no build/reload | Conservar estrategia y nombres por compatibilidad; una guía/entrada canónica, sin ocultar la composición |
| `deploy/docker-compose.test.yml` | Stack sintético con nombres/labels propios, sin puertos de instancia real | Conservar aislamiento; actualizar rutas/targets después de retirada sin relajar contexto |
| `deploy/docker-compose.maintenance.yml` | Overlay explícito sobre prod, secretos por archivo y rutas privadas | Conservar como overlay separado; mover archivos no debe invalidar configuración/journal de instancia registrada |

Muchos Dockerfiles no prueban falta de profesionalidad: separan ciclos de dependencias y privilegios distintos. No se fija una cuota de archivos. Se centraliza lo transversal, no la lógica de build de cada producto. La ubicación no determina el build context. Al mover un Dockerfile con ignore específico se mueve/actualiza también su ignore; este sustituye al `.dockerignore` raíz, no se suma automáticamente.

Fortalezas existentes: imágenes Python/tooling con digests, locks y caché BuildKit; API no-root/read-only, cap_drop y no-new-privileges; API/DB privadas y web loopback; secretos por archivos y roles acotados; despliegue prod sin instalación/build al iniciar; healthchecks diferenciados y migración explícita mediante wrapper; pruebas de contexto, layout, ownership, imágenes y caché. No duplicar esas entregas ni atribuir su éxito a este nuevo cambio.

#### Contraste con AI Tutor

Se leyeron únicamente instrucciones y archivos de despliegue de `C:/Users/nenri/OneDrive/Desktop/proyectos/pry-ai-evaluator/ai-tutor`, revisión Git obtenida `c28d4c36559218565845c447bcc64a89565881d9`. No se modificó ni arrancó AI Tutor, ni se pudo acreditar su estado limpio con el `git status` ordinario del entorno; la referencia de revisión no certifica sus archivos locales.

Adoptar la claridad de `deploy/` como punto de entrada, documentación del contexto y variantes separadas local/e2e. No copiar su imagen única frontend+FastAPI, blue/green ni Whisper: resuelven otro producto. Su Compose repite la configuración app-blue/app-green y fija container_name; varias bases usan tags sin digest, Whisper instala dependencias sin lock y el override local expone directamente el puerto app mientras el CMD confía proxies de cualquier IP. Son trade-offs/riesgos observados en archivos, no incidentes reproducidos. openGym no debe retroceder en reproducibilidad, permisos, separación web/API ni aislamiento para parecerse a esa estructura.

#### Contrato de reorganización y verificación

1. Registrar matriz receta→propietario→contexto→ignore efectivo→targets→consumidores→estado conservar/mover/retirado según baseline. Todos los COPY requeridos deben entrar al contexto; tests deben cubrir la lista completa, no solo dos fixtures representativas. Env privados, credenciales, scratch, dependencias host y salidas previas deben quedar fuera. No leer ni imprimir secretos reales para comprobarlo.
2. Mantener un Dockerfile principal por producto con stages reutilizables donde comparten dependencias; conservar browser/security/diagnóstico separados por propósito. No adoptar Bake/include ni generar Compose sin necesidad comprobada. Actualizar CI, runners, docs y referencias absolutas/relativas; no dejar aliases editables duplicados.
3. Mantener manifiestos/locks antes que fuente para caché; probar frío/repetido/cambio fuente/cambio lock/tests. Fuente/tests no reinstalan dependencias sin motivo; lock incompatible falla. Para tags mutables web, fijar versión+digest o fuente de resolución inmutable revisada, sin inventar digests; políticas de actualización de seguridad explícitas. Un digest base no hace reproducibles `apk upgrade` o repositorios apt por sí solo: registrar manifiesto/inputs reales y no prometer identidad bit a bit sin snapshot de paquetes. No añadir repositorios/sistemas de build propios en esta propuesta.
4. Renderizar combinaciones dev, prod, test y prod+maintenance con valores sintéticos, fuera de cualquier `.env` real y con `--project-directory` canónico. Comparar modelo resuelto antes/después: redes, puertos, volumes/secrets/configs por servicio, command, roles, usuario, readonly/tmpfs/capabilities, healthchecks y logging. Cambios de rutas de receta permitidos; nombres de recursos existentes no cambian por mover carpetas. No cambiar política restart/workers/plataforma ni habilitar puertos API/DB.
5. DB healthy no acredita esquema compatible. Mantener bootstrap/migración puntuales antes de API mediante el entrypoint documentado; no migrar al arrancar API. Probar migración fallida/no ready y caída posterior de DB. No introducir `service_completed_successfully` ciegamente si contradice los perfiles/wrapper operativos existentes.
6. Mantener env de test/dev/prod distintos y nombres por proyecto; evitar container_name nuevo. Mover recetas es un cambio de código/config, no una migración de volúmenes. Si scripts/configs/journal registrados guardan rutas, preservar la ruta contractual o proporcionar compatibilidad explícita sin reescribir instancias reales. Probar reinicio/captura/restauración sintéticos pertinentes antes de aceptar.

```text
backend/Dockerfile                 # runtime/dev/test/migrate/ops del producto
backend/.dockerignore              # contexto backend, lista acotada
web/Dockerfile                     # producto web, contexto raíz filtrado
.dockerignore                     # contexto web raíz
deploy/
  docker-compose.yml              # base
  docker-compose.dev.yml          # fuentes/reload solo desarrollo
  docker-compose.prod.yml         # imágenes ya verificadas, sin build
  docker-compose.test.yml         # verificador aislado
  docker-compose.maintenance.yml  # configuración operativa explícita
  images/
    browser.Dockerfile
    browser.Dockerfile.dockerignore
    security.Dockerfile
    security.Dockerfile.dockerignore
  diagnostics/
    Dockerfile                    # y sus config/runner actuales
```

Es organización objetivo; las recetas transitorias activas se conservan explícitamente si tienen consumidores. Si una receta transversal ya fue retirada/reorganizada, se acredita su finalidad vigente sin recrearla.

#### Fuentes oficiales y evidencia de la auditoría

- [Docker: multi-stage builds](https://docs.docker.com/build/building/multi-stage/) y [best practices](https://docs.docker.com/build/building/best-practices/): separar build/runtime, reutilizar stages, dependencias mínimas, USER no-root y pins con actualización deliberada.
- [Docker: build context](https://docs.docker.com/build/concepts/context/) y [cache](https://docs.docker.com/build/cache/optimize/): inputs mínimos, ignore por Dockerfile y capas/cachés; una receta fuera del contexto no permite leer archivos excluidos.
- [Docker: merge](https://docs.docker.com/compose/how-tos/multiple-compose-files/merge/) y [project name](https://docs.docker.com/compose/how-tos/project-name/): orden de overlays/rutas, render con config y aislamiento por proyecto.
- [Docker: startup order](https://docs.docker.com/compose/how-tos/startup-order/) y [secrets](https://docs.docker.com/compose/how-tos/use-secrets/): readiness explícita y acceso a secretos por servicio; no son cifrado automático del host ni autorización para operar producción.

Herramientas observadas: Docker client 29.4.0, Compose v5.1.1. La prueba existente `scripts/docker-layout.test.mjs` pasó sus dos casos y el check Git de contextos pasó uno; seis pruebas de build-context quedaron bloqueadas/fallaron al abrir el lock Buildx por permisos, con API Docker también inaccesible. No se acredita build/contexto efectivo ni arranque por esta auditoría; no se diagnosticó como bug de las recetas. Requiere entorno Docker autorizado antes de acreditar V10. No instalar ni actualizar tooling por inferencia.

Etapa 10 es aditiva, se ejecuta después de 3 y antes de refactors frontend/aceptación 8; etapa 9 sigue siendo el cierre documental final. No existen prerrequisitos de otras OpenSpec. Las pruebas de imagen/aislamiento/render proponen seams de build/config/containers sintéticos existentes, sin nuevo control de host ni acceso a instancias reales.

## Risks / Trade-offs

- [El checkout futuro ya corrigió un hallazgo] → reexplorar, acreditar la garantía existente y evitar refactor duplicado; no marcar cumplimiento solo por esta propuesta.
- [Separación Training–Coach rompe atomicidad] → pruebas de éxito/rollback/revocación y cancelación postcommit antes y después; sin efectos externos dentro del commit SQL.
- [Sync duplica estado o pierde pendientes] → pruebas de secuencia contra la misma autoridad y recorrido navegador del slice; extraer por responsabilidad, no por tamaño.
- [Seis capacidades amplían revisión] → slices separados con aceptación propia; no mezclar todos los movimientos ni sustituir cobertura por un build exitoso.
- [Limpieza destruye evidencia única o explica peor una carrera] → revisar finalidad/consumidores y conservar cuando haya duda; condición de retirada concreta y respaldo privado acotado.
- [Controles de imports excesivos o insuficientes] → reglas pequeñas, fixtures negativas y revisión de colaboradores indirectos; sin framework polyglot nuevo.
- [Checks documentales pasan con prosa falsa] → contraste manual con fuente/contratos además de OKF.

## Migration Plan

Con baseline propio D1: baseline limpio y mapa actualizado → metadata/colaboración backend → navegación y controles → etapa 10 Docker → coordinación sync → seis slices frontend → higiene residual y regresión integrada → etapa 9 documental. La higiene de un slice puede acompañarlo en un commit separable, manteniendo atribución de fallos. No se despliega como parte de esta propuesta.

Reversión mediante cambios de código separables sobre el checkout propio y recuperación de archivos desde Git/copia privada; nunca revertir datos, restaurar un runtime retirado ni sobrescribir trabajo concurrente. No hay migraciones SQL. Repetir pruebas afectadas tras una reversión.

## Planificación cerrada y estado de ejecución

Implementation Ready como especificación independiente, con comprobaciones de planificación completadas en [verification-plan.md](verification-plan.md). Ese artefacto fija comandos/casos actuales, archivos de prueba, exportaciones permitidas, interfaces de destino, observadores y cobertura nueva prevista. No hay decisiones materiales de alcance pendientes ni dependencia de otra OpenSpec.

D11 precisa D6–D10: metadata en core/schema.py y operación iniciadora en training_save.py; Training participante no conoce Coach; helper de secretos con interface pública load_secret sin cambio de formato/permisos. El mapa y pruebas exactas están en el plan. Revalidar drift al ejecutar es una obligación de seguridad y mantenimiento, no una decisión de diseño aún por resolver.

Docker/Buildx es una restricción local de ejecución separada. Afecta builds y suites containerizadas de cualquier capacidad, no solo etapa 10; si su preflight falla no iniciar el slice que los requiere. No bloquea la planificación ni tareas documentales con checks disponibles. No se declara ninguna prueba Docker aprobada en este cambio. La aceptación final sí exige ejecutar todas las pruebas obligatorias del código implementado.

## D11. Comprobaciones de planificación completadas

El [plan concreto](verification-plan.md) es parte de este diseño y sustituye las selecciones genéricas de V0–V10 a efectos de iniciar ejecución. Revisar nombres si hay drift, conservando las garantías especificadas. Los seams públicos/HTTP/PG/browser y fixtures negativas quedan definidos para la implementación solicitada; no se introducen hooks de producto ni se amplían permisos. Implementation Ready no equivale a autorización para implementar, publicar, archivar o hacer commit.

### Precisiones localizadas tras la revisión ponytail ultra

El coordinador save recibe coach como keyword obligatorio desde training.router, que reutiliza la instancia Jobs gestionada por el lifespan. No hay instancia adicional ni lookup global; Training participante sigue sin recibir Coach. La matriz browser del plan fija acciones/observaciones mínimas y reutiliza los recorridos existentes antes de ampliarlos, incluidos los de audit que ya estén ejecutados. El tipo de target de una prueba no es su garantía: distinguir toolchain, pool PostgreSQL, HTTP y UI.

La unidad de entrega es un recorrido coherente con sus consumidores y pruebas, no un archivo/capa. Cada checkpoint registra resultado antes del siguiente recorrido solapado; los diffs editoriales son separables. No se agregan tareas, frameworks ni condiciones de otra OpenSpec; todos los IDs, el orden de etapas y la etapa 9 final se conservan.
