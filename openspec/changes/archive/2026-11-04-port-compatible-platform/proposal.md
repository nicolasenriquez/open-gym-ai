## Why

El diseño de esquema SQL y operación local ya fue confirmado por el promotor.
Foundation prepara infraestructura y caracterización sintéticas, pero no porta
capacidades ni demuestra recuperación operativa. Hace falta convertir el diseño
acordado en requisitos y slices posteriores, sin ampliar Foundation ni presentar
la aprobación documental como implementación.

## What Changes

- Portar capacidades actuales por módulos con identidad mínima antes del piloto
  Training, frontend conservado y paridad verificable contra la referencia Node.
- Implementar en su fase el esquema aprobado, sus restricciones/índices, contratos
  de autorización, limpieza externa recuperable.
- Conservar JS neutral en shared/coach-core, catálogo, import/export, offline,
  coach local y proveedores HTTP actuales; Claude Agent SDK/Codex CLI quedan
  temporalmente no disponibles por aprobación expresa Q6, sin fallback Node ni
  conversión de credenciales o selección a otros proveedores.
- Entregar imágenes/ambientes separados, logging estándar/diagnóstico privado y
  backup con parada controlada de escritores por wrapper host; mantener copias
  cada 3 h, al arranque si vencidas y antes de migrar, cifrado/retención/restore.
- Extender el harness Foundation por slice sin duplicar cleanup; no anticipar
  browser ni exporter/almacén de telemetría propios.
- Entregar port funcional y operación local recuperable como checkpoints separados;
  ensayar corte/retirada sintéticos y cerrar la entrega del repositorio sin migrar la instancia real.
- Restore: continuidad con evidencia o nueva vía local explícitamente autorizada,
  sin reactivar credenciales históricas dudosas ni elevar roles. Especificar
  autorización/entrega privada antes de ese slice; sin ledger nuevo. Conservar
  reparación hacia adelante tras nuevas escrituras, sin exportador inverso a Node.
- Entregar cleanup revisado del código sustituido y temporales propios antes de
  aceptación, preservando biblioteca neutral, pruebas útiles y recuperación protegida;
  no basta desactivar la implementación anterior ni se autoriza borrar originales.
- Mantener Recovery, Garmin, IA ampliada, despliegue remoto y arm64 fuera de la
  primera aceptación, tratando soporte/clientes actuales expresamente. No entregar
  launcher SDK/CLI, perfil seccomp coach ni scaffolding LangChain/LangGraph; mostrar
  la excepción en cliente/administración y conservar configuración e historia de los
  diferidos y originales protegidos sin activar sus credenciales.

**Estado vigente:** port funcional y tooling de operación implementados/verificados
por slices; [tasks.md](tasks.md) conserva decisiones, progreso y prueba de entrega.
Decisión vigente del promotor: S11 cierra código, pruebas y documentación del repositorio.
La migración/corte y aceptación de la instancia real se aplazan a una intervención
operativa posterior con autorización específica; no son prerrequisito de archive.
11.2 registra ese aplazamiento, no un corte ejecutado. 11.3–11.5 conservan sus
checks de retirada y aceptación del repositorio; no acreditan G0/G2/G3 operativos.
La [guía S11](design.md#contratos-de-ejecución-consolidados) concentra procedimiento y checks reutilizados.
La evidencia sintética no acepta una instancia ni autoriza corte o Recovery.
El resto de la propuesta describe el alcance acordado, no una lista adicional de pendientes.

## Capabilities

### New Capabilities

- `compatible-platform-persistence`: esquema y port modular compatible de identidad,
  Training, notificaciones, coach, auditoría y consumidores vigentes, con cleanup
  verificable; sin reconstruir el consumidor MCP retirado.
- `local-platform-operation`: ambientes/roles/imágenes, respaldo, restauración,
  diagnóstico, corte y retirada verificables para la instancia personal local.

### Modified Capabilities

La sincronización previa en `openspec/specs/` no acreditaba entrega. El repositorio
entrega ahora Python/FastAPI/PostgreSQL; las tareas registran su evidencia sintética
y la migración real aplazada. La Foundation PostgreSQL histórica y sus specs se
conservan. Esta consolidación no sincroniza ni archiva el cambio.

## Impact

Implementación en backend Python, frontend, shared, Alembic, contenedores, CI y
documentación operativa, con estado y evidencia en tasks.md. Node 22+ host sirve
al wrapper operativo; no se incorpora al runtime Python. Las pruebas sintéticas
no autorizan instalar jobs, migrar datos reales, operar o retirar la instancia.
Los diagnósticos Q4/Q5 y Foundation conservan su contexto histórico.

Autoridad: [PRD](../../../../docs/open-gym-evolution.prd.md),
[arquitectura](../../../../docs/open-gym-evolution.architecture.md),
[esquema](../../../../docs/reference/platform-schema.md),
[seguridad](../../../../docs/reference/platform-security.md),
[operación](../../../../docs/reference/platform-operations.md) y
[modularidad](../../../../docs/reference/platform-modularity.md).
Foundation está completada en [su cambio archivado](../2026-10-25-add-python-platform-foundation/proposal.md).
Contribución esperada EV-01–EV-09 y G0/G1 operativo/GP/GO/G2/G3, todos sin acreditar
por esta especificación. Recovery solo comienza después del cierre de plataforma.
