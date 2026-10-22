## Why

La Foundation PostgreSQL archivada verifica Node, no el destino Python/FastAPI del PRD Evolution. El siguiente tramo de arquitectura (§§14–14.2) necesita una referencia de compatibilidad y evidencia sintética propia antes del port de capacidades, sin cambiar la autoridad Node/JSON actual.

## What Changes

- Caracterizar contratos actuales mediante una matriz de capacidades/consumidores y casos sintéticos reproducibles contra Node; dejar preparados sus inputs y expectativas para el futuro port.
- Añadir una aplicación Foundation FastAPI aislada, con pool asyncpg, lifecycle, límites, transacciones y diagnóstico seguro.
- Añadir migraciones Alembic como proceso separado, roles restringidos y pruebas de concurrencia/interrupción; un único migrador para el futuro esquema Python.
- Verificar aislamiento RLS con fixtures de dos propietarios y backup cifrado/restore sintético separado.
- Proveer comandos locales y CI en contenedores, lockfile/versiones verificables y evidencia diferenciada por gate.
- Mantener intactos el stack normal, sus contratos HTTP y la Foundation Node histórica. Sin usuarios reales, corte, funcionalidades Recovery, Garmin o nuevas capacidades IA.

## Capabilities

### New Capabilities

- `platform-contract-characterization`: referencia versionada y casos sintéticos observables de las capacidades actuales para el port posterior.
- `python-platform-foundation`: entorno Python/PostgreSQL aislado, lifecycle, migraciones, privilegios, RLS, recuperación y verificación obligatoria.

### Modified Capabilities

Ninguna. `postgres-foundation` conserva su contrato Node y su evidencia histórica; esta entrega no lo reescribe ni conecta ambos migradores al mismo esquema.

## Impact

Cambio de runtime/tooling, aunque esta fase solo crea la especificación. La implementación añadirá `backend/` como raíz Python, `compose.python-foundation.yml`, un orquestador Node sin dependencias en `scripts/python-foundation.mjs` y un job en `.github/workflows/test.yml`. Node se conserva para frontend, MCP y referencia de compatibilidad.

Dependencias objetivo: FastAPI/Pydantic/Uvicorn, asyncpg, Alembic/SQLAlchemy limitado a migraciones, uv, pytest/pytest-asyncio/httpx, Ruff/mypy y cryptography para cifrado autenticado. Resolver y fijar versiones/licencias en el primer prerrequisito de entrega, dentro de un contenedor desechable y sin instalar herramientas en el host.

Autoridad de alcance: [PRD Evolution](../../../docs/open-gym-evolution.prd.md), [arquitectura](../../../docs/open-gym-evolution.architecture.md), [seguridad](../../../docs/reference/platform-security.md) y [observabilidad](../../../docs/reference/platform-observability.md). Esta entrega contribuye a EV-01/02/03/04/08; no acredita cierre de plataforma EV-05/06/07, GP/GO ni G1 operativo.
