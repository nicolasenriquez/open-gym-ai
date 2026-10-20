# openGym — instrucciones para agentes

Estas son las instrucciones compartidas del repositorio. Claude Code las carga
a través de `CLAUDE.md`.

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
- `mcp/`: servidor MCP opcional, de solo lectura y por stdio; ver `mcp/README.md`.
- `docs/`: guías indexadas en `docs/README.md` y notas de diseño en `docs/dev/`.
- `website/`: sitio estático del proyecto, desplegado por separado.
- `kubernetes/`: manifiestos de ejemplo.

## Comandos

```bash
# Stack local (servicios api y web)
cp .env.example .env
docker compose up -d --build

# Frontend en desarrollo
cd frontend && npm install && npm run dev

# Tests del frontend
cd frontend && npm test
cd frontend && npm run test:watch
npx vitest run src/lib/progression.test.js
npx vitest run -t "some test name"

# Tests de API y MCP
cd api && npm test
cd mcp && npm test

# Build de producción
cd frontend && npm run build
cd frontend && npm run build:mobile
```

La CI usa Node 22. No hay configuración de ESLint o Prettier; sigue el estilo
del código cercano. Mantén pequeña la huella de dependencias y justifica las nuevas;
consulta los `package.json` para ver las dependencias actuales.

## Reglas de trabajo

- Los cambios que deciden qué levantar o que leen una sesión registrada pertenecen
  a helpers puros en `frontend/src/lib/` y necesitan un test junto al código.
- Añade las nuevas cadenas de UI a todos los locales aplicables y verifica con
  `node scripts/check-locales.mjs`.
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
- El MCP lee los mismos datos del usuario que escribe la API; es opcional y
  no forma parte del stack Docker por defecto.

## Git y despliegue

GitHub (`DuarteSantos8/openGym`) es el repositorio principal. El workflow
`.github/workflows/mirror.yml` actualiza el mirror de GitLab; no hagas push ni
merge manual allí. La CI de GitHub ejecuta las suites del frontend, API y MCP,
las comprobaciones de locales y los builds de imágenes. GitLab CI produce los
artefactos de release.
