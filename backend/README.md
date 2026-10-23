# Python Foundation — isolated synthetic tooling

[add-python-platform-foundation](../openspec/changes/add-python-platform-foundation/tasks.md): **1.1** supplies the pinned toolchain, **2.1** recorded the first CLI RED, **2.2** supplies the executable environment skeleton, and **2.3** verifies its runtime isolation, cleanup and ordinary Node API startup. Only `environment` runs proofs today. No business routes, Database wrapper, migrations, roles/RLS, recovery, contract baseline or CI job exist yet. The ordinary Node/JSON stack and historical Node Foundation are unchanged.

## Pinned environment

[versions.json](versions.json) records immutable multi-platform image references for CPython **3.14.9** (normal GIL, Debian Bookworm slim), uv **0.13.5**, and PostgreSQL/tools **18.6** (Debian Trixie). Execution was verified only on **linux/amd64**, Docker Desktop Linux Engine 29.4.0. Other architectures are not credited.

[pyproject.toml](pyproject.toml) pins the approved direct dependencies; [uv.lock](uv.lock) pins the transitive graph and artifact hashes from verified-TLS PyPI. No prereleases or Uvicorn extras. SQLAlchemy/Alembic are reserved for migrations, not an application ORM. The importable application package lives in `src/opengym_platform/` and runs via the image's explicit `PYTHONPATH`. `package = false` remains intentional: this application does not need wheel publication or a new build-backend dependency. The manifests, lock and Python dependency inventory from 1.1 are unchanged.

Direct versions: FastAPI 0.161.1, Pydantic 2.14.1, Uvicorn 0.54.0, asyncpg 0.32.0, Alembic 1.20.1, SQLAlchemy 2.1.6, cryptography 50.0.2; pytest 9.1.1, pytest-asyncio 1.4.0, httpx 0.28.1, Ruff 0.17.2 and mypy 2.4.0.

FastAPI requires `opentelemetry-api` transitively. No OpenTelemetry SDK, collector, exporter or instrumentation was added; this does not satisfy EV-08.

## Reproduce locked installation without host Python

Run from the repository root. `.dockerignore` allowlists manifests and Foundation source/tests; this toolchain-only Dockerfile copies only the manifests. The image copies no instance environment or user data. The verification needs outbound HTTPS for PyPI, but no database, published ports, bind mounts or credentials.

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

Observed prerequisite checks (1.1):

- Fresh disposable resolution: stable direct pins and universal lock generated successfully with CPython 3.14.9/uv 0.13.5.
- A separate image built from the saved manifests: `uv lock --check`, `uv sync --locked`, `uv pip check`, all direct imports and offline lock verification **passed**. SHA-256 checks confirmed pyproject/lock unchanged.
- Additional assert-based self-check: installed names/versions exactly matched all 37 applicable inventory entries; interpreter patch and normal GIL matched; **passed**. This is a toolchain check, not behavioral RED or application coverage.
- `postgres`, `pg_dump` and `pg_restore` from the pinned image all reported **18.6**. No server or restore was run.
- Resolution/export initially needed corrections for conditional colorama, wheel-only license metadata and executable tmpfs. None is credited as a behavioral RED. Final clean locked installation passed without reselecting dependencies.

## CLI and environment (2.2–2.3)

From the repository root, with Node 22+ and a trusted Docker Engine/Compose installation:

```sh
node scripts/python-foundation.mjs config
node --test scripts/python-foundation.test.mjs
node scripts/python-foundation.mjs run environment
```

`config` emits effective JSON using only `compose.python-foundation.yml`, an explicit empty env file/project directory and no inherited `COMPOSE_*` overrides. No instance `.env` is read. The Python build context is allowlisted by `.dockerignore`; the root-context Node target uses `Dockerfile.contracts.dockerignore`, which admits API source/manifests and the target runner, not personal directories or host dependencies.

`run environment` prints a unique project, builds its two labelled images, checks the Node target, starts the private disposable PostgreSQL service, runs two Python smoke tests and cleans up in `finally`. The Python tests import the source package/FastAPI, check the interpreter/GIL and exact 37-distribution inventory, then connect with bounded direct asyncpg setup to `SELECT 1`/PostgreSQL 18.6. This is **not** the future `Database` API or a transaction/privilege proof. Successful output includes `FOUNDATION_NODE_API_OK`, `FOUNDATION_NODE_TARGET_OK`, `FOUNDATION_ENVIRONMENT_OK` and `Python Foundation cleanup complete`.

The Node target uses **22.23.2/npm 10.9.8**, reusing the historical immutable base recorded in `versions.json`, without modifying the historical Foundation. It installs the existing API lock with `npm ci --ignore-scripts --omit=optional`. Since 2.3 it starts the unchanged `api/server.js` as a child **before the Foundation DB is started**, with an allowlisted environment, empty private DATA_DIR under `/tmp`, no PostgreSQL configuration and coach disabled. It waits for the actual boot port (10-second deadline), asserts `/api/health` returns 200 and `{ok:true, users:0, writable:true}` (5-second HTTP limit), and confirms the synthetic secret file exists. It stops the child within 5 seconds and removes the temporary directory before emitting success. Forced shutdown fails the check. This replaces the weaker syntax-only smoke; it does not test authentication or the later FastAPI lifecycle. Optional coach SDKs, client/MCP fixtures and real contract cases belong to the contracts slice; no compatibility is credited here.

Only `environment` is implemented. `contracts`, `pool`, `migrations`, `isolation`, `recovery` and `all` are recognized but **exit 1 before Docker**, explicitly unimplemented; unknown/missing groups and malformed/extra arguments also fail. Python/Node target runners likewise reject unavailable groups. Exit 0 means the selected implemented checks **and cleanup** succeeded; Docker/build/startup/test/cleanup failure returns nonzero. Docker subprocesses have a 300-second limit (captured output capped at 4 MiB), DB startup 60 seconds, pytest 60 seconds and the direct probe connection/command/close 5 seconds each. No automatic retries or missing-dependency skips.

Cleanup accepts **only the exact printed** `opengym-python-foundation-test-<16 hex>` project: pass that as the sole argument after `node scripts/python-foundation.mjs cleanup`. It discovers by project label **and** scoped names/tags, checks the **entire** target set's project/marker/service/name before any removal, and refuses shared image tags. It never runs down/prune/remove-orphans. SIGINT/SIGTERM trigger the same cleanup; hard kill or an unresponsive daemon can leave owned resources requiring explicit cleanup. Base images and build caches may remain. This is not protection against a malicious Docker administrator.

Observed on linux/amd64, Windows host Node **24.14.0**, Docker Engine **29.4.0**, Compose **v5.1.1**: the resumed 2.2 baseline passed **7/7**; the integrated 2.3 CLI suite passed **13/13**, zero failures/skips, in about 98 seconds with cached bases/dependencies. The contained Python smoke remains **2/2** and Node **22.23.2** now verifies actual API health without PostgreSQL. Host CLI execution under Node 22, independent clean-checkout execution and remote CI are not credited. The initial 2.2 environment launch failed because unquoted commas in a YAML flow-list tmpfs value became separate mount paths; quoting corrected it, and the repeat passed. That setup correction is not behavioral RED.

Ad hoc checks inside the disposable `foundation-test` container passed: `ruff check --no-cache src tests`, `ruff format --check --no-cache src tests`, and `mypy --ignore-missing-imports --cache-dir /tmp/mypy src tests` (3 Python files). This does not check asyncpg driver stubs or provide the `all`/CI static gate of 9.2. Initial check failures prompted normalized `.py` permissions for Windows build contexts, narrow driver/OS exception handling and formatting; these are not behavioral RED.

The 2.2 environment and stable-success-code cases each had an observed assertion RED before implementation/GREEN. Review-added characterization also checks mislabelled names and unavailable groups; no new RED is claimed for already-working guard behavior. 2.3 evidence follows below. Focused historical Node regression remains **5/5**; strict OpenSpec/OKF/syntax/diff checks passed. Review assumes one local operator with independent run projects, found no additional blockers for this environment slice and no now-false AGENTS rules: production authority remains Node/JSON. This is not readiness for change closeout.

## Real environment verification (2.3)

Reproduce with `node --test scripts/python-foundation.test.mjs`; `config` and `run environment` use the commands above. No production or historical Foundation service is started or modified.

- **Actual isolation:** the suite builds the same Compose services and keeps owned probes alive for inspection. All three run UID/GID 1000, read-only root, zero effective capabilities and kernel no-new-privileges. Docker inspect and `/proc`/filesystem probes verify these settings, tmpfs flags and per-container writable `/tmp` contents that are not shared. The DB alone mounts its exact named volume, all services use the sole internal project network, and none has published ports, host binds or Docker socket. The fresh DB has zero public tables: no migration/history is reused or applied.
- **Ownership and preflight:** project, marker, service and name mismatches reject cleanup. A deliberately added second image tag makes cleanup reject the entire live set **before** deleting verified containers/volume. All probe containers remain running; the unrelated empty sentinel volume's inspect metadata remains unchanged. Removing only that test-created alias allows exact-project cleanup, after which both project-labelled and scoped name/tag queries are empty. The sentinel is checked before its separately label-guarded test teardown.
- **Failure cleanup:** an allowlisted temporary checkout copies only CLI/Compose/empty-env inputs and supplies two minimal pinned-image fixture targets. The Python fixture connects to the actual disposable DB, then emits `FOUNDATION_EXPECTED_TEST_FAILURE` and exits 23. The real CLI returns 1, performs automatic cleanup and preserves the sentinel, despite poisoned synthetic `.env`/Compose/password settings. This characterizes already-working failure handling; it is not a substitute for the real Python/Node success checks. A separate fixture runs the actual Node target against a valid API process that deliberately exits 23 before readiness: the target/CLI fail without success markers, do not proceed to the Python target, and clean up.
- **Hard kill:** a second fixture announces a coordinated ready marker after connecting to DB, then waits with a finite deadline. SIGKILL of the host CLI demonstrably leaves owned resources; cleanup using the exact printed project removes them. This proves the documented manual recovery path, not graceful signal handling. Windows termination is not credited as Linux SIGINT/SIGTERM handler execution; those graceful paths remain unverified here.
- **RED/GREEN and harness correction:** the new API-success assertion first failed because the otherwise successful environment run lacked an actual API health proof; adding the real HTTP smoke made it pass. Other additions characterize existing behavior. The first inspection incorrectly expected `HostConfig.Binds` to be empty: Docker also serializes legitimate named volumes there. The corrected test checks the exact owned volume and `Mounts.Type`; no host-bind prohibition was relaxed and no runtime/security defect or behavioral RED is claimed for that correction.

Verification is synthetic and from the current working tree. It completes the slice-2 environment checkpoint, not the complete clean-checkout/Node-22-host/CI scenario or platform gates. No new dependencies, host installations, instance data, published ports, socket mounts or changes to the ordinary stack/historical Foundation. Base images/build cache may remain; final synthetic/probe-labelled container, network, volume and image listings were empty.

## Historical first RED (2.1)

```sh
node --test scripts/python-foundation.test.mjs
```

Historical result before 2.2: **exit 1, three assertion failures** on host Node 24.14.0 and Docker Engine 29.4.0. The current suite passes; this section preserves what the original RED did and did not prove.

- Foreign cleanup with Docker absent from PATH incorrectly exits 0.
- Config emits no effective Compose configuration. Its test prepares an allowlisted temporary checkout with synthetic root/caller `.env` files, Compose overrides and environment markers; isolation assertions are present but **not reached yet**.
- Mixed ownership cleanup incorrectly exits 0. Real Docker inspect first confirms the owned volume, mismatched network and unrelated sentinel volume remain unchanged. These are empty resources, with no containers, data mounts or ports. The test teardown removes only resources bearing its unique probe label, even when the expected assertion fails. Preservation by a no-op does **not** prove cleanup safety.

Focused historical regression: `node --test api/foundation/environment.test.mjs api/foundation/configuration.test.mjs` **passed 5/5**. Strict OpenSpec validation, OKF, syntax and diff checks passed. Probe-labelled Docker network/volume listings were empty after teardown. Scope review found no additional blockers for this RED-only task; the CLI is not ready for operational use.

The one-comment CLI scaffold at that point let Node execute normally, so these failures concerned missing CLI behavior, not a missing module or broken setup. No dependencies were installed during 2.1. The subsequent 2.2 request and explicit approval authorized locked installations/builds in disposable containers only; no host installation or new dependency selection occurred.

The six test seams and three clarifications are approved in [design §7](../openspec/changes/add-python-platform-foundation/design.md#7-seams-públicas-de-prueba). Application lifecycle, transaction/pool behavior, privilege separation, parity, RLS, restore, CI execution and operational gates remain unproven. The current request and its explicit container-build/failure-test approval authorize **2.3 only**; 3.1 and later tasks and change closeout remain outside scope.
