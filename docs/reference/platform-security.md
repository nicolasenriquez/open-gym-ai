---
type: Reference
title: Plataforma — autenticación, autorización y auditoría
description: Contrato objetivo de autenticación, autorización, aislamiento y auditoría de plataforma.
---
# Plataforma — autenticación, autorización y auditoría

**Estado:** contrato objetivo autorizado documentalmente el 2026-10-22; implementación y pruebas pendientes. [Arquitectura §12](../open-gym-evolution.architecture.md#12-gates-y-experimentos-antes-de-producción) gobierna los gates. [SELF_HOSTING](../SELF_HOSTING.md), [SECURITY](../../SECURITY.md) y [OpenAPI](../../api/openapi.yaml) describen el sistema actual.

Leer al modificar identidad, sesiones, permisos, consumidores o eventos de seguridad. Esta referencia define el detalle técnico objetivo; el [PRD Evolution](../open-gym-evolution.prd.md) define resultados. La migración preserva la seguridad existente; OIDC/SSO u otros proveedores de identidad son ampliaciones independientes.

## Identidad y acceso

Preservar IDs, passkeys y material WebAuthn, contadores, scrypt/NFKC, passwords opcionales, pairing/device links, cookies y bearer de clientes móviles. Caracterizar firma/encoding, expiración, revocación y límites del sistema Node con fixtures antes del port. Resolver explícitamente conservación de sesiones o reautenticación controlada y biblioteca WebAuthn Python compatible; evitar una conversión implícita a Google/JWT/bcrypt.

Mantener origen/RP ID y HTTPS para publicación, proxy de mismo origen y clientes/subpaths admitidos. Cambiar hostname puede exigir nuevas passkeys; localhost compatible sirve para ensayos, no acredita publicación HTTPS. El contrato CORS/bearer móvil requiere pruebas propias además del navegador. La confianza en headers de proxy se limita a la topología realmente desplegada.

## Autorización por actor y recurso

El servidor resuelve identidad y permisos en cada operación protegida; el propietario procede de esa identidad, no de un campo cliente. Denegar cuando no exista una concesión válida y conservar las rutas públicas y el uso invitado local previstos. Definir la matriz completa de recurso × acción en el cambio implementable, incluyendo lectura, creación, modificación y borrado.

| Actor | Contrato |
| --- | --- |
| Público/invitado | Rutas públicas previstas y Training local; sin acceso a datos servidor privados por conocer un ID. |
| Usuario propietario | Sus recursos según operación y estado de cuenta/sesión. |
| Otro usuario | Sin acceso a recursos ajenos, incluidos medios y operaciones por ID. |
| Administrador | Facultades actuales inventariadas y privilegios explícitos; sin acceso clínico o exportación Recovery implícitos. |
| MCP/coach | Contrato Training restringido y credencial/propietario verificables; sin privilegios Recovery. El coach conserva sus propuestas/aprobación actuales. |

Una autorización que cambió durante una espera no confirma con una sesión obsoleta: definir y probar serialización con revocación, deshabilitación y eliminación. Conservar respuestas HTTP/errores de compatibilidad; validar acceso en backend aunque la UI oculte controles.

## Roles, RLS y datos

- Separar propietario/migrador y runtime; runtime sin DDL, superusuario o `BYPASSRLS`, con privilegios mínimos y sin extensiones anticipadas.
- Fijar contexto de propietario desde el servidor con alcance transaccional y denegar contexto ausente. Probar conexión reutilizada tras commit, rollback, timeout y cancelación.
- Respaldar asociaciones coherentes con propietario mediante constraints/FK; RLS complementa la autorización HTTP y no sustituye estas invariantes.
- Aislar roles/contratos Training para consumidores. RLS Recovery y sus políticas reales se prueban en G4; Foundation utiliza fixtures, sin crear su dominio anticipadamente.
- Deshabilitación/eliminación incluyen estado relacionado y, cuando exista Recovery, sus datos; limpieza de archivos externos recuperable y sin GC destructivo ante error DB.
- SQL parametrizado, validación acotada, límites de cuerpo/rate limits, respuestas privadas/no-store y errores sin payloads personales.

## Secretos y conexiones

Secretos fuera de Git, frontend y logs; separar credenciales runtime/migrador y claves del coach. Proteger rotación, firma de sesiones y restauración de credenciales conforme al contrato. PostgreSQL privado, autenticación y mínimo privilegio; verificar certificados TLS al cruzar redes no confiables o por requisito del proveedor. Las URLs con contraseñas no se registran.

Preservar el sandbox/límites de cada proveedor del coach o resolver su tratamiento explícitamente. Separación de módulos y RLS no son un sandbox frente al administrador del host o un backend comprometido.

## Auditoría y trazabilidad de datos

El audit actual es un registro operativo JSON con retención, borrable por administración; no acredita inmutabilidad. La migración debe inventariar sus eventos/consumidores, seleccionar una autoridad duradera y definir acceso, integridad, retención, tratamiento de IP y recuperación. Preservar eventos incluidos en el contrato actual y documentar cambios intencionales.

Cada evento definido identifica actor/recurso/acción/instante/resultado con datos mínimos; controlar acceso y evitar credenciales, contenido de entrenamiento/rehabilitación o secretos. No copiar nombres o payloads personales al tracing por reutilizar audit. El historial de correcciones Recovery tiene su contrato propio y no se reemplaza por audit operativo.

La escritura fallida de audit debe ser observable y tener política explícita por tipo de operación. Caracterizar el comportamiento existente y resolver cualquier cambio; no prometer auditoría atómica sin probarla ni cambiar silenciosamente el resultado de una operación ya confirmada. [Telemetría técnica](platform-observability.md) y audit son canales distintos: el muestreo de traces no decide qué eventos de seguridad/historia se conservan.

## Evidencia de aceptación

GP antes del corte y G3 después de retirada deben demostrar:

- Login/passkeys/passwords/pairing, sesiones inválidas/expiradas/revocadas y cuentas deshabilitadas; vectores Node/Python y clientes compatibles.
- Lectura/escritura/borrado por actor, IDs de otro propietario, elevación no autorizada y revocación durante espera, preservando el acceso público legítimo.
- Roles reales no exentos, contexto ausente y reutilización del pool; políticas Recovery solo en su etapa.
- Eventos audit definidos, permisos/retención/restore y fallo de escritura identificable; ausencia de credenciales o payloads sensibles en errores y registros.

Registrar revisión, entorno, fixtures, resultados y limitaciones. Una prueba de autenticación correcta no demuestra autorización; mocks o SQL como superusuario no prueban RLS efectivo.

Referencias: [OWASP Authorization](https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html), [OWASP Logging](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html). Los patrones pertinentes de AI Tutor y sus límites están en la [evidencia histórica](../audit/evolution-architecture-evidence-2026-10-22.md#23-ai-tutor-como-referencia).
