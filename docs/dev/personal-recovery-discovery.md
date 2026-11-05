---
type: Research
title: OpenGym Recovery — discovery consolidado
description: Evidencia histórica de necesidades, decisiones y límites del discovery de Recovery.
---
# OpenGym Recovery — discovery consolidado

Estado: discovery cerrado tras confirmación final del usuario, conservado como antecedente del [PRD aprobado](../open-gym-recovery.prd.md) y la [arquitectura aprobada](../open-gym-evolution.architecture.md). No es una especificación implementable; el estado de entrega se sigue en OpenSpec.

**Revisión de prioridad autorizada el 2026-10-22:** completar y aceptar primero la plataforma Python/FastAPI/PostgreSQL del [PRD Evolution](../open-gym-evolution.prd.md); después implementar Recovery, luego Garmin y ampliaciones de IA. Se conserva el testimonio original y el alcance funcional Recovery. Las preferencias técnicas inicialmente exploratorias quedan sustituidas por esta dirección; no se declara ninguna implementación o prueba nueva.

**Revisión aprobada del alcance web:** este discovery incorpora la entrega web responsive y conserva su testimonio inicial como contexto histórico. El PRD y la arquitectura desarrollan esta revisión; no se requieren app nativa ni validación en un teléfono concreto.

## 1. Problema, evidencia y usuario objetivo

El usuario recibe indicaciones de kinesiología principalmente de forma verbal y las conserva en WhatsApp, Notas del iPhone y notas de voz. Esta fragmentación dificulta consultar qué está indicado, qué se realizó y cómo cambia el proceso de recuperación.

La primera versión es de uso personal: el usuario registra las indicaciones recibidas de su profesional tratante. No se construirá una plataforma para gestionar pacientes ni se requiere acceso del profesional.

El proceso está comenzando; se busca construir un historial continuo desde el preoperatorio al postoperatorio y el retorno progresivo a actividades deportivas. No se ha demostrado aún que Recovery sustituya los registros informales: esa es la hipótesis a validar.

OpenGym debe mantener su utilidad para el entrenamiento convencional, incluido el acceso rápido a rutinas y ejercicios. Recovery debe ser sencillo y cómodo en la web, desde escritorio y pantallas pequeñas, sin exigir un dashboard complejo.

## 2. Flujo principal

**Capturar indicación → Organizar ejercicios → Iniciar sesión → Guardar avances → Completar sesión → Consultar historial y evolución.**

- Capturar información escrita personalmente, pegada desde otra fuente o mediante el dictado opcional del sistema o dispositivo.
- Organizar los ejercicios e indicaciones vigentes usando el catálogo de OpenGym o ejercicios personales cuando no exista uno adecuado.
- Registrar lo efectivamente realizado: ejercicios, series, repeticiones, cargas o tiempos, incluidos isométricos, aprovechando las capacidades de Training.
- Consultar las indicaciones actuales, la última sesión, resultados anteriores y cambios de indicación con sus fechas de vigencia.

La captura precede a la organización de ejercicios; no exige iniciar una sesión. Durante una sesión se pueden guardar explícitamente los avances y retomarla posteriormente. No se exige guardado automático.

## 3. Requisitos confirmados

### Indicaciones y ejercicios

- Conservar tanto las indicaciones profesionales registradas por el usuario como los resultados reales. Una anotación personal no implica validación del profesional.
- Reutilizar el catálogo existente cuando corresponda, sin elegir equivalentes incorrectos para forzar una coincidencia.
- Permitir ejercicios personales con nombre, instrucciones y registro por repeticiones o por tiempo, revisando primero las capacidades existentes.
- Diferenciar «vigente desde», elegido por el usuario, de «registrado el», recogido automáticamente. La vigencia puede preceder al registro.
- Mantener accesibles las indicaciones anteriores y sus cambios de vigencia.

### Correcciones e historial

- Corregir un error de registro no equivale a recibir una nueva indicación.
- Una corrección conserva una referencia sencilla al valor anterior, el nuevo y la fecha de corrección.
- Una nueva indicación conserva la anterior y tiene su propia fecha de vigencia.
- Las sesiones realizadas no se modifican automáticamente al cambiar o corregir indicaciones.
- No se exige una auditoría clínica compleja.

### Proceso e historial cronológico

- Un único proceso de recuperación activo basta para el MVP; los procesos finalizados se conservan para consulta.
- El primer caso es recuperación de LCA, pero el concepto de proceso no debe depender de esa lesión ni impedir otros procesos futuros.
- El proceso reúne indicaciones, ejercicios asociados, sesiones, notas, cambios de indicaciones e hitos en un historial cronológico continuo.
- Preoperatorio, cirugía y postoperatorio pueden registrarse como eventos o hitos; no se requiere motor de fases ni administración avanzada de programas simultáneos.

### Sesiones y evolución

- Dos estados iniciales: **en curso** y **completada**.
- Una sesión en curso permite registrar ejercicios, series, repeticiones, cargas, tiempos y observaciones; guardar explícitamente avances y continuar posteriormente.
- Marcar una sesión como completada indica que terminó y conserva lo realizado.
- Mostrar confirmación clara de guardado y advertir antes de abandonar una sesión con cambios sin guardar. Las limitaciones de cierre forzado del navegador deben explicitarse; la advertencia no equivale a persistencia automática.
- Consultar en una sesión pasada los ejercicios y objetivos indicados (series, repeticiones, cargas o tiempos), la indicación vigente al realizarla, lo efectivamente realizado y las observaciones.
- Los cambios posteriores de indicación o de un ejercicio personal no alteran retrospectivamente el contexto histórico de la sesión. La estrategia técnica se decidirá en arquitectura.
- Registrar sesiones y ejercicios sin necesitar un registro paralelo en otra aplicación.
- Distinguir lo indicado de lo realizado.
- Consultar evolución de ejercicios, cargas, repeticiones y duración. Estos datos no deben confundirse automáticamente con mediciones clínicas.
- Una nota opcional de sesión basta inicialmente para molestias u observaciones.
- Recovery no aumenta automáticamente cargas, repeticiones ni tiempos: el usuario registra cambios recibidos del profesional.
- Reutilizar la interacción de Training no autoriza heredar sus reglas de progresión en Recovery.
- Un resumen sencillo y un historial cronológico bastan; no se exige un componente visual de timeline complejo.

### Conectividad y plataforma

- Recovery puede requerir conexión para guardar en el MVP.
- No se incluyen colas offline, resolución de conflictos ni almacenamiento local avanzado para Recovery.
- Preservar el funcionamiento offline existente de Training y sus capacidades útiles.
- No mostrar éxito sin confirmación de guardado. Ante fallos, comunicar claramente que el guardado no está confirmado.
- Conservar temporalmente el contenido en edición es deseable si puede reutilizarse una capacidad existente sin complejidad significativa. No se ha prometido supervivencia ante recarga, cierre o reinicio.
- Mantener las capacidades actuales del AI Coach, sin ampliarlo para rehabilitación inicialmente.
- Validar el recorrido web responsive completo antes de usar datos reales: captura, organización, autenticación, navegación, guardado, continuación e historial. La matriz y evidencia técnica se concretan en [arquitectura §12.1](../open-gym-evolution.architecture.md#121-validación-web-responsive).
- No es necesario adelantar el VPS definitivo ni sustituir la autenticación existente. El objetivo posterior es publicar una web responsive con HTTPS y origen/RP ID compatibles; las verificaciones locales pueden usar localhost cuando proceda.

## 4. Hipótesis y validación

Creemos que centralizar indicaciones y sesiones en OpenGym permitirá al usuario registrar y consultar su rehabilitación sin recurrir a aplicaciones paralelas, manteniendo una experiencia sencilla y confiable.

**Ventana:** primeras tres sesiones reales de kinesiología, desde cualquier navegador y tamaño admitidos.

**Señales de éxito:**

1. Encontrar ejercicios e indicaciones vigentes sin buscar en WhatsApp o Notas.
2. Registrar ejercicios, series, repeticiones, pesos o tiempos sin mantener registros paralelos.
3. Consultar la última sesión y distinguir lo indicado de lo realizado.
4. Recuperar indicaciones anteriores, fechas de vigencia y cambios. Si no existe un cambio real en esas tres sesiones, comprobarlo con un escenario controlado, no presentado como evidencia clínica real.

El indicador principal es que Recovery se convierta en la herramienta habitual para completar el flujo de captura, organización, registro y consulta. No se fijan tiempos arbitrarios: se observarán las fricciones reales.

**Señal de fracaso o necesidad de revisión:** seguir necesitando WhatsApp o Notas porque Recovery resulta lento, complejo o poco confiable. Un fallo de guardado o la confusión entre indicaciones y resultados exige revisar el flujo aunque las otras tareas se completen.

La validación técnica web responsive comprueba interacción, revisión visual y persistencia antes del uso real. Las tres sesiones evalúan utilidad y fricciones; las pruebas técnicas no sustituyen esa evaluación de adopción. No se exige un dispositivo físico concreto ni el VPS definitivo.

## 5. Exclusiones del MVP

- Gestión clínica multiusuario, cuentas de profesionales y acceso compartido con kinesiólogos.
- Auditoría clínica compleja, motor de fases y administración avanzada de múltiples programas simultáneos.
- Formularios estructurados de síntomas y escalas de dolor.
- Progresión automática en Recovery y recomendaciones clínicas autónomas.
- Sincronización Garmin Connect.
- Servicio propio de transcripción de voz; inicialmente puede usarse dictado nativo.
- Ampliación del AI Coach para rehabilitación.
- Dashboards y análisis avanzados.
- Infraestructura offline avanzada para Recovery.
- Desarrollo de apps nativas y distribución en tiendas para esta entrega; se conservan las capacidades existentes del proyecto base.
- Implementar la modernización dentro del alcance funcional Recovery: ahora corresponde a una entrega previa de plataforma con aceptación independiente. No añade funciones clínicas al MVP.

## 6. Riesgos y decisiones abiertas

### Revisión final de coherencia

Las tres decisiones funcionales pendientes quedaron confirmadas: guardado explícito y continuación, contexto histórico original y un único proceso activo con conservación de finalizados. No se identifican contradicciones que bloqueen el PRD.

- Guardado online y continuación son compatibles: continuar usa avances guardados, no una promesa de sincronización offline.
- Correcciones trazables y contexto histórico son compatibles: corregir una indicación no reescribe automáticamente sesiones anteriores.
- Historial cronológico e hitos no implican dashboard avanzado ni motor de fases.
- Un proceso activo no implica eliminar procesos finalizados ni limitar el dominio exclusivamente al LCA.
- Validar la web responsive localmente no implica desplegar ya el VPS; publicación y autenticación conservan sus requisitos de HTTPS y origen.

Los detalles de interacción y diseño técnico restantes deben tratarse al especificar y validar la solución; no justifican prolongar el discovery.

### Validación técnica posterior, no requisitos inventados

- Evitar pérdidas y duplicados cuando una solicitud se guarda en servidor pero se pierde la respuesta. Resolver en el diseño sin exigir una cola offline.
- Examinar el acoplamiento entre persistencia, sincronización y registrador de Training antes de reutilizarlos para Recovery.
- Revisar que notas y datos de Recovery no se incorporen inadvertidamente al coach, exportaciones compartidas o superficies de acceso no previstas. Conservar el coach actual no significa autorizar nuevos datos en sus payloads.
- Verificar el recorrido web completo con la matriz acordada de Playwright CLI; preparar cobertura dedicada de autenticación y Recovery antes de las tres sesiones reales.
- Verificar advertencias de cambios sin guardar en los flujos de navegación y las limitaciones de los navegadores admitidos. No prometer recuperación de contenido no guardado tras cierre forzado, recarga o reinicio.
- Planificar respaldo y restauración antes de guardar información real relevante; no confundir historial sencillo con cifrado o garantías clínicas.
- Referencias de kinesiología aún no aportadas; aclarar la mención previa a Mapbox si sigue siendo pertinente. No bloquean por sí solas el recorte actual.

## 7. Roadmap posterior — OpenGym Evolution

Orden vigente de implementación: **plataforma Python/FastAPI/PostgreSQL completada y aceptada → Recovery → Garmin Connect → ampliaciones de IA**. La plataforma tiene aceptación técnica propia; las tres sesiones reales validan Recovery después de entregar su recorrido completo. Sin fechas comprometidas; acceso remoto, voz y análisis se concretarán cuando corresponda, preservando validación local antes del VPS definitivo.

| Iniciativa | Intención y límites |
| --- | --- |
| Acceso remoto seguro | VPS, dominio HTTPS y experiencia web responsive; preservar acceso a datos y planificar la transición de passkeys. |
| Garmin Connect | Explorar importación y sincronización de actividades y métricas; investigar autenticación, procedencia y duplicados. La exportación `.fit` existente no equivale a importación. |
| Voz | Evaluar transcripción propia si el dictado nativo no resuelve la captura. |
| AI Coach | Evaluar análisis con información de Training, Recovery y Garmin, con consentimiento, límites de datos y revisión humana. No autoriza tratamientos autónomos. |
| Plataforma Evolution — previa | Python/FastAPI/PostgreSQL confirmado; completar paridad, migración y operación antes de implementar Recovery. Herramientas auxiliares y gates en arquitectura; LangChain/LangGraph y pgvector no se anticipan. |
| Análisis y offline | Evaluar vistas avanzadas y soporte offline de Recovery según fricciones reales, no anticiparlas como requisitos. |

## 8. Referencias y evidencia técnica inicial

- `GLOSSARY.md`: términos de dominio acordados.
- `docs/SELF_HOSTING.md`: ya documenta acceso web HTTPS, passkeys y pantalla de inicio de iPhone. No hay evidencia de que el acceso remoto requiera sustituir la autenticación. La elección de hostname afecta las passkeys existentes.
- `frontend/src/store/useStore.js`: persistencia local y sincronización existentes; mantener pantallas no basta para preservar comportamiento.
- `docs/AI_COACH.md`: consentimiento, selección explícita de datos enviados, validación y aprobación de propuestas.
- `frontend/src/lib/fit-export.js`: exportación `.fit`, no sincronización entrante desde Garmin.
- Referencia AI Tutor: `C:/Users/nenri/OneDrive/Desktop/proyectos/pry-ai-evaluator/ai-tutor`. Revisados inicialmente `AGENTS.md`, `README.md`, `deploy/Dockerfile` y `deploy/docker-compose.local.yml`. Hay patrones de FastAPI, PostgreSQL/asyncpg, Alembic, pgvector, revisión humana y builds por capas; no se ha auditado toda su implementación ni verificado LangGraph.
- AI Tutor ha evolucionado a dominio dental. Reutilizar patrones apropiados, no trasladar automáticamente su modelo, autenticación ni topología de contenedores.

## 9. Entrega al PRD y arquitectura

Este documento es el insumo de discovery para `plan-create-prd`: problema, evidencia, usuario, hipótesis, MVP, criterios de validación, exclusiones y preguntas abiertas. No generar requisitos adicionales como hechos ni convertir preferencias de stack en requisitos de producto.

Handoff realizado: el PRD Recovery conserva las decisiones funcionales; el PRD Evolution y la arquitectura revisada concretan la nueva prioridad de plataforma previa. Distinguir evidencia aportada por el usuario de hipótesis aún no validadas; esta revisión conserva el dominio y el alcance web.

Los PRD describen intención, alcance y resultados; arquitectura desarrolla mecanismos y contratos. Python/FastAPI/PostgreSQL es una restricción estratégica del promotor y una dependencia de implementación de Recovery, sin demostrar su valor de producto. Las hipótesis de utilidad y las tres sesiones reales se conservan; no se confunden con pruebas de paridad o aceptación de plataforma.

Foundation Node completó su entrega sintética y fue archivada; su evidencia histórica no acredita el stack Python ni una migración real. El estado técnico vigente se consulta en [arquitectura §§12 y 14](../open-gym-evolution.architecture.md#12-gates-y-experimentos-antes-de-producción) y los trackers correspondientes. Esta revisión solo actualiza documentación y no inicia plataforma o Recovery ni valida sus gates.
