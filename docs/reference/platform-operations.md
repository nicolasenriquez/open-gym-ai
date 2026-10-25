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
Perfil diagnóstico: herramientas locales opcionales, no servicios de negocio
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
Foundation aislada; futuro `compose.platform.yml` con selección explícita de overlay
dev u ops. Desarrollo usa fuentes en recarga, dependencias Linux y datos sintéticos
separados. Operación usa imágenes identificadas por digest, sin bind de fuentes,
node_modules o .venv ni instalaciones al arrancar. Misma revisión/lock para targets
test/runtime/migrate y herramientas operativas. Mantener una API/un worker inicial.

| Almacén objetivo | Propiedad y protección |
| --- | --- |
| Volumen PostgreSQL | Privado y duradero, distinto entre dev/operación y entre Foundations. No copiar PGDATA caliente como backup. |
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
migra al arrancar. Probes internos live/ready y métricas no se publican por nginx;
`/api/health` mantiene su contrato público compatible. Readiness comprueba DB y
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
Barrera de escrituras --> capturar DB + medios/config/secretos coherentes
                                   |
                            liberar barrera
                                   |
                      cifrar --> copiar --> verificar
                                   |
                      punto recuperable válido
```

La barrera detiene nuevas mutaciones relevantes, espera las transacciones activas
y estabiliza medios/GC; también cubre escrituras internas y GET con efectos. Los
resultados de coach no confirman estado fuera de ella. Medir duración y tratamiento
de deadline antes de aceptar operación; conservar pendientes cliente ante respuesta
de mantenimiento, sin prometer una pausa de duración no medida. Cifrado/transferencia
se realizan fuera de la pausa, desde captura coherente protegida.

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
Si falta información suficiente, el acceso permanece bloqueado: la mera revisión
no permite omitir esa condición ni restaurar contadores WebAuthn dudosos como seguros.
Incluir revisión y verificación en el RTO medido. Un nuevo ledger persistente o almacén
para automatizar reconciliación requiere aprobación expresa del promotor. Antes del
corte identificar fuente y cobertura verificables o bloquear recuperación abierta.

También comprobar pendientes offline y linaje Training. No borrar cliente ni
permitir sobrescritura silenciosa por una restauración. La reautenticación tras
restore es una medida de recuperación; durante el port normal se conserva la sesión
si es segura/compatible y solo se admite excepción documentada probada.

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

## Procedimientos operativos especificados

Son contratos de comandos **futuros**, no herramientas disponibles ni ejecuciones
realizadas. El [plan ejecutable](../../openspec/changes/port-compatible-platform/execution-plan.md)
fija prefijos Compose, suites, flags, salidas y checkpoints. Operador solo necesita
Docker/Compose; Python, PostgreSQL y cifrado corren en target `ops`. No reutilizar
la CLI Foundation fuera de sus guardas sintéticas.

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
SDK de nube. Fijar asset/digest/licencia en imagen ops durante delivery y probar
cifrado/decrypt/truncamiento/clave equivocada; consulta de release no es aceptación.

Entregar plantillas de Task Scheduler Windows y cron Linux, sin instalarlas desde
la app: backup cada 3 h y al inicio si han pasado 3 h desde snapshot verificado,
restore-rehearse mensual y diagnostics-retain cada hora. Cada job ejecuta comando
puntual con config/rutas explícitas y código de salida observable, sin GUI/secretos
en argumentos. Mutex operativo de sesión PostgreSQL **728322**, compartido con
migrador/importador/restore: segundo proceso falla en <= 5 s sin ejecución solapada.
Una tarea mensual solo tiene permiso sobre proyecto/volumen de ensayo aislado, no
sobre el volumen activo. Autorizar programación real pertenece a GO, no a este plan.

### Backup, barrera y estado recuperable

1. `backup --reason scheduled|startup|pre-migration` ejecuta preflight, toma mutex y
   pide mantenimiento por socket Unix privado de control (no socket Docker),
   compartido solo con ops y permisos 0600. Token de instancia/operación y deadline
   identifican al dueño; no endpoint público para detener escrituras.
2. El único worker cierra admisión de mutaciones, incluidos GET con efectos, media
   upload/rename/GC, enlaces/credenciales, audit y resultados/schedulers internos.
   HTTP mutante recibe 503/code `maintenance`, Retry-After 60; probar dirty/offline
   y ausencia de confirmación aparente. Drenar leases activas <= 30 s; no mantener
   TX mientras un proveedor contesta. Resultados externos esperan fuera de TX para
   adquirir lease de commit, o terminan por su timeout normal sin resucitar datos.
3. Deadline de captura <= 120 s después de drenaje; es presupuesto de aborto, no
   duración exitosa prometida. Exportar snapshot repeatable-read; pg_dump custom
   `--enable-row-security --no-owner --no-acl --snapshot=<snapshot>` con rol backup
   y copiar archivos/secretos estables al staging 0700 en almacenamiento cifrado
   configurado. Inventariar cada escritor en prueba; ninguno puede confirmar fuera
   de lease. Mantener snapshot hasta fin del dump. Congelar GC y referencias juntos.
4. Manifiesto dentro del cifrado: formato/revisión/heads/major/tools, instante de
   snapshot, instance_id, cobertura, tamaños/checksums de dump/medios/marcas/config/
   secretos necesarios. Validar paths sin symlink/hardlink/dispositivos/.. y nombres
   duplicados; no incluir clave age, cachés SDK/CLI ni telemetría. Catálogo se recupera
   del release/digest, no duplica medios personales. Sesión activa/pendientes cliente
   siguen fuera de este backup y tienen evidencia G0 separada.
5. Finalizada captura, liberar barrera solo tras confirmar cese de procesos de copia.
   Timeout/fallo descarta captura incompleta. Si muere API/ops, marcador de operación
   en control volume fuerza arranque en mantenimiento; no abrir por TTL solamente.
   `maintenance-recover --operation <id>` verifica mutex libre/procesos cesados y
   propiedad antes de retirar marcador. Probar fallo en cada fase y restablecimiento
   explícito sin bloqueo eterno ni liberación concurrente peligrosa.
6. Fuera de pausa: cifrar tar vía age, copiar como `.partial` al disco independiente,
   fsync, releer/decrypt hasta EOF y verificar manifiesto/checksums. Rename atómico
   a bundle final; solo entonces actualizar último punto recuperable verificado.
   Registrar snapshot_at, verified_at, resultado y duración de pausa/transferencia.
   Tras verificación borrar staging claro propio; crash deja staging protegido y
   señal de cleanup pendiente, nunca una copia contabilizada como válida.
7. Retener bundles verificados 30 d. No borrar última copia válida para hacer lugar
   a una copia fallida; fallar por espacio y avisar. RPO usa `ahora - snapshot_at`
   del último bundle **verificado**, no hora de inicio o transferencia. Punto nuevo
   corrupto/clave perdida no desplaza al válido; > 3 h advierte, > 6 h incumple.

Prueba con upload, GC, credencial, login/last_pull, audit y finish coach concurrentes
verifica snapshot SQL y bytes contra observador independiente; no solo el manifiesto
producido por backup. No descargar/copiar PGDATA caliente ni confundir pg_dump con PITR.

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
5. Rehabilitar solo cuentas con vías revisadas suficientes, no mediante bootstrap
   admin automático. Comprobar login sintético autorizado, rechazo de cada vía
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

`forward-repair --incident <id> --release <compatible-digest>` pausa escritores,
conserva copia del destino actual y resultados de inspección; compara revisión DB
con release Python de reparación ya probada. Si compatible, restablece esa imagen/
config Python sobre **el destino actual**, no restaura datos viejos. Si requiere
DDL, solo revisión correctiva forward ensayada y backup pre-migración; prohibidos
stamp/downgrade/retorno Node. Resultado de COMMIT incierto se resuelve observando
wid/revisión almacenados, nunca reintentando ciegamente ni afirmando rollback.

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
