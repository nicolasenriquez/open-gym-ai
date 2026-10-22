---
type: Research
title: Evolution — evidencia de la investigación arquitectónica
description: Fuentes y límites de la investigación que sustenta Evolution y su inventario previo al corte.
---
# Evolution — evidencia de la investigación arquitectónica

**Estado:** transcripción histórica conservada durante el cleanup del 2026-10-22. Procede de arquitectura §2 antes de separar referencias; no acredita ejecución nueva. Los números de sección y las observaciones puntuales conservan su contexto original. La [arquitectura vigente](../open-gym-evolution.architecture.md) gobierna las decisiones; [§14.1](../open-gym-evolution.architecture.md#141-evidencia-histórica-add-postgres-foundation) enlaza Foundation archivada.

### 2.1 OpenGym

**Evidencia histórica de la investigación original:** checkout `666d9080374a39ab0edd28fc8c15d2a72d153412`. Frontend/API declaran versión `1.4.1`; no se verificó que sea la última versión upstream. Las observaciones de contenedores y datos a continuación corresponden a esa investigación, no a una revalidación del despliegue el 2026-10-22.

Contenedores existentes observados en ejecución y saludables:

- API: `sha256:ecfa3156057b2b76231dc3d4fc598c54913098344d1062e156962a81863a1d20`.
- Web: `sha256:1b7008edb7215f483af7ddd4ba8b769115cb8a88e88c0c25c6a68c5060875b5d`.

Las imágenes etiquetadas `latest` declaran revisión/versión `dev`. Una comparación SHA-256 de los 47 archivos JavaScript y manifiestos encontrados por el recorrido de aplicación API —raíz y árbol `coach`, sin dependencias instaladas— coincidió con los archivos correspondientes del checkout. Esto acredita esa comparación, no la identidad de toda la imagen, dependencias, configuración ni frontend.

No existe `frontend/dist` local para comparar con la imagen web. **Correspondencia frontend/build pendiente:** antes del corte se necesita procedencia reproducible y revisión/digest identificables; no basta la etiqueta `latest`.

El contenedor API monta el `data/` del proyecto en `/data`. En el inventario agregado observado no hay `db.json` ni `state-*.json`; sí existen secretos de instancia y VAPID. No se imprimieron valores de secretos. No se encontraron uploads ni configuración persistida del coach en ese inventario. Es una observación puntual, no prueba de ausencia histórica ni inventario de datos de clientes.

Configuración no secreta observada en API: `RP_ID=localhost`, `ORIGIN=http://localhost:8080`, `DATA_DIR=/data`. **No acredita HTTPS accesible desde iPhone.**

No se ejecutaron suites funcionales, restauraciones, pruebas PostgreSQL ni validaciones Safari durante esta investigación. Estado saludable de contenedores no acredita estos resultados.

**Revisión documental del 2026-10-22:** checkout `2cc7ee1fa110453b71f8790891603b06689c6d86`, rama `docs/opengym-evolution-discovery`. El código de aplicación sigue en Node/archivos y Compose normal mantiene `api` + `web`; no hay backend Python versionado. Foundation completó 18/18 tareas sintéticas y fue archivada; su evidencia es de Node/PostgreSQL, sin corte de autoridad. La revisión no reejecutó suites, servicios ni restauraciones y no acredita G1 operativo, G0/G2–G5, GP o GO. Véase §14.1 para el alcance histórico.

### 2.2 Datos locales de clientes

Pendiente: inventario asistido de navegadores, perfiles y teléfonos realmente utilizados. `frontend/src/store/useStore.js` mantiene estado local (`gym_state_v1`), copias apartadas (`gym_stash`), propietario y metadatos de sincronización; los clientes móviles tienen persistencia específica. También pueden existir medios locales.

Antes del corte: identificar cada origen/perfil, cuenta o modo invitado, trabajo pendiente, sesión activa y medios; respaldar mediante las capacidades existentes y verificar el resultado. Un export ordinario no debe suponerse suficiente para restaurar todos los borradores o metadatos internos. No borrar almacenamiento, cerrar sesiones indiscriminadamente ni cambiar origen antes de resolver este inventario. No se inspeccionaron perfiles personales del navegador ni se accedió al iPhone.

### 2.3 AI Tutor como referencia

Repositorio disponible: `C:/Users/nenri/OneDrive/Desktop/proyectos/pry-ai-evaluator/ai-tutor`, revisión `c28d4c36559218565845c447bcc64a89565881d9`. Solo lectura.

| Evidencia, relativa a AI Tutor | Patrón y utilidad |
| --- | --- |
| `app/backend/db/postgres.py` | Pool `asyncpg` inicializado/cerrado por lifecycle. Aplicar en Python con límites/timeouts y pruebas propias; no importar ajustes pgvector ni dimensionamiento sin verificar. |
| `app/backend/alembic/env.py` | SQLAlchemy async para ejecutar Alembic; acceso de aplicación mediante `asyncpg`, no ORM SQLAlchemy general. |
| `app/backend/evolution_exports/service.py` | Operaciones relacionadas bajo transacción; separar responsabilidades y fallos. No importar el sistema de exportación dental. |
| `app/backend/alembic/versions/0024_condition_corrections.py` | Restricciones, antecedentes de corrección y operación identificable. Referencia para integridad, no modelo de pacientes. Su downgrade no garantiza reversión de datos. |
| `app/backend/routes/patients.py` | Validación explícita y ownership; reutilizar principios, no cuentas clínicas ni dominio dental. |
| `app/backend/tests/conftest.py` | Entorno aislado; PostgreSQL sustituido por defecto y pruebas reales opt-in. No confundir fixtures simuladas con integridad relacional probada. |
| `.github/workflows/ci.yml` | Comprobaciones de calidad, tests y build; no acredita por sí sola ejecución de todas las pruebas PostgreSQL reales. |
| `deploy/Dockerfile`, `deploy/docker-compose.yml` | Lockfiles, etapas, runtime no root y healthchecks. No copiar topología blue/green ni imagen conjunta sin necesidad. |
| `app/backend/main.py` | Migra al arrancar: patrón observado, no recomendado literalmente para OpenGym. |
| `app/backend/clinical_assistant/agent.py`, `llm/tool_loop.py` | Bucle de herramientas acotado y aprobación humana; no se verificó necesidad de LangGraph. |
| `app/backend/pyproject.toml`, `uv.lock` | Gestión con uv y controles Ruff/mypy/pytest; seleccionar versiones compatibles y fijarlas durante la especificación. Mantener las herramientas frontend de OpenGym. |
| `justfile` y override Compose local | Comandos reproducibles de desarrollo. AI Tutor admite tooling en host; proponer verificaciones containerizadas para OpenGym, sin atribuirle una política exclusivamente containerizada. |

La revisión documental revalidó la revisión Git local de AI Tutor, no su runtime. Su CI inspeccionado no acredita por sí solo PostgreSQL real obligatorio. No trasladar OAuth/JWT, bcrypt, Bun, modelo dental, blue/green ni confianza ilimitada en headers de proxy como requisitos de OpenGym.

