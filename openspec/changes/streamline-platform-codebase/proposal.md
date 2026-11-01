# Streamline Platform Architecture and Maintenance

## Why

El repositorio presenta fricciones de mantenimiento: dependencias hacia la composición HTTP, coordinación Training–Coach poco explícita, sincronización frontend dispersa y documentación que puede describir estados anteriores. Este cambio mejora localidad, verificación y navegación para personas y agentes, e incorpora retirada revisada de textos, pruebas de ejecución antiguas y comentarios sin finalidad vigente.

## What Changes

- **P0 — baseline propio:** reexplorar revisión, runtimes, contratos y consumidores actuales. Ejecutar después del port es una preferencia no vinculante: no hay dependencia de cierre, aceptación o retirada de otra OpenSpec.
- **P1 — backend:** separar metadata pura de compatibilidad de la composición HTTP y reconciliar la colaboración Training–Coach conservando autorización, transacción compartida y efectos posteriores al commit.
- **P1 — navegación y controles:** actualizar fuentes propietarias, reducir instrucciones duplicadas y comprobar dependencias arquitectónicas mediante tooling proporcional ya integrado en la verificación.
- **P2 — frontend:** profundizar coordinación de sincronización manteniendo una autoridad persistente; organizar Training, Identity, Coach, Media, Administration y Notifications en slices independientes, sin cambio de UX.
- **P2 — higiene editorial y evidencias:** inventariar, conservar, condensar o retirar material por finalidad y consumidores; eliminar solo evidencia propia sustituida, textos obsoletos y comentarios redundantes. Conservar invariantes, regresiones relevantes, directivas de herramientas, licencias y material protegido todavía necesario.
- Incluir históricos protegidos solo mediante retirada revisada caso por caso, tras demostrar que no quedan consumidores ni obligaciones de aceptación y preservar lo necesario. Ninguna eliminación se ejecuta al preparar esta propuesta.
- **Cierre obligatorio — etapa 9:** reconciliar documentación con el árbol final, verificar comandos documentados en checkout limpio aislado y bloquear aceptación documental si quedan contradicciones o referencias activas a artefactos retirados.
- Distinguir JSON de ejecución, fixtures independientes y contratos transitorios: no eliminar por extensión/tamaño; preservar consumidores activos y exigir prueba independiente solo para la eliminación concreta que se revise.
- Dividir las seis capacidades en recorridos verificables, conservando IDs existentes y añadiendo trazabilidad y comprobaciones por tarea. La limpieza editorial no requiere un nuevo subsistema.
- **P1 — entrega Docker, etapa 10 aditiva:** ordenar recetas de verificación transversales y diagnóstico bajo deploy, mantener Dockerfiles de producto junto a su propietario y preservar contextos/targets/aislamiento. Auditar pins, caché, secretos, overlays, rutas, volúmenes y comandos a partir de fuentes Docker oficiales; AI Tutor es referencia comparativa, no plantilla normativa. Ejecutar esta etapa antes de aceptación técnica y de la etapa 9 documental, que sigue siendo la final.

## Capabilities

### New Capabilities

- `post-port-maintainability`: precondiciones de ejecución, colaboración modular comprobable, sincronización localizada y navegación verificable para agentes.
- `repository-evidence-hygiene`: mantenimiento editorial y retirada acotada de evidencias y comentarios, con preservación de garantías y artefactos ajenos.
- `container-delivery-organization`: organización por propietario de builds y Compose, reproducibilidad, higiene de contexto y preservación comprobada de los contratos operativos al mover recetas.

### Modified Capabilities

Ninguna. Se preservan los contratos funcionales y operativos vigentes. El corte operativo y la retirada del runtime Node quedan fuera de alcance y no son condiciones para ejecutar esta propuesta.

## Impact

Afecta potencialmente a composición/backend, coordinación Training–Coach, store y seis capacidades frontend, instrucciones de agentes, documentación propietaria, verificadores y artefactos de ejecución propios ya sustituidos. Las rutas actuales citadas en el diseño son evidencia de exploración, no ubicaciones obligatorias futuras.

No introduce endpoints, DDL, motores de workflow, microservicios, cambio general a TypeScript, nuevas capacidades IA ni una reorganización global `apps/packages`. No opera datos, credenciales, respaldos o instancias reales, ni publica, despliega, hace commit/push o modifica históricos Git. La propuesta no autoriza implementación.

## Planning readiness

Implementation Ready como especificación independiente. El [plan concreto de verificación y exportaciones](verification-plan.md) forma parte del diseño y fija casos/comandos actuales e interfaces de destino. Docker/Buildx es una restricción de ejecución por slice, no un bloqueo de planificación ni una dependencia de otra OpenSpec. No se implementó código ni se acreditaron pruebas containerizadas.
