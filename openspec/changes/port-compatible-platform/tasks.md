## Estado y límites

Plan de entrega futura derivado del diseño confirmado. Solo autoría documental
autorizada: todas las tareas de implementación/ensayo/corte permanecen pendientes.
Depende de Foundation; no altera sus checkboxes/evidencia ni autoriza datos reales,
instalaciones, publicación, migración, sync/archive o despliegue. Antes de ejecutar
cada slice, concretar pruebas/seams y checkpoint con su autorización de entrega.

## 1. Prerrequisitos y esquema

- [ ] 1.1 Verificar cierre de Foundation, contratos de referencia, alcance de cliente/proveedores y pruebas/seams del primer slice; registrar límites y revisión.
  Traceability: compatible-platform-persistence / Phase-bounded compatible capability port / Training pilot follows identity.
- [ ] 1.2 Preparar historial/migrador y entregar incrementalmente el DDL aprobado e índices con el slice propietario, verificando vacío/revisión anterior, constraints, privilegios y fallos reales; separar importador, sin crear tablas futuras solo como scaffolding ni Recovery.
  Traceability: compatible-platform-persistence / Faithful import and retirement parity / Unrepresentable legacy data; local-platform-operation / Controlled images migrations and lifecycle / Incompatible schema or failed migration.

## 2. Identidad y slice piloto Training

- [ ] 2.1 Portar identidad mínima compatible y funciones/roles de acceso; probar aliases concurrentes/Unicode/reset, scrypt/WebAuthn, sesión/revocación y última vía de acceso.
  Traceability: compatible-platform-persistence / Legacy-compatible identity namespace and credentials / Concurrent alias reservation and reset expiry; Credential and account access continuity; Least-privilege access and restricted MCP HTTP / Preauthentication and pool reuse.
- [ ] 2.2 Implementar piloto Training con JSONB/proyecciones y transacción por propietario; probar primer documento, conflicto, stamps/reset/linaje, respuesta perdida, offline/pendientes y recorrido frontend existente.
  Traceability: compatible-platform-persistence / Canonical compatible Training persistence / First write and competing revision; No document and legacy metadata; Phase-bounded compatible capability port / Training pilot follows identity.

## 3. Capacidades restantes y consumidores

- [ ] 3.1 Portar medios, administración y notificaciones con referencias PG, limpieza externa pendiente, cuotas/ownership/GC, endpoint/device, fechas locales y audit compatible; probar fallos y revocación concurrente.
  Traceability: compatible-platform-persistence / Recoverable deletion and compatible audit / External cleanup or audit failure; Compatible notification and coach state.
- [ ] 3.2 Portar coach por operaciones, contadores/job atómicos, propuestas/eventos/olvido y reinicio; verificar proveedores/sandbox y no persistir contenido efímero nuevo.
  Traceability: compatible-platform-persistence / Compatible notification and coach state / Atomic limits and repeated job events; Forget and late provider response.
- [ ] 3.3 Adaptar MCP HTTP y credencial revocable read-only con positivos/negativos y errores; retirar lectura de archivos sin introducir espejo o acceso Recovery.
  Traceability: compatible-platform-persistence / Least-privilege access and restricted MCP HTTP / MCP credential boundaries.
- [ ] 3.4 Trasladar JS neutral canónico y generadores/builds, verificar formatos/catálogo/coach local y recorridos web/mobile pertinentes con frontend conservado.
  Traceability: compatible-platform-persistence / Faithful import and retirement parity / Parity after removing the replaced backend.

## 4. Ambientes e imágenes operativas

- [ ] 4.1 Entregar overlays dev/ops y targets test/runtime/migrate/tooling, comprobar aislamiento/red/egress, pins/caché/inventario, pool/lifecycle y arranque sin instalación ni migración automática.
  Traceability: local-platform-operation / Isolated local Compose operation / Resolved topology and environment isolation; Controlled images migrations and lifecycle / Incompatible schema or failed migration.
- [ ] 4.2 Implementar diagnóstico privado y perfil opcional, cotas/edad efectiva, fallos de exportación y ausencia de datos sensibles; ensayar casos GO.
  Traceability: local-platform-operation / Private bounded diagnostic operation / Age expiry sensitive fixture and unavailable exporter.

## 5. Importación, respaldo y recuperación ensayados

- [ ] 5.1 Entregar importador separado y ensayo sintético representativo, bloqueo de diferencias no fieles y matriz de paridad GP con permisos/cliente/proveedores resueltos.
  Traceability: compatible-platform-persistence / Faithful import and retirement parity / Unrepresentable legacy data.
- [ ] 5.2 Implementar captura coordinada/cifrado/transferencia/verificación y programación local acordada; medir barrera con escritores internos y cliente, fallos de destino y antigüedad.
  Traceability: local-platform-operation / Coordinated encrypted recovery points / Capture with internal writers and failed transfer.
- [ ] 5.3 Ensayar restore completo aislado mensual y reconciliación posterior al snapshot con cuentas/passkeys revocadas, sesiones/tokens y clientes offline; medir objetivos y bloquear acceso no resoluble.
  Traceability: local-platform-operation / Coordinated encrypted recovery points / Monthly complete recovery rehearsal; Restore preserves later security decisions / Deleted account or revoked credential exists in snapshot.

## 6. Corte, retirada y aceptación posteriores

- [ ] 6.1 Antes de autorización de corte real, verificar G0/G1 operativo/GP/GO, destino/rutas/claves, fuente de reconciliación, clientes/orígenes, duración y reversión ensayada; conservar origen/release/configuración.
  Traceability: local-platform-operation / Single-authority cutover and verified retirement / New writes followed by rollback request; Restore preserves later security decisions.
- [ ] 6.2 Ejecutar corte solo bajo autorización operativa posterior, probar autoridad única y recuperación antes/después de nuevas escrituras; retirar dependencias legacy y repetir capacidades/seguridad/operación G3/GO.
  Traceability: compatible-platform-persistence / Faithful import and retirement parity / Parity after removing the replaced backend; local-platform-operation / Single-authority cutover and verified retirement / New writes followed by rollback request; Post-retirement acceptance.
- [ ] 6.3 Consolidar evidencia por EV/gate, actualizar guías al runtime entregado y registrar aceptación de plataforma antes de Recovery; sin borrar originales automáticamente ni acreditar cierre por documentación.
  Traceability: local-platform-operation / Single-authority cutover and verified retirement / Post-retirement acceptance.

## Execution Order

Foundation requerida → 1.1 → preparación de 1.2 → 2.1 → 2.2 → 3.1 → 3.2 → 3.3 → 3.4.
1.2 es criterio transversal: cada slice entrega sus tablas necesarias y el conjunto
se completa al portar las capacidades, sin un paso inicial de tablas vacías futuras.
4.1 prepara infraestructura de desarrollo/CI cuando el port lo necesite; su aceptación
operativa y 4.2 preceden 5.2/5.3. 5.1 puede ensayarse por capacidades durante el port.
No habilitar corte sin 1–5 y gates previos: 6.1 → autorización separada → 6.2 → 6.3.
Cada tarea requiere desglose conductual acotado antes de delivery; este plan no
autoriza implementar la transición completa de una vez.
