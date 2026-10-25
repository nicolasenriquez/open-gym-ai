---
type: Reference
title: Plataforma — autenticación, autorización y auditoría
description: Contrato objetivo de autenticación, autorización, aislamiento y auditoría de plataforma.
---
# Plataforma — autenticación, autorización y auditoría

**Estado:** contrato objetivo autorizado documentalmente el 2026-10-22; implementación y pruebas pendientes. [Arquitectura §12](../open-gym-evolution.architecture.md#12-gates-y-experimentos-antes-de-producción) gobierna los gates. [SELF_HOSTING](../SELF_HOSTING.md), [SECURITY](../../SECURITY.md) y [OpenAPI](../../api/openapi.yaml) describen el sistema actual.

Leer al modificar identidad, sesiones, permisos, consumidores o eventos de seguridad. Esta referencia define el detalle técnico objetivo; el [PRD Evolution](../open-gym-evolution.prd.md) define resultados. La migración preserva la seguridad existente; OIDC/SSO u otros proveedores de identidad son ampliaciones independientes.

## Identidad y acceso

Preservar IDs, passkeys y material WebAuthn, contadores, scrypt/NFKC, passwords opcionales, pairing/device links, cookies y bearer de clientes móviles. Caracterizar firma/encoding, expiración, revocación y límites del sistema Node con fixtures antes del port. Conservar sesiones si es seguro/compatible; reautenticación o reemparejamiento excepcional solo documentado y respaldado por pruebas, preservando pendientes locales. Seleccionar biblioteca WebAuthn compatible; evitar conversión implícita a Google/JWT/bcrypt. El [esquema aprobado](platform-schema.md#identidad-y-acceso) separa nombres visibles, alias y credenciales sin cambiar el mecanismo firmado de sesiones.

Mantener origen/RP ID y HTTPS para publicación, proxy de mismo origen y clientes/subpaths admitidos. Cambiar hostname puede exigir nuevas passkeys; localhost compatible sirve para ensayos, no acredita publicación HTTPS. El contrato CORS/bearer móvil requiere pruebas propias además del navegador. La confianza en headers de proxy se limita a la topología realmente desplegada.

## Autorización por actor y recurso

El servidor resuelve identidad y permisos en cada operación protegida; el propietario procede de esa identidad, no de un campo cliente. Denegar cuando no exista una concesión válida y conservar las rutas públicas y el uso invitado local previstos. Definir la matriz completa de recurso × acción en el cambio implementable, incluyendo lectura, creación, modificación y borrado.

| Actor | Contrato |
| --- | --- |
| Público/invitado | Rutas públicas previstas y Training local; sin acceso a datos servidor privados por conocer un ID. |
| Usuario propietario | Sus recursos según operación y estado de cuenta/sesión. |
| Otro usuario | Sin acceso a recursos ajenos, incluidos medios y operaciones por ID. |
| Administrador | Facultades actuales inventariadas y privilegios explícitos; sin acceso clínico o exportación Recovery implícitos. |
| Coach | Acceso a Training limitado al propietario autorizado; sin privilegios sobre Recovery. Conserva consentimiento y aprobación explícita de propuestas. |

Una autorización que cambió durante una espera no confirma con una sesión obsoleta: definir y probar serialización con revocación, deshabilitación y eliminación. Conservar respuestas HTTP/errores de compatibilidad; validar acceso en backend aunque la UI oculte controles.

## Roles, RLS y datos

Diseño de roles aprobado para el port, pendiente de DDL y pruebas:

| Rol | Facultades |
| --- | --- |
| `schema_owner` NOLOGIN | Posee objetos/esquemas; no atiende peticiones. ENABLE/FORCE RLS y políticas explícitas. |
| `migrator` LOGIN | Puede asumir propietario únicamente en el proceso Alembic puntual; credencial ausente del runtime. |
| `api_runtime` LOGIN | Operaciones autorizadas por contexto transaccional/RLS y funciones allowlisted; sin ownership, DDL, superusuario o BYPASSRLS. |
| `identity_executor` NOLOGIN | Funciones limitadas para preauth y credenciales; grants/políticas solo sobre tablas necesarias. |
| `administration_executor` NOLOGIN | Funciones administrativas concretas, comprobando actor activo, privilegio, versión de sesión y acción/recurso. |
| Rol operativo de backup | Lectura completa explícita y comprobada para dump coherente, separado de runtime y acceso cliente. |

Runtime no puede asumir roles ejecutores; recibe EXECUTE sobre funciones revisadas.
Preauth busca solo material mínimo para verificar una credencial, sin inventar un
owner autenticado ni dar SELECT global a anónimos. Funciones SECURITY DEFINER usan
propietario dedicado, search_path seguro, objetos cualificados, ausencia de SQL
dinámico y EXECUTE PUBLIC revocado; sus políticas/grants siguen siendo explícitos,
no se asume que el nombre SECURITY DEFINER eluda FORCE RLS. Administración coordina
interfaces propietarias con el handle compartido, sin SET owner arbitrario.

- Separar propietario/migrador y runtime; runtime sin DDL, superusuario o `BYPASSRLS`, con privilegios mínimos y sin extensiones anticipadas.
- Fijar contexto de propietario desde el servidor con alcance transaccional y denegar contexto ausente. Probar conexión reutilizada tras commit, rollback, timeout y cancelación.
- Respaldar asociaciones coherentes con propietario mediante constraints/FK; RLS complementa la autorización HTTP y no sustituye estas invariantes.
- Aislar roles/contratos Training para consumidores. RLS Recovery y sus políticas reales se prueban en G4; Foundation utiliza fixtures, sin crear su dominio anticipadamente.
- Deshabilitación/eliminación incluyen estado relacionado y, cuando exista Recovery, sus datos; limpieza de archivos externos recuperable y sin GC destructivo ante error DB.
- SQL parametrizado, validación acotada, límites de cuerpo/rate limits, respuestas privadas/no-store y errores sin payloads personales.

## Secretos y conexiones


### Protección de material y proveedores

Secretos fuera de Git, frontend y logs; separar credenciales runtime/migrador y claves del coach. Proteger rotación, firma de sesiones y restauración de credenciales conforme al contrato. PostgreSQL privado, autenticación y mínimo privilegio; verificar certificados TLS al cruzar redes no confiables o por requisito del proveedor. Las URLs con contraseñas no se registran.

Preservar el sandbox/límites de cada proveedor del coach o resolver su tratamiento explícitamente. Separación de módulos y RLS no son un sandbox frente al administrador del host o un backend comprometido.

## Auditoría y trazabilidad de datos

El audit actual es un registro operativo JSON con retención, borrable por administración; no acredita inmutabilidad. El destino aprobado es `audit.events`, con lectura/clear administrativos explícitos, secuencia conservada y máximos configurables de 90 días/5000 eventos, aplicando ambos límites; IP off por defecto. IDs/nombres históricos no tienen FK destructiva al borrar usuario, e invitaciones consumidas conservan su marca. Inventariar eventos/consumidores y probar recuperación; no incluir credenciales o contenido personal de negocio en nuevos eventos.

Cada evento definido identifica actor/recurso/acción/instante/resultado con datos mínimos; controlar acceso y evitar credenciales, contenido de entrenamiento/rehabilitación o secretos. No copiar nombres o payloads personales al tracing por reutilizar audit. El historial de correcciones Recovery tiene su contrato propio y no se reemplaza por audit operativo.

Política aprobada: preservar best effort de eventos heredados, incluido login y administración, con fallo observable/código seguro. Audit se intenta en unidad separada o después del commit de negocio, sin abortarlo mediante un error SQL de auditoría ni devolver fallo tras éxito confirmado. No prometer entrega garantizada, atomicidad o reintento ilimitado; endurecimiento obligatorio por operación requiere otro cambio explícito. [Telemetría técnica](platform-observability.md) y audit son canales distintos: el muestreo de traces no decide qué eventos de seguridad/historia se conservan.

### Eliminación y restauración

Eliminar cuenta borra datos SQL operativos, desconecta credenciales personales
ligadas del coach y registra limpieza externa pendiente en la misma transacción.
Medios/secretos se eliminan después por sus propietarios; fallo conserva tarea y
señal de pendiente, no resucita acceso ni se presenta como limpieza completa.
Olvidar coach conserva únicamente cuota del día; eliminar cuenta borra su cuota,
conservando agregado de instancia sin vínculo personal.

La [restauración aislada](platform-operations.md#restauración-y-decisiones-de-seguridad-posteriores)
invalida sesiones/tokens restaurados y reconcilia bajas/revocaciones posteriores,
incluidas passkeys. Sin información suficiente, acceso bloqueado hasta revisión;
retención de backups no significa eliminación inmediata de toda copia histórica.

## Evidencia de aceptación

GP antes del corte y G3 después de retirada deben demostrar:

- Login/passkeys/passwords/pairing, sesiones inválidas/expiradas/revocadas y cuentas deshabilitadas; vectores Node/Python y clientes compatibles.
- Lectura/escritura/borrado por actor, IDs de otro propietario, elevación no autorizada y revocación durante espera, preservando el acceso público legítimo.
- Roles reales no exentos, contexto ausente y reutilización del pool; políticas Recovery solo en su etapa.
- Eventos audit definidos, permisos/retención/restore y fallo de escritura identificable; ausencia de credenciales o payloads sensibles en errores y registros.

Registrar revisión, entorno, fixtures, resultados y limitaciones. Una prueba de autenticación correcta no demuestra autorización; mocks o SQL como superusuario no prueban RLS efectivo.

Referencias: [OWASP Authorization](https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html), [OWASP Logging](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html). Los patrones pertinentes de AI Tutor y sus límites están en la [evidencia histórica](../research/evolution-architecture-evidence.md#23-ai-tutor-como-referencia).
