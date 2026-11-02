---
type: Reference
title: Plataforma — operación local y recuperación
description: Redes, ambientes, respaldo, restauración y corte aprobados para una instancia personal con Compose.
---
# Plataforma — operación local y recuperación

## Estado y alcance

Diseño confirmado para una instancia personal, contenedores Linux/amd64 en Docker
Compose y primer acceso desde el computador anfitrión. No describe comandos hoy
entregados ni autoriza ejecución, migración o despliegue. La operación actual sigue
en [SELF_HOSTING](../SELF_HOSTING.md). La [arquitectura](../open-gym-evolution.architecture.md)
gobierna gates; [esquema](platform-schema.md), [seguridad](platform-security.md),
[observabilidad](platform-observability.md) y [modularidad](platform-modularity.md)
poseen sus contratos. Los escenarios futuros están en
[port-compatible-platform](../../openspec/changes/port-compatible-platform/proposal.md).

## Servicios y redes

```text
Navegador anfitrión
  127.0.0.1:8080 --> web:80
                       |
                 red aplicación
                       |
                    api:3000 --> salida DNS/HTTPS push/coach autorizada
                       |
                 red DB internal
                       |
                    db:5432

Migrador / backup / restore: procesos puntuales con permisos propios
Diagnóstico: logs estándar y herramientas locales, no servicios de negocio
```

Tres servicios permanentes web/api/db. Solo publicar web en loopback; API y DB sin
puertos publicados. Web no pertenece a red DB; API pertenece a ambas para conservar
egress. Mantener validación SSRF push y excepciones LAN específicas del proveedor
coach, sin autorización global de redes privadas. Sin socket Docker en contenedores.

Origen inicial estable `http://localhost:8080`; conservar origen/RP ID de clientes
existentes durante corte o resolver su transición explícita. Acceso autenticado
desde teléfono/LAN o publicación remota requiere diseño HTTPS posterior; no se
presenta localhost como acceso desde otro dispositivo. Arm64 queda pendiente de
verificación específica; no atribuirle aceptación por una imagen multiarch.

## Ambientes, imágenes y almacenamiento

Mantener la [matriz por fase](platform-modularity.md#matriz-de-ambientes-y-comandos-objetivo):
Foundation archivada; `deploy/docker-compose.yml` con selección explícita de overlay
`docker-compose.dev.yml` o `docker-compose.prod.yml`. Los comandos y capacidades
entregados se consultan en [backend/README.md](../../backend/README.md);
el nombre `prod` no acredita aceptación operativa ni autoriza corte.
Desarrollo usa fuentes en recarga, dependencias Linux y datos sintéticos
separados. Operación usa imágenes identificadas por digest, sin bind de fuentes,
node_modules o .venv ni instalaciones al arrancar. Misma revisión/lock para targets
test/runtime/migrate y herramientas operativas. Mantener una API/un worker inicial.

| Almacén objetivo | Propiedad y protección |
| --- | --- |
| Volumen PostgreSQL | Privado y duradero, distinto entre dev/operación y verificación sintética. No copiar PGDATA caliente como backup. |
| Medios y marcas GC | Volumen duradero con ownership, cuotas, temporales y limpieza segura; captura coordinada con DB. |
| Secretos | Material de firma de sesión, VAPID y cifrado/credenciales coach protegido y fuera de imagen/Git/frontend/logs. |
| Cache SDK/CLI coach heredada | No montar ni renovar en el runtime Python inicial: ambos proveedores están diferidos por [Q6 del port](../../openspec/changes/port-compatible-platform/design.md#11-q6-migración-segura-antes-de-evolución-agéntica). Conservar originales protegidos según su política, sin prometer reutilización futura ni añadir estas caches al backup Training. |
| Respaldo cifrado | Destino en disco independiente del disco de instancia, con acceso restringido; clave del bundle en lugar separado. Ruta/dispositivo se configura y verifica antes del corte. |

Toolchain parte de los pins/lock de Foundation, revalidando compatibilidad operativa;
no duplicar versiones como otra autoridad. Pool por aplicación min=1/max=4 como
punto inicial, conexión/adquisición 5 s, statement 5 s, comando 6 s, lock 2 s y cierre
10 s. La nueva configuración de aplicación distingue `local_compose` (DB alias
privado, sin puertos, red propia comprobada, TLS desactivado solo explícitamente)
de destinos no locales (TLS verify-full/CA, sin fallback). No falsear variables
Foundation ni quitar sus guardas para abrir la aplicación. Config no local o
incompleta sin TLS válido bloquea arranque. Pruebas representativas pueden justificar ajustes explícitos. No mantener
transacciones durante red externa, autenticadores, streaming o copia de medios.

Migrador puntual con rol separado y conexión dedicada; lock antes de leer historial
y hasta terminar. Solo después de éxito se habilita tráfico compatible. API no
migra al arrancar. Probes internos `/api/v1/health/live` y
`/api/v1/health/ready` y métricas no se publican por nginx;
`/api/v1/health` mantiene el comportamiento público de salud. Python no conserva
alias sin versión. El frontend Python se compila con `VITE_API_PREFIX=/api/v1`;
ver el [contrato HTTP](../../backend/README.md#http-api-v1). Readiness comprueba DB y
revisión, sin confundirse con paridad ni recuperación.

## Respaldo coordinado

Objetivos aceptados: **RPO 6 h / RTO 24 h**, pendientes de demostración medida; no
son garantías actuales. Retención de bundles 30 días. Disco independiente no
acredita ubicación externa al host ni cobertura de pérdida completa del equipo.

Programar en el sistema operativo backup cada 3 h, comprobación al arrancar si
vencido, copia antes de migraciones y restore de ensayo mensual. Son entregables
futuros, no tareas instaladas por esta edición ni automaciones de chat creadas.
Cada ejecución expone éxito/fallo, transferencia e integridad verificadas; no dar
por cumplido RPO por la mera frecuencia. Señalar incumplimiento del objetivo y
antigüedad del último punto recuperable al operador por la superficie local definida.

```text
Parar escritores/API --> capturar DB + medios/config/secretos coherentes
                                   |
                         recuperar servicio previo
                                   |
                      cifrar --> copiar --> verificar
                                   |
                      punto recuperable válido
```

La primera operación local admite una pausa controlada: un wrapper del host toma
exclusión operativa, detiene limpiamente la API y comprueba el cese de todos sus
escritores antes de capturar PostgreSQL, medios, configuración y secretos.
PostgreSQL permanece disponible para el dump; ningún contenedor recibe socket Docker.
La pausa sustituye el protocolo de leases/socket de mantenimiento en la aplicación.
Inventariar escritores externos y detenerlos también; un escritor desconocido bloquea
la captura. No reiniciar la API hasta comprobar el cese de procesos de captura.
Medir pausa y comprobar clientes dirty/offline; no prometer indisponibilidad cero.
Cifrado, transferencia y verificación ocurren fuera de la pausa.

Usar dump PostgreSQL consistente y captura coordinada de archivos, manifiesto de
revisión/esquema/versiones/alcance/checksums y cifrado autenticado. Incluir los
secretos necesarios para interpretar/restaurar los datos bajo protección; nunca
incluir la clave del propio bundle. No atribuir PITR a pg_dump. La restauración
mensual verifica acceso, roles/RLS, medios, historial y clientes antiguos, midiendo
alcance/tiempo completo. Copia corrupta, transferencia fallida o clave perdida no
cuentan como punto recuperable.

## Restauración y decisiones de seguridad posteriores

```text
Restore aislado, sin tráfico ni efectos externos
  --> invalidar sesiones/pairings restaurados
  --> reconciliar eliminaciones y revocaciones posteriores
  --> comprobar datos, credenciales, medios y linaje
  --> habilitar únicamente accesos revisados
```

Una copia antigua puede resucitar cuentas o passkeys borradas y retroceder contadores
WebAuthn. Invalidar sesiones no soluciona por sí solo las credenciales históricas.
Conservar información protegida posterior al snapshot para reaplicar bajas y
revocaciones. El procedimiento inicial aprobado es revisión manual explícita por
acceso: identificar cuenta/credencial, snapshot, fuente posterior protegida, cobertura,
decisión y resultado de comprobación aislada. Guardar evidencia operativa mínima y
protegida, sin secretos; no crear otro registro general de seguridad por esta regla.
Backup, login correcto o audit borrable/best effort no bastan para probar vigencia.
Si falta información suficiente, la credencial histórica permanece bloqueada: la
mera revisión no permite restaurar contadores WebAuthn dudosos como seguros. Q1
admite dos salidas: continuidad con evidencia suficiente, o recuperación local
explícita de una vía nueva sin reactivar credenciales históricas dudosas. Incluir
revisión, recuperación de acceso y verificación en el RTO. No crear un ledger.
Antes del corte probar al menos una salida completa; un restore de datos sin acceso
recuperable no acredita RTO ni habilita tráfico.

También comprobar pendientes offline y linaje Training. No borrar cliente ni
permitir sobrescritura silenciosa por una restauración. La reautenticación tras
restore es una medida de recuperación; durante el port normal se conserva la sesión
si es segura/compatible y solo se admite excepción documentada probada.

## Importación aislada de origen Node

La imagen Python `ops` incluye el importador separado de Alembic y de HTTP. El
comando no crea la base, no ejecuta DDL de negocio, no arranca servicios ni abre
tráfico. Solo acepta un destino recién provisionado con las migraciones vigentes,
sin datos de negocio y con los siete proveedores/configuración iniciales intactos.
No es restore, corte ni aprobación de las credenciales históricas de Q1.

Preparar un PostgreSQL/volumen independiente, sin API ni otros clientes conectados.
Después del bootstrap/migraciones, su administrador debe marcar explícitamente la
base con `COMMENT ON DATABASE ... IS 'opengym-import:new-a'` y retirar `CONNECT`
de `opengym_api_runtime`; PUBLIC tampoco debe concederlo. El ID debe coincidir con
la configuración y `--target`. No marcar una base existente para reutilizarla:
el importador comprueba vacío, defaults, revisión, conexiones y lock 728322. No
modifica roles/grants para sortear una denegación.

En un contenedor `ops` aislado, montar exclusivamente el origen congelado en
`/run/import/source:ro`, configuración privada en `/run/import/operator.json:ro`,
los tres ficheros de passwords DB y un directorio de destinos escribible privado.
Configurar explícitamente `PLATFORM_ENV`, `PLATFORM_DB_MODE=local_compose`,
`PLATFORM_DB_HOST=db`, `PLATFORM_DB_PORT=5432`, `PLATFORM_DB_NAME`,
`PLATFORM_DB_TLS=disable` y los ficheros `PLATFORM_DB_PASSWORD_FILE` (bootstrap),
`PLATFORM_MIGRATOR_PASSWORD_FILE` y `PLATFORM_RUNTIME_PASSWORD_FILE`, según
[configuración de imágenes](../../backend/README.md#platform-images-and-compose).
El servicio `ops` normal de Compose conserva sus mounts de diagnóstico: estos
mounts/variables adicionales se proporcionan solo al comando de importación sobre
el destino independiente; no se añaden secretos privilegiados a diagnose/API.

Configuración del importador, sin passwords ni rutas elegidas por HTTP:

```json
{"target_id":"new-a","target_root":"/run/import/targets","admin_uids":[]}
```

`admin_uids` declara expresamente los IDs que tenían facultad por `ADMIN_UIDS` en
la configuración protegida del origen, además de `user.admin`. No usar el entorno
heredado para decidirlos. Conservar también la configuración de despliegue original;
este comando no interpreta `.env` ni instala su configuración en una instancia.
El directorio raíz debe existir, pertenecer al UID operativo y tener modo 0700.
El subdirectorio `new-a` debe ser nuevo; ni enlaces ni destinos anteriores se usan.

Dentro de la imagen `ops`, ejecutar:

```sh
python -m opengym_platform.operations import --config /run/import/operator.json --source /run/import/source --target new-a
```

El origen exige filesystem/mount de solo lectura, UTF-8 y archivos regulares sin
symlinks/hardlinks. Congelar realmente sus escritores es una precondición operativa:
un bind `ro` no detiene otro escritor del host. Se comparan inventarios SHA-256 antes
y después de leer/copiar; discrepancia bloquea. Límite de lectura: 64 MiB por archivo
y 512 MiB por origen; un exceso bloquea, nunca trunca. Backups `db.json.bak` quedan
solo en el origen protegido. Archivos/propiedades desconocidos, temporales u owners
sin resolver bloquean en vez de perderse. No se consulta el cache SDK/CLI externo.

| Capacidad | Equivalencia exigida o bloqueo |
| --- | --- |
| Identidad | IDs/roles efectivos, alias NFKC, hash scrypt completo, sv, passkeys/contadores/bytes COSE, resets y device links/digests. Fechas históricas ausentes permanecen nulas; colisiones/credenciales inválidas bloquean. |
| Training | Documento interno completo, `_prior`, `_unstamped`, linaje, tipos y ausente/null; ninguna fila para un owner sin documento. Proyecciones derivadas de SQL, sin convertir strings ni redondear `_rev`. |
| Medios | Bytes/hash por owner y `.gc.json` conservados fuera de SQL. Owner/nombre/hash incorrectos bloquean. |
| Notificaciones | Endpoint/owner/keys/device/fecha originales, fechas locales reminder/nudge y pareja VAPID válida. No se envían notificaciones durante importación. |
| Coach | Selección/modelos/opciones/vínculos, compartir, cuotas diarias, propuestas completas e historial como eventos; IDs de job repetidos no colisionan. Secretos HTTP cifrados externos por perfil o referencia estable, sin descifrado en SQL/reporte. |
| Excepción Q6 | `claude`/`codex` conservan selección/configuración/vínculo no secreto. Sus credenciales y los registros personales de una selección diferida quedan únicamente en el origen protegido, fuera del destino activo; sin remap, login/refresh, job ni cuota nueva. |
| Administración/audit | Invitaciones consumidas/revocadas e IDs históricos sin FK destructiva. Audit conserva IDs; los eventos Coach sin ID SQL reciben ordinales, conservando job ID/orden. Las tres secuencias continúan después del máximo importado. |

La equivalencia compara todas las filas/campos mapeados mediante una lectura SQL
posterior, dentro de la misma transacción; las copias externas se releen byte a byte.
Las secuencias usan `ALTER SEQUENCE RESTART`, transaccional, en lugar de `setval`.
No se desactivan constraints, RLS ni triggers. El importador requiere la credencial
bootstrap explícita solo en el contenedor operativo; la API no recibe esa facultad.

Dos diferencias concretas del origen actual no se corrigen automáticamente:
`coach.json.log` con UID o detalle no vacío carece de representación en el contrato
SQL de resultados anónimos (`summary={}`); un trabajo `current` sin `trigger` no
permite deducir manual/scheduled. Ambos bloquean intactos, sin descartar el log,
inventar un trigger o repetir trabajo. Resolverlos exige caracterización y una
decisión explícita antes del corte. Igual ocurre con JSON duplicado, Unicode/NUL,
fechas o tipos no representables y líneas audit dañadas.

Salida 0 significa importación equivalente en cuarentena; 1 bloqueo/dato/IO/DB;
2 configuración/uso inválidos o imagen sin herramienta. Stdout solo emite códigos
cerrados. El reporte privado `import-report-<aleatorio>.json` (0600) registra códigos
y, en éxito, conteos por tabla y huella del origen; nunca passwords/SQL/ciphertext.
El destino contiene `data/`, `session-secret` y `coach-secret` separados (0600,
directorios 0700), y `import.json` solo tras commit confirmado. El comando mantiene
CONNECT denegado incluso después de éxito. No equivale a autorización para usar los
secretos/datos originales ni para borrar el origen.

Un error previo a copiar deja SQL/secuencias y subdirectorio destino intactos. Un
fallo de copia revierte SQL/secuencias, pero puede conservar un subdirectorio parcial
sin marcador. Un commit incierto o un fallo posterior tampoco permite promoción:
mantener cuarentena, conservar reporte/material y revisar independientemente; no
reintentar sobre ese destino ni limpiar automáticamente. La creación de backup,
parada/journal de escritores y restauración quedan en sus procedimientos separados.

## Corte, retirada y conservación

G0 e inventario de orígenes/usuarios/clientes comprobados; G1/GP/GO previos al corte.
Pausar escritores HTTP e internos, respaldar y congelar origen, importar todos los
campos internos, verificar equivalencia y activar una sola autoridad PostgreSQL.
Datos no representables fielmente bloquean el corte; no rellenar o limpiar historial
silenciosamente. Documentar la ventana según duración ensayada, sin plazo inventado.

Conservar origen congelado, release previa por revisión/digest, configuración y
secretos al menos 30 días después del corte aceptado. No lecturas legacy activas,
dual-write ni fallback. Antes de nuevas escrituras, reversión validada al origen;
después, la estrategia base aprobada es reparar hacia adelante Python/PostgreSQL,
preservando las nuevas escrituras mediante un procedimiento ensayado. El exportador
inverso a Node queda fuera del alcance salvo aprobación expresa. Si el ensayo no
preserva las escrituras exigidas, bloquear corte y resolver con el promotor; nunca
restaurar silenciosamente una copia vieja. Distinguir reparación con destino
superviviente de pérdida del destino bajo el RPO aceptado: backups cada 3 h no
prometen pérdida cero ni recuperan por sí solos toda escritura reconocida.

Retirada de código y borrado de originales son decisiones distintas: cumplir el
plazo no autoriza borrar. G3 y GO posteriores comprueban capacidades, seguridad,
recuperación, diagnóstico e independencia de imports/builds respecto de API Node
retirada; la biblioteca neutral JS permanece conforme a su contrato.

El cleanup es un checkpoint obligatorio antes de aceptar plataforma: inventario de
rutas/consumidores con destino retirar, conservar con propósito vigente o material
protegido. Migrar primero imports, generadores, builds, CI y comandos soportados;
retirar implementación sustituida y configuración/dependencias exclusivas, no dejar
una segunda API desactivada. Conservar/adaptar pruebas de comportamiento antes de
retirar tests exclusivos del mecanismo anterior. No borrar por extensión o por nombre
de carpeta: biblioteca neutral, catálogo, herramientas vigentes y evidencia Foundation
útil siguen teniendo propósito; el lenguaje no determina la retirada.

Limpiar temporales sintéticos propios tras conservar evidencia saneada necesaria en
OpenSpec/CI; no añadir informes permanentes duplicados. Usar rutas/recursos exactos,
sin prune global ni tocar datos, perfiles o pendientes cliente. Ensayar preservación
de un sentinel ajeno y material protegido. Checkout limpio, builds, paridad, seguridad,
restore y ausencia de dependencias activas legacy se verifican después del cleanup.
Esto no autoriza borrar origen, releases ni respaldos protegidos.

## Captura SQL entregada

El wrapper `node scripts/platform.mjs operate backup --config <ruta-absoluta>
--reason scheduled|startup|pre-migration`, **sin la sección `bundle`**, entrega parada
limpia, dump SQL y conjunto de archivos coherente. Esa captura sola **no es un backup
recuperable**: incluso si captura correctamente, devuelve
`BACKUP_CAPTURED_UNVERIFIED`, `verified: false` y código **1**. No marca ni sustituye
un punto verificado. No usar esta fase para programar backups ni autorizar DDL.

Requisitos de preparación explícita, no ejecutados automáticamente:

- Imágenes runtime/ops probadas y selección Compose propia, sin puertos PG publicados,
  clientes SQL externos ni escritores desconocidos. El proceso host controla Docker;
  no se monta su socket ni se añade un protocolo de leases a la API.
- Directorio de staging preexistente en **almacenamiento cifrado**, fuera de datos
  activos, con espacio para el dump sin comprimir. Contiene datos completos en claro
  hasta la futura entrega de cifrado/copia. En POSIX: propietario del operador y modo
  0700, accesible por el UID 1000 de ops. En Windows: propietario actual y ACL sin
  Allow para identidades distintas del propietario, SYSTEM o Administrators. El
  wrapper valida permisos, no los modifica ni acredita el cifrado del volumen.
- Aplicar `backend/backup-role.sql` al destino elegido mediante psql como bootstrap
  autorizado, después del esquema. Provisionar por separado `opengym_backup` mediante
  `\password` y el fichero privado `backup_password`; no poner contraseñas en SQL
  versionado, argv ni variables de entorno. La preparación es repetible, no se ejecuta
  al arrancar API ni en una migración. Tras cambios de catálogo, revisar y repetir
  grants/policies explícitos antes de capturar.
- Añadir `deploy/docker-compose.maintenance.yml` después de base y prod durante la
  preparación autorizada de la instancia. No aplicarlo automáticamente sobre una
  instancia personal: registrar los labels de DB puede recrear su contenedor.
  El overlay monta staging y credencial backup solo en ops; API conserva su rol
  y recibe únicamente `gate/` en solo lectura, nunca dumps ni credencial backup.
  Durante captura, el wrapper añade a ops montajes de solo lectura de los orígenes
  seleccionados; no amplía permisos de la API.

Antes del primer arranque gestionado, crear `gate/` dentro del estado privado, con
propietario/permisos compatibles con el UID de API/ops, directorio 0700 y
`gate/admission.json` 0600. **Solo para una instancia nueva, sin operación pendiente**,
el operador provisiona explícitamente:

```json
{"instance_id":"personal-a","operation":"00000000000000000000000000000000","allowed":true}
```

No inicializar, reemplazar ni renombrar ese directorio para desbloquear una captura.
Después de preparar el bind, el wrapper modifica únicamente el fichero por rename
atómico; el directorio debe permanecer estable. Marcador ausente/corrupto/ajeno,
enlace o `allowed: false` impide crear la aplicación antes de abrir DB o arrancar
escritores. No hay polling, lease, socket ni llamada a backup en el arranque API.
El overlay exige un directorio existente (`create_host_path: false`); instalarlo o
actualizar una imagen/instancia preparada anteriormente requiere preparación propia,
no lo hace `maintenance-recover`.

El fichero de entorno explícito para Compose contiene referencias, no secretos:
`PLATFORM_INSTANCE_ID`, `PLATFORM_MAINTENANCE_STATE_DIR` (ruta absoluta del estado),
`PLATFORM_BACKUP_CONFIG_FILE` (ruta absoluta de la configuración ops),
`PLATFORM_SECRETS_DIR` y los digests ya probados de prod. Los labels persistentes de
DB fijan ID y ruta de estado; cambiar solo la ruta de configuración no elude exclusión.
No se usa `.env` implícito. Configuración host de ejemplo, con todas las rutas
sustituidas por las propias (en JSON Windows se pueden usar `/`):

```json
{
  "instance_id": "personal-a",
  "project": "opengym-ops",
  "project_directory": "/srv/opengym/release",
  "compose_files": [
    "/srv/opengym/release/deploy/docker-compose.yml",
    "/srv/opengym/release/deploy/docker-compose.prod.yml",
    "/srv/opengym/release/deploy/docker-compose.maintenance.yml"
  ],
  "env_file": "/srv/opengym/private/maintenance.env",
  "state_root": "/srv/opengym/private/capture",
  "writers": ["api"]
}
```

La configuración ops referenciada es distinta de la configuración host y de la de
`diagnose`; contiene exactamente:

```json
{
  "instance_id": "personal-a",
  "project": "opengym-ops",
  "staging_root": "/run/maintenance",
  "expected_schema": "p004_audit"
}
```

`writers` enumera todos los servicios escritores, incluida API; procesos internos
Coach/audit/upload/GC/schedulers cesan al cerrar su contenedor. El wrapper comprueba
salida limpia, PG vivo, imágenes seleccionadas y ausencia de peers desconocidos.
Antes de parar y después de capturar, también inspecciona contenedores activos de
otros proyectos: un montaje de escritura sobre los medios, secretos/configuración
o staging protegido bloquea la operación, aunque ese contenedor no comparta red DB.
La API debe coincidir con imagen, entorno/comando seleccionado y origen de datos;
los volúmenes nombrados deben pertenecer al proyecto. No se admiten montajes anidados
bajo `DATA_DIR` ni secretos/configs sin fichero local explícito.

**Límite de confianza:** durante toda la pausa el operador debe mantener control
exclusivo de Docker y de los ficheros host seleccionados, sin rotación/edición ni
escritores host ajenos. Inspecciones puntuales no son una barrera contra contenedores
transitorios ni procesos host arbitrarios. El wrapper compara hash e identidad de
los ficheros host antes/después; detectar estabilidad no equivale a congelarlos.
Un bind `read_only` tampoco congela su origen. Si no puede garantizarse esta custodia,
no ejecutar captura ni acreditar coherencia.

Ops toma el lock 728322 y exporta una instantánea repeatable-read para `pg_dump`
custom con RLS habilitado e INSERTs. Su rol no tiene superuser/BYPASSRLS/DML ni
membresías privilegiadas; `backup_read` permite SELECT completo explícito y
`pg_read_all_stats` permite rechazar otros clientes. No admite políticas restrictivas
que pudieran ocultar filas. La fase interna `capture-sql` requiere journal/exclusión;
no equivale al comando `operations backup`, que empaqueta/verifica después de la
captura acreditada y del reinicio compatible, sin volver a capturar SQL.

Los healthchecks de PostgreSQL usan `pg_isready -d postgres`, fuera de la base de
aplicación: sus conexiones transitorias no deben competir con la comprobación de
ausencia de clientes en el destino. Esto solo acredita disponibilidad del servidor;
readiness API comprueba su base y esquema reales. No excluir clientes por llamarse
`pg_isready`: cualquier conexión ajena en el destino sigue bloqueando captura.
Un contenedor ya creado conserva su healthcheck anterior hasta recrearlo mediante
su procedimiento operativo autorizado. `node scripts/platform.mjs verify backup --case capture_quiescence`
comprueba ambos casos con la ventana de conexión del probe extendida.

Durante el inventario global, un contenedor ajeno puede desaparecer entre listado
e inspección. El wrapper solo omite ese ID si un segundo listado Docker exitoso
confirma que ya no existe. Si sigue presente o Docker no puede confirmar ausencia,
la operación falla; no se omiten inspecciones fallidas de contenedores activos.

Estado privado: `owner.json`, directorio `exclusive` con identidad del controlador
host (hostname, PID y token de creación del sistema), `gate/`, `journal.json` atómico y un
subdirectorio por operación con `database.dump`, `data/`, `runtime-secrets/`,
`configuration/`, `capture.json` y copia del journal. `data/` conserva medios por
propietario, marcas GC, temporales pendientes, registros Coach cifrados y VAPID.
Solo se admiten `uploads/`, `vapid.json` y registros `coach-auth-*`/`coach-key-*` en
la raíz de datos; material desconocido bloquea, no se descarta. Configuración incluye
los ficheros host/env/Compose, selección Compose resuelta e imagen/config runtime,
configs/secrets de la selección y los ficheros bind
bajo `/run/secrets/` y `/run/operator/`. Los secretos runtime montados realmente en
API se conservan además de los seleccionados y deben coincidir en contenido.
El fichero privado `<operación>.selection.json` queda en el estado y en el conjunto
capturado; no publicar su entorno ni rutas. El manifiesto privado relaciona
orígenes/destinos, tamaños y SHA-256, snapshot/esquema y `verified: false`.

Ops compara inventarios/identidad y hashes antes de SQL, al copiar y al releer las
fuentes. Rechaza enlaces, hardlinks de archivos, dispositivos, nombres inseguros,
entradas duplicadas y cambios de contenido/árbol. Directorios 0700 y archivos 0600;
los archivos y directorios copiados se sincronizan. Presupuesto de captura 120 s,
con límites de profundidad 64 y 100 000 entradas; sobrepasarlos bloquea sin avanzar
un punto recuperable. Staging sigue **en claro sobre almacenamiento cifrado**;
la protección del volumen y su capacidad son prerrequisitos del operador, no una
propiedad acreditada por el wrapper. Logs/caches SDK/clave age no son orígenes de
captura. Se registran `pause_started_at`, `pause_ms`, `capture_ms` y presupuesto.
Tras captura y comprobación de esquema, se usa `start`, nunca `up`, solo
para servicios antes activos. `pre-migration` **no reinicia** entre captura y DDL:
queda bloqueado hasta la futura entrega de migración coordinada. Fallo/interrupción
conserva journal/bloqueo; no hay recuperación automática por PID/TTL ni borrado global.
El bundle cifrado opcional se describe debajo; retención y programación siguen pendientes. No retirar un bloqueo
ni editar admisión/arrancar servicios a ciegas.

### Bundle cifrado entregado

Para habilitar publicación cifrada en el mismo comando, añadir a la configuración
**host** (no al fichero de `capture-sql`):

```json
{
  "bundle": {
    "destination": "/mnt/backup-disk/opengym",
    "identity_file": "/srv/opengym/private-keys/backup.agekey",
    "recipient": "<recipient-X25519-age1>"
  }
}
```

Sustituir el recipient por el valor X25519 completo, no el placeholder. Provisionar
la identidad separadamente con herramientas age; no se genera ni imprime desde el
wrapper. Destino y clave deben existir, con rutas absolutas sin enlaces/hardlinks,
fuera de staging/datos/fuentes capturadas y sin solaparse entre sí. Destino 0700 y
clave 0600 en POSIX, accesibles al UID ops; en Windows el wrapper exige ACL privada
como para staging, también en el fichero clave y destino. Docker Desktop puede
presentar permisos POSIX sintéticos: ops solo acepta esa excepción por la prueba
host `win32` registrada tras verificar las ACL. El wrapper no configura permisos,
cifra volúmenes ni acredita físicamente que el destino sea un disco independiente.

Mantener privados y estables configuración Compose/ops, estado, clave y destino
**durante toda la operación**. Las fuentes activas solo se congelan durante captura;
API vuelve a trabajar mientras se cifra/transfiere. La clave se monta RO únicamente
en ese contenedor puntual, fuera de `/run/secrets/` y de la selección de captura;
**no declararla como secreto/config Compose**: la captura conserva esos ficheros.
Nunca copiarla dentro de datos, staging o configuración. Un solapamiento detectado
bloquea; inspecciones/hash no excluyen escritores host arbitrarios o transitorios.

Tras parada/captura/check/restart, el wrapper conserva exclusión y registra fase
`bundling`, cliente y contenedor ops nombrado, con imagen fijada al ID inspeccionado.
Ops requiere esa prueba, operación exacta y mutex PG 728322 (sesión, sin transacción
durante IO). Usa age **1.3.2** oficial Linux/amd64 fijado por SHA-256 en
`backend/versions.json`; licencia BSD-3-Clause en `backend/age.LICENSE`. Binarios solo
en ops/pruebas, no API/dev/migrate ni instalación host o al arrancar.

El formato v1 es tar USTAR sin comprimir, enviado por streaming a age X25519. El
manifiesto cifrado contiene versión, instancia/operación, `snapshot_at`, head SQL,
imágenes reales, versiones age/PG, cobertura e inventario de directorios y archivos
con tamaños/SHA-256. Incluye SQL, datos/medios/GC/temporales, registros Coach/VAPID,
secretos runtime, configuración y procedencia de captura/journal. No incluye clave
age, logs ni caches SDK. Nombres no representables por USTAR o manifiestos >32 MiB
bloquean sin truncar. Inventario de captura y fuentes deben coincidir; enlaces,
tipos especiales, traversal, duplicados y cambios de bytes bloquean.

Primero crea `bundle.age` en staging protegido, fsync; copia cifrado a
`<destination>/<operation>.age.partial`, fsync y relee **desde ese destino** con age.
Verifica manifiesto, entradas/tamaños/checksums y consume hasta EOF, exigiendo exit 0
de age: el EOF de tar por sí solo no acredita el último chunk autenticado. Compara
SHA-256/identidad del ciphertext alrededor de la verificación y antes de publicar.
Solo entonces hace rename al nombre único `.age`, fsync del directorio y actualización
atómica de `gate/backup.json`. El fichero anterior no se sobrescribe por un fallo de
copia, clave incorrecta, corrupción, truncamiento, ENOSPC o mutex ocupado.

Éxito host: `BACKUP_VERIFIED`, `verified: true`, exit **0**, journal `verified`.
Acredita publicación íntegra del bundle, **no restore completo, acceso Q1 ni RPO/RTO**.
Sin `bundle` continúa `BACKUP_CAPTURED_UNVERIFIED`/exit 1. `startup` comprueba una
vez la antigüedad bajo exclusión host y captura si hace falta; `pre-migration` conserva
el bloqueo previo y falla sin publicar ni ejecutar DDL hasta su coordinación propia.

Un fallo conserva exclusión/journal y parciales protegidos; API ya reiniciada puede
seguir trabajando. `maintenance-recover` también acredita cese del contenedor/cliente
de cifrado antes de liberar, sin borrar o acreditar parciales ni volver a capturar.
Interrupción tras una publicación completa pero antes de unlock conserva el punto
válido; recuperación de servicio no lo invalida ni equivale a una publicación nueva.
Si falla la persistencia final o se pierde la respuesta, el resultado puede ser
incierto: conservar bundle/recibo/lock y revisar, nunca sobrescribir o adivinar éxito.

`gate/backup.json` es recibo privado de la última verificación (instancia/operación,
snapshot/verificación, tamaño/SHA-256 del ciphertext y `cleanup_pending: true`). API
solo lee ese resumen por su bind RO: diagnóstico privado muestra edad calculada desde
**snapshot**, `current` <3 h, `overdue` 3–6 h y `rpo_exceeded` >6 h; ausente/corrupto/
ajeno no se acredita. Es evidencia de última verificación, **no una sonda actual de
presencia del disco ni una nueva comprobación criptográfica**. No publica rutas,
claves o manifiesto; salud global requiere además DB/esquema y logging saludables.

Staging sigue en claro sobre volumen cifrado, con copia cifrada y parciales propios.
Esta entrega registra cleanup pendiente protegido; no borra automáticamente capturas,
puntos anteriores o archivos ajenos. Reservar capacidad para captura+ciphertext y
destino, revisar/liberar solo material propio mediante permiso operativo separado.
Retención y limpieza/programación automática quedan en sus slices, sin jobs reales.

Prueba sintética: `node scripts/platform.mjs verify backup --case verified_bundle`.
Reutiliza setup/captura/cleanup existentes, con lector age/tar y SQL independientes,
fallos reales acotados de disco, corrupción incluso posterior al decrypt EOF,
interrupción durante cifrado y después de publicar antes de unlock. No ejecuta el
comando de restore futuro ni prueba pérdida física del equipo.

### Recuperación explícita del journal

```sh
node scripts/platform.mjs operate maintenance-recover --config <ruta-host-absoluta> --operation <id-hex32-del-journal>
```

Operación privada y explícita, bajo la misma custodia exclusiva de Docker/ficheros.
Valida configuración/ownership, operación exacta, contenedores e imágenes originales.
Un controlador vivo impide takeover. Windows usa PowerShell y tiempo de creación;
Linux usa `/proc` con boot ID/start time. Un PID reutilizado no identifica el proceso
anterior; un tiempo vencido nunca autoriza apertura. La recuperación toma un sucesor
atómico `exclusive/recovery/` con identidad propia; otro recuperador vivo bloquea.
Si ese recuperador muere, otra invocación explícita puede tomar su sucesor. Se limita
a 64 niveles; no se retiran locks con identidad ausente, corrupta, host distinto o
imposible de comprobar. Los temporales de escrituras interrumpidas se conservan.

Antes de recuperar servicio, cierra admisión y detiene solo contenedores capture/check/bundle
registrados de esa operación, con nombre, proyecto, servicio e imagen comprobados.
Comprueba cese del cliente Docker registrado, detiene/verifica escritores originales
y rechaza peers DB o montajes de escritura externos sobre fuentes protegidas.
Reutiliza `capture-sql --check-only` con mutex/rol backup para verificar esquema,
catálogo/permisos y ausencia de clientes SQL; no vuelve a capturar ni restaura datos.
Los checkers tienen nombre persistido, no `--rm`, para poder acreditar su cese tras
morir el wrapper. Solo después admite y arranca por ID los servicios antes activos;
API debe alcanzar readiness real. Si un arranque falla, vuelve a cerrar admisión y
detiene escritores, dejando exclusión/journal para otro intento explícito.

Éxito: `MAINTENANCE_RECOVERED`, exit **0**, fase `recovered_unverified` y
`verified: false`; significa servicio recuperado, **no una nueva verificación de backup**. No modifica
el último punto verificado ni elimina staging. `startup` no se vuelve a invocar:
se conserva la operación y la API no lanza el wrapper. Un servicio antes parado
permanece parado. `pre-migration` devuelve `MAINTENANCE_MIGRATION_HELD`, exit **1**,
con fase `migration_held`, exclusión y admisión cerrada: nunca ejecuta DDL ni abre
tráfico entre copia y la futura migración coordinada. Errores/estado incierto salen
con **1**; argumentos/configuración inválidos con **2**.

Un journal antiguo sin prueba de controlador, una creación de captura incierta
sin contenedor persistido o un fallo antes de persistir identidad/journal no se
adivina ni se convierte en éxito: requiere revisión forense del operador. No borrar
el lock para eludirlo. Esta entrega no acredita apagado físico, durabilidad del
hardware, recuperación universal de archivos dañados ni aceptación operativa.

Verificación sintética: `node scripts/platform.mjs verify backup --case
writer_shutdown` observa parada con PG vivo, exclusión, servicios inicialmente
parados y dump restaurado por observador independiente. `verify backup --case
sql_files_coherence` añade bytes/checksums de medios/GC/config/secretos y referencias
Training del SQL capturado, rechazo de escritores externos antes/durante captura y
cambio de fichero host durante la pausa, enlace inseguro, medio alterado después del
dump real y secreto seleccionado distinto del runtime, conservando bloqueo/journal
sin reinicio inseguro. `verify backup --case interrupted_capture` añade muerte real
de wrapper/recuperador, contenedores ops aún activos, arranque API con barrera
persistida y marcador inválido, concurrencia, esquema incompatible y fallo de
restart; verifica API inicialmente parada y pre-migración retenida sin DDL.
Los tres IDs reutilizan la prueba integrada. No reinicia el daemon Docker ni el
host real: el nuevo proceso API sobre estado persistido ensaya esa barrera local.
`verify training_browser`
es la regresión separada de dirty/active/offline y cola de medios persistida; no
es un ensayo integrado de navegador con el wrapper ni acredita clientes reales,
recuperación completa, RPO/RTO o aceptación operativa.

## Procedimientos operativos especificados

Los procedimientos completos siguientes son contratos **futuros**, salvo la fase
SQL/archivos, bundle cifrado opcional, recuperación y restore de datos en cuarentena
entregados en esta página; no acreditan herramientas completas ni ejecuciones
reales. El [plan ejecutable](../../openspec/changes/port-compatible-platform/execution-plan.md)
fija prefijos Compose, suites, flags, salidas y checkpoints. Operador necesita
Docker/Compose y Node 22+ para el wrapper host de parada/recuperación; Python,
PostgreSQL y cifrado corren en target `ops`. Node no entra al runtime API.
No reutilizar la CLI Foundation fuera de sus guardas sintéticas.

### Preparación y programación

`operator.json` privado contiene instance_id, nombres de proyecto/volúmenes propios,
revisión/digests, origen/RP ID, refs a ficheros de credenciales, backup/staging roots,
recipient age e identity-file de verificación/restore separado. Sin secretos literales
en argv/env, logs o Compose resuelto. Rechazar rutas solapadas, enlaces, volumen de
otro ambiente, destino no vacío o sin ownership verificable, falta de espacio y
clave inaccesible. No mostrar rutas privadas en evidencia pública.

Tooling operativo usa pg_dump/pg_restore del major fijado en backend/versions.json
y **age 1.3.2**, [release oficial inspeccionada](https://github.com/FiloSottile/age/releases/tag/v1.3.2),
para cifrado autenticado streaming X25519 de un tar de formato versionado; no extender
el envelope AES-GCM en memoria del harness Foundation a backups completos. Justificación:
herramienta estándar fuera del runtime API, sin protocolo criptográfico propio ni
SDK de nube. Asset/digest/licencia quedan fijados en la imagen ops entregada y sus pruebas;
la consulta de release por sí sola no acredita cifrado o recuperación.

Las [plantillas entregadas](../../deploy/scheduling/opengym.cron) de cron Linux y
Task Scheduler Windows no se instalan desde la app: backup cada 3 h y al inicio si
han pasado 3 h desde snapshot verificado, restore-rehearse mensual y
diagnostics-retain cada hora. Cada job ejecuta comando
puntual con config/rutas explícitas y código de salida observable, sin GUI/secretos
en argumentos. Backup/migrate/maintenance-recover entran por wrapper host; ops directo
rechaza captura/migración sin prueba de parada de escritores y exclusión vigente. Mutex operativo de sesión PostgreSQL **728322**, compartido con
migrador/importador/restore: segundo proceso falla en <= 5 s sin ejecución solapada.
El wrapper del host añade exclusión local por instance_id antes de controlar Compose;
no depender solo de un lock DB que desaparece si muere el proceso ops.
Una tarea mensual solo tiene permiso sobre proyecto/volumen de ensayo aislado, no
sobre el volumen activo. Autorizar programación real pertenece a GO, no a este plan.

### Uso de las plantillas de programación

En `deploy/scheduling/`, `opengym.cron` contiene los cuatro jobs Linux;
[windows-backup.xml](../../deploy/scheduling/windows-backup.xml),
[windows-startup.xml](../../deploy/scheduling/windows-startup.xml),
[windows-restore.xml](../../deploy/scheduling/windows-restore.xml) y
[windows-retain.xml](../../deploy/scheduling/windows-retain.xml) son definiciones
Task Scheduler, no instaladores. La plantilla manual
[windows-pre-migration.ps1](../../deploy/scheduling/windows-pre-migration.ps1) recibe
`-Node`, `-Repository` y `-Config` absolutos y propaga el exit code, sin DDL.
Sustituir rutas absolutas de Node/release/config y
`OPERATOR_ACCOUNT` por la cuenta privada del operador. No usar SYSTEM ni compartir
credenciales de la cuenta; la instalación autorizada entrega su contraseña por la
interfaz del sistema, nunca en XML, argumentos o repositorio. La cuenta debe poder
usar Docker y leer las claves privadas sin exponerlas a otros usuarios.

Las horas usan la zona del host. Linux no recupera ejecuciones omitidas; `@reboot`
comprueba antigüedad una vez. Windows usa `StartWhenAvailable`, `IgnoreNew` por tarea
y límites de ejecución; estos no sustituyen la exclusión host/PG entre tareas.
En cron, conservar rutas entre comillas si contienen espacios y no usar `%` en las
rutas (cron lo interpreta antes del shell). Asegurar que Docker y los recursos
seleccionados estén disponibles antes de invocar; fallo al boot no es éxito ni
habilita un bucle de reintentos. No ejecutar estas plantillas contra la instancia
personal sin autorización operativa separada.

`operate backup --reason startup` reutiliza la config privada de backup. Dentro de
la exclusión existente rechaza primero journals sin resolver; solo con `bundle`
configurado, gate admitido y recibo propio válido de snapshot **<3 h** devuelve
`BACKUP_NOT_DUE`/exit **0**, `verified:false` (no produce ni acredita una copia nueva).
Recibo ausente, inválido, ajeno, futuro o vencido no permite omitir captura. Es una
lectura de evidencia previa, no prueba de disponibilidad actual del disco externo.
A las **3 h** intenta captura; a más de **6 h** la señal diagnóstica indica RPO
excedido. Scheduled y pre-migration nunca se omiten por antigüedad. Lock ocupado
falla sin esperar ni liberarse por TTL. El arranque interno del wrapper no invoca
startup: no hay recursión ni modificación del arranque API.

`operate diagnostics-retain --config <backup-host.json>` reutiliza selección
Compose explícita del operador. Exige imagen diagnóstica por ID, contenedor vivo,
volumen de logs propio y permisos restringidos; ejecuta `rotate` dentro del colector
con su lock existente, sin necesitar disco/clave de backup disponibles.
Puede funcionar con API detenida; si el colector está parado,
no lo arranca y devuelve fallo. Su supervisor ya aplica retención horaria sin API;
esta tarea permite la invocación explícita, sin segundo motor de retención ni
borrado de backups. Imagen/propiedad inválidas o mutex de retención ocupado fallan.

El job mensual invoca `operate restore-rehearse` con su propia config privada de
**destino nuevo**. El operador debe preparar nuevo target/config y revisión privada
para cada ejecución; no se recicla automáticamente un destino usado ni se fabrica
revisión o evidencia cliente. Config no preparada, revisión ausente o prueba parcial
fallan: no prometemos ensayo mensual desatendido. El comando pre-migración figura
como instrucción manual en cron, no como job con DDL: sigue detenido/bloqueado y
su código no cero debe impedir que un script continúe la migración.

Observar `LastTaskResult` en Windows y conservar salida/estado del proceso mediante
el mecanismo privado de monitorización del operador en cron. El éxito del scheduler
no sustituye el código del comando: **0** significa punto verificado, startup no
vencido, retención ejecutada o ensayo completo según el comando; **1** indica fallo,
parcial, hold o exclusión; **2**, uso/config inválidos. No silenciar fallos con
`|| true`. Una terminación por límite exige revisar journal y recuperación explícita,
no borrar locks. Las plantillas no instalan alertas ni acreditan RPO/RTO por horario.
Verificar sin instalar jobs: `node scripts/platform.mjs verify backup --case scheduling_and_age`.

### Backup, barrera y estado recuperable

La barrera operativa es la parada comprobada de escritores, no un protocolo interno
de leases. El wrapper host `node scripts/platform.mjs operate <command>
--config <absolute-operator.json>` entrega backup, maintenance-recover y
diagnostics-retain; migrate sigue pendiente;
backup exige además `--reason scheduled|startup|pre-migration`;
controla Compose por argv allowlisted, sin shell ni flags arbitrarios. Es tooling
host, nunca dependencia de la imagen API. Captura/cifrado/restore siguen en ops.
S10 entrega estos comandos por fases; están disponibles captura SQL/archivos y
recuperación explícita del journal y bundle opcional descritos arriba. Sin `bundle`,
captura devuelve fallo explícito; recuperación exit 0 no acredita una copia nueva.
Esto no entrega `migrate` ni desbloquea pre-migración.

1. Backup scheduled/startup/pre-migration ejecuta preflight y exclusión host por
   instancia; el proceso ops toma además el mutex PG compartido. Registrar proyecto,
   operación, fase y si API estaba activa en un journal privado atómico antes de
   detenerla. Config explícita, sin .env implícito ni recursos de otra instancia.
2. Detener API con deadline de cierre 30 s y comprobar que no quedan escritores
   propios, incluidos coach, audit, upload/GC y schedulers. Si no puede acreditarse
   cierre limpio, abortar captura. Una llamada coach interrumpida puede tener coste
   externo sin resultado guardado; no reproducirla automáticamente. El proxy puede
   devolver indisponibilidad temporal; comprobar que cliente conserva dirty/active.
3. Capturar con API detenida: dump PG consistente con rol backup y copiar archivos
   estables a staging 0700 en almacenamiento cifrado. Presupuesto de captura 120 s;
   si se excede, cancelar y esperar cese de procesos antes de recuperar servicio.
   No copiar PGDATA caliente. Registrar snapshot_at y comprobar SQL/bytes mediante
   observador independiente. Abortos nunca producen un bundle final.
4. Manifiesto cifrado incluye revisión/heads/major/tools, instance_id, cobertura,
   tamaños/checksums de dump/medios/marcas/config/secretos. Rechazar enlaces,
   dispositivos, traversal y entradas duplicadas; excluir clave age, caches SDK/CLI
   y logs. Catálogo viene del release; pendientes/active cliente requieren G0 aparte.
5. Tras cese de captura, recuperar únicamente servicios que estaban activos y solo
   si revisión/esquema son compatibles. Un fallo de captura recupera servicio cuando
   es seguro y devuelve fallo; no iniciar una API previamente detenida. Si muere el
   wrapper, journal conserva la fase. maintenance-recover toma exclusión, comprueba
   ownership y cese de procesos antes de recuperar; no apertura por TTL. Un reinicio
   host no arranca API si el journal indica captura sin resolver; el entrypoint solo
   comprueba ese bloqueo local, sin migrar ni implementar leases/socket.
6. Fuera de pausa cifrar vía age, copiar `.partial`, fsync, releer/decrypt hasta EOF,
   verificar checksums y rename atómico. Solo después actualizar punto verificado.
   Error no desplaza última copia válida; limpiar staging propio tras verificación
   o registrar cleanup pendiente protegido. Retener bundles 30 d; > 3 h advierte y
   > 6 h incumple RPO según snapshot_at del último bundle verificado.
7. Migración usa el mismo wrapper y exclusión: detener escritores, obtener backup
   pre-migración verificado antes de DDL en instancia poblada y no reiniciar API entre
   copia y migración. Arrancar solo tras revisión compatible; fallo conserva estado
   bloqueado y datos actuales. Backup startup no vuelve a dispararse al reinicio
   interno del wrapper; comprobar antigüedad una vez por invocación, sin recursión.

Probar fallos antes/durante/después de parada, captura, reinicio y transferencia;
interrupción del wrapper y host, API inicialmente detenida, mutex ocupado, timeout,
escritor externo y cliente dirty/offline. Retener evidencia de pausa medida y
sentinels propios/ajenos. No afirmar recuperación ni RPO por mera programación.

### Restore de datos entregado (cuarentena)

`operations restore --config <privado> --bundle <hex32> --target <new-id>` entrega
solo SQL/archivos a un **destino nuevo y cerrado**. No abre tráfico, revisa credenciales,
rota firma, reconcilia clientes ni acredita Q1/RPO/RTO. Usa el fichero **standalone**
`deploy/docker-compose.restore.yml`: nunca combinarlo con los overlays activos.
Solo define DB/bootstrap/migrate/ops, sin API/web/jobs/puertos y con una red internal.
No monta Docker socket, origen vivo ni credenciales bootstrap en API.

Mantener custodia exclusiva de Docker, selección/configuración, bundle, clave y
volúmenes destino toda la operación. Antes de crear nada, elegir ID nuevo distinto
al origen (`[a-z0-9][a-z0-9-]{0,47}`) y proyecto exclusivo, por ejemplo
`opengym-restore-restored-b`. Comprobar que **no existan** contenedores/volúmenes de
ese proyecto ni sus nombres exactos `*_restore-postgres-data`/`*_restore-data`,
incluso si les faltan labels. Si existen, parar y elegir otro destino; nunca vaciar
un volumen para forzar el preflight. No usar el nombre/proyecto/volúmenes de la
instancia activa. Inspecciones y montajes RO no congelan escritores host arbitrarios.

Provisionar tres contraseñas **nuevas** (bootstrap/migrator/runtime, 32–4096 caracteres
sin saltos internos), ficheros privados con esos nombres; no reutilizar contraseñas
de roles del origen ni las capturadas. Preparar directorios 0700/ficheros 0600 en
POSIX y ACL privada en Windows, sin enlaces/hardlinks. Bundle/identidad/configuración
host son binds RO, con `create_host_path: false`; identidad separada, no Compose secret.
El volumen Linux `restore-data` se inicializa desde `/data` de ops con UID 1000/0700.
Comprobar almacenamiento cifrado y capacidad de **ambos** volúmenes con el operador:
solo se sondea espacio libre del root de extracción (bytes declarados +32 MiB), no
capacidad física del volumen PostgreSQL ni cifrado/disco independiente.

Configuración privada de restore (rutas **dentro** del contenedor):

```json
{
  "instance_id": "restored-b",
  "target_root": "/data",
  "bundle_root": "/bundles",
  "identity_file": "/identity"
}
```

El env-file host privado contiene `PLATFORM_RESTORE_TARGET=restored-b`,
`PLATFORM_MIGRATE_DIGEST`/`PLATFORM_OPS_DIGEST` (64 hex, imágenes compatibles ya
construidas, ops con restore), `PLATFORM_RESTORE_SECRETS_DIR`,
`PLATFORM_RESTORE_BUNDLES`, `PLATFORM_RESTORE_IDENTITY` y `PLATFORM_RESTORE_CONFIG`
(rutas host absolutas). Solo referencias/pins, nunca valores de secretos en env/argv.
Limpiar `COMPOSE_*` heredadas y usar siempre `--env-file`, fichero standalone y
`--project-name` explícitos. Con ese prefijo fijo:

```sh
docker compose --env-file /private/restore.env --project-name opengym-restore-restored-b -f deploy/docker-compose.restore.yml up -d --wait db
docker compose --env-file /private/restore.env --project-name opengym-restore-restored-b -f deploy/docker-compose.restore.yml run --rm --no-deps bootstrap
docker compose --env-file /private/restore.env --project-name opengym-restore-restored-b -f deploy/docker-compose.restore.yml run --rm --no-deps migrate
```

Aplicar también `backend/backup-role.sql` al **nuevo** DB con su psql local privilegiado,
como en preparación de captura (sin copiar password histórico). Luego ejecutar en
ese DB este SQL, sustituyendo el ID por el mismo de configuración/CLI:

```sql
COMMENT ON DATABASE opengym IS 'opengym-restore:restored-b';
REVOKE CONNECT ON DATABASE opengym FROM opengym_api_runtime;
```

Bootstrap/migrador son one-offs terminados; nunca API startup. El restore requiere
ese ownership explícito, head y catálogo de tablas exactos (ninguna tabla ajena,
tampoco en otros esquemas), tablas vacías salvo defaults canónicos, runtime
sin CONNECT, ningún otro cliente DB y mutex de sesión 728322 libre. No mantiene TX
mientras descifra/transfiere. Con el mismo prefijo Compose:

```sh
docker compose --env-file /private/restore.env --project-name opengym-restore-restored-b -f deploy/docker-compose.restore.yml run --rm --no-deps ops -m opengym_platform.operations restore --config /run/operator/restore.json --bundle <hex32> --target restored-b
```

Solo seleccionar bundles propios bajo custodia: age autentica integridad/EOF, **no
identidad del autor** que conocía el recipient público. Comprobar procedencia/hash
contra evidencia privada protegida antes de entregar un dump a tooling privilegiado.
Primero relee/autentica el bundle completo sin extraer, valida versión v1/major PG/
head/tools/cobertura/inventario y espacio. Luego extrae en directorio nuevo 0700 con
filtro `tarfile.data_filter`, USTAR estricto sin extensiones/enlaces/tipos especiales,
traversal/duplicados, máx. 100.000 entradas/profundidad 64/manifiesto 32 MiB. Segunda
pasada también exige EOF age; contrasta `capture.json` para no omitir secretos/config
y **relee archivos extraídos** con tamaños/SHA-256 antes de cargar SQL. Comprueba
ciphertext estable alrededor de extracción/carga; originales no se modifican.

Roles/ownership/grants/FORCE RLS y funciones proceden del bootstrap/migraciones
confiables del destino, **no de DDL/ACL/passwords del dump**. pg_restore aplica solo
datos/secuencias, sin owner/ACL, con triggers temporalmente deshabilitados y TX única
(timeout 300 s), tras vaciar exclusivamente las tablas de ese destino acreditado.
El TRUNCATE incluye solo el catálogo permitido y nunca CASCADE hacia tablas ajenas.
Fallo/commit incierto conserva cuarentena, no rollback a datos viejos ni reintento
automático. Antes de reconciliar/apertura se necesita comparación independiente de
todas las tablas/owners/secuencias y RLS con rol runtime real, no SELECT superusuario.
La prueba sintética aporta esa comparación con referencia independiente conocida;
un exit 0 de este comando no aporta evidencia de vigencia de accesos históricos.

Éxito: `RESTORE_QUARANTINED`, exit 0, `access: quarantined`. Bajo `/data/<new-id>`
quedan datos/medios/GC/temporales, secretos/configuración **en cuarentena**, SQL,
manifiesto y journal/`restore.json` privados, con `q1: pending`, `cleanup_pending: true`.
No activar Compose/config capturados ni instalar secretos históricos como passwords
PG. `gate/admission.json` bloquea arranque y runtime sigue sin CONNECT; futuras API
solo podrán recibir data/gate adecuados, nunca este root con dump/bootstrap/clave.
Cuentas/sesiones/links/jobs conservan snapshot para comparación: su tratamiento y
firma nueva separados de decrypt Coach corresponden a 10.5, no están acreditados aquí.

Clave errónea, corrupción/truncamiento, formato incompatible, inventario incompleto,
espacio o destino ajeno/ocupado/no vacío fallan cerrados. Config/argumentos/destino
no elegible devuelven 2; bloqueo operativo 1. No borrar parciales/directorios/journal
para reusar un intento ni usar `maintenance-recover` para abrirlo: el restore no tiene
reanudar automático. Tras interrupción o respuesta/persistencia incierta, acreditar
cese de sus contenedores/clientes, preservar evidencias y mantener destino cerrado;
elegir otro proyecto/volúmenes nuevos para otro intento. Limpieza/retirada requieren
permiso operativo propio; no hay jobs ni borrado automático de datos/bundle/origen.

`node scripts/platform.mjs verify restore --case isolated_target` reutiliza captura
10.3 y ejecuta esta plantilla con fuentes/roles sintéticos: tablas, secuencias no
triviales, ownership/ACL/FORCE RLS, conexión runtime A/B y password PG nuevo, bytes
medios/GC/secretos/config, rechazo de corrupción posterior a extracción, ENOSPC real
y muerte durante age. Comprueba red/puertos reales y API bloqueada sin bootstrap,
sin atribuirlo a restore completo, Q1, hardware independiente o aceptación operativa.

### Recuperación local de acceso entregada

Después de `RESTORE_QUARANTINED`, la CLI ops `restore-access-recover` entrega la
**vía nueva password**, no continuidad de credenciales históricas. Solo sobre el
mismo target aislado: custodia exclusiva local del operador, sin tráfico/egress,
ningún otro peer DB, `CONNECT` runtime revocado y gate cerrado. No es autorización
para abrir servicios. El operador verifica identidad y decisiones posteriores fuera
de la aplicación; un fichero de revisión no prueba por sí mismo esos hechos.

Montar una revisión JSON propia, 0600 y del UID ops (1000), desde directorio privado;
en Windows conservar además ACL exclusiva del operador en el origen. El fichero
no admite symlinks/hardlinks, duplicados JSON ni campos extra. Ejemplo sintético:

```json
{
  "target": "restore-b",
  "instance_id": "restore-b",
  "bundle": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "snapshot_at": "2026-01-01T00:00:00+00:00",
  "session_secret": "session_secret",
  "coach_secret": "coach_secret",
  "accounts": [{
    "uid": "selected-account",
    "decision": "recover",
    "status": "active",
    "identity_verified": true,
    "evidence": ["referencia privada a comprobación independiente"],
    "password": true,
    "passkeys": ["credential-id-del-snapshot"]
  }]
}
```

`accounts` debe cubrir exactamente **todas** las cuentas restauradas; `password`
indica presencia histórica y `passkeys` enumera todos sus IDs, no una selección a
reactivar. Para las demás usar `decision: "block"`, con estado `active`, `unknown`,
`disabled` o `deleted` y evidencia disponible. Solo `recover` con estado activo,
identidad confirmada/evidencia no vacía y cuenta no disabled en snapshot puede
recibir vía nueva. Los nombres de secretos deben coincidir con los montajes reales
`PLATFORM_SESSION_SECRET_FILE`/`PLATFORM_COACH_SECRET_FILE` de la selección capturada,
no con una clave arbitraria del bundle. ID, roles y Training se conservan.

Con el mismo standalone/env/proyecto de restore, añadir el mount RO de la revisión:

```sh
docker compose --env-file <restore.env> -f deploy/docker-compose.restore.yml \
  run --rm --no-deps --volume <revision-privada>:/run/operator/review.json:ro \
  ops -m opengym_platform.operations restore-access-recover \
  --config /run/operator/restore.json --target restore-b --review /run/operator/review.json
node scripts/platform.mjs verify restore --case reviewed_access
```

Éxito: `RESTORE_ACCESS_REVIEWED`, exit 0, **todavía cuarentena**. Bajo
`<target_root>/<target>/access/` (0700), ficheros 0600 exclusivos contienen:
`review.json`, `session-secret` nuevo, `coach-secret` original, `credential-N.json`
(UID, identifier aleatorio y password aleatorio) y `result.json`. Entregar cada
credencial únicamente a la persona verificada por canal privado; no copiarla a
argv/env/logs/terminal grabado. Es una contraseña normal, no token público ni
contraseña de un solo uso. No dar a la futura API el directorio `access` completo.
Una apertura **separadamente autorizada** deberá seleccionar firma nueva y decrypt
original por sus respectivos ficheros, habilitar `PASSWORD_LOGIN=1` y montar solo
sus secretos runtime; nunca bootstrap, revisión, dumps ni credenciales de entrega.

La transacción bloquea cuentas no seleccionadas, retira passwords/passkeys históricos
activos y claims de nombre/reset, elimina resets/links y marca jobs interrumpidos
failed/restart sin replay; deshabilita Coach. Bundle/material original siguen
protegidos e intactos. No elimina datos de negocio de cuentas bloqueadas ni acredita
purga de cuentas posteriormente eliminadas. No abre gate ni `CONNECT`, no entrega
push ni prueba proveedor externo. Ceremonias y timers son efímeros: ninguna API
restaurada corre durante este paso.

Fallo: exit 1/`RESTORE_ACCESS_BLOCKED`, sin detalle sensible. Si existe `access/`,
aunque falte `result.json`, **no borrar ni reintentar**: conservar incertidumbre y
revisar bajo custodia; elegir un target nuevo para otro ensayo. Un fallo SQL revierte
los cambios de acceso; un fallo después del commit no se supone rollback. Esta
salida no acredita apertura, continuidad de credenciales históricas, RPO/RTO completo,
autenticador físico ni identidad de personas reales. El navegador sintético de
`verify training_browser` cubre además dirty/linaje/respuesta perdida con su propio
restore controlado, no una instancia real ni clientes reales.

### Ensayo mensual entregado y medición completa

El comando del **host**, no un subcomando dentro de API/ops, es:

```sh
node scripts/platform.mjs operate restore-rehearse --config /srv/opengym-private/rehearsal.json
node scripts/platform.mjs verify restore --case full_timing
```

Reutiliza el restore/vía nueva anteriores. Preparar primero el proyecto standalone,
cluster/roles/esquema nuevos, ownership comment y `CONNECT` revocado según
[restore de datos](#restore-de-datos-entregado-cuarentena). No crear un segundo
runtime productivo ni reutilizar el proyecto/volúmenes de la instancia activa.
El coordinador comprueba también la DB **en ejecución**: imagen seleccionada, salud,
puertos ausentes, red interna única y ningún peer Docker desconocido; no basta que
el YAML parezca aislado. Las imágenes deben existir localmente por ID inmutable;
no construye ni instala dependencias al operar. Solo ops contiene el observador.

Declarar el incidente **antes de buscar/seleccionar bundle y revisar accesos** y
conservar su hora UTC real en la configuración privada. Preparar la revisión de
10.5 con evidencia independiente del bundle/target elegido; su fichero no puede
preceder al incidente. El tiempo desde esa declaración hasta invocar la CLI se
informa como `preparation_including_review`, sin fingir que puede separar cuánto
fue búsqueda y cuánto revisión humana. La declaración y veracidad de la revisión
son responsabilidad del operador bajo custodia local, no una medición forense de
identidad ni una garantía contra un host arbitrario.

Configuración host mínima; sustituir rutas/IDs y hora por los reales del ensayo:

```json
{
  "instance_id": "monthly-2026-11",
  "project": "opengym-restore-monthly-2026-11",
  "project_directory": "/srv/opengym",
  "compose_files": ["/srv/opengym/deploy/docker-compose.restore.yml"],
  "env_file": "/srv/opengym-private/monthly.env",
  "state_root": "/srv/opengym-private/rehearsals",
  "bundle": "0123456789abcdef0123456789abcdef",
  "incident_at": "2026-11-02T00:00:00.000Z",
  "review_file": "/srv/opengym-private/monthly-review.json",
  "runtime_image": "sha256:<64hex-de-la-imagen-runtime-compatible>",
  "verification_file": "/srv/opengym-private/monthly-client/verification.json"
}
```

`env_file` selecciona el mismo target/JSON ops montado como
`/run/operator/restore.json`, pins y secretos **nuevos** de la plantilla standalone.
`state_root` existe de antemano y es privado; ficheros config/review/evidencia 0600,
directorios 0700 y UID propio en POSIX. Windows exige ACL privada del usuario/SYSTEM/
Administrators, no confianza en chmod sintético de Docker Desktop. No rutas relativas,
symlinks/hardlinks de ficheros ni `.env` implícito. Mantener estables configuración,
Compose, binds y fuentes durante todo el ensayo. Se crea exclusivamente
`state_root/<instance_id>/report.json`; un directorio existente bloquea otro intento.
Conservar parciales y elegir target/proyecto nuevo; no hay resume/cleanup automático.

Sin revisión, termina incompleto tras copiar datos, sin habilitar acceso. Con revisión
válida, entrega la vía nueva de 10.5 y cuenta los accesos bloqueados/desconocidos.
`runtime_image` es opcional solo para producir un informe parcial: sin ella no verifica
HTTP/clientes ni acredita RTO. Durante la comprobación autorizada, un guardián ops
independiente mantiene el mutex y concede temporalmente `CONNECT`. API privada no-root,
read-only y sin puertos/egress recibe solo datos restaurados y secretos runtime/firma/
Coach seleccionados, **nunca** bootstrap, dump, bundle, revisión o `access/` completo.
El gate normal del target no cambia; el marcador permitido existe solo bajo
`<target>/rehearsal/keys/gate` para esa sonda privada.

El observador verifica catálogo/owner/FORCE RLS, conexión runtime restringida,
ausencia de contexto ajeno, login/rol y rechazo de sesiones antiguas, hashes de
medios y descarga HTTP, decrypt Coach y retirada de passkeys/links/resets/jobs.
La API dura como máximo **240 s**, por debajo del primer GC automático (300 s);
no entrega push ni invoca proveedores a través de una red externa. El guardián tiene
presupuesto de trabajo global **600 s**, incluido HTTP, y en cierre revoca CONNECT, termina
conexiones runtime, bloquea su marcador y comprueba ausencia de peers. SIGTERM del
guardián también cierra. No se atribuye esa garantía a SIGKILL/pérdida física del
guardián/DB: incertidumbre exige inspección privada y conserva informe incompleto.

#### Evidencia cliente y lectura independiente

`verification_file` es evidencia **explícita del operador**, no un booleano generado
por un login correcto. Si se especifica y aún no existe, el coordinador espera hasta
180 s durante `client_verification`; omitirla produce parcial sin esa espera. El
informe protegido identifica red, nombre de sonda, volumen y `client_subpath`.
Un cliente de verificación dentro de esa red puede montar **solo** ese subdirectorio
RO en `/run/client`: contiene `credential.json` (vía nueva) y `binding.json` (nonce de
operación/target/bundle). Nunca copiar la contraseña a argv/env/stdout/logs; no montar
el directorio `keys` en el navegador. El entorno cliente y su salida deben permanecer
privados, sin publicación de puertos. Ningún comando instala un navegador o un job.

Registrar comprobaciones reales de pendientes dirty, rama restaurada/linaje, respuesta
perdida y persistencia después de reload. Guardar capturas/notas saneadas necesarias
en el mismo directorio privado del JSON, con hashes SHA-256; cada artefacto se limita
a 16 MiB. No reemplazar esas observaciones por marcar checks manualmente sin pruebas.
Formato (valores ilustrativos; nonce/target/bundle vienen de `binding.json`):

```json
{
  "operation": "<nonce-hex32-de-esta-ejecución>",
  "target": "monthly-2026-11",
  "bundle": "0123456789abcdef0123456789abcdef",
  "completed": true,
  "checks": {
    "dirty_preserved": true,
    "lineage_reconciled": true,
    "lost_reply_reconciled": true,
    "persisted": true
  },
  "observation": {
    "uid": "<UID-recuperado>",
    "rev": 12,
    "wid": "<write-id-observado>",
    "sha256": "<SHA-256-UTF8-de-JSON.stringify(state)-del-GET-data-final>"
  },
  "artifacts": [{"name": "client.png", "sha256": "<SHA-256-del-fichero>"}]
}
```

La CLI comprueba binding nuevo, permisos, existencia/hashes de artefactos y lectura
PG independiente de UID recuperado/revisión/wid/contenido **antes** de finalizar el
reloj. Para el hash aplica la proyección pública (sin `_prior`/`_unstamped`) y el
encoder compatible con JSON.stringify ya usado por Training. No convierte una
atestación del operador en prueba automática de todos los clientes reales. El caso
`full_timing` genera esa evidencia con frontend compilado/Playwright, API y PG reales;
su control de rewind SQL pertenece solo al fixture desechable del test.

La invocación de restore se acota a 300 s y recuperación de acceso a 60 s; agotar
un presupuesto deja el ensayo incompleto, aunque todavía queden horas hasta el
objetivo RTO. Esos límites de seguridad no prometen capacidad para cualquier dataset
u hardware. En informe interrumpido, el elapsed persistido llega solo al último
checkpoint; no sustituye el tiempo completo de una recuperación finalizada.

El informe registra alcance efectivo, imagen/host, bytes, snapshot, preparación con
revisión, autenticación age, extracción/verificación, carga SQL, recuperación de
acceso, comprobaciones/cliente y cierre; `elapsed_ms` usa el máximo entre reloj civil
y monotónico más preparación. RPO es incidente menos snapshot verificado; negativo
no satisface objetivo. Los presupuestos son **6 h/24 h**. Sin cobertura, revisión,
cliente, cierre o con accesos `unknown`, `complete`/`rto_credited` son false aunque
pg_restore sea rápido. Bloqueados por decisión resuelta (p. ej. deleted/disabled)
no son accesos recuperados ni una purga de sus datos. `operational_acceptance` siempre
es false; `complete` se refiere al ensayo y alcance comprobado, no a abrir producción.

Salidas: exit 0/`REHEARSAL_VERIFIED` solo con cobertura completa y ambos objetivos;
exit 1/`REHEARSAL_OBJECTIVE_FAILED` si el ensayo es completo pero incumple objetivo;
exit 1/`REHEARSAL_INCOMPLETE` en parcial/fallo/incertidumbre. Uso/config inválidos dan
exit 2. stdout solo resume código/target/complete/admisión; el detalle queda privado.
La muerte del host deja progreso no completado; no inferir éxito ni cierre de un
campo ausente. Si también falla guardián/DB, inspeccionar revocación/gates/contenedores
propios bajo custodia antes de liberar recursos. Mantener bundle/origen intactos.
Esto entrega un comando invocable mensualmente; las plantillas de 10.9 se entregan
por separado y no se instalan. No acredita aceptación de una instancia real ni
disco independiente, y no autoriza corte/Q2.

### Restore aislado y revisión Q1

1. `restore --bundle <id> --target <new-id>` solo acepta destino propio nuevo, sin
   puertos/egress ni jobs externos; nunca in-place ni sobrescritura. Preflight valida
   key, formato/major/revisión, espacio, digests y paths **antes** de extraer; tarfile
   usa filtro seguro y rechaza enlaces/duplicados, además de checksums tras extracción.
   Bundle truncado o secreto necesario ausente bloquea sin activar nada.
2. Bootstrap operativo puntual crea BD/roles de destino aislado; pg_restore con
   credencial privilegiada temporal fuera de API, sin ACL/ownership heredados de
   otros clusters. Reaplicar ownership schema_owner, grants, ENABLE/FORCE RLS y
   configuración de migrador; quitar credencial bootstrap antes de posible tráfico.
   Nunca acreditar SELECT como superusuario como prueba de RLS. Conteos/digests de
   todas las tablas/owners y secuencias deben coincidir antes de reconciliar.
3. Antes de abrir, bloquear todas las cuentas restauradas, eliminar pairings/links/
   challenges y marcar jobs interrumpidos failed/restart sin replay. Generar clave
   **de firma de sesión nueva** para invalidar también tokens emitidos después del
   snapshot; aumentar sv antiguo no basta si colisiona con versiones posteriores.
   Conservar separadamente material original de descifrado coach: rotar firma no
   vuelve ilegibles credenciales. Port normal conserva firma original; esta excepción
   solo corresponde a restore. No habilitar proveedor real durante revisión.
4. Usar revisión manual protegida Q1 por cuenta/credencial con snapshot, fuente
   posterior independiente, cobertura, decisión y comprobación; no crear tabla/ledger.
   Reaplicar bajas y revocaciones verificadas; credenciales dudosas quedan fuera de
   acceso activo. Conservar material excluido en bundle protegido, no borrarlo como
   atajo. Contador passkey requiere último valor/estado verificable, no reset a cero
   ni login aislado como prueba. Password también necesita evidencia de vigencia;
   verificar una passkey no habilita automáticamente password u otras passkeys.
   Alternativamente, restore-access-recover solo sobre destino restaurado aislado
   establece una vía nueva para una cuenta seleccionada explícitamente. Requiere
   control local del host, target/instance_id exactos y confirmación privada por
   cuenta; sin endpoint público, selección automática de admin ni elevación de rol.
   No rehabilita cuentas eliminadas o disabled sin decisión separada sustentada;
   ausencia de identidad verificable bloquea esa cuenta. Credenciales históricas
   dudosas permanecen inhabilitadas; no rotar su contador ni reciclar su material.
   El contrato y la CLI de vía nueva se describen en
   [recuperación local entregada](#recuperación-local-de-acceso-entregada), sin
   secretos en argv/env/logs. No se acredita continuidad de credenciales históricas.
5. Rehabilitar solo cuentas con vías verificadas o recuperadas explícitamente,
   conservando ID, roles y datos, no mediante bootstrap admin automático. Comprobar login sintético autorizado, rechazo de cada vía
   revocada/dudosa, cookie/bearer viejos, rol/runtime RLS, medios/hash/GC seguro,
   propuestas/historia y cliente dirty/linaje/respuesta perdida. Mantener sin egress
   y sin entrega push durante ensayo; disponibilidad SDK/CLI sigue Q6.
6. `restore-rehearse` mide desde declaración del incidente y elección de bundle hasta
   todas las comprobaciones y revisión manual, no solo pg_restore. Publicar alcance,
   tamaño, snapshot_at, tiempo de búsqueda/descifrado/carga/reconciliación/verificación
   y accesos aún bloqueados. Ensayo mensual falla si omite revisión o supera RTO
   24 h para el alcance declarado; un restore parcial no acredita recuperación total.

Fixture mínima: owners A/B, password y passkeys con contador cero/no cero, revocación
posterior de una credencial, B eliminado después del snapshot, un acceso sin evidencia,
un medio referenciado y otro huérfano, pending offline y cambios Training posteriores.
El cliente no se borra; snapshot de servidor antiguo no sobrescribe su dirty local.
Fuente posterior ausente deja acceso bloqueado y reporte incompleto, no aprobación
ficticia de RTO. RPO de pérdida del destino se mide por snapshot verificado disponible.

### Reparación hacia adelante Q2

Modelo obligatorio de ensayo: destino PostgreSQL/medios duraderos supervivientes,
fallo de imagen/config API, migración transaccional fallida o respuesta de commit
perdida. No promete recuperar corrupción/destrucción de los datos supervivientes ni
las escrituras posteriores al último punto si se pierde el destino; ese caso usa
restore/RPO y una decisión explícita sobre pérdida. No ampliar garantías por editar
runbook. Mantener origen Node congelado sin tráfico ni doble escritura.

`node scripts/platform.mjs operate forward-repair --config <absolute-private-host.json>
--incident <id> --release sha256:<compatible-image-id>` pausa escritores,
conserva copia del destino actual y resultados de inspección; compara revisión DB
con release Python de reparación ya probada. Si compatible, restablece esa imagen/
config Python sobre **el destino actual**, no restaura datos viejos. Si requiere
DDL, solo revisión correctiva forward ensayada y backup pre-migración; prohibidos
stamp/downgrade/retorno Node. Resultado de COMMIT incierto se resuelve observando
wid/revisión almacenados, nunca reintentando ciegamente ni afirmando rollback.

La entrega actual sustituye solo la imagen API por su ID local inmutable, conservando
comando, entorno, secretos y mounts seleccionados. Exige el mismo head del destino
y release no-root; no ejecuta DDL correctivo. Una migración transaccional fallida se
repara tras comprobar su rollback y head intacto. Head desconocido o corrección que
requiera DDL mantiene no-go hasta un procedimiento forward ensayado por separado.
La copia coherente SQL/archivos del incidente queda privada y no se presenta como
backup cifrado/verificado ni actualiza el recibo del último punto válido.

El JSON host de mantenimiento añade `repair: {"witness_file": "<absolute-private-json>"}`.
El testigo privado, preparado independientemente del backend, contiene exactamente
`instance_id`, `incident` y `writes`; cada recibo tiene `owner`, `rev`, `wid`,
`state` (GET Training reconocido completo) y `media` (lista de `name` y `sha256`).
Máximo 16 MiB, entre dos y cien propietarios distintos. Se comparan contenido,
revisión y wid actuales, y bytes de medios de la captura coherente; `_prior` y
`_unstamped` internos no forman parte del GET. Nunca generar los recibos a partir
del destino averiado para declarar preservación. Para un COMMIT incierto, incorporar
la observación independiente del resultado sin reenviar la escritura a ciegas.

Tras verificar preservación/compatibilidad, el wrapper recrea únicamente API sobre
el mismo destino y persiste el overlay por digest en `compose_files` del JSON host
antes de reiniciar. Se inicia explícitamente API aunque la imagen fallida estuviera
detenida; otros escritores conservan su estado previo. Éxito requiere readiness,
devuelve `FORWARD_REPAIR_VERIFIED` y libera exclusión. No abre una instancia real
sin su autorización operativa. Fallo iniciado conserva gate cerrado/exclusión y
evidencia para revisión; `maintenance-recover` no admite journals `repair` ni permite
saltarse la comprobación. No borrar locks ni restaurar un snapshot viejo para continuar.

Ensayo independiente: importar origen sintético, reconocer W1/W2 de A/B con payloads,
wid y medios conocidos por cliente/fixture externa al backend, inyectar cada fallo,
reparar y comparar datos actuales/medios con expectativas independientes y nuevas
lecturas HTTP. Verificar además una escritura W3 y acceso/RLS/clientes; contar filas
no demuestra contenido. Falta W1/W2, release incompatible o preservación no demostrada
produce no-go, mantiene mantenimiento y exige resolución del promotor. La reversión
antes de cualquier escritura nueva usa origen validado y una comprobación explícita
de ausencia de nuevos commits; no se infiere de un contador HTTP ni de un timeout.

## Evidencia de aceptación y límites de esta revisión

Inspección de Compose resuelto, aislamiento entre ambientes, rol/runtime/image
inventory, probes y caída/reconexión DB; backup con escrituras concurrentes y fallo
de transferencia; restore mensual aislado con cuenta/passkey revocada después del
snapshot; reconciliación offline; ensayo de corte y fallo después de nuevas
escrituras; confirmación de limpieza externa pendiente y completada.

Registrar revisión, plataforma, comandos, resultados y límites; las cotas/destino
de diagnóstico se verifican según observabilidad. Ninguna prueba, programación,
credencial, directorio operativo, migración o corte se ha ejecutado por aprobar
este documento.
