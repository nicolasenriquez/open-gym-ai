---
type: Research
title: OpenGym Recovery — benchmark de referencias
description: Benchmark histórico de referencias Recovery y límites de sus recomendaciones.
---
# OpenGym Recovery — benchmark de referencias

**Revisión documental posterior aprobada:** E7 se alinea con la entrega web responsive del PRD y arquitectura §12.1. Se conservan las observaciones históricas y sus límites; esta revisión no ejecuta pruebas ni amplía el producto.

**Revisión de prioridad del 2026-10-22:** el dictamen de esta investigación corresponde a la base documental anterior. La solicitud posterior del usuario establece [plataforma Python/FastAPI/PostgreSQL completada y aceptada](../open-gym-evolution.prd.md) antes de implementar Recovery, según [arquitectura §14](../open-gym-evolution.architecture.md#14-secuencia-conceptual-confirmada-de-futuras-openspecs-y-handoff). Se conservan los hallazgos funcionales; esta nota no los reejecuta ni convierte el benchmark en autoridad sobre la nueva secuencia.

## 1. Estado, autoridad y dictamen

**Estado:** resultado del benchmark especializado aprobado por el usuario; documentado como referencia complementaria para las futuras OpenSpecs funcionales de Recovery.

**Dictamen aprobado de la investigación original:** no era necesario modificar el [PRD](../open-gym-recovery.prd.md), la [arquitectura](../open-gym-evolution.architecture.md) ni el [glosario](../../GLOSSARY.md) por estos hallazgos. Refuerzan decisiones funcionales existentes; no demuestran una omisión fundamental ni autorizan ampliar el MVP. La revisión posterior de prioridad procede del usuario, no de estos hallazgos.

El PRD sigue siendo la fuente de verdad funcional y la arquitectura mantiene las decisiones técnicas aprobadas. Este benchmark no es una nueva especificación, un DDL aprobado ni una validación de utilidad clínica o adopción. Si existe una diferencia de interpretación, prevalecen los documentos aprobados, no las capacidades de las referencias externas.

**Autorización de la investigación original:** guardar y verificar esta investigación. No generar OpenSpecs de Recovery, implementar, instalar dependencias ni modificar código, PRD, arquitectura o glosario. Las recomendaciones de interacción no se convierten en requisitos obligatorios sin aprobación adicional.

**Independencia:** el benchmark no añade una dependencia ni un bloqueo a `add-postgres-foundation`. Esa iniciativa conserva su autorización independiente y el handoff de arquitectura §14.1; esta investigación no la inicia ni la autoriza por sí misma.

## 2. Pregunta y método

Se contrastaron patrones para una herramienta **personal** de registro de indicaciones profesionales y trabajo realizado, no para gestionar pacientes ni prescribir tratamientos. El contraste cubrió captura, ejercicios, sesiones, guardado, contexto histórico, correcciones, retrospectivas, evolución, móvil y privacidad.

### Alcance de la evidencia

| Referencia | Evidencia inspeccionada | Límites |
| --- | --- | --- |
| Fisio MSK | README, esquema Prisma, servicios de planes/sesiones, formularios e historial, validación y pruebas seleccionadas. | Inspección estática de una revisión concreta. Sin instalar, levantar ni ejecutar sus pruebas. No es una auditoría exhaustiva. |
| PhysioBuddy de Singapur | Publicación oficial de 2025, landing pública, pestañas demostrativas y pantalla pública de acceso. Navegación con Chrome/Playwright existente a 390 y 1365 px. | Inspección de DOM e interacción pública, no evaluación visual exhaustiva. Sin cuenta, acceso autenticado, prescripción real ni prueba Safari/iPhone. Las demostraciones no prueban persistencia. |
| Physio-Galenus | README, entidades, DTO de progreso, servicios/controladores de rutinas, interfaz y pruebas seleccionadas. | Inspección estática. Sin levantar backend, frontend, exergames o motor de decisión; sin ejecutar pruebas. |
| OpenGym | Documentos aprobados y código de controles, catálogo, cierre/edición Training y payload del coach. | Evidencia de código, no validación funcional o de dispositivo en esta investigación. |

Se consultaron fuentes públicas por HTTP y GitHub, sin clonar ni ejecutar los proyectos externos. No se instalaron navegadores o dependencias. La navegación de PhysioBuddy se limitó a contenido público, sin autenticar, enviar planes ni introducir datos personales. No se realizaron pruebas PostgreSQL, migraciones, restauraciones, cambios de infraestructura ni modificaciones de AI Tutor/AI Coach.

Las cifras, testimonios y beneficios publicados por terceros se tratan como declaraciones de sus autores, no como resultados medidos por esta investigación. No se comprobó equivalencia entre cada repositorio y una aplicación desplegada. Las revisiones fijan la evidencia del código; los sitios web pueden cambiar.

## 3. Fuentes y rutas examinadas

### 3.1 Fisio MSK

- Proyecto: <https://github.com/Mrcipo/fisio-app>.
- Rama consultada: `master`.
- Revisión: `dbb1d0f6bebe98c3cb10d147b61a63d12f004ae9`.
- [Árbol fijado a la revisión](https://github.com/Mrcipo/fisio-app/tree/dbb1d0f6bebe98c3cb10d147b61a63d12f004ae9).
- No se estableció una licencia de reutilización a partir de la metadata consultada; no asumir permiso de copiar código o medios.

Rutas examinadas, relativas a ese repositorio:

```text
README.md
apps/backend/prisma/schema.prisma
apps/backend/src/modules/rehabPlans/rehabPlans.service.ts
apps/backend/src/modules/sessions/sessions.service.ts
apps/backend/src/modules/sessions/sessions.schemas.ts
apps/backend/src/test/setup.ts
apps/backend/src/test/prisma-mock.ts
apps/backend/src/test/rehab-plans.test.ts
apps/frontend/src/components/patients/sessions-form.tsx
apps/frontend/src/components/patients/sessions-panel.tsx
```

### 3.2 PhysioBuddy de Singapur

- Sitio oficial: <https://physiobuddy.gov.sg/>.
- Acceso público: <https://physiobuddy.gov.sg/sign-in>.
- Publicación oficial, **10 de febrero de 2025**: <https://www.hack.gov.sg/2025/physiobuddy/>.
- La URL tentativa `/2023/physiobuddy/` devolvió 404; no es una fuente válida para este reporte.
- No se examinó un repositorio de implementación ni se dispone de revisión de código del sitio.
- **No es** `onkar0127/PhysioBuddy`; ese proyecto queda excluido.

La landing contiene demostraciones con recursos bajo `/assets/landing-demo/`: `1-physiobuddy_search.png`, `2-physiobuddy_edit.png`, `3-physiobuddy_review.png`, `4-physiobuddy_enterpatientinfo.png` y `5-confirmation_after.png`. Se identificaron en el DOM; no equivalen a haber utilizado esas funciones dentro del producto autenticado ni a una auditoría visual de esas imágenes.

### 3.3 Physio-Galenus

- Proyecto: <https://github.com/AIR-Research-Group-UCLM/Physio-Galenus>.
- Rama consultada: `master`.
- Revisión: `193513554ca8fc3d537367e45f181bf123ef7d18`.
- [Árbol fijado a la revisión](https://github.com/AIR-Research-Group-UCLM/Physio-Galenus/tree/193513554ca8fc3d537367e45f181bf123ef7d18).
- Licencia identificada: MIT. No se copió código ni se evaluaron licencias de todos sus datos, medios o dependencias.

Rutas examinadas, relativas a ese repositorio:

```text
README.md
sources/backend/src/database/entity/routine.entity.ts
sources/backend/src/database/entity/routine-to-exercise.entity.ts
sources/backend/src/database/entity/routine-execution-data.entity.ts
sources/backend/src/database/entity/exercise.entity.ts
sources/backend/src/database/entity/embedded/embedded-audit-dates.ts
sources/backend/src/common/dto/request/upsert-routine-progress.ts
sources/backend/src/api/routines/routines.service.ts
sources/backend/src/api/routines/routines.controller.ts
sources/backend/src/api/routines/routines.service.spec.ts
sources/backend/test/app.e2e-spec.ts
sources/frontend/src/app/ui/base-layout/general-manager/patient-profile/patient-profile.component.html
```

### 3.4 Referencias internas

Además del PRD, la arquitectura y el glosario, se consultaron el [discovery](../dev/personal-recovery-discovery.md) y estas rutas de OpenGym:

- [`frontend/src/components/ui.jsx`](../../frontend/src/components/ui.jsx).
- [`frontend/src/lib/exercises.js`](../../frontend/src/lib/exercises.js).
- [`frontend/src/lib/finish-workout.js`](../../frontend/src/lib/finish-workout.js).
- [`frontend/src/lib/session-edit.js`](../../frontend/src/lib/session-edit.js).
- [`api/coach/core/payload.js`](../../api/coach/core/payload.js).

Las observaciones internas corresponden al checkout inspeccionado, no prueban que Recovery esté implementado ni que todos los límites estén cubiertos por pruebas existentes.

## 4. Hallazgos verificables y consecuencias

### 4.1 Fisio MSK: organización útil, historial no equivalente

**FM1 — Modelo relacional sin vínculo histórico suficiente.** El stack declarado combina Next.js, Express/TypeScript y Prisma/PostgreSQL. En el [esquema, líneas 209–302](https://github.com/Mrcipo/fisio-app/blob/dbb1d0f6bebe98c3cb10d147b61a63d12f004ae9/apps/backend/prisma/schema.prisma#L209-L302), `RehabPlan` y `Session` pertenecen al paciente, pero no hay una asociación directa entre sesión y revisión inmutable de indicación. Esto no demuestra cómo conservar la indicación A después de crear B.

**FM2 — Actualización y soft delete no son un registro de correcciones.** El [servicio de sesiones, líneas 140–178](https://github.com/Mrcipo/fisio-app/blob/dbb1d0f6bebe98c3cb10d147b61a63d12f004ae9/apps/backend/src/modules/sessions/sessions.service.ts#L140-L178) actualiza la sesión y, cuando recibe ejercicios, elimina sus hijos anteriores y crea otros. El borrado de sesión establece `deletedAt`. Esos recorridos no conservan por sí mismos anterior/nuevo/fecha de corrección. No se afirma que se haya auditado todo mecanismo posible del proyecto.

**FM3 — Dependencia del catálogo actual al mostrar historia.** El [panel de sesiones, líneas 219–245](https://github.com/Mrcipo/fisio-app/blob/dbb1d0f6bebe98c3cb10d147b61a63d12f004ae9/apps/frontend/src/components/patients/sessions-panel.tsx#L219-L245) busca el nombre del ejercicio en el catálogo cargado. Una FK, aun con borrado restringido, no conserva el nombre o las instrucciones originales frente a ediciones futuras.

**FM4 — Pruebas simuladas, no integridad PostgreSQL demostrada.** El README declara 61 pruebas; la documentación y `prisma-mock.ts` muestran uso de mocks de Prisma. No se ejecutó esa suite ni se acreditó cobertura real de constraints, RLS o concurrencia en PostgreSQL. `setup.ts` por sí solo no acredita esa cobertura.

**FM5 — Formularios de otro dominio.** El formulario incluye ejercicios y dolor opcional 0–10. Es evidencia de una interfaz clínica más amplia, no una razón para exigir escalas o evaluaciones en Recovery.

**Consecuencia:** adaptar modularidad, validación y pruebas de acceso; no copiar el esquema como solución a snapshots, correcciones o contexto histórico. La conservación clínica declarada y el soft delete no equivalen a los escenarios A–D del PRD.

### 4.2 PhysioBuddy: claridad de prescripción, ejecución no demostrada

**PB1 — Recorrido público explícito.** La landing presenta buscar → personalizar → revisar → datos del paciente → confirmar/enviar. Sus pestañas explican ajustar series/repeticiones/instrucciones, ordenar ejercicios y revisar el plan. Es evidencia del recorrido comunicado y de una demostración pública, no de un guardado real.

**PB2 — Descubrimiento y personalización.** El sitio declara búsqueda, filtros, etiquetas, catálogo de más de 800 ejercicios, favoritos y plantillas. Son patrones para contrastar con nuestro catálogo existente; no justifican duplicarlo ni importar contenido.

**PB3 — Prescripción e historial no equivalen a ejecución.** La publicación oficial de 2025 describe crear y consultar prescripciones. En «Next Steps», el autorregistro de ejercicios completados y métricas aparece como evolución futura. No debe atribuirse a esa publicación una implementación demostrada de sesiones realizadas, continuación o correcciones. Tampoco se concluye que esas capacidades sigan ausentes hoy: no se accedió al producto autenticado.

**PB4 — Dominio y evidencia limitados.** La publicación declara entrevistas con seis fisioterapeutas y objetivos de reducir tiempos de prescripción de diez a tres minutos. No se verificaron esos beneficios ni se trasladan como métricas de OpenGym. El acceso público indica usuarios gubernamentales autorizados; no se intentó autenticar.

**Consecuencia:** adaptar búsqueda, instrucciones cercanas a la dosificación y revisión sencilla. No copiar un asistente obligatorio de cinco pasos: podría dificultar capturar una indicación verbal. Datos de pacientes, distribución por SMS/email e historial hospitalario compartido no pertenecen al MVP personal.

### 4.3 Physio-Galenus: separación conceptual y riesgos de identidad temporal

**PG1 — Planificación distinta de ejecución.** `Routine` y `RoutineToExercise` representan planificación/dosificación; [`RoutineExecutionData`](https://github.com/AIR-Research-Group-UCLM/Physio-Galenus/blob/193513554ca8fc3d537367e45f181bf123ef7d18/sources/backend/src/database/entity/routine-execution-data.entity.ts) contiene datos de ejecución. Refuerza la distinción indicado/realizado, sin aprobar una equivalencia de tablas con Recovery.

**PG2 — Transacción no equivale a versionado histórico.** `upsertRoutine` emplea `manager.transaction`. Ese mecanismo y las fechas de auditoría son referencias de integridad, pero no prueban revisiones inmutables de indicaciones o correcciones anterior/nuevo/fecha. No se verificó equivalencia con los escenarios del PRD.

**PG3 — Identidad de ejecución inferida por calendario.** En [routines.service.ts, líneas 208–275](https://github.com/AIR-Research-Group-UCLM/Physio-Galenus/blob/193513554ca8fc3d537367e45f181bf123ef7d18/sources/backend/src/api/routines/routines.service.ts#L208-L275), el recorrido busca una ejecución por paciente, ejercicio, serie y comparación de fecha. Usa `getDay()`, mes y año. `getDay()` devuelve el día de la semana, por lo que puede confundir fechas de semanas distintas del mismo mes y actualizar un registro anterior. Es un hallazgo estático, no reproducido ejecutando la aplicación. Incluso corregirlo a día del mes no resolvería distinguir dos sesiones del mismo día.

**PG4 — Supervisión especializada fuera del alcance.** El proyecto incluye exergames, resultados de aplicaciones externas y DSS basado en R/lógica difusa. Compensación, fatiga y adaptación automática no se importan como requisitos.

**Consecuencia:** adoptar separación conceptual y mantener identificadores explícitos de sesión/operación. No copiar agrupación implícita por fecha ni convertir ejecución en supervisión o prescripción clínica.

### 4.4 OpenGym: reutilización selectiva, no copia del flujo Training

- **OG1 — Controles:** `ui.jsx` contiene controles compartidos; comentarios y código contemplan objetivos táctiles y entrada numérica con coma decimal/estados parciales en iOS. No es evidencia de una prueba real en iPhone.
- **OG2 — Catálogo:** `exercises.js` ofrece búsqueda y ejercicios personales, pero `registerCustom()` incorpora contenido al índice global. La arquitectura ya excluye registrar información sensible Recovery en `S.customEx`/ese índice.
- **OG3 — Cierre Training:** `finish-workout.js` transforma el registro y filtra trabajo no completado; no garantiza preservar toda la indicación ni los pendientes necesarios para Recovery.
- **OG4 — Edición Training:** `session-edit.js` reemplaza registros y participa en cálculos de récords/cargas. No equivale a correcciones Recovery trazables y aisladas.
- **OG5 — Coach:** la allowlist de `payload.js` sirve como patrón de selección explícita, pero incluye notas/workouts/ejercicios Training. Poner rehabilitación en esos campos podría filtrarla indirectamente.

**Consecuencia:** reutilizar controles y catálogo de referencia donde encajen; no reutilizar íntegramente cierre, edición, progresión ni estado Training. Estos límites ya figuran en la arquitectura §§5, 6 y 9–12.

## 5. Clasificación de patrones

**Adoptar** significa conservar un principio ya aprobado, no autorizar implementación. **Adaptar** significa evaluar su encaje sin copiar dominio o interfaz. **Descartar** se refiere al MVP. **Investigar posteriormente** no crea una dependencia ni compromiso de entrega.

| Patrón | Clasificación | Motivo y destino |
| --- | --- | --- |
| Separar indicación, objetivo y trabajo realizado | Adoptar | PG1 refuerza el dominio aprobado; F1. |
| Contexto histórico estable y correcciones explícitas | Adoptar | FM1–FM3 muestran por qué no bastan relaciones actuales o soft delete; F2–F3. |
| Identidad explícita y fechas con significados distintos | Adoptar | PG3 refuerza F4; no fusionar por calendario. |
| Estados mínimos y proceso personal | Adoptar | Mantener alcance aprobado; F5. |
| Transacciones y pruebas de integridad | Adaptar | PG2/FM4 son referencias parciales; se exige el contrato propio, no equivalencia por herramienta; F6/F8. |
| Selección explícita de datos y aislamiento | Adoptar | OG2/OG5 refuerzan F7; una allowlist no basta si el origen ya mezcla dominios. |
| Búsqueda, personalización y revisión clara | Adaptar | PB1/PB2 y OG1/OG2; E1–E4, sin asistente obligatorio. |
| Guardado, historial y controles reutilizables | Adaptar | Requisitos propios y OG1–OG4; E5–E7, sin heredar semántica Training. |
| Esquema Fisio MSK como sustituto de snapshots/correcciones | Descartar | FM1–FM3 no satisfacen el contrato histórico. |
| Agrupar sesiones por ejercicio/día o guardar con last-write-wins | Descartar | PG3 y arquitectura §7; no resuelve identidad/concurrencia. |
| Soft delete o `updatedAt` como única trazabilidad | Descartar | FM2/PG2; no documentan anterior/nuevo/fecha. |
| Asistente profesional obligatorio, pacientes, SMS/email, acceso hospitalario compartido | Descartar | PB1–PB4: dominio distinto del MVP. |
| Dolor obligatorio, fases automáticas, DSS, exergames y prescripción automática | Descartar | FM5/PG4 y PRD §8; no ampliar alcance. |
| Favoritos/plantillas adicionales | Investigar posteriormente | Solo si aparece fricción no resuelta por capacidades existentes; sin compromiso. |
| Comportamiento autenticado de PhysioBuddy | Investigar posteriormente | No comprobado; solo con acceso autorizado y una pregunta concreta. No bloquea Recovery. |

## 6. Matriz de recomendaciones y requisitos aprobados

Todas las recomendaciones identificadas como F1–F8 y E1–E7 se trazan aquí. El benchmark original no requirió cambios normativos. La revisión posterior aprobada de entrega web actualiza E7 y sus referencias al PRD/arquitectura; las alternativas de interacción siguen siendo opcionales. La evidencia de terceros conserva su alcance y fecha originales.

| ID | Recomendación | Evidencia de contraste | Requisito PRD ya aprobado | Apoyo arquitectónico / carácter |
| --- | --- | --- | --- | --- |
| F1 | Distinguir indicación transcrita, objetivos y resultados reales. | PG1, PB3, FM1 | §§6.1–6.2 | §§5–6; invariante existente. |
| F2 | Preservar revisión conocida y snapshot de nombres, instrucciones, objetivos y unidades; permitir contexto desconocido. | FM1, FM3 | §6.3; §9.1 A/C/D | §6; invariante existente. |
| F3 | Corregir con anterior/nuevo/fecha sin cambiar otras sesiones ni indicaciones. | FM2, PG2, OG4 | §6.3; §9.1 B | §§6–7; invariante existente. |
| F4 | Separar vigencia, fecha efectiva y registro; identificar sesiones/operaciones sin inferir identidad por calendario. | PG3 | §§6.1–6.3; §9.1 C/D | §§6–7; precisión técnica de identidad/fechas. |
| F5 | Conservar un proceso activo, finalizados consultables, hitos simples y estados en curso/completada. | Contraste con dominio clínico FM5/PG4 | §§6.2, 6.4 | §6; límites existentes. |
| F6 | Confirmar cambio/corrección/recibo atómicamente; conservar versión, generación e idempotencia. | PG2 es parcial; ninguna referencia acredita nuestro contrato completo | §6.2; riesgo §9.3 sobre guardado/duplicados | §§7, 12; decisión técnica existente. |
| F7 | Aislar ownership, datos, Training, progresión, coach, MCP y exportaciones. | OG2–OG5; contraste PB4 | §6.5; riesgo §9.3 sobre privacidad | §§5, 9–10, 12; decisión existente. |
| F8 | Probar escenarios A–D e integridad sobre PostgreSQL real, no solo mocks. | FM4, PG2/PG3 | §9.1 A–D; §§6.6, 7 | §12/G4; estrategia de verificación existente. |
| E1 | Permitir captura textual antes de organizar ejercicios o iniciar sesión. | PB1 como contraste: no copiar pasos obligatorios | §6.1 | §5; requisito existente, presentación opcional. |
| E2 | Buscar en catálogo existente y facilitar ejercicio personal cuando no encaje. | PB2, FM5, OG2 | §§6.1, 6.5 | §5; requisito existente, interacción opcional. |
| E3 | Facilitar instrucciones y objetivos por series/reps/carga/tiempo sin exigir valores no aplicables. | PB1, OG1 | §6.1 | §6; requisito existente, disposición visual opcional. |
| E4 | Facilitar revisar orden/contenido e identificar indicado frente a realizado. | PB1, PG1 | §§6.1–6.3 | §§5–6; revisión como paso/pantalla es opcional. |
| E5 | Mostrar guardado confirmado, cambios pendientes, continuación y errores sin falso éxito. | PB3 no lo demuestra; OG3/OG4 no son sustitutos | §6.2 | §7; requisito existente, copy/controles opcionales. |
| E6 | Consultar historial cronológico, contexto anterior/desconocido, correcciones e hitos sin análisis clínico. | FM3, PG3 | §§6.3–6.4; §9.1 A–D | §6; requisito existente, visualización opcional. |
| E7 | Mantener edición web responsive sencilla, controles adecuados y acceso rápido Training; validar la matriz de arquitectura §12.1. | OG1; límites de inspección pública PB1 | §§6.5, 7 | §§5, 10, 12/G5; requisito existente, diseño concreto opcional. |

El impacto del benchmark original fue **ninguno** para F1–F8/E1–E7. La revisión web posterior propaga el ajuste aprobado de E7 al PRD y arquitectura, sin alterar los contratos de dominio F1–F8. Las investigaciones posteriores de §5 son **futuro**, no requisitos. Un diseño que añada obligatoriedad o funcionalidad fuera de estos contratos necesitará aprobación adicional.

## 7. Handoff — `add-recovery-foundation`

**Destino:** evidencia complementaria para la futura definición autorizada del cambio. No es su OpenSpec ni inicia implementación. Debe respetar la secuencia revisada de arquitectura §14: Foundation Python/PostgreSQL, port/migración/retirada y aceptación de plataforma antes de implementar Recovery. No adelantar su esquema funcional en la plataforma ni reabrir `add-postgres-foundation`, archivada como entrega sintética Node.

### Invariantes y modelo conceptual — F1/F5

- Mantener conceptos propios de proceso, indicación/revisión, sesión, trabajo, corrección, hito y recibo. El detalle relacional/JSONB sigue sujeto a la arquitectura §6, no al esquema de otro proyecto.
- Una indicación profesional es una transcripción del usuario, no una validación del profesional ni una instrucción generada por IA.
- Objetivos no ejecutados no son resultados. Completar puede dejar ejercicios pendientes sin presentarlos como realizados.
- Como máximo un proceso activo; procesos finalizados consultables. Sesiones en curso/completadas, sin fases clínicas automáticas ni estados añadidos por imitación.

### Snapshots y correcciones — F2/F3

- Conservar contexto conocido con la revisión/snapshot estable de nombres, instrucciones, objetivos y unidades. Editar catálogo o indicación no reescribe sesiones.
- Sesión bajo A permanece bajo A después de B; trabajo bajo B exige nueva sesión. Mantener también los pendientes del contexto original.
- Permitir retrospectiva sin asociación conocida y sin inventar objetivos. Una FK al catálogo actual no sustituye el snapshot.
- Corrección explícita conserva anterior/nuevo/fecha, sin crear otra sesión ni recalcular Training, otras sesiones o indicaciones. No tratar soft delete o `updatedAt` como evidencia suficiente.

### Trazabilidad, fechas y guardado — F4/F6

- Separar vigencia de indicación, fecha efectiva de sesión e instantes automáticos de registro/corrección. No convertir indiscriminadamente fechas de calendario a medianoche UTC.
- Mantener IDs explícitos de sesión y elementos corregibles; dos sesiones del mismo día no se fusionan. No usar ejercicio/serie/calendario como sustituto de identidad.
- Aplicar el contrato ya aprobado de transacción, versión, generación y recibo idempotente. Timeout significa no confirmado; reintento conserva la operación, sin duplicar ni descartar ediciones posteriores al envío.

### Aislamiento y verificación — F7/F8

- Ownership coherente en relaciones, autorización y RLS real bajo roles no exentos, incluido contexto ausente y reutilización del pool tras commit/rollback.
- Sin datos Recovery en `S.workouts`, `S.active`, `S.customEx`, progresiones/PR, payload del coach, MCP o exportaciones Training. No registrar instrucciones sensibles en el índice global de ejercicios.
- Convertir A–D en pruebas verificables de dominio/persistencia. Cubrir cambios de ejercicio, correcciones sucesivas, sesiones distintas en fechas coincidentes, atomicidad, respuesta perdida/reintento y ausencia de filtración.
- Mocks complementan; no demuestran constraints, RLS o concurrencia PostgreSQL. Este benchmark no certifica G4 ni los otros gates.

## 8. Handoff — `add-recovery-experience`

**Destino:** orientar alternativas de interacción dentro de los requisitos, no imponer pantallas, pasos o componentes. Validar el recorrido completo del PRD; disponer del backend no basta para el experimento de adopción.

- **Captura rápida — E1:** preservar texto libre/pegado/dictado nativo y captura independiente de sesión. Propuesta opcional: entrada inicial breve con organización posterior, sin asistente profesional obligatorio.
- **Búsqueda — E2:** aprovechar catálogo/búsqueda existentes sin mezclar datos sensibles. Propuesta opcional: acceso al ejercicio personal dentro del recorrido, evitando saltos innecesarios.
- **Personalización — E3:** contemplar instrucciones y objetivos apropiados, incluidos isométricos y ausencia de carga cuando no aplique. Propuesta opcional: mostrar instrucciones cerca de los controles numéricos, con detalles secundarios desplegables.
- **Revisión — E4:** distinguir indicado/realizado y contexto anterior/vigente. Propuesta opcional: revisión fácil de contenido/orden sin exigir pantalla adicional, casilla de aprobación profesional o un paso de confirmación nuevo.
- **Guardado — E5:** cumplir confirmación explícita, advertencia de cambios sin guardar y continuación de versión guardada. El diseño no debe prometer autosave, cola offline o recuperación tras cierre forzado. Copy y disposición de controles quedan por diseñar; un recibo no limpia ediciones posteriores al envío.
- **Historial — E6:** conservar fecha efectiva y registro posterior visibles, contexto anterior/desconocido, correcciones e hitos simples. No confundir evolución registrada con mejoría clínica ni añadir dashboards por imitación.
- **Web responsive — E7:** evaluar controles compartidos por su encaje, no reutilizar íntegros `Workout`, cierre/edición Training o temporizadores acoplados. Verificar con Playwright CLI el recorrido completo, autenticación, navegación, guardado, continuación e historial según [arquitectura §12.1](../open-gym-evolution.architecture.md#121-validación-web-responsive), preservando acceso rápido y offline Training. HTTPS y origen/RP ID siguen siendo requisitos de publicación/autenticación.

No son nuevos requisitos obligatorios: asistente multipaso, nueva pantalla de revisión, favoritos, plantillas, reordenamiento específico, disposición visual determinada o interacción concreta para crear ejercicios. Cualquier ampliación normativa requiere aprobación adicional. La validación de valor sigue siendo la del PRD: primeras tres sesiones reales y revisión de la necesidad de mantener WhatsApp/Notas por fricción, sin atribuir eficacia clínica.

## 9. Exclusiones, límites pendientes y cierre

No se incorpora gestión de pacientes, acceso hospitalario compartido, prescripción automática, escalas clínicas obligatorias, DSS, sensores/exergames, motor de fases, autorización de retorno deportivo, analítica clínica avanzada, distribución profesional o ampliación del AI Coach. Garmin y otras iniciativas Evolution conservan su independencia y autorización posterior.

Pendientes de evidencia, no de redefinición automática del producto:

- Usabilidad y confiabilidad de la web responsive en el recorrido completo; evidencia técnica y tres sesiones reales de utilidad según PRD.
- Integridad, concurrencia, RLS, recuperación y ausencia de filtraciones en la implementación futura.
- Capacidades autenticadas actuales de PhysioBuddy, si alguna pregunta posterior justifica investigarlas con permiso.
- Necesidad real de favoritos/plantillas adicionales; no se presume por existir en otra aplicación.

**Cierre:** benchmark aprobado y disponible como referencia complementaria para `add-recovery-foundation` y `add-recovery-experience`. El benchmark original no exigió cambios al PRD, arquitectura o glosario; la revisión web posterior, aprobada por separado, actualiza las referencias normativas de E7 sin reescribir la evidencia original. La evidencia externa no certifica gates, utilidad clínica ni adopción; las recomendaciones UX no amplían el MVP. No se generan OpenSpecs ni se inicia implementación. Este documento no bloquea el inicio independiente, debidamente autorizado, de `add-postgres-foundation`.
