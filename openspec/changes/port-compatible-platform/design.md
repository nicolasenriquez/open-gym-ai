## Context

Diseño confirmado mediante rondas Q1–Q20 y consolidado posterior. Solo se autoriza
documentación; el runtime actual continúa Node/JSON. Foundation contiene trabajo
en curso independiente; su harness, fixtures y evidencia no son producto operativo.

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
intermedia, publicación remota o aceptación arm64 no probada.

## Decisions

### 1. Propiedad modular y orden de slices

Identidad y primitivas transaccionales antes del piloto leer/guardar Training;
después medios, administración/notificaciones, coach y formatos/builds cliente.
Cada slice declara entrada/salida/errores, actor/recurso, tablas/almacenes, operación
iniciadora/participantes y recorrido frontend. Service posee transacción; repository
SQL propio; domain puro. Colaboración pública con handle compartido, sin commits
internos ni import de repositorios ajenos.

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

Captura coordinada mediante barrera de escrituras relevantes, incluidos internos;
cifrado/transferencia fuera de pausa. Backup cada 3 h/arranque vencido/pre-migración,
30 días y disco independiente, clave separada; restore mensual. RPO 6 h/RTO 24 h
son objetivos por demostrar. Destino físico y duración de pausa se verifican antes
del corte; no se presumen off-host/PITR ni pérdida completa de equipo cubierta.

Restore aislado sin efectos: invalidar sesiones/tokens, reconciliar bajas/revocaciones
posteriores con información protegida y bloquear acceso no resoluble. No convertir
esta condición en un ledger/event sourcing no aprobado. Diagnóstico privado,
logs 7 d/traces 24 h/métricas 7 d con cotas y borrado por edad verificables.

### 5. Gates y autorización

Foundation debe cerrar sus pruebas requeridas antes del port. GP/GO previos al corte,
G0 e inventario real antes de tocar datos. Corte con escritores detenidos e importación
equivalente; una autoridad. Antes de nuevas escrituras puede revertirse al origen
validado; después requiere recuperación sin pérdida silenciosa. Origen/release/config
protegidos al menos 30 días tras corte aceptado y sin borrado automático. G3/GO
posteriores demuestran independencia del backend sustituido antes de Recovery.

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
posterior. Primero especificar casos, seams y checkpoints por slice, y verificar
Foundation; implementar en entorno sintético. Operación y corte solo después de
evidencia previa e inventario real. Esta autoría no ejecuta los pasos.

## Open Questions

Preferencias de producto/esquema/operación quedan resueltas por el diseño confirmado.
Antes de ejecución: detallar pruebas/seams de cada slice, DDL y funciones, biblioteca
WebAuthn y adaptadores proveedores, herramientas/cotas
de telemetría y fuente protegida para reconciliación restore. Antes de corte:
inventario real, disco/rutas/claves, clientes/orígenes, duración de pausa/ventana y
evidencia G0/GP/GO. Son prerrequisitos técnicos y operativos, no resultados afirmados
ni razón para modificar por defecto decisiones ya aceptadas.
