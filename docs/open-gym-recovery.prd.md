---
type: PRD
title: OpenGym Recovery — PRD
description: Requisitos funcionales y validación de Recovery posteriores a la aceptación de plataforma.
---
# OpenGym Recovery — PRD

**Estado:** aprobado formalmente por el usuario desde la perspectiva funcional y de producto. Product Discovery y elaboración del PRD cerrados. Este documento es la fuente de verdad de los requisitos funcionales; la aprobación no equivale a validación en uso real ni a aprobación de arquitectura.

**Fuentes principales:** [discovery consolidado](dev/personal-recovery-discovery.md) y [glosario](../GLOSSARY.md). Este PRD traduce esas decisiones a intención de producto; no es un diseño técnico ni autoriza implementación.

**Revisión de prioridad autorizada el 2026-10-22:** la implementación de Recovery comienza después de completar y aceptar la plataforma Python/FastAPI/PostgreSQL del [PRD Evolution](open-gym-evolution.prd.md), conforme a [arquitectura §12](open-gym-evolution.architecture.md#12-gates-y-experimentos-antes-de-producción). Se conservan los requisitos funcionales y escenarios A–D. La aprobación documental no acredita plataforma terminada ni inicia Recovery.

**Revisión aprobada del alcance web:** la entrega actual es una web responsive. La aceptación deja de depender de Safari/iPhone; conserva las tres sesiones reales como evaluación de utilidad. Esta revisión documental no acredita pruebas visuales ejecutadas ni modifica los escenarios A–D.

## Resumen ejecutivo

OpenGym Recovery busca que una persona en rehabilitación pueda consultar sus indicaciones y registrar lo realizado sin mantener información dispersa en otras aplicaciones. El primer caso es una recuperación personal de LCA, sin restringir el producto a esa lesión.

La apuesta es sustituir los registros paralelos mediante un recorrido sencillo: **capturar indicación → organizar ejercicios → iniciar sesión → guardar avances → completar sesión → consultar historial y evolución**. Se reutilizará OpenGym cuando permita cumplir el recorrido sin comprometer el historial ni Training.

La validación se realizará durante las primeras tres sesiones reales de kinesiología, desde cualquier navegador y tamaño admitidos para la entrega web, después de aceptar plataforma y verificar la experiencia Recovery completa. Se considerará cuestionada la hipótesis si el usuario necesita seguir registrando en WhatsApp o Notas por lentitud, complejidad o falta de confianza. Garmin, voz avanzada y ampliación del coach quedan fuera del MVP funcional. La modernización se entrega previamente con aceptación propia; las tres sesiones no evalúan la migración arquitectónica.

## 1. Problema

Una persona que comienza una rehabilitación recibe indicaciones principalmente verbales y conserva información en WhatsApp, Notas del iPhone y audios. Le cuesta recuperar qué corresponde hacer actualmente, qué realizó en la última sesión y qué cambió durante la recuperación.

Mantener esa información dispersa obliga a buscar y reconstruir el contexto entre aplicaciones. Además, dificulta distinguir una indicación recibida de un resultado real o de una observación personal. No se ha cuantificado el tiempo perdido ni demostrado un impacto clínico; no se atribuyen mejoras clínicas al producto.

La necesidad es disponer de continuidad y confianza en el registro personal, sin añadir un proceso administrativo que haga más difícil entrenar o rehabilitarse.

## 2. Evidencia y límites de conocimiento

| Evidencia | Fuente y alcance |
| --- | --- |
| Indicaciones principalmente verbales, guardadas en WhatsApp, Notas y audios | Testimonio directo del usuario recogido en el discovery; no es una observación instrumentada. |
| Necesidad de consultar indicaciones actuales, última sesión y evolución | Prioridades expresamente confirmadas por el usuario. |
| Necesidad de distinguir indicaciones, resultados y correcciones | Confirmada, incluidos vigencia, contexto histórico y valores anterior/nuevo de una corrección. |
| Necesidad de guardar una sesión y continuarla | Confirmación final: una sesión puede interrumpirse o realizarse en distintos momentos. |
| Preferencia por simplicidad, reutilización de OpenGym y uso web responsive | Confirmada en el discovery y en la revisión posterior del alcance web. |
| Primer proceso de recuperación de LCA, desde preoperatorio hasta eventual retorno deportivo | Contexto aportado por el usuario; no constituye un protocolo de tratamiento. |
| Existencia de Training, catálogo, coach y documentación de acceso web | Referencias del repositorio recogidas en el discovery; la aptitud concreta para reutilización requiere evaluación técnica. |

**Hipótesis, no hechos demostrados:** una experiencia integrada será suficientemente cómoda para sustituir los registros paralelos; el recorrido funcionará bien en navegadores de escritorio y pantallas pequeñas; la reutilización de OpenGym permitirá preservar Training sin un registrador paralelo.

La evidencia corresponde a una sola persona y a una etapa inicial. No permite inferir demanda comercial, utilidad para profesionales ni resultados clínicos.

## 3. Tesis: por qué construirlo

### Por qué ahora

El discovery original recoge el comienzo del proceso de recuperación y la oportunidad de construir continuidad con sesiones reales. La revisión de prioridad del 2026-10-22 antepone la plataforma antes de implementar Recovery; no presupone que la etapa personal siga siendo la misma al entregar la función ni inventa una fecha de validación. La oportunidad de producto y sus hipótesis se conservan.

### Por qué podría superar las alternativas actuales

WhatsApp, Notas y el dictado nativo resuelven la captura rápida. La oportunidad no es reemplazarlos con otro bloc de notas, sino conectar esa captura con ejercicios, sesiones realizadas y contexto histórico, manteniendo una fricción baja.

La diferenciación se comprobará si el usuario puede consultar y registrar en una sola aplicación sin duplicar trabajo. La mera centralización de información no demuestra que vaya a cambiar de hábito.

### Visión

Una herramienta personal de entrenamiento y recuperación que permita saber qué estaba indicado, qué se hizo y cómo cambió el recorrido, de forma sencilla y confiable en la web, tanto en escritorio como en pantallas pequeñas.

## 4. Hipótesis falsable

**Creemos que** reunir indicaciones personales, ejercicios y sesiones con contexto histórico en una experiencia sencilla de OpenGym permitirá a la persona en rehabilitación completar su seguimiento sin mantener registros paralelos, obteniendo continuidad y confianza al consultar lo indicado y lo realizado.

**Sabremos que vamos en la dirección correcta si**, durante las primeras tres sesiones reales de kinesiología, el usuario puede encontrar sus indicaciones, registrar su trabajo y revisar la última sesión sin recurrir a WhatsApp o Notas por limitaciones de Recovery. También debe poder recuperar una indicación anterior y su vigencia; si no hay un cambio real, se comprobará con un escenario controlado separado del historial real.

**Sabremos que la hipótesis queda cuestionada si** necesita mantener registros paralelos porque Recovery resulta lento, complejo o poco confiable. Un fallo de guardado, pérdida de contexto o confusión entre lo indicado y lo realizado exige revisar la solución aunque las demás tareas se completen.

Tres sesiones proporcionan una señal inicial, no una prueba de hábito sostenido ni de eficacia clínica.

## 5. Usuario objetivo y Jobs to Be Done

### Usuario principal

Una persona que registra por sí misma las indicaciones recibidas de su profesional tratante, realiza entrenamiento y rehabilitación, y consulta desde un navegador web en escritorio o pantallas pequeñas. El primer usuario y evaluador es el propio promotor del proyecto.

### Jobs to Be Done

- **Al recibir indicaciones**, quiero capturarlas rápidamente para no depender de recordar una conversación ni organizar todo en ese instante.
- **Antes de una sesión**, quiero encontrar ejercicios e instrucciones vigentes para saber qué tengo registrado que corresponde realizar.
- **Durante una sesión**, quiero registrar el trabajo y guardar avances para poder interrumpirla y continuar sin repetir el registro.
- **Al revisar una sesión pasada**, quiero distinguir lo indicado de lo realizado para entender lo ocurrido sin que cambios posteriores reescriban el contexto.
- **Al cambiar una indicación**, quiero conservar su antecedente y vigencia para comprender la evolución del proceso.
- **Al equivocarme al registrar**, quiero corregir el error dejando una referencia sencilla para no confundirlo con un cambio de indicación.

### No usuarios del MVP

Profesionales que gestionan pacientes, equipos clínicos, organizaciones que requieren auditoría clínica o personas que buscan diagnóstico, prescripción o autorización automática para progresar.

## 6. MVP: recorrido completo mínimo

Los siguientes requisitos están confirmados en el discovery y sus precisiones posteriores aprobadas por el usuario. Describen resultados funcionales, no pantallas, relaciones de datos ni estrategias de almacenamiento.

### 6.1 Capturar y organizar indicaciones

- Registrar texto personal, pegado o introducido mediante el dictado opcional proporcionado por el sistema o dispositivo. La captura no exige iniciar una sesión ni organizar inmediatamente todos los ejercicios.
- Identificar que una indicación fue recibida del profesional y transcrita por el usuario: no implica que el profesional haya validado el registro.
- Separar las indicaciones de notas u observaciones personales.
- Organizar ejercicios del catálogo existente; permitir ejercicios personales con nombre e instrucciones cuando no exista uno adecuado.
- Contemplar objetivos por series, repeticiones, carga o tiempo, incluidos ejercicios isométricos, según corresponda. No exigir valores de carga donde no apliquen.
- Consultar las indicaciones vigentes y las anteriores.
- Diferenciar **vigente desde**, elegido por el usuario, de **registrado el**, automático. Se admite registrar una indicación después de su inicio de vigencia.

### 6.2 Registrar, guardar y continuar sesiones

- Dos estados iniciales: **en curso** y **completada**.
- En una sesión en curso, registrar ejercicios, series, repeticiones, cargas, tiempos y observaciones; guardar explícitamente los avances y retomarlos posteriormente.
- Mostrar claramente cuándo el guardado quedó confirmado. No presentar éxito si no existe confirmación.
- Advertir antes de abandonar una sesión con cambios sin guardar. No prometer recuperación de contenido no guardado ante cierre forzado, recarga o reinicio.
- Completar una sesión conserva el registro del trabajo realizado y señala que el usuario terminó, aunque no haya realizado todos los ejercicios previstos. Los ejercicios pendientes no se presentan como realizados.
- Una sesión en curso conserva el contexto de su indicación original aunque posteriormente cambie la prescripción. Para realizar trabajo bajo la nueva indicación, se inicia una nueva sesión asociada a ella; no se segmentan indicaciones por serie.
- Mostrar claramente cuando una sesión corresponde a una indicación anterior y distinguirla de la prescripción vigente.
- Permitir registrar sesiones después de su realización, distinguiendo la **fecha efectiva de realización** de la **fecha de registro en OpenGym**.
- Conservar la indicación aplicable cuando pueda identificarse; permitir guardar la sesión sin esa asociación cuando sea incierta, sin asignar una por suposición.
- Incluir una nota opcional de sesión para molestias u observaciones; no exigir escalas de dolor ni formularios clínicos.
- Distinguir lo efectivamente realizado de lo indicado. No presentar objetivos como si fueran resultados ejecutados.

### 6.3 Consultar contexto histórico y evolución

- Consultar la última sesión y sesiones anteriores, con ejercicios, resultados y observaciones.
- Conservar el contexto original: ejercicios y objetivos indicados e indicación aplicable cuando estén identificados, además del trabajo efectivamente registrado. Si no se conoce la indicación de una sesión retrospectiva, mostrar esa ausencia de información sin inventar objetivos ni asociación.
- Un cambio posterior de indicación o de un ejercicio personal no altera retrospectivamente ese contexto.
- Diferenciar **corrección de captura** de **nueva indicación**. Una corrección conserva valor anterior, nuevo y fecha; una nueva indicación conserva la anterior y tiene su propia vigencia.
- Cambiar o corregir una indicación no modifica automáticamente sesiones pasadas.
- Permitir al usuario corregir explícitamente errores de registro de una sesión completada, conservando el valor anterior, el nuevo y la fecha de corrección.
- Corregir una sesión no altera silenciosamente las indicaciones profesionales originales, no modifica otras sesiones ni recalcula automáticamente registros históricos ajenos a esa corrección. Esta acción no equivale a iniciar una nueva sesión.
- Mostrar evolución de ejercicios, cargas, repeticiones y duración sin equipararla automáticamente a mejoría clínica.
- Ordenar las sesiones cronológicamente por su fecha efectiva de realización, manteniendo visible cuándo se registraron posteriormente.
- Ofrecer un historial cronológico sencillo; no se exige una visualización avanzada de timeline.

### 6.4 Mantener un proceso de recuperación

- Un único proceso activo es suficiente. Conservar los procesos finalizados para consulta, sin administración avanzada de programas simultáneos.
- Reunir indicaciones, ejercicios asociados, sesiones, notas, cambios e hitos en el proceso.
- Registrar acontecimientos como preoperatorio, cirugía y postoperatorio como hitos cronológicos, sin motor de fases ni progresión automática.
- El primer caso es LCA, pero el concepto no depende exclusivamente de esa lesión.

### 6.5 Preservar OpenGym y ofrecer una experiencia web responsive

- Reutilizar las capacidades existentes cuando encajen con los requisitos, evitando módulos paralelos innecesarios. No se prescribe qué componentes concretos reutilizar.
- Preservar Training, su acceso rápido a rutinas y ejercicios y su funcionamiento offline existente.
- Recovery no aumenta automáticamente cargas, repeticiones ni tiempos. El usuario registra cambios recibidos del profesional, sin heredar automáticamente las progresiones de Training.
- Mantener el AI Coach actual sin ampliar sus flujos para rehabilitación.
- Recovery puede requerir conexión para guardar. No exige autosave avanzado ni sincronización offline.
- La conservación temporal del contenido en edición es deseable si puede aprovechar capacidades existentes sin complejidad significativa; no es una garantía de recuperación tras cierre.
- Validar el recorrido web completo en escritorio y pantallas pequeñas: captura, organización, autenticación, navegación, guardado, continuación e historial. Los controles deben ser accesibles y operables, sin recortes que impidan completar el recorrido; lo guardado debe conservarse tras recarga. La matriz técnica se concreta en [arquitectura §12.1](open-gym-evolution.architecture.md#121-validación-web-responsive).
- La publicación y autenticación deben preservar HTTPS y la compatibilidad de origen/passkeys. La verificación local puede usar localhost cuando sea compatible; no exige adelantar el VPS definitivo.

### 6.6 Límite del experimento y decisiones difíciles de revertir

Este es un corte funcional completo para probar la hipótesis, no la construcción de toda la visión Evolution. Presentación del resumen, organización visual y copy podrán ajustarse con las fricciones observadas.

La pérdida de datos y la alteración del historial son consecuencias costosas o imposibles de revertir. El diseño posterior debe evaluar esos riesgos antes de usar registros reales; este PRD no decide persistencia, migraciones, mecanismos de recuperación ni pruebas técnicas.

## 7. Criterios de éxito y fracaso

**Período:** primeras tres sesiones reales de kinesiología. **Método:** uso real desde cualquier navegador y tamaño admitidos, con revisión de fricciones junto al usuario, sin exigir instrumentación analítica ni tiempos arbitrarios.

| Resultado | Objetivo acordado | Cómo se comprobará |
| --- | --- | --- |
| Consultar lo vigente | Encontrar ejercicios e indicaciones sin buscar en WhatsApp o Notas por limitaciones de Recovery | Revisar la consulta durante las tres sesiones y registrar dificultades. |
| Evitar doble registro | Documentar ejercicios, series, repeticiones, pesos o tiempos sin un registro paralelo necesario | Revisar qué se registró y si hubo que mantener otra aplicación. |
| Entender lo realizado | Consultar la última sesión y distinguir objetivos de resultados | Recorrer la sesión registrada con el usuario y recoger confusiones. |
| Recuperar cambios | Consultar una indicación anterior, su vigencia y cambios | Usar un cambio real o un escenario controlado claramente separado si no hubo cambios. |
| Continuar con confianza | Retomar una sesión con sus avances explícitamente guardados | Comprobar una interrupción y continuación; puede usarse un escenario controlado si no ocurre naturalmente. |
| Conservar el contexto | Cambios posteriores no reescriben una sesión anterior | Comparar una sesión antes y después de cambiar indicación o ejercicio en un escenario controlado. |
| Mantener Training | No perjudicar sus recorridos actuales, incluido el offline existente | Verificar los recorridos relevantes antes de considerar satisfactoria la validación; el método técnico se definirá después. |

La validación técnica del recorrido web y su persistencia es un requisito previo al uso de datos reales; capturas y pruebas técnicas no demuestran adopción ni sustituyen estas tres sesiones.

Los tres últimos resultados son comprobaciones funcionales de requisitos confirmados, no métricas nuevas de adopción.

**Indicador principal:** el usuario elige Recovery como herramienta habitual para el recorrido completo. El uso en tres sesiones es una primera señal; la continuidad posterior sigue pendiente de validación.

**Condición de fracaso o revisión:** persistencia de registros paralelos por fricción, guardados poco confiables, pérdida de información, contexto histórico alterado o confusión entre indicaciones y resultados. No se compensan estos problemas con una mayor cantidad de funciones o sesiones registradas.

## 8. Exclusiones y visión posterior

### Fuera del MVP

- Gestión de pacientes, cuentas profesionales, acceso clínico compartido y auditoría clínica compleja.
- Versionado de indicaciones por cada serie y segmentación temporal avanzada dentro de una sesión.
- Varios procesos activos simultáneos, motor configurable de fases y administración avanzada de programas.
- Diagnóstico, recomendaciones clínicas autónomas, autorización de retorno deportivo o progresión automática en Recovery.
- Formularios estructurados de síntomas, escalas de dolor y mediciones clínicas especializadas.
- Dashboards y análisis avanzados.
- Colas offline, resolución de conflictos, autosave avanzado y almacenamiento offline avanzado para Recovery.
- Sincronización Garmin Connect y servicio propio de transcripción.
- Ampliación del AI Coach para rehabilitación.
- Desarrollo o distribución de apps nativas y publicación en tiendas. Las capacidades móviles existentes del proyecto base no forman parte de esta entrega.
- Despliegue definitivo en VPS como condición de la primera validación.
- Implementación de la modernización dentro del alcance funcional Recovery: Python/FastAPI/PostgreSQL corresponde a la entrega previa Evolution. No implica sustituir el frontend o cambiar automáticamente la experiencia de autenticación.

### Roadmap de OpenGym Evolution

Orden de entrega vigente: **plataforma Python/FastAPI/PostgreSQL completada y aceptada → Recovery → Garmin Connect → ampliaciones de IA**. La plataforma es una dependencia de implementación y tiene aceptación independiente; no demuestra por sí misma la utilidad de Recovery. Sin fechas comprometidas; voz, análisis y offline avanzado se evalúan por necesidad. Validar localmente no obliga a adelantar el VPS definitivo.

| Iniciativa | Intención de producto futura |
| --- | --- |
| Acceso remoto seguro | Publicar la web responsive fuera del entorno local mediante VPS y dominio HTTPS, preservando datos y acceso. |
| Garmin Connect | Explorar sincronización de actividades, frecuencia cardíaca, sueño y otras métricas deportivas. La exportación `.fit` actual no equivale a esta capacidad. |
| Voz | Evaluar transcripción propia si el dictado nativo no basta. |
| AI Coach | Evaluar una ampliación con información pertinente de entrenamiento y recuperación, sin convertirla en prescripción autónoma. |
| Análisis y offline | Evaluar mejoras según necesidades observadas, no como requisitos anticipados. |
| Plataforma Evolution — previa | Completar y aceptar el [PRD Evolution](open-gym-evolution.prd.md) antes de implementar Recovery; preservar las capacidades actuales y operar/recuperar la instancia conforme a arquitectura. |

## 9. Preguntas abiertas y handoff

### 9.1 Decisiones cerradas y escenarios de aceptación

Las tres precisiones fueron confirmadas expresamente por el usuario después de la primera revisión del PRD. Complementan el discovery y el glosario sin cambiar sus distinciones de dominio. No quedan preguntas funcionales críticas abiertas en estos casos.

#### A. Cambio de indicación con una sesión en curso

**Dado** que una sesión en curso tiene trabajo guardado bajo la indicación A y todavía quedan ejercicios previstos, **cuando** se registra una nueva indicación B, **entonces**:

- La sesión conserva la indicación A, sus objetivos originales y todo el trabajo registrado, sin adoptar retrospectivamente B.
- La interfaz identifica que corresponde a una indicación anterior y la distingue de la vigente B.
- El usuario puede completar la sesión aunque queden ejercicios sin realizar; estos no aparecen como ejecutados.
- Para registrar trabajo bajo B, el usuario inicia una nueva sesión asociada a B. La sesión anterior permanece sin alteraciones por esa acción.

La comprobación no requiere versiones por serie ni segmentación temporal avanzada.

#### B. Corrección explícita de una sesión completada

**Dado** que una sesión completada contiene por error una serie de 12 repeticiones, **cuando** el usuario corrige explícitamente el valor a 10 y guarda, **entonces**:

- La consulta del registro refleja 10 repeticiones y permite consultar que el valor anterior era 12, el nuevo es 10 y cuándo se corrigió.
- La operación corrige esa sesión completada, sin crear otra sesión ni exigir un nuevo estado funcional.
- Las indicaciones profesionales originales y las demás sesiones permanecen sin cambios.
- No se recalculan automáticamente registros históricos ajenos a la corrección.

Cambiar una indicación sin ejecutar esta corrección explícita tampoco modifica el resultado de la sesión.

#### C. Registro retrospectivo con indicación identificable

**Dado** que el usuario realizó una sesión el lunes y la registra el miércoles, **cuando** introduce la fecha efectiva del lunes e identifica la indicación que correspondía, **entonces**:

- La sesión muestra el lunes como fecha de realización y el miércoles como fecha de registro.
- En el historial de sesiones ocupa el lugar correspondiente al lunes, no al miércoles.
- Conserva la indicación identificada y su contexto, aunque actualmente haya otra indicación vigente; no se sustituye por esta última.

#### D. Registro retrospectivo sin indicación identificable

**Dado** el mismo registro retrospectivo, pero sin certeza sobre la indicación aplicable, **cuando** el usuario guarda el trabajo realizado sin asociar una indicación, **entonces**:

- El guardado está permitido y conserva ejercicios, resultados, observaciones y ambas fechas registradas.
- La consulta deja claro que la indicación no está identificada, sin asignar la vigente ni inventar objetivos o una comparación con lo prescrito.
- La sesión se ordena por su fecha efectiva de realización y mantiene visible la fecha posterior de registro.

Estos escenarios son comprobaciones de aceptación; no agregan métricas de adopción ni deciden la estrategia técnica de conservación del historial.

### 9.2 Hipótesis pendientes de validación

- La integración compensará el esfuerzo inicial de organizar indicaciones y desplazará los registros paralelos.
- La experiencia web responsive será suficientemente cómoda y confiable en los tamaños admitidos.
- Tres sesiones darán información suficiente para decidir la siguiente iteración, aunque no prueben hábito sostenido.
- La entrada de texto, el dictado opcional del sistema y una nota opcional bastarán para la captura inicial y las observaciones.

### 9.3 Riesgos y decisiones que se entregan a arquitectura

Son temas a investigar y decidir después de la aprobación del PRD, no decisiones técnicas tomadas aquí:

- Reutilización real del registrador y catálogo, acoplamiento de persistencia y sincronización, preservación de Training y aislamiento de sus progresiones.
- Estrategia para conservar contexto histórico, correcciones y procesos finalizados sin reescrituras retrospectivas.
- Confirmación de guardado ante interrupciones de conexión y prevención de duplicados al repetir una operación; no se prescribe manejo de errores, protocolo ni reintentos.
- Alcance viable de protección del contenido no guardado y advertencias en los navegadores admitidos, incluidas las limitaciones del cierre forzado.
- Entorno de verificación web local, compatibilidad de autenticación y transición posterior a dominio/VPS con HTTPS, origen y RP ID válidos.
- Respaldo, restauración y protección de registros reales antes de la validación; trazabilidad sencilla no equivale a garantías clínicas.
- Revisión de acceso, exportaciones y selección de datos del coach para evitar que incorporar Recovery extienda inadvertidamente el uso de información personal. Los límites y mecanismos se decidirán expresamente en arquitectura.
- Python/FastAPI/PostgreSQL es la dirección confirmada de la plataforma previa, no una nueva necesidad clínica ni un requisito de utilidad de Recovery. Arquitectura concreta herramientas auxiliares y condiciones de aceptación. LangChain/LangGraph y pgvector no son dependencias anticipadas.
- Evaluación de prácticas de AI Tutor como referencia, sin importar automáticamente su dominio dental, estructura o topología de despliegue.

Referencias de kinesiología y la mención previa a Mapbox siguen sin aclararse; no son dependencias del alcance confirmado y no autorizan incorporar protocolos clínicos ni mapas.

### 9.4 Revisión de calidad frente al discovery

| Control | Resultado |
| --- | --- |
| Problema respaldado por evidencia | Cumple: testimonio personal identificado; no se presenta como demanda de mercado ni resultado clínico. |
| Hipótesis con éxito y fracaso separados | Cumple: ventana de tres sesiones y condiciones explícitas de revisión. |
| Requisitos confirmados cubiertos | Sin omisiones identificadas en la revisión documental: captura, ejercicios personales, fechas, correcciones, sesiones, contexto, proceso, hitos, web responsive y preservación de Training; incorporadas las tres precisiones posteriores. |
| Coherencia del alcance | Guardado explícito online permite continuación; cambiar de prescripción requiere nueva sesión; completar no exige ejecutar todo; corrección explícita no equivale a reescritura automática; una indicación desconocida no impide registrar trabajo real. |
| Métricas orientadas a resultados | Cumple: consulta, ausencia de doble registro, comprensión y confianza; sin tiempos o porcentajes inventados. |
| Supuestos visibles | Cumple: utilidad, cambio de hábito y experiencia web responsive siguen sin validarse. |
| Ambigüedades de aceptación | Tres decisiones cerradas por el usuario y cuatro escenarios verificables en 9.1, distinguiendo el registro retrospectivo con y sin indicación identificable. No quedan ambigüedades funcionales críticas identificadas. |
| Exclusiones y roadmap | Plataforma previa con aceptación propia; luego Recovery, Garmin y ampliaciones de IA. La revisión de prioridad no amplía los requisitos funcionales del MVP. |
| Separación producto/ingeniería | No se eligen librerías, versiones, relaciones de datos, estructura, mecanismos de seguridad, reintentos ni arquitectura de pruebas. Los temas técnicos se entregan, no se resuelven. |

**Preparación:** revisión documental completada y aprobación final de producto recibida. Las tres precisiones funcionales están confirmadas y expresadas como requisitos y escenarios verificables. No se identifican contradicciones con el discovery o el glosario: los cambios automáticos siguen prohibidos y las correcciones explícitas son trazables; el contexto conocido se preserva y el desconocido no se inventa.

El PRD aprobado conserva la autoridad funcional de Recovery dentro de la [arquitectura revisada](open-gym-evolution.architecture.md); el [PRD Evolution](open-gym-evolution.prd.md) gobierna la plataforma previa. No es una especificación lista para implementar ni una validación de viabilidad técnica. Las hipótesis de valor y usabilidad y los riesgos técnicos de 9.2 y 9.3 permanecen abiertos, sin nuevas decisiones funcionales que requieran otra ronda de discovery.

**Handoff vigente:** completar plataforma conforme al PRD Evolution y G0–G3/GP/GO antes de comenzar implementación Recovery. Después se aplican los contratos Recovery, G4/G5 y el recorrido completo de este PRD; solo entonces se realizan las tres sesiones reales para evaluar utilidad. La entrega Node sintética del [OpenSpec Foundation archivado](../openspec/changes/archive/2026-10-22-add-postgres-foundation/tasks.md) no demuestra Python, G1 operativo ni plataforma terminada. Cualquier nueva funcionalidad del MVP requiere justificación de producto y aprobación explícita; la revisión de prioridad no amplía el alcance funcional.

La evolución debe preservar Training, su historial y el acceso a los datos existentes. La sustitución de la persistencia y las condiciones para cerrar su retirada técnica se definen en la [arquitectura, §§9, 11–12 y 14](open-gym-evolution.architecture.md); no constituyen criterios adicionales de utilidad o adopción de Recovery.

Cada cambio OpenSpec y su implementación requieren autorización propia. Esta revisión del PRD no inicia tareas técnicas, modifica código ni acredita pruebas de Recovery.
