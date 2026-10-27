## Context

Diseño confirmado mediante rondas Q1–Q20 y consolidado posterior. Se autoriza
autoría documental y los diagnósticos sintéticos acotados de Q4/Q5, no implementación;
el runtime actual continúa Node/JSON. Foundation Python está
completada y archivada; su harness, fixtures y evidencia no son producto operativo.
La revisión de alcance conserva Q2 y cleanup verificado. Revisa Q1: continuidad
con evidencia o vía nueva local explícitamente autorizada, sin reactivar credenciales
dudosas. Autorización/entrega privada se especifican antes del slice. Se acepta pausa
de backup y logging estándar, no leases/socket ni subsistema OpenTelemetry. Estas decisiones no autorizan implementación.

El contrato físico vive en [platform-schema](../../../docs/reference/platform-schema.md),
roles/auth/audit en [seguridad](../../../docs/reference/platform-security.md),
topología/recuperación en [operación](../../../docs/reference/platform-operations.md)
y recorridos/módulos en [modularidad](../../../docs/reference/platform-modularity.md).
Evitar copiar una segunda lista editable de columnas aquí.

## Goals / Non-Goals

**Goals:** preservar capacidades y datos; implementar esquema/roles aprobados;
frontend actual sobre Python; operación local recuperable;
autoridad única y retirada verificada. Demostrar comportamiento, no solo carpetas.

**Non-Goals:** implementar durante esta revisión, Recovery, nuevas capacidades IA,
normalización general Training, microservicios, colas generales, producción Node/PG
intermedia, publicación remota o aceptación arm64 no probada. Q6 excluye además
Claude Agent SDK/Codex CLI, su launcher/perfil seccomp y LangChain/LangGraph de
la primera entrega Python; el coach local y HTTP siguen incluidos (véase §11).

## Decisions

### HTTP v1 exclusivo de la plataforma Python

Todas las rutas HTTP Python, incluidas live/ready, usan `/api/v1`, sin alias ni
redirecciones desde URLs anteriores. Los contratos Node congelados conservan
sus URLs de origen; la equivalencia del port compara comportamiento bajo el
nuevo prefijo, no igualdad literal de URL. El cliente compartido selecciona
`VITE_API_PREFIX=/api/v1` al compilar para Python y conserva `/api` para Node.
Nginx bloquea las dos sondas internas. Esto no autoriza cutover ni acredita
capacidades pendientes. El contrato vigente vive en
[backend/README.md](../../../backend/README.md#http-api-v1).

### 1. Propiedad modular y orden de slices

Identidad y primitivas transaccionales antes del piloto leer/guardar Training;
después medios, administración/notificaciones, coach y formatos/builds cliente.
Cada slice declara entrada/salida/errores, actor/recurso, tablas/almacenes, operación
iniciadora/participantes y recorrido frontend. Service posee transacción; repository
SQL propio; domain puro. Colaboración pública con handle compartido, sin commits
internos ni import de repositorios ajenos. Python posee transporte, criptografía y
coordinación; SQL constraints, autorización privilegiada e invariantes concurrentes.
No duplicar reglas ni añadir funciones por simetría; firmas/grants/RLS se conservan.

### 2. Esquema físico e importación

DDL Alembic para las tablas del contrato físico, sin crear Recovery. IDs textuales
legacy, alias separado de nombre, reservas expirables bajo lock, no índice now().
Training JSONB canónico con revision/write_id GENERATED STORED y primera escritura
serializada por propietario. Coach separa actuales, propuesta y eventos; contadores
atómicos al encolar. Auditoría histórica/invitaciones sin cascadas destructivas.

Separar DDL e importador. Ensayar con fixtures sin inventar valores legacy,
comparando tipos, ausente/null y metadatos internos. Una discrepancia no representable
fielmente bloquea avance; no normalización silenciosa ni reidentificación.

### 3. Acceso y efectos externos

Sesiones firmadas actuales, scrypt/WebAuthn compatibles, roles mínimos y owner
transaccional. Preauth mediante funciones limitadas con grants/políticas explícitos;
admin verifica facultad, no SET owner arbitrario.

Audit best effort se ejecuta fuera de la transacción de negocio que podría abortar;
fallo observable no cambia éxito confirmado. Eliminación confirma datos SQL y tarea
de limpieza externa; medios/secretos ejecutan después con reintento seguro y señal
de pendiente. Credencial coach personal ligada se desconecta, no se libera a otro
usuario por cascada. Resultados tardíos verifican owner/consentimiento/generación.

### 4. Operación y recuperación

web/api/db, loopback:8080/web:80/API:3000/PG:5432 privada, un worker Linux/amd64.
Red app con egress autorizado y DB internal. Overlays dev/ops y datos distintos;
targets test/runtime/migrate y herramientas puntuales, sin instalar al arrancar.
Un historial/lock Alembic y migrador previo al tráfico, no startup migration.

Captura con parada limpia de API/escritores por wrapper host con exclusión/journal;
PG sigue disponible. Sin leases ni socket de mantenimiento. Recuperar solo servicios
antes activos tras cese de captura y esquema compatible; interrupción exige
recuperación explícita. Cifrado/transferencia fuera de pausa. Backup cada 3 h,
arranque vencido/pre-migración, retención 30 días, disco independiente y clave
separada; restore mensual. RPO 6 h/RTO 24 h y pausa requieren medición, no prometen
PITR, off-host ni pérdida completa del equipo cubierta.

Q1 invalida sesiones y bloquea credenciales dudosas. Permite continuidad con evidencia
suficiente o nueva vía local autorizada para cuenta verificada, sin cambiar ID/rol,
resucitar credenciales ni bootstrap admin. Backup/login/audit best effort no prueban
vigencia. Especificar autorización y entrega privada antes de implementar 10.5;
sin salida completa probada no se acredita recuperación. Incluir revisión/verificación
en RTO; no crear ledger.
Diagnóstico privado con logging estándar, request_id, resultados/duraciones, salud,
pool y backup; logs 7 d/256 MiB. Seleccionar/fijar retención estándar antes de S9.
Sin OpenTelemetry, spans, sampling ni snapshots métricos.

### 5. Gates y autorización

Foundation archivada aporta la entrada sintética, no la aceptación operativa. GP/GO previos al corte,
G0 e inventario real antes de tocar datos. Corte con escritores detenidos e importación
equivalente; una autoridad. Antes de nuevas escrituras puede revertirse al origen
validado; después Q2 fija reparación hacia adelante de Python/PostgreSQL preservando
las nuevas escrituras. Exportación inversa a Node queda excluida salvo autorización
expresa. Ensayo fallido de preservación bloquea corte; distinguir reparación del
destino superviviente de pérdida del destino bajo RPO, sin prometer RPO cero.
Origen/release/config protegidos al menos 30 días tras corte aceptado y sin borrado automático. G3/GO
posteriores demuestran independencia del backend sustituido antes de Recovery.

### 6. Cleanup como checkpoint de entrega

Después del corte equivalente y antes de aceptación, inventariar rutas y consumidores:
retirar código de negocio sustituido, lectores/escritores/config/dependencias exclusivos
y scaffolding temporal; conservar o adaptar pruebas de comportamiento. Primero adaptar
consumidores de shared, generadores, web/mobile, CI y operación. No conservar una segunda
implementación desactivada por comodidad ni borrar `api/` por nombre sin ese inventario.

Conservar biblioteca JS neutral, catálogo, herramientas vigentes y evidencia Foundation
que aún sustente garantías. La retirada depende de consumidores y propósito, no del
lenguaje. Origen/release/config/secretos protegidos permanecen fuera de dependencias
activas durante su ventana; su eliminación exige permiso distinto. Limpiar únicamente
artefactos temporales propios tras conservar evidencia saneada necesaria; sin prune
global, datos cliente, perfiles ni informes permanentes duplicados. G3/GO se repiten
sobre el árbol limpio; un sentinel ajeno y material protegido deben sobrevivir al ensayo.

### 7. Preparación por slice y seams aprobados

El [plan ejecutable](execution-plan.md) conserva trazabilidad y checkpoints de port
funcional y operación local recuperable. S11 es handoff de corte/retirada reales a
cambio operativo separado; aquí solo ensayos sintéticos. Transferir obligaciones
antes de archive, sin acreditar G0/G2/G3 ni autorizar Recovery. Harness incremental
reutiliza ownership/ejecución Foundation sin duplicar cleanup ni anticipar browser. Los comandos futuros se entregan
con el runner y tooling del propio slice; no existen por escribirlos aquí. La
aprobación de planificación no es permiso de ejecución global.

**Q3 aprobada expresamente por el promotor:** las cinco fronteras siguientes cubren
la verificación prevista durante delivery; no pedir aprobación por cada test dentro
de ellas. Reconfirmar únicamente cambios materiales de frontera o garantías. Esta
aprobación no permite implementar, instalar runtimes, usar credenciales, llamar
proveedores ni ejecutar ensayos operativos. Dispositivos/autenticadores y servicios
externos reales necesitan su evidencia específica, no se acreditan por sustitutos.

| Frontera aprobada | Detecta | No demuestra |
| --- | --- | --- |
| Vectores independientes Node/Python | scrypt/NFKC, firma, serialización, stamps | HTTP, autenticador físico o RLS |
| HTTP Python + PG real restringido | actor → RLS, concurrencia, errores, pool y commits | Navegador/offline o SDK real |
| Frontend actual contra Python en navegador | pendientes, sesión activa, sync y respuesta perdida | Todos los dispositivos nativos |
| Adaptador SDK/CLI en contenedor aislado (diagnóstico Q4/Q5 concluido; fuera de delivery por Q6) | arranque, flags, privilegios/sandbox y fallo cerrado | Soporte entregado, cuenta/modelo real o adopción de la política candidata |
| Comandos operativos y checkout desechable | restore medido, cleanup propio y ausencia de dependencias | Datos/entorno reales ni permiso de corte |

Investigar WebAuthn y proveedores HTTP admitidos antes del port de negocio. Q6
resuelve SDK/CLI por aplazamiento explícito, no exige continuar su investigación.
Q4 permite instalaciones solo en imágenes diagnósticas desechables, no en el host
ni en producto; no permite llamadas a proveedores reales. Elegir detalles técnicos compatibles
no exige al promotor escoger bibliotecas. Pérdida de soporte, sandbox debilitado,
reautenticación excepcional, nuevo almacén de seguridad o cambios de recuperación
sí requieren decisión expresa. Los comandos y prerrequisitos de cada slice se concretan
antes de su readiness; comandos futuros se distinguen de los disponibles.

### 8. Autoridad OpenAPI y compatibilidad de transporte

Decisión técnica: conservar un contrato YAML editable y trasladarlo de
`api/openapi.yaml` a `backend/openapi.yaml` durante el port. No se crea ahora ese
archivo ni se mantienen dos fuentes editables. Frente a adoptar la generación de
FastAPI como autoridad, esta opción preserva las descripciones, errores, headers y
cookies del contrato existente y el generador estático sin introducir codegen.
Los modelos Pydantic implementan ese contrato; la salida automática de FastAPI es
una comprobación auxiliar, no otra especificación editable ni permiso para introducir
422, coerciones, defaults o endpoints `/docs`/`openapi.json` nuevos.

Consumidores verificados: `scripts/build-api-docs.mjs`, `website/README.md`,
`website/api.html`, `api/test/openapi-routes.test.js`, CI y comentarios frontend.
Antes de retirar el YAML anterior, actualizar ruta del generador/enlaces, conservar
`node scripts/build-api-docs.mjs --check` y sustituir el test ligado al registro de
handlers Node por cobertura de método/ruta/response del router Python. Omitir rutas
internas live/ready del contrato público; las fixtures HTTP siguen contrastando lo
que un cliente realmente recibe, no solo el esquema. El traslado y la regeneración
son tareas de delivery, no resultados de esta revisión.

### 9. Factibilidad: hechos inspeccionados y bloqueo de investigación

| Fuente de código o dependencia | Hecho verificado por inspección | Consecuencia y comprobación pendiente |
| --- | --- | --- |
| `api/server.js` (sesiones) y `api/password.js` | HMAC-SHA256 base64url sobre payload textual; versión legacy 0; scrypt serializado con NFKC | Python puede usar primitivas estándar; conservar selección cookie/bearer y probar vectores cruzados, sin JWT/bcrypt. No es paridad ejecutada. |
| `api/server.js` (ceremonias) y `api/passkeys-store.js` | Clave pública codificada base64url, ID/transports/contador conservados; `requireUserVerification: false` en verificaciones actuales | Seleccionada `webauthn` 3.0.1 tras ensayo Q4 de 30 vectores. Falta integración HTTP/challenges/SQL, revocación y autenticador físico; no usar re-registro como conversión silenciosa. |
| `api/node_modules/@anthropic-ai/claude-agent-sdk/package.json` y `sdk.d.ts` | SDK instalado 0.3.223, Node >=18; hook `spawnClaudeCodeProcess` y opciones LOCKDOWN declarados | Inspección histórica Q4; Q6 excluye este runtime y su auxiliar de la primera entrega. |
| `api/coach/adapters/spawn.js`, `claude.js` y `api/Dockerfile` | Launcher Linux requiere API root para bajar UID/GID a coach; falta de drop bloquea jobs | No copiarlo al runtime no-root; Q6 no implementa un sustituto en este port. |
| `api/coach/adapters/codex.js` y `api/Dockerfile` | Codex 0.160.0, bubblewrap, flags ephemeral/ignore-user-config y cache externa | Ensayo histórico Q4/Q5; Q6 excluye ejecución/cache activa de este proveedor sin relajar controles. |
| `core/database.py`, `migrate.py` y `backend/README.md` | Configuración sin TLS y bootstrap actuales están restringidos al harness Foundation | Entregar configuración dev/ops propia; no reutilizar variables sintéticas ni eliminar guardas para convertir el harness en producto. |

**Q4 aprobada y ejecutada como diagnóstico, no delivery:** contenedores Linux/amd64
desechables, dependencias instaladas solo en imagen de ensayo, scripts temporales
fuera del repositorio, fixtures ficticias, sin llamadas a modelos ni credenciales.
No se modificaron runtime, manifests ni lockfiles del producto. No se habilitaron
privileged, socket Docker, capacidades adicionales o sandbox desactivado.

#### Resultado de factibilidad WebAuthn

Seleccionar `webauthn==3.0.1` (py_webauthn, BSD-3-Clause) para el port. Su API verifica
registro/assertion, COSE, origen/RP y contadores sin implementar criptografía propia;
es más cercana al adaptador actual que `fido2` 2.2.1, alternativa de nivel inferior
instalada para inspección de metadata, no ensayada conductualmente. Fuentes de versión
y compatibilidad: PyPI oficial y código instalado en el contenedor diagnóstico.
`cryptography==50.0.2` coincide con Foundation; el resto de transitivas debe bloquearse
y añadirse al inventario de licencias durante delivery, no asumir el lock actualizado.
La superficie adicional se justifica por WebAuthn servidor, no por nuevas capacidades.

Python 3.14.9 ejecutó 30 vectores independientes también verificados por
`@simplewebauthn/server` en Node 22.23.2: para cada ES256/RS256/Ed25519, registro
`none`, assertion válida sin UV, contador cero, credencial sincronizada con backup,
replay, RP/origen/challenge incorrectos, firma alterada y presencia ausente.
Expectativas positivas/negativas escritas antes de ambos verificadores. Resultado
PASS 30/30 en ambos; bytes de clave/ID y nuevo contador se comparan en los positivos.
No se exportaron claves privadas. No demuestra todas las atestaciones/proveedores,
algoritmos opcionales fuera de esos tres, HTTP/RLS, reautenticación ni dispositivos.

#### Resultado de factibilidad coach y límite operativo

Imagen coach existente inspeccionada por ID inmutable
`sha256:58a5c147cb9861a628d51cb6b22a55be5db803b0a6270d5670f8fdc63da77377`,
no llamada imagen productiva Python. SDK 0.3.223 lanzó su runtime real y completó
`query.initializationResult()` como UID/GID 1000, root filesystem read-only,
`--network none`, `--cap-drop ALL`, `no-new-privileges`; solo tmpfs temporales.
Se comprobaron args tools vacíos, `--setting-sources=` (sintaxis con igual), MCP
estricto, no persistencia, dontAsk, un turno, ausencia de bypass y ausencia de
variables DB/VAPID ficticias heredadas. `skills: []` se traduce en el SDK sin un
flag `--skills`; no inventar ese flag como aserción. No se envió prompt a un modelo,
no hubo login y este resultado no demuestra aislamiento de archivos/credenciales.

Codex 0.160.0 y bubblewrap 0.12.0 disponibles. Tanto bubblewrap con user namespace
como `codex sandbox linux -- /bin/sh ...` fallaron antes de ejecutar el hijo:
`No permissions to create a new namespace`. Docker Desktop 4.69.0, Engine 29.4.0,
Linux/amd64, kernel 6.6.87.2-microsoft-standard-WSL2; seccomp builtin activo,
CapEff=0 y NoNewPrivs=1. `user.max_user_namespaces=63361`: el error no prueba por sí
solo que el host haya deshabilitado namespaces; no se aisló todavía cuál control
de seccomp/kernel causa la denegación. No se cambió política del daemon ni del host.
**Bloqueo observado en Q4:** no había prueba de sandbox compatible no-root bajo la
política predeterminada. Q5 aporta el candidato distinto de §10, no vuelve válido
ese baseline. No acreditarlo por SDK inicializado ni por `codex --version`.

Comandos diagnósticos ejecutados desde el temporal Q4:
`node interoperability.mjs` (Node → fixtures → Python, exit 0),
`node coach-final.mjs` (SDK init positivo y salida SANDBOX_EXIT=1 de Codex).
El wrapper coach imprime resultados por caso; su exit 0 no convierte el caso
sandbox en PASS. Son comandos históricos sobre temporales diagnósticos, no comandos
disponibles de producto; tras cleanup sus fuentes no se conservan. El port deberá
entregar sus propias pruebas versionadas para las capacidades admitidas.

La imagen WebAuthn propia se retiró tras verificar su label; todos los contenedores
propios terminaron con `--rm` y la consulta por label no dejó ninguno. No se tocaron
imágenes base/ajenas ni cachés compartidas. Q6 concluyó la investigación SDK/CLI;
el temporal propio se retiró tras conservar aquí los resultados mínimos necesarios,
sin informe permanente duplicado ni comandos diagnósticos instalados.

Q5 autorizó investigar un perfil específico y acotado, no adoptarlo para operación.
Un fallo diagnóstico no autoriza relajar controles, volver root a la API, retirar
Codex ni añadir un servicio permanente.

### 10. Candidato de aislamiento coach ensayado en Q5

**Estado histórico:** factibilidad positiva acotada. Q6 decidió no adoptar este
candidato en la primera entrega; esta sección conserva evidencia diagnóstica, no
requisitos ni tareas para implementar un launcher o perfil de producto.
La API sigue sin root ni capacidades añadidas. No hubo cambios de daemon/sysctl,
privileged, socket Docker, `seccomp=unconfined` ni llamadas a modelos.

El candidato usó [Moby profiles, revisión fija
6fe7deb1b9fb7c0397a4593480d7d22b9ee8caef](https://github.com/moby/profiles/blob/6fe7deb1b9fb7c0397a4593480d7d22b9ee8caef/seccomp/default.json),
no una exportación exacta del builtin. Añadió reglas acotadas para namespaces y
montajes; SHA-256 candidato
`e5aa9c611a259d1117ff75fcf16d88b2e408b4422a1e4e63e8a323699a0095bd`.
La ampliación afectaba al contenedor completo, incluida API, no solo al hijo:
ese coste no fue aceptado y Q6 difiere ambos proveedores.

`node q5-isolation.mjs` devolvió exit 0/`Q5_ISOLATION_SUITE_PASS`: UID 1000,
CapEff=0, NoNewPrivs=1, runtime read-only, input/credencial propios accesibles,
secretos ficticios ajenos ocultos y controles de `/proc`, entorno, symlink y fds.
SDK 0.3.223 inicializó dentro del wrapper y `codex sandbox -- /bin/sh -c ...`
produjo `CODEX_ISOLATION_OK` con assertions de shell independientes. Cache admitió
escritura ficticia y matar supervisor no dejó centinela huérfano observado.
El control builtin con la sintaxis correcta siguió denegando namespaces; `linux`
en la invocación Q4 era un comando, no un subcomando válido de Codex 0.160.0.

Lección de seguridad conservada: bubblewrap preserva fds heredados. El control
negativo con fd privado detectó la fuga; cerrar fds no estándar antes del exec
pasó con el secreto aún abierto en el padre. Si se retoman subprocesses, exigir
argv sin shell, entorno/mounts allowlisted, cierre de fds y controles negativos.
No implementar ahora ese launcher ni copiar el prototipo como política operativa.

Un subensayo Node nativo con exit 0 sin marcador fue rechazado como prueba
positiva. No se probaron herramientas arbitrarias, egress real, autenticación,
modelos/cuotas, integración Python ni durabilidad/revocación de credenciales.
Esta evidencia no acredita GP/GO/G3 ni soporte para cualquier host Docker.

Cleanup Q5 verificado: imagen de ensayo propia retirada tras comprobar label;
consulta por label sin contenedores restantes. No se retiraron imagen coach de
referencia, bases ni cachés compartidas. Perfil/scripts/logs diagnósticos no son
artefactos de producto. Tras Q6 se verificó la ruta propia
`opengym-feasibility-Sgcnei`, sus entradas regulares allowlisted y ausencia de enlaces;
se retiró ese directorio y se comprobó su ausencia. Consultas por label sin recursos
propios restantes; imágenes compartidas, fuentes protegidas y artefactos ajenos intactos.

### 11. Q6: migración segura antes de evolución agéntica

**Decisión aprobada expresamente por el promotor:** conservar coach local y los
cuatro proveedores HTTP (`anthropic`, `openai`, `gemini`, `compatible`); mantener
fixture determinista para pruebas. Claude Agent SDK (`claude`) y Codex CLI (`codex`)
quedan temporalmente no disponibles en la primera entrega Python. No se adopta el
perfil Q5, no se mantiene una API Node como fallback ni se agrega servicio auxiliar.
La excepción está autorizada, pero su comportamiento aún necesita implementarse y
verificarse; no equivale a paridad total con todos los proveedores Node.

La importación conserva selección/configuración no secreta de los diferidos sin
remapear IDs ni cambiar proveedor por marca. El material de credenciales original
queda protegido por la política de conservación del origen, fuera de mounts activos;
no se promete reutilización futura ni se autoriza borrarlo. En Python no se ejecutan
login/refresh ni jobs manuales/programados para esos proveedores: intentos de usuario
reciben el fallo compatible 503/code `off`, antes de encolar o consumir cuota. No
reproducir jobs interrumpidos tras import/reinicio. Historial/propuestas preservados
no se eliminan para resolver la indisponibilidad.

AdminCoach/CoachSetup y disponibilidad pública deben mostrar la limitación real,
distinguir SDK/CLI de Anthropic/OpenAI HTTP y no ofrecer conexión/test/ejecución que
parezcan soportados. Verificar configuración importada diferida, cliente anterior,
cliente conservado y cambio voluntario a HTTP; los textos nuevos deben cubrir los
locales aplicables. Probar con transporte HTTP sintético y PostgreSQL real los
contratos vigentes de permisos, consentimiento, validación/aprobación, cuotas,
cancelación y olvido, sin acreditar acceso a proveedor real.

LangChain/LangGraph, nuevas tools/memoria y flujos agénticos pertenecen a un cambio
posterior con necesidad y aceptación propias. Mantener la separación existente
entre autorización/datos/propuestas y transporte del proveedor; no construir ahora
un motor genérico, adaptadores vacíos, tablas futuras ni dependencias anticipadas.
La primera entrega no requiere runtimes SDK/CLI, Node runtime ni override seccomp
coach. Su ausencia y la excepción de compatibilidad forman parte de GP/GO/G3 y del
inventario de cleanup; la evidencia Foundation y sus fixtures históricos no cambian.

### 12. Cierre técnico de preparación

El [plan ejecutable](execution-plan.md) y [tasks](tasks.md) sustituyen el mapa de
21 paquetes no ejecutados; no se reetiqueta progreso runtime. El orden es S1 boot,
S2 identidad mínima → S3 Training → resto S2, S4 medios, S5 coach, S7 push antes de
S6 administración/audit por hasPush, S8 shared/contrato, S9 diagnóstico/imágenes,
S10 recuperación y S11 corte separado. No bloquear el piloto por todo identity.
Cada tarea tiene caso/suite y checkpoint de su slice; no hay fase horizontal de
todas las pruebas seguida de todo el código.

Decisiones técnicas, no requisitos funcionales nuevos:
- [DDL](../../../docs/reference/platform-schema.md#especificación-ddl-y-evolución):
  cadena incremental p001–p005, proyecciones inmutables que rechazan tipos inválidos,
  FKs/índices/constraints y corrección forward-only. Se descartó guardar proyecciones
  editables o cargar todas las tablas futuras en bootstrap.
- [Funciones/roles](../../../docs/reference/platform-security.md#catálogo-sql-y-contexto-transaccional):
  catálogo tipado, ejecutores NOLOGIN, grants exactos, FORCE RLS y orden de locks.
  Se descartó dispatcher SQL/JSON genérico o ampliar privilegios runtime para evitar
  diseñar preauth/admin. Preservar proyección Training admin existente sin SET owner
  ajeno; no eliminar esa capacidad ni ampliar acceso a Recovery.
- [Diagnóstico](../../../docs/reference/platform-observability.md#configuración-cerrada-y-límites-iniciales):
  logging estándar/correlación y diagnose privado, sin OpenTelemetry/exporter propio.
  Seleccionar/fijar retención estándar antes de S9; probar todas las copias. Se
  difieren tracing avanzado e históricos métricos, no privacidad ni audit.
- [Recuperación](../../../docs/reference/platform-operations.md#procedimientos-operativos-especificados):
  age streaming y backup con parada por wrapper host/exclusión/journal, sin leases
  ni socket. Firma nueva separada de decrypt coach y Q1 con continuidad comprobada
  o vía nueva autorizada; Q2 mantiene W1/W2 independientes. Se descartan cifrado
  propio, apertura por TTL y snapshot viejo tras nuevos commits.

Estas elecciones permanecen dentro de Q3: vectores, HTTP+PG real, navegador y
comandos/checkout desechables; no reabren Q4/Q5 ni permiten operaciones reales.
Dependencies nuevas se fijan/prueban en delivery; metadata oficial consultada no
acredita instalación, integración Python ni resultados de operación.

## Risks / Trade-offs

- Más garantías de SQL no sustituyen paridad: vectores auth, sync/offline y casos
  HTTP/frontend reales, además de constraints/RLS.
- Backup antiguo no recuerda revocaciones nuevas: sin información/revisión no abrir
  acceso restaurado; medir ese procedimiento dentro de RTO.
- Pausa de captura puede afectar uso: medir y probar pendientes/deadlines; no prometer
  duración ni esconder escrituras internas.
- Bibliotecas coach y sandbox no están probadas por HTTP fixture: verificar cada
  runtime/proveedor admitido o resolver explícitamente diferencias.
- Todo comparte proceso: no atribuir a roles/RLS aislamiento ante host/API comprometida.

## Migration Plan

Todas las tareas de implementación quedan pendientes y requieren selección/autorización
posterior. Usar los casos, seams y checkpoints del plan y verificar
el handoff de Foundation archivada; implementar en entorno sintético solo después
de selección y autorización del slice preparado. Operación y corte solo después de
evidencia previa e inventario real. Esta autoría no ejecuta los pasos.

## Open Questions

**Decisiones conservadas/revisadas:** stack, alcance compatible, Q1 con credenciales
dudosas bloqueadas y continuidad o recuperación local explícita,
Q2 reparación hacia adelante, Q3 cinco fronteras de prueba, Q4/Q5 diagnósticos
acotados, Q6 aplazamiento explícito de SDK/CLI (§11) y cleanup sin borrar material
protegido automáticamente.
No volver a abrirlas por defecto.

**Prerrequisitos localizados pendientes:** selección/configuración del tooling estándar
de retención antes de S9 y autorización/entrega privada de vía nueva antes de 10.5.
No impiden el harness inicial ni autorizan implementar esos mecanismos sin resolverlos.
DDL/catálogo y OpenAPI §8 se conservan; Q5 no se adopta. RED/GREEN, imágenes y ensayos
son obligaciones de entrega, no resultados de esta revisión.

**Prerrequisitos operativos:** fuente protegida y cobertura de reconciliación manual,
inventario real, disco/rutas/claves, clientes/orígenes, ventana medida, ensayo de
reparación posterior a nuevas escrituras y evidencia G0/GP/GO. Sin ellos no hay corte.

**Readiness por slice, no aceptación global de implementación.**
Antes de S9 resolver selección/configuración de retención estándar; antes de 10.5
especificar autorización local y entrega privada de acceso nuevo. Esos slices están
bloqueados por sus prerrequisitos; harness inicial no requiere tooling futuro.
OpenSpec/OKF/diff-check comprueban artefactos, no producto. No se han ejecutado pruebas
runtime ni acreditado G0/GP/GO/G2/G3 por esta revisión. Transferir S11 antes de archive.

STOP antes de implementación. Especificación preparada no autoriza código ni
transición autónoma: entrega requiere solicitud explícita, y corte/datos reales/
programación/retirada requieren sus permisos operativos posteriores. Los
prerrequisitos reales de aceptación no se confunden con decisiones de planificación.
