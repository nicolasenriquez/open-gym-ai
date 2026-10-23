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
| Cache SDK/CLI coach | Aislamiento por adaptador, sin acceso a DB ni datos completos; caché renovable excluida del backup conforme al contrato actual y reautorización documentada. |
| Respaldo cifrado | Destino en disco independiente del disco de instancia, con acceso restringido; clave del bundle en lugar separado. Ruta/dispositivo se configura y verifica antes del corte. |

Toolchain parte de los pins/lock de Foundation, revalidando compatibilidad operativa;
no duplicar versiones como otra autoridad. Pool por aplicación min=1/max=4 como
punto inicial, conexión/adquisición 5 s, statement 5 s, comando 6 s, lock 2 s y cierre
10 s. Pruebas representativas pueden justificar ajustes explícitos. No mantener
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
  --> invalidar sesiones/pairings/tokens MCP restaurados
  --> reconciliar eliminaciones y revocaciones posteriores
  --> comprobar datos, credenciales, medios y linaje
  --> habilitar únicamente accesos revisados
```

Una copia antigua puede resucitar cuentas o passkeys borradas y retroceder contadores
WebAuthn. Invalidar sesiones no soluciona por sí solo las credenciales históricas.
Conservar información protegida posterior al snapshot para reaplicar bajas y
revocaciones; reconciliación operativa obligatoria antes de habilitar cada acceso.
Si falta información suficiente, mantenerlo bloqueado hasta revisión explícita.
No prometer reconstrucción automática a partir del backup ni crear implícitamente
un segundo almacén/event log general. El procedimiento de corte debe identificar
fuente disponible y cobertura de esta información o bloquear recuperación abierta.

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
después, exportación inversa validada o corrección hacia adelante. Nunca restaurar
silenciosamente una copia vieja perdiendo cambios nuevos.

Retirada de código y borrado de originales son decisiones distintas: cumplir el
plazo no autoriza borrar. G3 y GO posteriores comprueban capacidades, seguridad,
recuperación, diagnóstico e independencia de imports/builds respecto de API Node
retirada; la biblioteca neutral JS y MCP stdio permanecen conforme a sus contratos.

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
