# openGym — instrucciones para agentes

Estas son las instrucciones compartidas del repositorio. La organización y el
mantenimiento se describen en `.agents/README.md`.

## Proyecto

openGym es un rastreador self-hosted de gimnasio y entrenamiento con peso corporal,
con interfaz PWA y shells móviles opcionales para Android/iOS. La app se puede usar
sin cuenta; al iniciar sesión, la API almacena los datos del usuario en el servidor.
Licencia: AGPL-3.0-or-later.

## Mapa del repositorio

- `frontend/`: app React 19 + Vite; `src/lib/` contiene la lógica de dominio,
  `src/views/` las pantallas y `src/components/` los componentes compartidos.
  `android/` e `ios/` son shells Capacitor; ver `docs/MOBILE.md`.
- `api/`: backend Node.js con `node:http`; `server.js` implementa la API.
  `coach/` contiene el coach opcional y `openapi.yaml` describe las rutas.
- `web/`: imagen multi-stage que construye el frontend y lo sirve con nginx;
  nginx también hace proxy de `/api`.
- `catalogue/`: catálogo de ejercicios y medios. `catalogue/media/` se incluye
  en la imagen web; no hay un servicio Compose separado que descargue estos medios.
- `docs/`: guías indexadas en `docs/index.md` y notas de diseño en `docs/dev/`.
- `website/`: sitio estático del proyecto, desplegado por separado.
- `kubernetes/`: manifiestos de ejemplo.

## Comandos

```bash
# Stack local (servicios api y web)
cp .env.example .env
docker compose up -d --build

# Frontend en desarrollo
cd frontend && pnpm install --frozen-lockfile && pnpm run dev

# Tests del frontend
cd frontend && pnpm test
cd frontend && pnpm run test:watch
pnpm exec vitest run src/lib/progression.test.js
pnpm exec vitest run -t "some test name"

# Tests de API
cd api && pnpm test

# Build de producción
cd frontend && pnpm run build
cd frontend && pnpm run build:mobile
```

La CI usa Node 22 y pnpm 10.34.8; `corepack enable` activa el gestor fijado.
Oxlint verifica errores de corrección; no hay formateador automático. Sigue el estilo
del código cercano. Mantén pequeña la huella de dependencias y justifica las nuevas;
consulta los `package.json` para ver las dependencias actuales.

## Reglas de trabajo

- Los cambios que deciden qué levantar o que leen una sesión registrada pertenecen
  a helpers puros en `frontend/src/lib/` y necesitan un test junto al código.
- Añade las nuevas cadenas de UI a todos los locales aplicables y verifica con
  `node frontend/scripts/check-locales.mjs` desde la raíz.
- Antes de tocar autenticación, sesiones o notificaciones, lee
  `docs/SELF_HOSTING.md`; los despliegues dependen de su contrato de variables
  de entorno.
- No confirmes datos de usuario en `data/` ni los directorios locales heredados
  `media/img/` y `media/gif/`. `catalogue/media/` es distinto: forma parte del
  catálogo y se empaqueta en la imagen web.
- Para arquitectura y comportamiento detallados, consulta `README.md`,
  `CONTRIBUTING.md`, `docs/` y `api/openapi.yaml` según el área que vayas a cambiar.

## Orientación técnica

- `frontend/src/store/useStore.js` mantiene el estado de la app; `useUI.js`
  contiene estado efímero de interfaz. `frontend/src/lib/` alberga la lógica
  de dominio y helpers puros.
- La API usa almacenamiento JSON bajo `DATA_DIR`, passkeys WebAuthn y cookies
  de sesión firmadas. Las dependencias y las dependencias opcionales están
  declaradas en `api/package.json`.
- WebAuthn depende del hostname exacto y requiere HTTPS, salvo en localhost.
  El proxy de nginx mantiene frontend y API bajo el mismo origen.

## Git y despliegue

Este repositorio es `nicolasenriquez/open-gym-ai`; el upstream es
`DuarteSantos8/openGym`. `.github/workflows/test.yml` concentra la CI.
No hay publicación, despliegue ni mirror automáticos.

## Skills y contexto por tarea

- Mantén las reglas comunes en `AGENTS.md`, las referencias de agentes en
  `.agents/docs/` y las skills en `.agents/skills/`. Conserva esta estructura al
  generar reglas o incorporar skills.
- Para especificar o implementar un cambio formalizado, consulta `openspec/` y sus
  artefactos; los tickets locales de `.scratch/` enlazan esa especificación. Para
  flujos locales de issues y triage, lee `.agents/docs/issue-tracker.md` y
  `.agents/docs/triage-labels.md`.
- Al explorar conceptos del dominio o registrar decisiones, lee
  `.agents/docs/domain.md`: vocabulario en `GLOSSARY.md` y decisiones en `docs/adr/`.
- Para modernización, Recovery o integraciones futuras, empieza en `docs/index.md`
  y sigue el PRD Evolution y su arquitectura. El runtime actual sigue siendo
  Node/JSON; Python/FastAPI/PostgreSQL es una dirección futura sujeta a aceptación.

- Al crear, editar o reorganizar documentación, lee
  `docs/operations/okf-authoring-guide.md` y ejecuta
  `node scripts/docs/okf.mjs check`; el perfil está en
  `docs/standards/okf-profile.md`.
