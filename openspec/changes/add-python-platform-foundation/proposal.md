## Why

La Foundation PostgreSQL archivada verifica Node, no el destino Python/FastAPI del PRD Evolution. El siguiente tramo de arquitectura (§§14–14.2) necesita una referencia de compatibilidad y evidencia sintética propia antes del port de capacidades, sin cambiar la autoridad Node/JSON actual.

La ampliación documental solicitada concreta además EV-09: propiedad por funcionalidad de contratos, reglas, operaciones y consultas, inspirada en AI Tutor y conservando el frontend actual. La [propuesta modular](../../../docs/reference/platform-modularity.md) define el destino y su evidencia. Esta revisión solo ajusta documentación; no autoriza implementación ni acredita resultados nuevos de runtime.

## What Changes

- Caracterizar contratos actuales mediante una matriz de capacidades/consumidores y casos sintéticos reproducibles contra Node; dejar preparados sus inputs y expectativas para el futuro port.
- Añadir una aplicación Foundation FastAPI aislada, con pool asyncpg, lifecycle, límites, transacciones y diagnóstico seguro.
- Añadir migraciones Alembic como proceso separado, roles restringidos y pruebas de concurrencia/interrupción; un único migrador para el futuro esquema Python.
- Verificar aislamiento RLS con fixtures de dos propietarios y backup cifrado/restore sintético separado.
- Proveer comandos locales y CI en contenedores, lockfile/versiones verificables y evidencia diferenciada por gate.
- Colocar la infraestructura Python en `core/` y los contratos/probes internos en `health/`, compuestos por la factory cuando se implementen. Revisar dependencias y documentar módulo propietario/recorrido frontend en la referencia de contratos; no crear aún slices de negocio.
- Verificar caché de las imágenes de ensayo con builds fríos/repetidos, cambios de fuentes/manifiestos y lock incoherente; conservar pins, aislamiento y comandos CI reproducibles. Probar dos colaboradores sintéticos bajo una transacción sin commits internos.
- Inventariar consumidores JS/generadores y preparar su destino neutral `shared/coach-core/`, además de la matriz de ambientes y targets posteriores. El traslado, desarrollo del port e imágenes de operación pertenecen a sus futuros cambios, no a esta Foundation.
- Mantener intactos el stack normal, sus contratos HTTP y la Foundation Node histórica. Sin usuarios reales, corte, funcionalidades Recovery, Garmin o nuevas capacidades IA.

## Capabilities

### New Capabilities

- `platform-contract-characterization`: referencia versionada y casos sintéticos observables de las capacidades actuales, con propiedad modular y correspondencia cliente para el port posterior.
- `python-platform-foundation`: entorno Python/PostgreSQL aislado, lifecycle, migraciones, privilegios, RLS, recuperación y verificación obligatoria; estructura modular acotada a infraestructura y salud.

### Modified Capabilities

Ninguna. `postgres-foundation` conserva su contrato Node y su evidencia histórica; esta entrega no lo reescribe ni conecta ambos migradores al mismo esquema.

## Impact

Cambio de runtime/tooling, aunque esta fase solo crea la especificación. La implementación añadirá `backend/` como raíz Python, `compose.python-foundation.yml`, un orquestador Node sin dependencias en `scripts/python-foundation.mjs` y un job en `.github/workflows/test.yml`. Node se conserva para frontend, MCP y referencia de compatibilidad.

Dependencias objetivo: FastAPI/Pydantic/Uvicorn, asyncpg, Alembic/SQLAlchemy limitado a migraciones, uv, pytest/pytest-asyncio/httpx, Ruff/mypy y cryptography para cifrado autenticado. Resolver y fijar versiones/licencias en el primer prerrequisito de entrega, dentro de un contenedor desechable y sin instalar herramientas en el host.

Autoridad de alcance: [PRD Evolution](../../../docs/open-gym-evolution.prd.md), [arquitectura](../../../docs/open-gym-evolution.architecture.md), [modularidad](../../../docs/reference/platform-modularity.md), [seguridad](../../../docs/reference/platform-security.md) y [observabilidad](../../../docs/reference/platform-observability.md). Esta entrega contribuye a EV-01/02/03/04/08 y prepara parcialmente EV-09; no acredita cierre de plataforma EV-05/06/07/09, GP/GO ni G1 operativo. El slice piloto Training, los módulos funcionales y la adaptación acotada del frontend pertenecen al port posterior.

La [responsabilidad por fase](../../../docs/reference/platform-modularity.md#responsabilidad-y-aceptación-por-fase) separa: Foundation = builds/transacciones sintéticos e inventarios; port = biblioteca JS neutral, desarrollo/CI y casos intermodulares reales; operación = targets entregables, ambientes soportados, caché final y retirada verificada. Esta ampliación solo documenta requisitos pendientes; no cambia permisos, Dockerfiles, código, locks o tareas completadas.
