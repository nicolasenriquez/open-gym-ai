# Python Foundation — isolated synthetic tooling

[add-python-platform-foundation](../openspec/changes/add-python-platform-foundation/tasks.md): **1.1** supplies the pinned toolchain, **2.1–2.3** supply and verify the isolated environment, **3.1–3.2** supply contract inventory/comparison/execution, and **3.3** verifies per-area coverage and completes the port inventories. `environment`, `contracts` and `pool` are available. **4.2** implements the bounded Database interface and its focused synthetic tests; it is not an operational application or platform acceptance. No Python business routes, migrations/role provisioning, RLS, recovery or CI job exist yet. The ordinary Node/JSON stack and historical Node Foundation are unchanged.

## Database implementation (4.2)

The user selected **4.2** and confirmed **y** for existing-lockfile builds solely in disposable containers and creation/cleanup of owned synthetic PostgreSQL fixtures. The six seams remain unchanged. Work started from `22081065` plus the two existing 4.1 evidence edits, which were retained. No host installs, new dependencies, personal data, published ports, socket mounts, ordinary-stack changes or closeout actions.

`src/opengym_platform/core/database.py` owns configuration, a per-instance pool and the public `Database.open(settings)`, `execute`, `fetch`, `transaction(owner_id=None)` and `close` interfaces. Settings require explicit `host`, `port`, `database`, `user`, `password`; validated overrides/defaults and bounded limits are defined by the implementation and design §4. Unknown driver/DSN options and invalid sizes/types/deadlines are rejected with `DATABASE_CONFIG_INVALID`, without raw validation input or exception chains. There is no global pool, app/health/business dependency or new functional scaffolding.

TLS uses a verifying default SSL context, optionally with `ca_file`. Plaintext requires the synthetic harness host/database markers and the exact private DB destination; the private in-container loopback relay additionally requires the synthetic runtime login. The test-only relay forwards exclusively to `foundation-db:5432`, publishes no ports and does not replace PostgreSQL. TLS tests demonstrate fail-closed behavior against the non-TLS synthetic server and rejected unsafe settings, **not** a provider handshake or certificate matrix.

Transactions lease one connection, install parameterized transaction-local owner context, expire handles and remember failed SQL even when caught. Public errors expose stable codes, not driver messages/causes or SQL values. Standalone execute/fetch install no owner. Failure before COMMIT rolls back or discards; an acknowledged COMMIT succeeds, including when subsequent reset fails and requires discard. Explicit server constraint/serialization/deadlock rejection is transaction-aborted, not unknown. A lost COMMIT response produces `DATABASE_COMMIT_OUTCOME_UNKNOWN` and `commit_outcome="unknown"`; unresolved cancellation keeps `CancelledError` and that metadata. Neither retries writes nor claims that rollback undid a possibly committed write. Close rejects new work, drains active leases, coordinates concurrent close calls and terminates on deadline.

```sh
node scripts/python-foundation.mjs run pool
node --test scripts/python-foundation.test.mjs backend/contracts-compare.test.mjs api/foundation/environment.test.mjs api/foundation/configuration.test.mjs
```

Focused TDD: the existing rollback RED first became GREEN (project `96637e0c7bc917d4`). Further individual RED/GREEN cycles covered owner context, captured SQL, expired handles/safe errors, explicit settings/private relay, saturation, close, transport-lost COMMIT, cancelled unresolved COMMIT, server-rejected deferred COMMIT, concurrent close and reset failure after acknowledged commit. Other already-working paths were characterized without manufactured RED: successful collaboration, cancellation before commit, statement timeout, connection replacement, configuration boundaries/TLS and forced-close deadline. No all-tests-first matrix or fake driver was used.

Final run at `22081065` plus this diff: project `opengym-python-foundation-test-4a72209756724ed3`, **20 passed**, zero skips/setup/teardown errors, **exit 0**, `FOUNDATION_POOL_OK`, cleanup complete; pytest **2.14 s** excludes build/setup/cleanup and was measured alongside regressions. Pinned CPython 3.14.9/PostgreSQL 18.6 Linux amd64; host Node 24.14.0/Docker 29.4.0/Compose 5.1.1. Host regressions **29/29** (harness 14, comparator 10, historical guards 5; zero skips, 109.86 s), including Python environment smoke and ordinary Node API health without PostgreSQL. Disposable read-only static run `d9489ee5ea22fa95`: Ruff check/format and mypy `--ignore-missing-imports` PASS on seven files. Earlier broad-catch/import findings were corrected; the initial format invocation failed to initialize a read-only cache, then passed with `--no-cache`. These auxiliary failures are not behavioral RED. Mypy remains ad hoc, not strict driver typing or a CI gate.

Integrated review of the exact diff, callers and new relay found no further blockers for this synthetic 4.2 scope after the fixes above; shared handle guards were consolidated with tests kept GREEN. Core dependency direction and the ordinary Node/JSON authority remain consistent with AGENTS.md; no rules edit was needed. Independent project-label and scoped name/tag queries found no remaining containers, volumes, networks or images for all 34 recorded 4.2 projects. A limited final stdout/stderr check found none of the synthetic password, sensitive-value/DSN or INSERT/DDL-password markers. This is **not** the full 4.3 diagnostic scanner. Logs remain temporary outside Git. Focused implementation evidence does not complete **4.3**, the slice-4 verification checkpoint, lifecycle through FastAPI/Uvicorn, full role/ACL/RLS, migrations, recovery, remote CI, provider/arm64, parity or operational gates. No commit, sync, archive or publication. The sections below retain historical scope/results, not current authorization or pending-state claims.

## First Database RED (4.1 historical checkpoint, then partial)

The user authorized **4.1 only**, then approved existing-lockfile builds inside disposable containers and owned synthetic PostgreSQL fixtures. The six seams remain unchanged. This step stops at **one behavioral RED**; 4.2/GREEN and subsequent cycles are not authorized. **4.1 remains unchecked** because its other acceptance cases are pending.

```sh
node scripts/python-foundation.mjs run pool
```

Expected result at that historical checkpoint: **exit 1**, `DATABASE_ROLLBACK_REQUIRED`, `assert 2 == 0`, followed by `Python Foundation cleanup complete`, with no `FOUNDATION_POOL_OK`. This command builds only the Python target, starts its private DB, runs `tests/core/test_database.py` and cleans up in the existing `finally`. No Node contract suites or business server are involved.

At source revision `a9709d55` plus this working diff, host Node 24.14.0 / Docker 29.4.0 / Compose 5.1.1 / Linux amd64: the final RED project `opengym-python-foundation-test-523b54723b25cd41` produced **one assertion failure, zero setup/teardown errors** (0.10 s pytest, excluding build/setup/cleanup). The fixture starts empty, creates its own schema/table/login transactionally as bootstrap and gives the login only SELECT/INSERT on that table plus schema USAGE. Two synthetic collaborators receive the same handle, insert distinct parameterized IDs and the second raises. The max-one pool reuses the same PostgreSQL PID; a separate connection using the non-superuser login then sees **two durable rows instead of zero**. Fixture teardown closes clients and drops only its schema/login; the CLI removes its project. This proves a real missing rollback, not an import, unavailable DB or mocked driver failure. Full role/ACL and RLS acceptance is not credited from this fixture.

Resumed **4.1 only** at `22081065`, clean checkout: the same public command reproduced the intended RED in project `opengym-python-foundation-test-c5348838b760d517` (one assertion failure, 0.10 s pytest; exit 1, two durable rows, no setup/teardown error or success marker). Existing 4.1 build/fixture approval was reused without extending it to 4.2. Cleanup completed and independent project-label plus scoped name/tag queries found no containers, volumes, networks or images remaining. No runtime/test code changed, no new cases or acceptance were credited, and previous regression/static results below were not rerun. Logs remain temporary outside Git; the task stays partial pending interleaved RED/GREEN cycles.

At the 4.1 checkpoint, `src/opengym_platform/core/database.py` was explicitly **not operational**: it only delegated leased SQL, accepted exactly `{"max_size":1}`, connected solely to the fixed disposable runtime login, ignored owner context, and terminated the pool for teardown. It had no real transaction, safe driver-error surface, expired-handle guard, general validated configuration or graceful lifecycle. That scaffold was solely for the fixtures. Core imports no app/health/business modules and has no global pool; tests exercise public handles/SQL, not driver internals.

At that checkpoint, pending by vertical cycles after the first GREEN: installed/cleared owner context, successful collaboration, captured SQL error, lost/cancelled COMMIT via real relay, expired handles, saturation, broken connection, cancellation, bounded graceful close and safe configuration/errors. No relay or all-tests-first matrix was added; no pool checkpoint or platform gate is met.

Checks: host harness **14/14**, comparator **10/10**, historical guards **5/5**, normal environment smoke **2/2** plus Node health passed. The harness result does **not** mean the separate `pool` group passes. Ad hoc Ruff check/format and mypy `--ignore-missing-imports` passed on six Python files inside a disposable read-only container; mypy is not strict/driver-stub coverage or the future all/CI gate. The initial format check requested two line wraps, corrected during review; that is not behavioral RED. Final RED output was also checked for the synthetic password and INSERT/DDL-password text; no general diagnostic scanner is credited. Exact-diff/new-file review found no additional blockers for this partial RED-only scope; no AGENTS edit needed. Python locks/pins/inventory, ordinary stack, historical Foundation and CI remain unchanged. No host installations, personal data, ports, socket mounts, commit or closeout. Base images/build cache may remain.

## Contract checkpoint (3.3)

The authorized 3.3 run completed with synthetic fixtures only. `node scripts/python-foundation.mjs run contracts` passed: six HTTP cases and four manifest suites (comparator, 28 Node test files, 12 client files, three MCP files), with no detected skips. The existing ten comparator tests and nine adapter-contract tests are now selected by the manifest; no test/application logic or dependencies changed. Details, positive/negative evidence for all eight areas, providers/runtimes/sandbox limits, frontend ownership and neutral-JS/generator disposition live in [CONTRACTS.md](CONTRACTS.md#evidencia-y-cobertura-ejecutada-33).

Final project `opengym-python-foundation-test-feafd9ce288d9f11`: Node 22.23.2, Linux amd64, Docker 29.4.0, host CLI Node 24.14.0. Inspect confirmed UID 1000, read-only root, dropped capabilities, no-new-privileges, private tmpfs/internal network and no binds/published ports. Both the initial and expanded runs completed cleanup, independently checked by project labels and names/tags. No PostgreSQL/Python or personal data were used.

This completes the selected Node characterization checkpoint, not Python parity, clean-independent-checkout proof, real browser/device/provider validation, remote CI or operational gates. Cache was reused during build; the slice-9 cache matrix is not credited. At that checkpoint 4.1 was unstarted; its later partial RED is documented above. No source relocation, production migration, sync/archive, commit or publication occurred. Prior sections below retain their original task evidence and scope.

## Contract inventory and first RED (3.1)

[CONTRACTS.md](CONTRACTS.md) maps all eight architecture §9.1 areas to producers, consumers, current stores, proposed dispositions, existing positive/negative cases, commands and limits at revision `1b2daff9199611604783faabf76cd741123cec95`. The inventory and pending commands are not executed baseline/parity evidence.

```sh
node --test backend/contracts-compare.test.mjs
```

Observed on host Node 24.14.0: **exit 1, one intended assertion failure**. The independent `http.health.v1` fixture expects status 200; the synthetic actual changes only status to 503. The comparator process parses both JSON files, prints `FOUNDATION_CONTRACT_COMPARE_PENDING`, and exits 0 instead of the expected 1. This is behavioral RED, not an import/setup failure. The minimal `compare <expected.json> <actual.json>` branch is a deliberately incomplete scaffold, not an operational comparator; 3.2 owns its GREEN implementation. It does not affect `environment` or enable `run contracts`.

Only 3.1 is authorized in this step. No baseline suites, Docker builds, installs, real API requests or Python parity checks were run for characterization. The slice-3 checkpoint remains pending until 3.2–3.3. No expectations are regenerated from observed results, and no normalization is applied. Relevant focused host regressions and documentary checks are recorded alongside task 3.1.

## Contract comparison and runner (3.2)

The subsequent request authorized 3.2 and locked dependency builds in disposable containers. The first RED above is historical: the comparator now passes its rejection test and the matching-response case. It compares the complete declared response exactly, validates envelopes/64-KiB file bounds and emits only safe case ID/revision/result codes. No normalizations or expectation regeneration. Types, missing/null, ownership, semantic headers, cookie flags and Training stamps remain significant.

```sh
node --test backend/contracts-compare.test.mjs
node scripts/python-foundation.mjs run contracts
```

[CONTRACTS.md](CONTRACTS.md) owns coverage, fixtures, existing suite commands, limits and the 3.3 handoff. `contracts` builds only the Node target, executes six independent HTTP cases plus the versioned Node/client/MCP suite manifest, and cleans its owned resources. It never starts PostgreSQL/Python. Tests use temporary synthetic state, fixture transports and sanitized environments. Container execution is non-root/read-only with tmpfs and no published ports or personal mounts. Existing lockfiles, dependencies and application behavior remain unchanged.

Focused results: comparator **10/10**, new HTTP cases **6/6**, existing frontend import **16/16**, sync/import-restore **29/29**, MCP **95/95**, host CLI guards **4/4**, historical Foundation guards **5/5**. Node target version **22.23.2**; host CLI **24.14.0**. Input-validation and group-selection RED/GREEN are separate from baseline characterization. The first unavailable-Docker test using an empty Windows PATH timed out; using an explicit closed loopback Docker endpoint made that external prerequisite deterministic. That setup failure is not credited as behavioral RED.

Integrated `node scripts/python-foundation.mjs run contracts`: **PASS, exit 0**. Six HTTP cases and all three manifest suites reported OK with revision/ID/command and no detected skips. Project `opengym-python-foundation-test-b404874bdb284358` completed owned cleanup. This executes the new integration for 3.2; it does not close 3.3's per-area coverage audit.

Full affected harness regression: `node --test scripts/python-foundation.test.mjs` **PASS 14/14**, zero skips, including the existing environment isolation, failure and hard-kill cleanup proofs. Historical Foundation guards pass 5/5. Strict OpenSpec, syntax, diff, local fixture/source links and unchanged lockfile/pin checks pass. OKF initially passed (28 concepts); a subsequent global check found an unrelated concurrently added `docs/reference/platform-modularity.md` missing from `docs/reference/index.md` (29 concepts, `local/index-stale`). That file/index is outside this patch and preserved; the final global check cannot be credited as passing on that observed tree.

3.3 remains pending for the per-area walkthrough and complete contract checkpoint. No Python parity, physical device/browser, real provider, clean independent checkout, remote CI or operational gate is credited here. Build cache/base images may remain; run-owned resources must be removed.

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

`environment` and `contracts` are implemented; `pool` executes the partial 4.1 RED described above and is not a passing transaction proof. `migrations`, `isolation`, `recovery` and `all` are recognized but **exit 1 before Docker**, explicitly unimplemented; unknown/missing groups and malformed/extra arguments also fail. Python/Node target runners likewise reject unavailable groups. Exit 0 means the selected implemented checks **and cleanup** succeeded; Docker/build/startup/test/cleanup failure returns nonzero. Docker subprocesses have a 300-second limit (captured output capped at 4 MiB), DB startup 60 seconds, pytest 60 seconds and the direct probe connection/command/close 5 seconds each. No automatic retries or missing-dependency skips.

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

The six test seams and three clarifications are approved in [design §7](../openspec/changes/add-python-platform-foundation/design.md#7-seams-públicas-de-prueba). Application lifecycle, transaction/pool behavior, privilege separation, parity, RLS, restore, CI execution and operational gates remain unproven. The current request and its explicit container-build/fixture approval authorize **4.1's first RED only**; 4.2/GREEN, later cycles/tasks and change closeout remain outside scope.
