# Python Foundation — toolchain prerequisite

Only task **1.1** of [add-python-platform-foundation](../openspec/changes/add-python-platform-foundation/tasks.md) is delivered. No application package, business routes, Compose runner, migrations or Python database proofs exist yet. The ordinary Node/JSON stack and historical Node Foundation are unchanged.

## Pinned environment

[versions.json](versions.json) records immutable multi-platform image references for CPython **3.14.9** (normal GIL, Debian Bookworm slim), uv **0.13.5**, and PostgreSQL/tools **18.6** (Debian Trixie). Execution was verified only on **linux/amd64**, Docker Desktop Linux Engine 29.4.0. Other architectures are not credited.

[pyproject.toml](pyproject.toml) pins the approved direct dependencies; [uv.lock](uv.lock) pins the transitive graph and artifact hashes from verified-TLS PyPI. No prereleases or Uvicorn extras. SQLAlchemy/Alembic are reserved for migrations, not an application ORM. `package = false` is temporary toolchain-only configuration: task 2.2 supplies the actual package.

Direct versions: FastAPI 0.161.1, Pydantic 2.14.1, Uvicorn 0.54.0, asyncpg 0.32.0, Alembic 1.20.1, SQLAlchemy 2.1.6, cryptography 50.0.2; pytest 9.1.1, pytest-asyncio 1.4.0, httpx 0.28.1, Ruff 0.17.2 and mypy 2.4.0.

FastAPI requires `opentelemetry-api` transitively. No OpenTelemetry SDK, collector, exporter or instrumentation was added; this does not satisfy EV-08.

## Reproduce locked installation without host Python

Run from the repository root. Build context is restricted by `.dockerignore` to toolchain manifests. The image copies no instance environment or user data. The verification needs outbound HTTPS for PyPI, but no database, published ports, bind mounts or credentials.

```sh
docker build -t opengym-python-foundation-toolchain-11:local -f backend/Dockerfile.toolchain backend
docker run --rm --read-only --cap-drop ALL --security-opt no-new-privileges --tmpfs /tmp:rw,exec,nosuid,nodev,mode=1777,size=1073741824 opengym-python-foundation-toolchain-11:local sh -ec '
  mkdir /tmp/check
  cp /opt/toolchain/* /tmp/check/
  cd /tmp/check
  sha256sum pyproject.toml uv.lock > /tmp/before
  python --version
  uv --version
  uv lock --check
  uv sync --locked
  uv pip check
  .venv/bin/python -c "import fastapi,pydantic,uvicorn,asyncpg,alembic,sqlalchemy,cryptography,pytest,pytest_asyncio,httpx,ruff,mypy; print(\"All direct imports passed\")"
  uv lock --check --offline
  sha256sum -c /tmp/before
'
```

In Git Bash on Windows, prefix `docker run` with `MSYS_NO_PATHCONV=1` to preserve container paths. No such prefix is needed in PowerShell/Linux. Runtime UID/GID is 1000, root filesystem read-only, and installation/cache exist only in disposable tmpfs. **That tmpfs needs `exec` to load native wheels**; the first import check with Docker's default noexec tmpfs failed, then passed with explicit exec. Do not generalize this to future writable artifact directories.

PostgreSQL binaries can be checked without starting a server:

```sh
docker run --rm --network none --read-only --user 1000:1000 --cap-drop ALL --security-opt no-new-privileges --entrypoint sh postgres:18.6-trixie@sha256:edb0c08dc33befd0262ab3b5cf1c4f3f8cfd8b09e88c05b45adee29d6761ddb6 -ec 'postgres --version; pg_dump --version; pg_restore --version'
```

Remove only the local verification image when finished: `docker image rm opengym-python-foundation-toolchain-11:local`. Base images/build cache may remain; never prune unrelated resources.

## License inventory and evidence

[dependency-licenses.json](dependency-licenses.json) inventories **38 locked third-party distributions**, including Windows-only colorama; **37 were installed on Linux amd64**. Metadata comes from the exact-version PyPI JSON over verified TLS; `mypy-extensions` lacks license metadata, so its installed wheel LICENSE text is preserved as fallback. Classifiers are retained when SPDX metadata is absent. Core tool license declarations are in versions.json; uv's value is the OCI image declaration. This is a dependency inventory, not a legal opinion, OS-package SBOM or vulnerability audit.

Observed prerequisite checks:

- Fresh disposable resolution: stable direct pins and universal lock generated successfully with CPython 3.14.9/uv 0.13.5.
- A separate image built from the saved manifests: `uv lock --check`, `uv sync --locked`, `uv pip check`, all direct imports and offline lock verification **passed**. SHA-256 checks confirmed pyproject/lock unchanged.
- Additional assert-based self-check: installed names/versions exactly matched all 37 applicable inventory entries; interpreter patch and normal GIL matched; **passed**. This is a toolchain check, not behavioral RED or application coverage.
- `postgres`, `pg_dump` and `pg_restore` from the pinned image all reported **18.6**. No server or restore was run.
- Resolution/export initially needed corrections for conditional colorama, wheel-only license metadata and executable tmpfs. None is credited as a behavioral RED. Final clean locked installation passed without reselecting dependencies.

The six test seams and three clarifications are approved in [design §7](../openspec/changes/add-python-platform-foundation/design.md#7-seams-públicas-de-prueba). Runtime tests, PostgreSQL connections, parity, RLS, restore, CI execution and operational gates remain unproven. Task 2.x is not authorized by completion of this prerequisite.
