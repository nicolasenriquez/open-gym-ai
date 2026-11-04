# Compatibilidad del runtime Python

El backend del repositorio es Python/FastAPI/PostgreSQL; sus rutas públicas usan
`/api/v1` y [openapi.yaml](openapi.yaml) es su autoridad HTTP.
El backend Node/JSON, su comparador, manifiestos, generadores y dumps de transición
se retiraron tras adaptar sus consumidores. Esto no migra ninguna instancia.

## Cobertura vigente

| Garantía | Propietario y verificación |
| --- | --- |
| HTTP público, métodos, rutas y respuestas anónimas | `node scripts/platform.mjs verify contracts --case python_routes`; suites de capacidad para comportamiento autenticado |
| Cookie/bearer HMAC, scrypt/NFKC e identificadores compatibles | [respuestas independientes](tests/platform/identity_vectors.py), suites `identity_*` de pytest |
| Passkeys ES256/RS256/Ed25519 y fallos de verificación | [transcripciones públicas firmadas](tests/platform/fixtures/webauthn.json), [expansor](tests/platform/webauthn_vectors.py) y `test_identity_passkey.py`; sin claves privadas |
| Stamps, reset, campos obsoletos, historial y escritura legacy | [regresiones legibles](tests/platform/test_training_stamps.py); HTTP y observación PG independiente en `test_training_lineage.py` |
| Coach neutral, validación, payload, prompts y adaptadores HTTP del cliente | Vitest en `frontend/src/lib/coach-core/`, fuente neutral `shared/coach-core/`; ejecución servidor en suites `coach_*` |
| Importación de fuente congelada y captura de bytes | Importador Python y tooling host `scripts/platform-node-*.mjs`; fixtures de protocolo no son otro backend ni ejecutan handlers Node |
| Catálogo, formatos, móvil, cliente offline, medios y notificaciones | Suites frontend/browser, generadores/builds y suites de capacidad Python registradas en `platform-suites.json` |

Las expectativas son independientes del código probado; no regenerar valores para
aceptar divergencias. El antiguo `contracts --case baseline` se rechaza.
Los comandos operativos y límites pertenecen a [README](README.md), no a un runner
de compatibilidad paralelo.

## Procedencia y límites

La caracterización original inspeccionó `1b2daff9199611604783faabf76cd741123cec95`;
Git y el cambio archivado `add-python-platform-foundation` conservan ese historial.
No necesitan una copia ejecutable del servidor ni volcados completos dentro del
runtime nuevo. La decisión vigente y el cierre pertenecen a
[port-compatible-platform](../openspec/changes/archive/2026-11-04-port-compatible-platform/tasks.md).

La migración real está aplazada. Los ensayos sintéticos no acreditan autenticadores,
proveedores push/coach o clientes reales, custodia/disco físicos ni G0/G2/G3
operativos. No autorizan corte, Recovery ni retirada de datos/configuración originales.
