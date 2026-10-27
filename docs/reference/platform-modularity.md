---
type: Architecture
title: Plataforma — módulos y vertical slices
description: Organización objetivo de contratos, lógica, persistencia y componentes conservando el frontend actual.
---
# Plataforma — módulos y vertical slices

## Decisión y alcance

Propuesta incorporada por solicitud del promotor: construir el backend Python como
un monolito modular por funcionalidad y orientar las intervenciones del frontend con
la misma propiedad funcional. Complementa la [arquitectura](../open-gym-evolution.architecture.md)
y concreta EV-09 del [PRD Evolution](../open-gym-evolution.prd.md). Es diseño objetivo,
no estructura implementada ni autorización de ejecución. El runtime sigue siendo
Node/JSON; Foundation, port y corte conservan sus límites y gates.

Un módulo concentra una capacidad y expone una interfaz pequeña. Un vertical slice
es un caso de uso verificable que atraviesa las piezas necesarias de ese módulo,
desde el contrato de entrada hasta el resultado observable y su persistencia. No
equivale a una carpeta, una tabla, un endpoint aislado ni un microservicio. Los
incrementos de infraestructura de Foundation preparan estos slices; no acreditan
por sí solos funcionalidad portada.

## Referencia AI Tutor y adaptación

La [evidencia histórica](../research/evolution-architecture-evidence.md#23-ai-tutor-como-referencia)
conserva su revisión original. Para esta propuesta se leyeron además los siguientes
archivos del checkout local de AI Tutor, sin ejecutar su aplicación ni atribuirles
una nueva revisión Git verificada:

| Fuente relativa a AI Tutor | Patrón adoptado y adaptación |
| --- | --- |
| `AGENTS.md`, `.claude/references/vertical-slice-architecture.md` | Propiedad por funcionalidad, infraestructura pequeña y dependencias explícitas. La guía contiene ejemplos, no requisitos de OpenGym. |
| `app/backend/routes/patients.py` | Pydantic para entradas/salidas y autorización explícita. OpenGym coloca los esquemas junto a su módulo y preserva sus contratos heredados. |
| `app/backend/evolution_exports/service.py`, `app/backend/db/postgres.py` | Operaciones de aplicación y transacciones con pool. Adaptar dependencias; evitar estado global entre factories. |
| `docs/design/frontend-architecture.md`, contrato frontend de `AGENTS.md` | Pantalla → componentes de dominio → patrones → primitivas/tokens; hooks y clientes poseen el acceso a datos. Reutilizar componentes y estilos OpenGym. |

AI Tutor combina carpetas funcionales con `routes/` y `db/` compartidos. Aquí se
elige mayor localidad: router, esquemas, operaciones y consultas junto al módulo.
No se copian dominio clínico, OAuth/JWT, ORM de ejemplos, migraciones al arrancar,
Bun, bibliotecas de UI o topología de despliegue.

## Backend: propiedad y colocación

Árbol objetivo; crear cada archivo únicamente cuando el caso de uso lo necesite:

```text
backend/
  src/opengym_platform/
    app.py                    # factory y composición de routers/lifespan
    core/                     # configuración, pool, transacciones, diagnóstico
    health/                   # contratos y probes internos Foundation
    identity/
    training/
      public.py               # interfaz para otros módulos, si hay consumidores
      router.py               # adaptación HTTP y dependencias de acceso
      schemas.py              # contratos Pydantic de entrada/salida
      service.py              # operaciones, autorización y transacción
      domain.py               # reglas puras cuando existan
      repository.py           # SQL parametrizado del módulo
    media/
    administration/
    notifications/
    coach/
    audit/                    # eventos duraderos, distinto de telemetría
  alembic/                    # un único historial de esquema
  tests/
    training/                 # pruebas por operación y contrato
    integration/              # recorridos entre módulos y PostgreSQL real
```

El patrón ilustrado con Training aplica a los otros módulos, sin imponer archivos
vacíos, clases de servicio, repositorios genéricos ni interfaces de paso. Los tests
de un módulo viven bajo `backend/tests/<module>/`; los casos Node de referencia se
conservan en el harness de caracterización. Foundation crea solo `core/`, `health/`
y las piezas operativas necesarias; no crea módulos de negocio como scaffolding.

| Módulo | Propiedad | Colaboraciones permitidas |
| --- | --- | --- |
| `core` | Configuración validada, conexiones/transacciones, límites y diagnóstico seguro | No importa módulos funcionales ni decide reglas de entrenamiento. |
| `health` | Liveness/readiness internos y revisión compatible | Usa infraestructura; no consulta datos de usuario. |
| `audit` | Registro y consulta autorizada de eventos duraderos | Usa infraestructura; recibe identificadores/contexto, sin importar funcionalidades. |
| `identity` | Identidad, credenciales, sesiones, revocación, roles y acceso | Usa `core` y la interfaz de audit; no importa Training para borrar datos. |
| `training` | Documento compatible, revisiones/linaje, stamps, conflictos y lectura restringida | Usa identidad para el actor autorizado y audit cuando corresponda; no depende de coach, notificaciones ni medios. |
| `media` | Bytes, ownership, referencias, cuotas y GC seguro | Usa identidad y lectura pública de referencias Training; un fallo no equivale a referencias vacías. |
| `notifications` | Suscripciones, recordatorios y adaptador push | Usa identidad y consultas públicas Training; secretos VAPID conservan su contrato externo. |
| `coach` | Configuración, consentimiento, operaciones/jobs y adaptadores HTTP actuales; SDK/CLI no disponibles por Q6 | Usa interfaces autorizadas de identidad/Training y medios si el contrato lo requiere; no lee sus tablas ni Recovery. |
| `administration` | Casos de uso de administración y coordinación de operaciones entre módulos | Invoca interfaces públicas de identidad, Training, medios y audit; no toma propiedad de sus repositorios. |

Catálogo y sus medios siguen empaquetados en `web`; no requieren un módulo Python
si no hay comportamiento servidor que lo justifique. Import/export Training sigue
en el cliente y debe probarse contra el nuevo contrato. MCP se ha retirado del fork; no se entrega adaptador ni credencial MCP. Recovery se añade solo
después de aceptar plataforma, con propiedad separada de Training.

Reglas de dependencia:

- `app.py` compone módulos; los módulos no importan la aplicación.
- Router adapta HTTP; service coordina autorización y operación; repository posee
  SQL; domain contiene reglas puras sin FastAPI, filesystem o acceso a DB. Las
  dependencias se suministran explícitamente, sin un localizador global.
- El service determina el alcance transaccional y pasa el mismo handle a las
  consultas relacionadas. Repository no abre otro commit por su cuenta. `core`
  conserva las garantías de cancelación, contexto local y resultado incierto.
- Una colaboración entre módulos usa su interfaz pública con permisos explícitos,
  no sus repositorios, SQL, tablas o estado interno. Las dependencias deben ser
  acíclicas; administración coordina, los módulos propietarios ejecutan. Los casos
  multioperación declaran atomicidad o recuperación de fallos parciales.
- Cada tabla/consulta tiene propietario. Un único historial Alembic puede cambiar
  varias tablas con revisión de sus propietarios; no hay un migrador por slice.

### Transacción entre operaciones de módulos

La operación iniciadora abre la transacción en `core` y es la única que confirma o
revierte. Las operaciones públicas participantes reciben explícitamente ese handle
y el actor autorizado; comprueban permisos y compatibilidad del contexto, usan la
misma conexión y no adquieren otro pool, cambian de propietario ni confirman por
su cuenta. La entrada HTTP de un módulo puede abrir su propia transacción cuando
no participa en otra; separar esa entrada de la operación participante para evitar
commits anidados. No exponer repositorios privados ni un framework genérico de
unidad de trabajo.

Foundation demuestra la primitiva con dos colaboradores sintéticos: ambos escriben
en una única transacción, falla el segundo y ninguna escritura persiste. Probar
también éxito conjunto y reuso limpio de conexión. No crea servicios de negocio.
En el port, cada caso intermodular declara iniciador, participantes, permisos,
resultado y eventos audit. Probar fallo del segundo participante y revocación
concurrente donde corresponda. El permiso de administración no permite introducir
un owner arbitrario: el caso debe definir su autorización y contexto explícitos.

Filesystem, push y proveedores externos no participan del commit PostgreSQL.
Ejecutarlos tras la decisión duradera apropiada y definir por caso el registro de
trabajo pendiente, reintento seguro o compensación y su recuperación. No confirmar
borrados externos antes del commit que los autoriza ni reintentar a ciegas un commit
incierto. Conservar la política audit de [seguridad](platform-security.md); no
prometer atomicidad entre DB y efectos externos ni introducir colas por anticipación.

## Contratos y validación

`schemas.py` posee los modelos Pydantic de request/response, límites y decisiones
de serialización del módulo. Las reglas de negocio y permisos pertenecen a la
operación; constraints, transacciones y RLS respaldan integridad en PostgreSQL.
Ninguno sustituye al otro. Los modelos HTTP no se convierten automáticamente en
modelos de persistencia ni en nuevas reglas de entrenamiento.

Durante la transición, `api/openapi.yaml` y los casos independientes de la matriz
son la referencia contrastada con Node. Cada ruta portada declara modelos y sus
respuestas/errores, incluidos cookies, headers y coerciones relevantes. La salida
OpenAPI de FastAPI se contrasta con esa referencia; no se mantienen dos contratos
editables discordantes. La autoridad final seleccionada es `backend/openapi.yaml`,
trasladada desde `api/openapi.yaml` durante el port, sin dos copias editables.
Pydantic implementa sus contratos; la generación FastAPI se contrasta, no introduce
por defecto nuevas respuestas 422, coerciones o endpoints públicos de documentación.
Actualizar el generador `scripts/build-api-docs.mjs`, website, checks CI y cobertura
de rutas Python antes de retirar el YAML legacy; `--check` sigue siendo la interfaz
de verificación del generador. El traslado todavía no está implementado.

No activar `strict` o rechazo de campos extra globalmente si cambia compatibilidad.
Registrar y probar ausente/null, números, fechas, aliases y campos Training antes
de endurecer validación. Cualquier incompatibilidad deliberada requiere alcance y
aceptación propios. Los clientes frontend consumen contratos específicos sobre el
transporte existente; no necesitan conversión general a TypeScript ni codegen.

## Frontend: componentes por funcionalidad, implementación preservada

Mantener React/Vite/Zustand, rutas, UX, estilos, PWA, locales y shells existentes.
Mapa objetivo para un área intervenida, sin traslado masivo de archivos:

```text
frontend/src/
  views/                      # ensamblaje de rutas/pantallas actuales
  features/<area>/
    components/               # UI específica de esa funcionalidad
    hooks/                    # interacción y coordinación con store/cliente
    api.js                    # operaciones y validación de respuestas del área
    contracts.js              # validadores/mapeos solo si son necesarios
  components/                 # primitivas y patrones compartidos existentes
  lib/                        # transporte, plataforma y helpers puros actuales
  store/                      # estado persistente y estado efímero existentes
```

| Responsabilidad | Ubicación y regla |
| --- | --- |
| Pantalla | `views/` compone componentes/hooks del área; no duplica reglas de dominio ni hace fetch inline. |
| Componente funcional | `features/<area>/components/` usa hooks del área y componentes compartidos; no importa internos de otra funcionalidad. |
| Hook | Coordina interacción y operaciones del área mediante store y cliente; no crea una segunda autoridad de datos locales. |
| Cliente funcional | `features/<area>/api.js` reutiliza `lib/api.js` para origen/subpath, auth, timeouts y errores; valida el contrato observable sin duplicar transporte. |
| Regla de entrenamiento o lectura de sesión | Helper puro en `lib/`, con test junto al código según AGENTS; no se desplaza por estética. |
| Patrón/primitiva compartida | `components/`, sin depender de módulos funcionales; extraer por intención repetida y reutilizar estilos/tokens existentes. |
| Estado | `useStore` sigue siendo la autoridad local persistente y `useUI` la efímera. Extraer responsabilidades solo con pruebas de propietario, pendientes, sesión activa, tabs y sync. |

Las capas de UI dependen hacia abajo: pantalla → dominio → patrón → primitiva →
tokens. Hooks/clientes conectan dominio con transporte/store; las primitivas no
importan store, clientes ni reglas de producto. Los tests de componentes/hooks se
colocan junto al código como en el frontend actual. La correspondencia funcional
backend/frontend no exige el mismo árbol ni un componente por endpoint.

Mapa inicial de recorridos, con rutas relativas al repositorio. Identifica puntos
de entrada existentes; el inventario de caracterización debe completar por caso
los consumidores y pruebas exactos, sin presentar esta tabla como cobertura ejecutada:

| Caso/área | Participantes frontend actuales | Destino backend y resultado a demostrar |
| --- | --- | --- |
| Acceso y sesión | `views/Login.jsx`, `components/Passkeys.jsx`, `components/PasswordAuth.jsx`, `lib/api.js`, `lib/remote.js`, `store/useStore.js` | `identity`: acceso válido, revocación y rechazo; conservar passkeys, cookies/bearer y propietario local. |
| Training y sync | `views/Workout.jsx`, `views/History.jsx`, `components/ServerSync.jsx`, `store/useStore.js`, helpers `lib/sync-*` | `training`: lectura/guardado, conflictos, historial, pendientes y sesión activa preservados. |
| Medios | `views/ProgressPhotos.jsx`, `components/CustomMediaField.jsx`, helpers `lib/media-*` y `lib/backup-media.js` | `media` con lectura pública Training: bytes/ownership y referencias seguros, también ante fallo de DB. |
| Administración | `views/Admin.jsx`, store y transporte existentes | `administration` coordina interfaces propietarias; demostrar acciones autorizadas/denegadas sin acceso directo a tablas ajenas. |
| Notificaciones | `views/Settings.jsx`, `lib/mobile.js`, `public/sw.js` | `notifications`: suscripción y recordatorios compatibles, aislamiento por dispositivo; diferenciar fixture de entrega push real. |
| Coach actual | `views/CoachChat.jsx`, `views/CoachSetup.jsx`, `views/AdminCoach.jsx`, `lib/coach-api.js`, `lib/coach.js` | `coach`: local/HTTP, consentimiento, propuesta, cancelación/fallo; SDK/CLI no disponibles visiblemente, sin fallback/remapeo ni nuevas capacidades IA. Véase [Q6 del port](../../openspec/changes/port-compatible-platform/design.md#11-q6-migración-segura-antes-de-evolución-agéntica). |
| Catálogo e import/export | `views/Library.jsx`, `views/Settings.jsx`, helpers de catálogo/importación/backup | Assets siguen en web y formatos en cliente; `training`/`media` reciben lo que corresponda con semántica preservada. |
| Auditoría y diagnóstico | Superficie administrativa autorizada cuando corresponda; sin nuevo panel obligatorio | `audit` posee eventos duraderos; `core` diagnóstico. Probar acceso/retención y privacidad según sus contratos, sin confundir logs con audit. |

El port conserva inicialmente las ubicaciones actuales. Cada cambio registra el
mapa de archivos que implementa el recorrido y cualquier desviación justificada.
Se agrupa un área solo al modificarla y verificarla; no se añaden wrappers vacíos
ni se exige reorganizar todo el frontend para aceptar plataforma.

### Biblioteca JavaScript compartida y retirada de api/

Destino del código neutral que hoy necesita el coach local del frontend:
`shared/coach-core/`, separado del backend HTTP Python. Es una biblioteca JavaScript,
no una API Node de negocio. En el port se trasladará una sola fuente canónica JS,
sin mantener copias editables bajo `api/coach/core` y `shared/`; durante Foundation
se conservan las rutas actuales y su referencia Node intactas.

El inventario debe seguir imports y cargas dinámicas desde `frontend/src/lib/coach-local.js`,
`frontend/src/views/CoachSetup.jsx`, tests de paridad y consumidores Node que
correspondan. Incluir `frontend/vite.config.js`, `web/Dockerfile`, scripts
`build-coach-assets.mjs`/`build-coach-library.mjs`, prompts, catálogo y artefactos
generados: el directorio fuente no es el único consumidor. Elegir un propietario
canónico para cada input generado y actualizar generador, destino y controles
`--check` sin duplicar fuentes. La implementación Python conserva sus propias
reglas tipadas y demuestra equivalencia mediante vectores independientes comunes;
no se promete compartir ejecución de código Python con el navegador.

Aceptación del port: build web y bundle móvil pertinente sin imports del árbol API
retirado; tests de coach local/consentimiento/proveedores/validación y paridad con
Python; artefactos generados vigentes. No requiere publicar una app nativa nueva.
Antes de borrar `api/`, la revisión G3 comprueba imports, scripts, tests, builds y
documentación; conserva únicamente referencias históricas identificadas. La imagen
web consume la biblioteca neutral, sin necesitar un servidor Node en ejecución.

## PostgreSQL y composición Docker

El [esquema SQL aprobado](platform-schema.md) posee tablas/columnas, claves,
restricciones e índices por consulta; [operación local](platform-operations.md)
posee puertos/redes, almacenamiento y recuperación. Cada módulo conserva la
propiedad de sus tablas y repositorios; compartir esquema no habilita acceso
directo desde otro módulo. Administración solo posee el registro mínimo de
limpieza externa que coordina tras borrado SQL, no los archivos de medios.

Conservar SQL explícito/asyncpg, Training JSONB compatible, IDs heredados y una
autoridad por dominio. Separar Alembic de importación de datos; probar vacío,
revisión anterior, concurrencia, fallo y recuperación con roles reales. Los medios,
secretos y pendientes de clientes mantienen sus contratos fuera de PostgreSQL.

Destino operativo: servicios permanentes `web`, `api`, `db`, más ejecución puntual
de migraciones con rol distinto. El proceso migrador termina antes de habilitar
tráfico compatible; la API no migra al arrancar. Compose puede expresar DB healthy
y migrador completado, pero se deben probar también caídas/reconexión posteriores.
Readiness no demuestra auth, paridad ni recuperación.

Primera operación acordada: instancia personal local Linux/amd64, web loopback:8080,
API:3000 y DB:5432 privadas, una API/un worker. Red aplicación con egress autorizado
y red DB internal; overlays/datos dev y operación separados. Ver contrato operativo
para acceso LAN/remoto posterior y tratamiento de clientes existentes.

Separar configuración de desarrollo de operación mediante overrides explícitos,
manteniendo una definición común cuando corresponda. La imagen runtime Python
excluye tests/harness Node y dependencias de desarrollo; los targets de pruebas
usan los mismos pins/lock. No publicar DB ni montar socket Docker; ejecutar con
privilegios mínimos y almacenamiento escribible explícito. No añadir servicios por
módulo, Redis, colas ni Kubernetes por la organización de carpetas. Los archivos
Compose normales solo cambian en su entrega autorizada; Foundation sigue aislada.

### Construcción y caché verificables

En Foundation, optimizar los Dockerfiles de ensayo cuando se ejecuten las tareas
pendientes de CI/build; no reinterpretar los resultados anteriores como prueba de
caché. Instalar manifiestos/lockfiles antes de copiar fuentes, separar cambios de
metadatos de release de instalaciones costosas y conservar contextos con allowlists
o exclusiones explícitas por imagen. El build web debe incluir la biblioteca neutral
y assets necesarios, excluyendo directorios móviles/cachés cuando no sean inputs.

Usar cache mounts BuildKit para descargas uv/pnpm con UID/GID compatibles con el
usuario de build; no incluir cachés en capas finales ni secretos en ARG/ENV de build.
Conservar `uv sync --locked`, `pnpm install --frozen-lockfile` y pins; la caché no sustituye verificaciones.
Reutilizar etapas de dependencias cuando corresponda, sin acoplar reinstalaciones
de proyectos independientes por el orden de sus COPY. No es obligatorio fragmentar
el harness si no mejora el recorrido medido.

La CI debe importar/exportar caché de capas mediante el mecanismo existente de
Buildx, con scopes separados por imagen/target. Una caché remota de capas no implica
persistencia remota de cache mounts: registrar qué se reutilizó realmente y no
añadir infraestructura de caché adicional sin necesidad. Mantener recursos de
ejecución aislados por proyecto; tags aleatorios no justifican eliminar las guardas
de ownership para compartir caché.

| Prueba de build | Evidencia exigida |
| --- | --- |
| Frío, sin caché importada ni montada | Instalación bloqueada, build y smoke correctos; no depende del estado previo del builder. |
| Repetido sin cambios | Logs BuildKit muestran reutilización de la etapa de dependencias; distinguir capas de descargas. |
| Cambio solo de fuente | Reconstruye la aplicación sin reinstalar dependencias cuyos manifiestos no cambiaron. |
| Cambio de lockfile/manifiesto coherente | Reconstruye la instalación afectada sin modificar el lock durante build; un lock incoherente falla. |
| Cambio solo de tests o metadata | No invalida dependencias sin causa; en operación, los tests no entran en runtime y metadata no fuerza su instalación. |

Registrar revisión, plataforma, comando, target, estado de caché, logs y duración
observada; no inventar umbrales de velocidad ni exigir digest idéntico cuando hay
metadata variable. Pruebas sobre fixtures/checkout y builder desechables propios,
sin editar locks de trabajo ni hacer prune de cachés compartidas. Foundation cubre
sus imágenes de ensayo; operación repite la matriz sobre imágenes entregables.

### Targets e imagen entregable

El port especificará targets `dev` y `test` para la aplicación funcional sintética,
con la misma revisión/lock y dependencias comunes; no convertirá el runner Foundation
en servidor de desarrollo. Operación completará el Dockerfile multistage y verificará
los targets entregables `test`, `runtime` y `migrate`. Runtime contiene solo dependencias productivas
resueltas desde el mismo lock, fuentes/recursos necesarios y el servidor; excluye
tests, harness Node y herramientas de desarrollo, y arranca sin instalar paquetes.
El migrador usa el mismo código/revisión/lock y su rol separado; backup/restore usa
un target operativo puntual con herramientas PostgreSQL compatibles, sin añadirlas
obligatoriamente al servidor. Los nombres son contratos objetivo, no targets hoy
disponibles; los Dockerfiles Foundation siguen siendo imágenes de ensayo.

Verificar inventario final, usuario no root, permisos y rutas escribibles mínimas,
ausencia de secretos/datos, health/readiness, arranque/parada y recuperación de
dependencias. Build y pruebas sobre la misma revisión; identificar el digest probado
para operación. Pins/digests requieren actualización deliberada y revalidación; no
atribuir reproducibilidad a tags flotantes o a upgrades de paquetes no fijados.

### Matriz de ambientes y comandos objetivo

Los siguientes nombres Compose operativos son propuestas para la futura entrega;
esta revisión no crea archivos ni sustituye `docker-compose.yml`. Seleccionarlos
siempre con `-f`, sin combinar automáticamente la instancia legacy con Foundation.

| Ambiente | Entrada y configuración | Montajes, red y datos | Alcance de soporte |
| --- | --- | --- | --- |
| Verificación actual | CLI `scripts/platform.mjs verify <suite>`, `deploy/docker-compose.test.yml`, env vacío y parámetros sintéticos allowlisted | Proyecto/red/volumen desechables propios; sin puertos ni mounts personales; pruebas en contenedor | Evidencia Linux/amd64; host Node y Docker según el contrato de la CLI. |
| Desarrollo del port | Base objetivo `deploy/docker-compose.yml` + `deploy/docker-compose.dev.yml`, configuración sintética explícita | Sources del área en recarga y biblioteca shared con rutas compatibles; dependencias/cachés Linux separadas del host; volumen dev exclusivo; un origen web estable, sin exponer DB por defecto | Conservar React/Vite y semántica passkeys/origen; nunca usar credenciales ni volumen de operación. |
| CI | Foundation usa su CLI; el port valida además los targets desde checkout limpio con configuración sintética | Sin binds de dependencias host ni datos personales; cachés BuildKit separadas de volúmenes DB; cleanup propio | Linux/amd64 obligatorio inicialmente; no acreditar arm64 solo por emulación o una base multiarch. |
| Operación | Base objetivo `deploy/docker-compose.yml` + `deploy/docker-compose.prod.yml`, imágenes probadas por digest y configuración explícita de instancia | Sin recarga ni binds de fuentes/node_modules/.venv; DB privada, almacenamiento duradero y secretos protegidos; migrador puntual antes de tráfico | Proveedor/TLS/backup/restore y plataformas soportadas validados antes de corte; arm64 requiere prueba y decisión expresa, sin retirar soporte previo silenciosamente. |

Comandos objetivo de inspección: `docker compose --project-directory . -f deploy/docker-compose.yml -f
deploy/docker-compose.dev.yml config` y equivalente con `deploy/docker-compose.prod.yml`.
Documentar en la entrega sus comandos de build/up/stop/migrate/backup/restore y
los archivos de configuración requeridos; para operación, migración controlada
con éxito antes de `up` compatible. La base debe ser segura sin overlay dev.
Inspeccionar cada combinación resuelta: puertos, mounts, variables, usuario,
targets y dependencias; probar overrides adversos para detectar mezcla de datos,
exposición DB y dependencias host. No imprimir secretos al conservar evidencia.

Definir orígenes y RP ID por ambiente, manteniendo un origen estable en desarrollo
y el contrato de clientes en operación. Variables públicas Vite se incorporan al
build; secretos solo al runtime/migrador apropiado. Un mismo lock no convierte
un entorno dev en operación. GO requiere comandos reproducibles y aceptación de
las plataformas reales; Foundation no demuestra proveedor, arm64 ni despliegue.

## Responsabilidad y aceptación por fase

| Punto | Foundation: evidencia sintética archivada | Port: entrega pendiente | Operación, corte y retirada: entrega pendiente |
| --- | --- | --- | --- |
| JavaScript compartido | Inventario de consumidores/generadores y destino propuesto; no mover fuentes Node | Trasladar biblioteca neutral, actualizar imports/builds y demostrar coach local/paridad | G3: ningún build/import activo depende de API retirada. EV-01/05/09. |
| Caché | Implementar y medir matriz fría/caliente/fuente/lock en imágenes de ensayo y CI | Mantener independencia entre módulos y builds al portar | Repetir matriz sobre targets entregables; demostrar inventario y digest probado. EV-03/06. |
| Imagen final | Harness con tests/dev permitido; documentar targets futuros | Aplicación compatible probada sobre Python/PG, sin llamar producción al harness | Entregar/verificar test/runtime/migrate y tooling operativo puntual. EV-03/06, GO. |
| Ambientes | Verificar aislamiento sintético y documentar matriz/handoff | Implementar ambiente dev/CI explícito para recorridos del cliente actual | Implementar combinación operativa, plataformas y recuperación; GO/G0–G3. |
| Transacción intermodular | Probar handle compartido con colaboradores sintéticos y rollback completo | Operaciones públicas comparten transacción; probar permisos y efectos externos recuperables por caso | Verificar integridad/recuperación y audit tras corte; EV-01/02/04/09. |

Foundation está completada y archivada dentro de su alcance sintético; las columnas
de port y operación siguen pendientes, no son pruebas ejecutadas en esta edición.
Foundation no entrega targets de producción, biblioteca shared ni ambiente dev del
port. El OpenSpec de port/operación debe convertir sus columnas en requisitos,
escenarios y tareas trazables antes de ejecutar; no basta citar este mapa para cerrar
GP/GO/G3. No se amplían los gates ni se autoriza despliegue por editar documentación.

## Slice piloto y evidencia de aceptación

Primer slice funcional recomendado para el cambio posterior de port: **leer y
guardar Training compatible de un propietario**. Precede la identidad mínima
necesaria; un actor fixture de Foundation no demuestra WebAuthn ni sesiones.

Recorrido: pantalla/store actuales → transporte → router/schemas Training →
operación autorizada → repository con una transacción → PostgreSQL → respuesta
compatible → reconciliación del cliente. Incluir `GET /api/v1/data`, revisión y
`PUT /api/v1/data`, conflicto 409, primera escritura concurrente, stamps/linaje,
legacy permitido, rechazo de otro propietario y caída DB sin fallback a archivos.
Verificar cliente con cambios pendientes, sesión activa y respuesta perdida. No
cambiar reglas de progresión, normalizar todo Training ni añadir Recovery.

Cada slice posterior debe identificar caso, propietario, archivos backend/frontend,
contrato público, dependencias, tablas/almacenes, migración si existe y comportamiento
ante fallos. Aceptación: EV → escenario OpenSpec → prueba positiva/negativa →
evidencia con revisión, entorno, resultado y límite. Añadir integración PostgreSQL
real y recorrido frontend cuando corresponda. Revisión de imports comprueba
dirección y ausencia de ciclos; pasar checks de docs no acredita esa revisión.

Foundation solo acredita la estructura de infraestructura/salud que entregue y el
mapa de handoff de los módulos futuros. EV-09 requiere posteriormente el slice
piloto y revisión de los módulos efectivamente portados en GP/GO/G3; un árbol de
directorios o un healthcheck no lo satisface. No se agrega un gate nuevo.

Referencias técnicas: [composición de routers FastAPI](https://fastapi.tiangolo.com/tutorial/bigger-applications/),
[modo estricto Pydantic](https://docs.pydantic.dev/latest/concepts/strict_mode/) y
[dependencias de Compose](https://docs.docker.com/compose/how-tos/startup-order/).
Son soporte de mecanismos; no acreditan ejecución ni imponen una plantilla completa.
