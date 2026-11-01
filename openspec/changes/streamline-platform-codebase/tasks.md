## 1. P0 — Baseline independiente del checkout actual

- [ ] 1.1 Registrar revisión, runtimes/contratos activos y permisos propios. Confirmar independencia de otras OpenSpec: su cierre o aceptación no condicionan ejecución; preservar consumidores y trabajo ajeno.
  Traceability: Independent execution and current-state baseline; JSON purpose classification and active contract preservation.
  Proof/Check: V0; baseline propio y consumidores identificados, sin condición de entrada basada en el estado de otra OpenSpec.
- [ ] 1.2 Reejecutar prime-codebase sobre revisión actual: estado Git, instrucciones, capacidades, consumidores, contratos y suites; registrar mapa actualizado y hallazgos ya resueltos en esta tarea, sin otro informe permanente.
  Traceability: Independent execution and current-state baseline.
  Proof/Check: V0; revisión/árbol/capacidades actuales identificados, trabajo ajeno intacto.
- [ ] 1.3 Ejecutar y registrar baseline del slice con comandos/casos/exportaciones ya concretados en verification-plan.md; revalidar drift y entorno, separar cambios ajenos e inventariar limpieza por finalidad/consumidores. No requiere cerrar otra OpenSpec.
  Traceability: Per-journey proof and task traceability; Purpose-based cleanup selection.
  Proof/Check: V0–V10; matriz exacta por recorrido con entorno/casos/observador y expectativa antes de modificar; referencias no resueltas bloquean.

## 2. P1 — Backend con dependencias explícitas

- [ ] 2.1 Separar metadata pura de compatibilidad de la composición HTTP; actualizar consumidores runtime/cleanup/backup y empaquetado afectado, conservando autoridad única y rechazo de esquema incompatible. Verificar import independiente, lifecycle y CLI afectadas.
  Traceability: Composition-independent compatibility metadata.
  Proof/Check: V1; import puro independiente y esquema incompatible rechazado en lifecycle y CLI.
- [ ] 2.2 Caracterizar el guardado Training–Coach con iniciador, participantes, permisos, transacción y efectos postcommit; comprobar éxito, rollback del segundo participante, revocación durante espera y cancelación posterior al commit y uso de la misma instancia Coach inyectada desde composición.
  Traceability: Explicit atomic Training and Coach collaboration; Single initiator and one-way participant knowledge.
  Proof/Check: V2; HTTP/PG independiente observa éxito, rollback, revocación durante espera y cancelación postcommit.
- [ ] 2.3 Aplicar la menor reorganización que elimine conocimiento recíproco innecesario y haga explícita la colaboración; descartar fachada pasante/event bus. Repetir pruebas de 2.2 y actualizar el grafo propietario contrastándolo con consumidores reales.
  Traceability: Explicit atomic Training and Coach collaboration; Single initiator and one-way participant knowledge.
  Proof/Check: V2 y revisión manual D6 ahora; repetir V3 en 8.2 después de entregar 3.2–3.3. Mismo resultado de 2.2; Training sin objeto Coach, un iniciador/handle y cero commits/pools participantes, sin crear Jobs ni buscarlo globalmente.

## 3. P1 — Navegación y controles para agentes

- [ ] 3.1 Reconciliar instrucciones y documentación propietaria con runtime/contratos aceptados, distinguiendo objetivo e histórico; enlazar propietario, colaboradores y comprobaciones de las seis capacidades sin duplicar reglas.
  Traceability: Discoverable ownership and enforceable dependency rules.
  Proof/Check: V0 + V9; seis recorridos código→regla→comando, sin declaraciones de runtime histórico como actual.
- [ ] 3.2 Añadir controles focalizados de dependencias a la verificación existente: imports hacia composición, core hacia funcionalidad e internos ajenos acordados; demostrar rechazo con fixtures negativas, incluidos imports locales y tratamiento explícito de dinámicos.
  Traceability: Explicit dependency contract and bounded static analysis.
  Proof/Check: V3; fixtures de import estático/local/dinámico literal y privado rechazadas; público declarado pasa; computado se señala para revisión.
- [ ] 3.3 Integrar controles en CI/runner existentes, comprobar selección/error y revisar solapamientos de skills por alcance/activación; no eliminar por cantidad ni añadir otro orquestador. Ejecutar controles positivos/negativos y docs checks aplicables.
  Traceability: Discoverable ownership and enforceable dependency rules; Explicit dependency contract and bounded static analysis.
  Proof/Check: V3; invocación local y CI aplican mismas reglas; comando/caso desconocido falla sin crédito; cada skill modificada tiene responsabilidad explícita.

- [ ] 3.4 Ratificar contra el checkout el mapa de exportaciones y fixtures ya decidido en verification-plan.md; registrar drift antes de implementar 3.2, sin allowlist global ni nuevos contratos por inferencia.
  Traceability: Explicit dependency contract and bounded static analysis; Per-journey proof and task traceability.
  Proof/Check: V0 + contrato diseñado de V3; mapa/fixtures y comando propuestos antes de 3.2, sin acreditar ejecución de la regla aún no implementada.

## 4. P2 — Sincronización y Training

- [ ] 4.1 Definir el slice de sincronización y Training con consumidores, interface y matriz de fallos; conservar/probar ownership, handover/perfil, pestañas, pendientes, sesión en curso, offline, 401/409 repetido y respuesta perdida antes de extraer coordinación.
  Traceability: Single-authority frontend synchronization; Per-journey proof and task traceability.
  Proof/Check: V4 + V5; baseline observa pendientes/owner/tabs, 401/409, sesión en curso y respuesta perdida sin mutar internals por UI.
- [ ] 4.2 Profundizar coordinación de sync preservando useStore persistente/useUI efímera y una sola autoridad de revisiones/pendientes; mantener helpers puros y pruebas conforme AGENTS. Actualizar todos los consumidores de la extracción.
  Traceability: Single-authority frontend synchronization.
  Proof/Check: V4 + V5; misma matriz antes/después y una sola autoridad; mocks solo en seam de unidad, no éxito browser fabricado.
- [ ] 4.3 Agrupar UI/hooks/operaciones propios de Training según beneficio de localidad, actualizar imports/pruebas y aceptar el recorrido real afectado en navegador contra backend; demostrar que la nueva interface concentra comportamiento y no es una fachada pasante.
  Traceability: Incremental locality across six frontend capabilities; Single-authority frontend synchronization.
  Proof/Check: V4 + V5 + V8; consumidores/pruebas junto a su propietario y recorrido Training completo sin duplicación de coordinación.

## 5. P2 — Identity y Coach, slices separados

- [ ] 5.1 Mapear y caracterizar Identity: acceso, pairing/adopción de datos, revocación, fallos y consumidores web/móvil; conservar contratos y transporte común sin estado persistente duplicado.
  Traceability: Incremental locality across six frontend capabilities; Per-journey proof and task traceability.
  Proof/Check: V4 + V5; casos Identity y consumidores declarados, incluyendo rechazo y propietario con pendientes.
- [ ] 5.2 Aceptar Identity tras completar los recorridos 5.5–5.6: verificar localidad, transporte común y cambio de propietario con pendientes. Este checkpoint no agrupa su implementación en una sola sesión.
  Traceability: Incremental locality across six frontend capabilities.
  Proof/Check: V4 + V5 + V8; resultados 5.5–5.6 aceptados por separado y sin transporte/store duplicados.
- [ ] 5.3 Mapear y caracterizar Coach: local/demo/HTTP, consentimiento, propuestas/jobs, validación/aplicación, cancelación y disponibilidad Q6; conservar biblioteca neutral y consumidores/generadores.
  Traceability: Incremental locality across six frontend capabilities; Per-journey proof and task traceability.
  Proof/Check: V4 + V6; matriz Coach local/demo/HTTP/Q6 y propuesta/consentimiento con casos adversos.
- [ ] 5.4 Aceptar Coach tras completar 5.7–5.8: verificar selección/fallos, biblioteca neutral y assets/bundles, sin fallback/SDK/CLI nuevos ni cambios de autorización.
  Traceability: Incremental locality across six frontend capabilities.
  Proof/Check: V4 + V6 + V8; resultados 5.7–5.8 y generadores vigentes, sin nueva capacidad/proveedor.

- [ ] 5.5 Caracterizar, reorganizar y verificar el recorrido Identity de login password, logout/revocación y adopción de pendientes; incluir éxito, rechazo y cambio de perfil sin segunda autoridad local.
  Traceability: Incremental locality across six frontend capabilities.
  Proof/Check: V4 + V5; password válido/inválido, logout/revocación y adopción/handover mantienen pendientes propios.
- [ ] 5.6 Caracterizar, reorganizar y verificar el recorrido Identity de passkey/pairing y rechazo de ceremonia o código obsoletos; conservar hostname/origen y contratos web/móvil.
  Traceability: Incremental locality across six frontend capabilities.
  Proof/Check: V4 + V5; passkey/pairing válidos, origen y códigos/ceremonias obsoletos rechazados; no afirmar hardware físico por fixture.
- [ ] 5.7 Caracterizar, reorganizar y verificar selección Coach local/demo/HTTP, configuración y consentimiento; probar opt-out y Q6 sin fallback, con generadores vigentes.
  Traceability: Incremental locality across six frontend capabilities.
  Proof/Check: V4 + V6; local/demo/HTTP y opt-out/Q6 compatibles; generador assets --check pasa.
- [ ] 5.8 Caracterizar, reorganizar y verificar solicitud/polling de propuesta, validación/aplicación autorizada y cancelación/respuesta tardía; no escribir Training automáticamente desde proveedor.
  Traceability: Incremental locality across six frontend capabilities; Explicit atomic Training and Coach collaboration.
  Proof/Check: V4 + V6; propuesta válida/inválida, cancelación/tardía y aplicación por usuario; proveedor no muta Training.

## 6. P2 — Media, Administration y Notifications, slices separados

- [ ] 6.1 Mapear y caracterizar Media: referencias/ownership, cola offline, almacenamiento, consumidores y fallos de lectura/upload antes de reorganizar.
  Traceability: Incremental locality across six frontend capabilities; Per-journey proof and task traceability.
  Proof/Check: V4 + V5 + V7; matriz Media upload/cola/referencias y fallos definida antes de reorganizar.
- [ ] 6.2 Aceptar Media tras completar 6.7–6.8: conservar bytes/pendientes, propietario ajeno y referencias ante fallos; revisar bundles/consumidores.
  Traceability: Incremental locality across six frontend capabilities.
  Proof/Check: V4 + V5 + V7 + V8; 6.7–6.8 aceptados y bytes/pendientes/ajeno conservados.
- [ ] 6.3 Mapear y caracterizar Administration: actor-target/facultades, inspección, borrado/cleanup, invitaciones/reset y audit; respetar operaciones propietarias sin SQL ajeno desde el cliente.
  Traceability: Incremental locality across six frontend capabilities; Per-journey proof and task traceability.
  Proof/Check: V4 + V7; casos admin actor-target, borrado, invitaciones/reset y audit identificados.
- [ ] 6.4 Aceptar Administration tras completar 6.9–6.12: verificar permisos y resultados por recorrido, sin paneles nuevos ni cambio de UX.
  Traceability: Incremental locality across six frontend capabilities.
  Proof/Check: V4 + V7; 6.9–6.12 aceptados individualmente, sin nuevo panel ni facultad.
- [ ] 6.5 Mapear y caracterizar Notifications: web/móvil, ownership/dispositivo, preferencias, opt-out, presencia/timers y transporte; mantener el alcance efímero y las garantías de entrega actuales.
  Traceability: Incremental locality across six frontend capabilities; Per-journey proof and task traceability.
  Proof/Check: V4 + V7; casos suscripción, timer, preferencias y opt-out separados por dispositivo/plataforma.
- [ ] 6.6 Aceptar Notifications tras completar 6.13–6.15: verificar dispositivos, opt-out y temporizadores sin prometer exactly-once ni atribuir entrega real a un fake.
  Traceability: Incremental locality across six frontend capabilities.
  Proof/Check: V4 + V7 + V8; 6.13–6.15 aceptados sin crédito de push/hardware real a partir de transporte fake.

- [ ] 6.7 Caracterizar, reorganizar y verificar upload/download Media y cola offline con éxito/fallo, propio/ajeno y reconexión; conservar bytes y pendientes.
  Traceability: Incremental locality across six frontend capabilities.
  Proof/Check: V4 + V5 + V7; upload/download y reconexión conservan cola/bytes; ajeno inaccesible.
- [ ] 6.8 Caracterizar, reorganizar y verificar referencias Media y su interacción con reset/borrado/GC: fallo de lectura no equivale a lista vacía y no elimina archivos ajenos.
  Traceability: Incremental locality across six frontend capabilities.
  Proof/Check: V4 + V5 + V7; fallo de lectura conserva archivos; reset/borrado propios no afecta sentinel ajeno.
- [ ] 6.9 Caracterizar, reorganizar y verificar listado/inspección/disable administrativos con actor-target y facultades vigentes; probar rechazo de objetivo/actor no permitido.
  Traceability: Incremental locality across six frontend capabilities.
  Proof/Check: V4 + V7; inspección/disable válido y actor/target prohibido con resultados compatibles.
- [ ] 6.10 Caracterizar, reorganizar y verificar borrado administrativo y estado cleanup pendiente/completo ante fallo externo, sin afirmar atomicidad SQL/filesystem.
  Traceability: Incremental locality across six frontend capabilities.
  Proof/Check: V4 + V7; borrado SQL autorizado y cleanup pendiente/reintentado observados ante fallo externo.
- [ ] 6.11 Caracterizar, reorganizar y verificar invitaciones y emisión administrativa de reset con permisos, consumo/expiración y no reapertura de invitaciones consumidas.
  Traceability: Incremental locality across six frontend capabilities.
  Proof/Check: V4 + V7; emisión permitida/rechazada y consumo/expiración sin reapertura tras borrado.
- [ ] 6.12 Caracterizar, reorganizar y verificar lectura/clear de audit administrativo con rechazo de acceso indebido y degradación compatible; no confundir audit con telemetría.
  Traceability: Incremental locality across six frontend capabilities.
  Proof/Check: V4 + V7; audit read/clear autorizado y rechazo ajeno; fallo audit no inventa fallo de negocio.
- [ ] 6.13 Caracterizar, reorganizar y verificar alta/baja/status de suscripciones por dispositivo y ownership con aislamiento propio/ajeno.
  Traceability: Incremental locality across six frontend capabilities.
  Proof/Check: V4 + V7; subscribe/status/unsubscribe propio y ajeno con aislamiento.
- [ ] 6.14 Caracterizar, reorganizar y verificar presencia y rest timer/test/cancel por dispositivo, revocación y reinicio sin persistencia inventada.
  Traceability: Incremental locality across six frontend capabilities.
  Proof/Check: V4 + V7; timer/test/cancel propio, revocación/reinicio y presencia efímera conservados.
- [ ] 6.15 Caracterizar, reorganizar y verificar preferencias/opt-out y su relación con recordatorios web/móvil, conservando transporte/locale y límites de entrega.
  Traceability: Incremental locality across six frontend capabilities.
  Proof/Check: V4 + V7; opt-out y preferencias vigentes suprimen envío elegible; web/móvil y locale conservados.

## 7. P2 — Higiene editorial y retirada de evidencias

- [ ] 7.1 Revisar textos duplicados/obsoletos en documentación, README, instrucciones y skills; condensar conocimiento útil en su propietario y actualizar consumidores activos también fuera de docs. No reescribir históricos protegidos ni borrar decisiones archivadas por cuota.
  Traceability: Purpose-based cleanup selection; Reviewed historical document retirement; Cleanup preserves reproducible guarantees and active navigation.
  Proof/Check: V9; diff editorial y consumidores/enlaces revisados, conocimiento en propietario sin duplicación.
- [ ] 7.2 Revisar comentarios de los módulos intervenidos; retirar narración literal y cronología sin utilidad, preservar/precisar invariantes, carreras, compatibilidad, atribución, directivas y deuda vigente. Separar el diff editorial del funcional y ejecutar checks afectados.
  Traceability: Value-based code comment maintenance.
  Proof/Check: V4 o V1–V7 según módulo + V9; sin cambios ejecutables/directivas/licencias perdidas; deuda vigente localizada.
- [ ] 7.3 Revisar cada candidato histórico protegido con finalidad/consumidores/obligaciones; conservar si sigue siendo necesario. Para retirada justificada, preservar conocimiento y actualizar enlaces/índices/config/manifiesto juntos, sin rehashear una reescritura para ocultarla.
  Traceability: Reviewed historical document retirement.
  Proof/Check: V9; decisión por candidato, conocimiento preservado y manifiesto/config/índices consistentes, sin rehash engañoso.
- [ ] 7.4 Preparar retirada de artefactos locales propios sustituidos: writers detenidos, rutas absolutas reales, límites y permisos; respaldo privado externo de lo necesario antes de retirada amplia, incluyendo trabajo local/untracked. Probar selección con fixture/sentinel ajeno, material protegido y escape por enlace sin eliminar nada ajeno.
  Traceability: Bounded safe artifact removal.
  Proof/Check: V9; fixture temporal de selección conserva sentinel/protegido y rechaza escape/owner incierto; copia privada cuando corresponde.
- [ ] 7.5 Retirar solo candidatos revisados de 7.4 y comprobar conservación de sentinels/material vigente, tests/fixtures necesarios y trazabilidad; usar verificador propietario para Docker si corresponde. Registrar resultado y pendientes en esta tarea, sin GC periódico, prune global ni informe permanente.
  Traceability: Purpose-based cleanup selection; Bounded safe artifact removal; Cleanup preserves reproducible guarantees and active navigation.
  Proof/Check: V9; solo rutas revisadas retiradas y conservados byte a byte ajeno/protegido; condición explícita para evidencia retenida.

- [ ] 7.6 Revisar clasificación JSON y finalidad de fixtures/runtime según D8; conservar assets/copy/vectores y contratos con consumidores. Reconciliar retención; una eliminación sin cobertura bloquea solo esa eliminación, no el cambio completo.
  Traceability: JSON purpose classification and active contract preservation.
  Proof/Check: V0 + V8 + V9; runtime/fixtures y contratos activos conservados; solo una eliminación concreta exige ausencia de consumidores y cobertura sustituta.

## 8. Aceptación integrada y cierre revisable

- [ ] 8.1 Verificar requisitos y escenarios de ambas specs contra evidencia por slice y revisión final; ejecutar suites nativas, integración PostgreSQL y browser afectados, build web y prueba de bundle móvil vigente, sin omisiones presentadas como éxito.
  Traceability: Per-journey proof and task traceability; Incremental locality across six frontend capabilities.
  Proof/Check: V1–V8 según impacto; pruebas nativas/PG/browser y bundles actuales pasan con casos/entorno/resultado anotados.
- [ ] 8.2 Ejecutar controles arquitectónicos y documentación: OKF check y tests de herramienta si cambió, enlaces/referencias/generadores afectados, diff-check y revisión de afirmaciones. Si se regeneran índices mediante OKF, comprobar que una segunda propuesta queda vacía.
  Traceability: Discoverable ownership and enforceable dependency rules; Cleanup preserves reproducible guarantees and active navigation.
  Proof/Check: V3 + V9; docs/generadores coherentes; segunda propuesta OKF vacía si hubo regeneración de índices.
- [ ] 8.3 Revisar diff completo, archivos nuevos/retirados y consumidores; confirmar invariantes/contratos sin cambios, cero dependencias nuevas no justificadas, ausencia de temporales staged y material retenido con finalidad/condición de retirada. Registrar límites de verificación sin afirmar pruebas reales no ejecutadas.
  Traceability: Per-journey proof and task traceability; Cleanup preserves reproducible guarantees and active navigation.
  Proof/Check: V0 + V9; diff completo y nuevo/retirado revisados, sin temporales staged ni garantías omitidas; no cierra etapa 9.

## 9. Documentación final del proyecto y aceptación documental

- [ ] 9.1 Inventariar las fuentes propietarias finales de D9 y sus consumidores: raíz, paquetes, instrucciones, arquitectura/API, operación/recuperación e infraestructura. Clasificar cada ejemplo como soportado, pendiente o histórico, sin ampliar soporte.
  Traceability: Final project documentation acceptance.
  Proof/Check: V0 + V9; inventario D9 completo y ejemplos soportado/pendiente/histórico con propietarios.
- [ ] 9.2 Reconciliar afirmaciones, rutas, interfaces, privilegios, imágenes, variables y comandos con el árbol resultante; registrar fuente/contrato o evidencia por afirmación relevante y corregir contradicciones activas.
  Traceability: Final project documentation acceptance.
  Proof/Check: V9; cada afirmación relevante tiene fuente actual; cero contradicciones activas, incluida retención JSON.
- [ ] 9.3 Retirar duplicaciones y referencias residuales a artefactos retirados, revisando consumidores fuera de docs; preservar historia/garantías vigentes y condiciones de eliminación de evidencia retenida. No intentar borrar todas las referencias históricas a Node/JSON.
  Traceability: Final project documentation acceptance; Cleanup preserves reproducible guarantees and active navigation.
  Proof/Check: V9; referencias entrantes activas resueltas; históricos preservados en su contexto y evidencia necesaria con finalidad.
- [ ] 9.4 Verificar comandos documentados aplicables desde checkout limpio aislado, con datos sintéticos; validar enlaces, índices y generadores. Registrar límites de hardware/proveedor/destrucción; no ejecutar operaciones reales ni aceptar como probada una instrucción no ensayada.
  Traceability: Final project documentation acceptance.
  Proof/Check: V1–V9 aplicables desde checkout limpio; comandos operativos solo sintéticos, límites explícitos y ningún requisito de aceptación sin prueba.
- [ ] 9.5 Aceptar documentación contra revisión final y árbol limpio, con matriz afirmación→fuente/comando→resultado/límite en esta tarea; cerrar discrepancias o bloquear. Si cambió código tras 9.4, revalidar lo afectado. El cierre completo requiere esta etapa, no solo 8 u OKF.
  Traceability: Final project documentation acceptance.
  Proof/Check: V0 + V9; revisión final, árbol limpio y matriz contrastada; cambios posteriores invalidan evidencia afectada; discrepancias bloquean cierre.

## 10. P1 — Organización Docker aditiva, antes de aceptación 8 y cierre 9

- [ ] 10.1 Revalidar inventario D10 del checkout actual: propietario/contexto/ignore/targets/consumidores y tooling. Registrar comandos exactos V10 y baseline sintético; no recrear recetas transitorias ni depender de AI Tutor.
  Traceability: Owned build recipes without arbitrary consolidation; Isolated container proofs before documentation acceptance.
  Proof/Check: V0 + preparación V10; inventario de recetas activas y consumidores; permisos faltantes bloquean builds sin atribuir defecto a la receta.
- [ ] 10.2 Reubicar browser/security transversales y el conjunto diagnóstico conforme D10 si siguen activos; actualizar ignores, CI/runners y consumidores juntos. Conservar Dockerfiles backend/web; cubrir todos los COPY requeridos en la prueba de contexto.
  Traceability: Owned build recipes without arbitrary consolidation; Minimal effective contexts preserve required inputs.
  Proof/Check: V10; inputs completos de cada target admitidos y sentinels privados/host excluidos con ignore efectivo, no solo YAML válido.
- [ ] 10.3 Reconciliar bases web/cadena activa con identidades inmutables revisadas y política de actualización; conservar locks/caché/runtime mínimo y registrar límites de paquetes no inmutables. No inventar digests ni crear repositorios de paquetes propios.
  Traceability: Reproducible input policy and minimal runtime.
  Proof/Check: V10; frío/repetido/fuente/lock con pasos reales, lock incompatible rechazado e inspección runtime sin tests/Node/herramientas ops; sin promesa bit a bit no acreditada.
- [ ] 10.4 Actualizar rutas Compose/entrypoints solo donde lo requiera 10.2; preservar dev/prod/test/maintenance, proyecto/volúmenes/journal y roles. Comparar renders sintéticos sin leer .env real ni migrar datos existentes.
  Traceability: Compose relocation preserves operational identity.
  Proof/Check: V10; diferencias limitadas a receta/inputs revisados, API/DB privados y prod sin build/reload/source; migración fallida no habilita readiness y caída DB conserva contrato.
- [ ] 10.5 Aceptar Docker con contextos/targets/aislamiento/lifecycle/caché y mantenimiento afectados en recursos propios; enlazar resultados/límites a 8 y 9 y actualizar fuentes propietarias, sin informe permanente ni modificaciones a AI Tutor.
  Traceability: Isolated container proofs before documentation acceptance; Final project documentation acceptance.
  Proof/Check: V10 + V9; cada prueba requerida pasa o bloquea aceptación; cleanup propio, consumidores actualizados y etapa 9 verifica árbol final.

## Execution Order

Cada recorrido entrega un diff coherente con sus callers, tests, fixtures y configuración necesarios. Antes del siguiente recorrido que comparta código/estado, registrar prueba, resultado y límites en su tarea. Mantener limpieza editorial/borrado separable de cambios ejecutables. No dividir una corrección atómica por archivo/capa ni exigir un commit por tarea; los commits siguen requiriendo autorización explícita.

Cada ID aparece una vez; checkpoints de capacidad siguen a sus recorridos. Cada recorrido encadena caracterización → cambio necesario → prueba, sin reunir todos los tests al principio.

- Entrada: 1.1 → 1.2 → 1.3.
- Backend: 2.1 → 2.2 → 2.3.
- Navegación/controles: 3.1 → 3.4 → 3.2 → 3.3.
- Docker aditivo: 10.1 → 10.2 → 10.3 → 10.4 → 10.5.
- Training/sync: 4.1 → 4.2 → 4.3.
- Identity: 5.1 → 5.5 → 5.6 → 5.2.
- Coach: 5.3 → 5.7 → 5.8 → 5.4.
- Media: 6.1 → 6.7 → 6.8 → 6.2.
- Administration: 6.3 → 6.9 → 6.10 → 6.11 → 6.12 → 6.4.
- Notifications: 6.5 → 6.13 → 6.14 → 6.15 → 6.6.
- Higiene residual: 7.1 → 7.2 → 7.3 → 7.6 → 7.4 → 7.5.
- Aceptación técnica: 8.1 → 8.2 → 8.3.
- Documentación final: 9.1 → 9.2 → 9.3 → 9.4 → 9.5.

El orden entre capacidades es conservador para compartir baseline; puede adelantarse un recorrido independiente si declara consumidores y no comparte archivos/estado en edición con otro slice. Sus prerrequisitos y checkpoint siguen siendo obligatorios. Higiene local puede acompañar su slice en diff separable; no retirar evidencia de revisión abierta.

## Matriz de comprobaciones V0–V10

Referencias existentes al preparar esta propuesta; NO ejecutadas ni acreditadas aquí como pruebas del refactor. Antes de cada slice, 1.3 concreta comando/casos/entorno/observador actuales. Si el port retiró un comando, se enlaza su reemplazo nativo con igual garantía; no basta una búsqueda textual ni revivir el harness retirado. Un check aún no implementado se identifica como nuevo y no recibe crédito hasta demostrarlo.

| Código | Comando o comprobación inicial | Observación y límite |
| --- | --- | --- |
| V0 | `git status --short`, `git rev-parse HEAD`, inventario de consumidores con `rg` y contratos activos | Revisión/árbol/propiedad; no prueba comportamiento ni aceptación por sí solo |
| V1 | `node scripts/platform.mjs verify lifecycle`, `verify admin_delete`, `verify backup` con el mismo prefijo del runner, o equivalentes nativos actuales | HTTP/PG/CLI reales sintéticos; agregar prueba de import puro sin cargar composición y rechazo de esquema incompatible |
| V2 | `node scripts/platform.mjs verify training_write` y `node scripts/platform.mjs verify coach_http` | Casos de lifecycle Coach/Training actuales; observador PG independiente y marca de cancelación postcommit; ampliar cobertura faltante antes del cambio |
| V3 | `node scripts/platform.mjs verify checks` o sucesor nativo | Integración nueva de reglas D6 con casos positivos/negativos y exit no-cero para violaciones; registrar comando exacto y fixture en 3.4, sin nuevo runner |
| V4 | Seis comandos Vitest completos por capacidad en [verification-plan.md](verification-plan.md) | Archivos actuales verificados al planificar; revalidar drift en 1.3, sin nuevo store; no es prueba browser |
| V5 | `node scripts/platform.mjs verify training_browser` y suites `identity_password`, `identity_passkey`, `identity_links`, `identity_account` aplicables | No resucitar harness retirado; completar recorrido UI específico si el browser actual no lo cubre; autenticador sintético no acredita hardware |
| V6 | Suites actuales `coach_state`, `coach_http`, `coach_admin`, `coach_client` con comandos completos suite/caso en verification-plan.md | Complementar Vitest/browser del recorrido; proveedor fake no acredita entrega externa |
| V7 | Suites `media`, `media_gc`, `admin_users`, `admin_delete`, `admin_invites`, `admin_audit`, `notifications` mediante runner vigente | Seleccionar casos exactos por recorrido, revisar qué es backend y añadir UI afectada; no afirmar six-capability E2E por pasar HTTP |
| V8 | `pnpm --dir frontend run build`; `node scripts/build-coach-assets.mjs --check`, `node scripts/build-coach-library.mjs --check`, `node scripts/build-push-assets.mjs --check` según generador vigente | Bundle móvil: usar prueba portable vigente identificada en 1.3; no ejecutar cap sync ni afirmar APK/IPA/dispositivo por copia de assets |
| V9 | `node scripts/docs/okf.mjs check`, `node scripts/build-api-docs.mjs --check`, `git diff --check`; tests OKF si cambia tooling; revisión de enlaces/afirmaciones/diff y fixture de retirada acotada | OKF/generadores no certifican verdad semántica; probar también untracked propios sin staging y no crear limpiador para la fixture |
| V10 | Versiones Docker/Compose; render sintético con --project-directory canónico y --env-file sintético; `node --test scripts/docker-layout.test.mjs scripts/docker-build-context.test.mjs`; pruebas vigentes platform-images/platform-build/lifecycle/backup pertinentes | 10.1 registra comandos exactos/casos y actualiza rutas tras movimientos; no usar env real. Daemon/Buildx necesarios para imágenes/contextos; render no acredita build. Reusar runners y recursos etiquetados propios |

Para tareas solo editoriales o de inventario no aplica RED runtime: la prueba concreta es consistencia de contenido/consumidores y preservación. Las reglas nuevas sí exigen rechazo negativo; refactors preservan caracterización antes/después, sin inventar fallo inicial de producto.

## Orden y trazabilidad

1 → 2 → 3 → 10 Docker → 4 → 5 → 6 → 7 residual → 8 técnico → 9 documental. La higiene de un slice puede acompañarlo mediante diff separable; 7.4 siempre precede a 7.5. No se ejecutan movimientos masivos ni se limpian evidencias de un slice todavía abierto. La matriz browser del plan exige acción UI y observación independiente; capturas/nombres solos no cierran recorridos y se actualizan juntos sus productores/consumidores de evidencia. Las prioridades ordenan trabajo, no rebajan la obligatoriedad de requisitos al aceptar el cambio completo.

| Requisitos | Tareas principales |
| --- | --- |
| Independent execution and current-state baseline | 1.1–1.3 |
| Composition-independent compatibility metadata | 2.1 |
| Explicit atomic Training and Coach collaboration | 2.2–2.3 |
| Single-authority frontend synchronization | 4.1–4.3 |
| Incremental locality across six frontend capabilities | 4–6 |
| Discoverable ownership and enforceable dependency rules | 3.1–3.3, 8.2 |
| Purpose-based cleanup selection | 1.3, 7.4–7.5 |
| Reviewed historical document retirement | 7.1, 7.3 |
| Value-based code comment maintenance | 7.2 |
| Bounded safe artifact removal | 7.4–7.5 |
| Cleanup preserves reproducible guarantees and active navigation | 7.1–7.5, 8.1–8.3 |

Estado: Implementation Ready de planificación; comandos/casos/exportaciones concretados en verification-plan.md. Ninguna tarea implementada. Preflight Docker limita solo los slices que requieren contenedores y bloquea su aceptación hasta ejecutar las pruebas. Sin dependencia de otra OpenSpec ni autorización implícita de implementación/commit.

Trazabilidad adicional: Single initiator and one-way participant knowledge → 2.2–2.3; Explicit dependency contract and bounded static analysis → 3.4/3.2–3.3; Per-journey proof and task traceability → 1.3/4–6/8.1; JSON purpose classification and active contract preservation → 1.1/7.6; Final project documentation acceptance → 9.1–9.5.

Trazabilidad Docker: cinco requisitos de container-delivery-organization → 10.1–10.5; documentación final Docker → 9.1–9.5.

## Selección exacta y preflight

[verification-plan.md](verification-plan.md) completa la matriz V0–V10 con comandos sin selectores pendientes, casos actuales, exportaciones y destinos decididos. 1.1–1.3, 3.4 y 10.1 son tareas de baseline/revalidación de ejecución, no authoring pendiente. Ningún checkbox se marca completo por terminar la planificación. Docker se comprueba antes de cualquier slice con HTTP/PG/browser o builds containerizados: si falta acceso, no iniciar ese slice; los trabajos independientes continúan.
