# Contributing to openGym

Thanks for taking a look. openGym is deliberately small and light on dependencies, and the aim is
to keep it that way: easy to read, easy to self-host.

## Project layout

```
frontend/  React + Vite app (src/views, src/components, src/store, src/lib). Builds to static files.
           android/ and ios/ are the Capacitor shells for the standalone app (docs/MOBILE.md).
backend/   Python/FastAPI/PostgreSQL backend, migrations and pytest suites; openapi.yaml owns HTTP.
shared/    Neutral JS coach core and push copy used by frontend builds.
web/       Multi-stage Dockerfile (builds the frontend, serves it with nginx) and the nginx template.
website/   The static project site at opengym.ch.
deploy/    Explicit Python Dev/prod/test Compose entrypoints; no root or legacy deployment.
docs/      User and operator guides (index: docs/index.md); docs/dev/ has feature design notes.
catalogue/ The exercise catalogue: one JSON file per exercise, translations in i18n/, and the
           licensed 180 px stills and animations in media/ (catalogue/README.md).
```

## Running for development

The runtime, private env/secrets and synthetic verifier are documented in
[backend/README.md](backend/README.md). Existing instances are not migrated by this
checkout; the real cutover is deferred and requires separate authorization.

Use Node 22 and the pinned pnpm 10.34.8 (`corepack enable`), or Docker for the stack.

```bash
# Prepare an independent private env-file and secrets per backend/README.md first.
just dev /absolute/private/dev.env

cd frontend && pnpm install --frozen-lockfile && pnpm run dev   # hot reload, proxies /api to :3000
cd frontend && pnpm test                     # training logic, locales, components
node scripts/platform.mjs verify identity_session  # run from repository root
```

The frontend suite runs the actual nginx entrypoint script and requires a POSIX `sh` on PATH.
On Windows, Git for Windows supplies it. In PowerShell, expose it to this terminal before
running the suite (no system PATH change):

```powershell
$gitRoot = Split-Path (Split-Path (Get-Command git.exe -ErrorAction Stop).Source)
$gitBin = Join-Path $gitRoot 'bin'
if (!(Test-Path (Join-Path $gitBin 'sh.exe'))) { throw 'Locate your Git for Windows sh.exe and add its directory to this terminal PATH.' }
$env:PATH = "$gitBin;$env:PATH"
cd frontend
pnpm.cmd test
```

Python HTTP/PG tests run inside Docker with synthetic ownership and restricted
roles. Never point verifier/capture/import/restore tooling at instance data without
separate scoped permission. Pure client/coach tests use Vitest, not a Node server.

## Guidelines

- **Keep it dependency-light.** See `frontend/package.json`, `backend/pyproject.toml` and
  their locks for current client/platform dependencies. Justify new dependencies.
- **Match the style.** Small components, clear names, comments only where the *why* isn't obvious.
  State lives in the Zustand store (`src/store`), pure helpers in `src/lib`. Oxlint checks a small set of correctness rules; there is no automatic
  formatter, so follow the surrounding code.
- **Don't commit** `data/`; it is gitignored. Don't add or replace anything in
  `catalogue/media/`: the stills and animations are licensed from Gym visual, 180 px at most, and
  not open to contributions (see [NOTICE.md](NOTICE.md)).
- **Exercise fixes and translations go through `catalogue/`**, one JSON file per exercise and one
  per language. [catalogue/README.md](catalogue/README.md) explains the fields and how the app is
  built from them; don't edit the generated `frontend/src/lib/exercises-data.js` by hand.
- **Click through what you touched**, including the workout flow, in a browser before opening a
  pull request.
- **Training logic gets a unit test.** Anything that decides what you lift next, or reads a logged
  session back, belongs in a pure helper in `src/lib` with a test beside it. These rules are easy
  to get subtly wrong and nearly impossible to check by clicking; the progression engine has had
  real bugs that only a test caught.
- **New UI strings go into every locale** in `frontend/src/locales/`. English is the source
  language and has no file. `node frontend/scripts/check-locales.mjs` (from the repository root;
  also run in CI) flags a key that is
  missing, blank or has lost a `{n}` placeholder. Portuguese (Brazil) inherits from Portuguese
  (Portugal) and has its own guard test.

## CI and security checks

[Tests](.github/workflows/test.yml) is the only workflow. Every PR runs quality,
source/dependency security, documentation, catalogue, frontend/API, PostgreSQL
and Python Foundation checks. Image checks depend on quality and product tests;
all other checks run independently. Pushes to main/coach and manual runs are supported.
No workflow publishes or deploys.

Build mobile packages locally using [the mobile guide](docs/MOBILE.md).
A first-time contributor's workflows may wait for maintainer approval.
Required checks are configured separately in GitHub branch rules.

Run `pnpm install --frozen-lockfile --ignore-scripts` at the root, then
`pnpm run lint:ci`. Run `pnpm audit` at root, frontend and api.
Audit failures, including an unavailable advisory service, block CI. API's scoped
Zod override corrects the optional SDK's pinned vulnerable dependency; remove it
when the SDK supplies a fixed version and adapter/image checks pass.

The separate locked `backend/security/` environment leaves Foundation dependencies
unchanged. Build it with `docker build -f backend/Dockerfile.security -t opengym-security:ci .`.
Its CI commands run Bandit (medium severity and confidence), zizmor offline, and
pip-audit over hashed application/development/tool requirements. Bandit's two B108
exceptions document Recovery's mandatory tmpfs check and no-follow directory open.
Bandit/pip-audit use Apache-2.0, zizmor MIT and Oxlint MIT; retain dependency notices.
Scanners supplement review and runtime isolation; they do not certify security.

CodeQL uses the extended JavaScript/TypeScript queries. Its job alone does not
block merges on alerts: configure code-scanning merge protection separately in
GitHub. Repository rules and CodeQL availability must be verified remotely before
requiring these checks; this change does not alter remote settings.

## Documentation changes

README files describe current purpose, supported commands and where to find detail.
Keep tasks in OpenSpec/the tracker, execution artifacts outside Git, and change
history in Git/PRs and the changelog. Do not append session permissions, task
counters or fail-first histories to guides. Review documented commands as well as links.

Start with the [documentation index](docs/index.md) and follow the
[OKF authoring guide](docs/operations/okf-authoring-guide.md) when adding, editing
or moving a document. Run `node scripts/docs/okf.mjs check` before submitting.

## Versioning and changelog

Future releases use [SemVer 2.0.0](https://semver.org/): PATCH for compatible bug
fixes, MINOR for compatible additions or deprecations, MAJOR for incompatible
public-contract changes. Compatibility includes supported HTTP interfaces,
import/export formats and documented deployment/upgrade behavior. An internal
runtime rewrite alone does not determine the version increment.

Keep one curated [CHANGELOG.md](CHANGELOG.md), using
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) principles. Add implemented,
reviewed changes under `Unreleased`, with nonempty Added, Changed, Deprecated,
Removed, Fixed or Security categories as appropriate. Describe reader-visible
effects; do not copy task lists, commits, test logs or planned work into it.

At release time, select the version from compatibility, not cadence. Preserve
published release entries and artifacts. Keep `## vX.Y.Z` release headings for
continuity with published history. The Git tag `vX.Y.Z`,
frontend/API package versions `X.Y.Z` and changelog section must agree. This policy
supersedes the historical cadence rule in ROADMAP.md. This repository has no
automated publication; any future release workflow needs a separate change.

## Using AI tools

[`AGENTS.md`](AGENTS.md) holds the shared project context. Agent conventions and
skills are centralized in [`.agents/`](.agents/README.md). You are welcome to use
whatever tools you like for a pull request. The bar is the same either way: you
understand the change, it is tested, and you can answer questions about it in review.

## What CI does with your pull request

See [CI and security checks](#ci-and-security-checks).

## Good first issues

- More starter plans
- Exercise translations: any language in `catalogue/i18n/` with gaps, or a new one
  (see [catalogue/README.md](catalogue/README.md#translating))
- Percentage or training-max programming (5/3/1 style) on top of the progression engine in
  `src/lib/progression.js`; the policy interface is already there
- Accessibility passes on the workout and chart screens

## Where to ask what

| You have | Goes to |
| --- | --- |
| A quick question, or you'd rather chat | [Discord](https://discord.gg/e62jY6fwVb) |
| A question, or self-hosting that won't behave | [Discussions → Q&A](https://github.com/DuarteSantos8/openGym/discussions/categories/q-a) |
| An idea you're not sure about yet | [Discussions → Ideas](https://github.com/DuarteSantos8/openGym/discussions/categories/ideas) |
| A reproducible bug | [Issues](https://github.com/DuarteSantos8/openGym/issues) |
| A change you've already built | [A pull request](https://github.com/DuarteSantos8/openGym/pulls) |
| A security problem | [Private report](https://github.com/DuarteSantos8/openGym/security/advisories/new), see [SECURITY.md](SECURITY.md) |

An answered question in Discussions is worth more than the same answer in a chat log, because the
next person searching "passkey login fails behind my reverse proxy" finds it. If a Discord answer
turns out to be worth keeping, it belongs in Discussions afterwards.

## Reporting bugs

Open an issue with what you did, what you expected, what happened, and your browser and OS. For
login or passkey problems, include your `RP_ID` and `ORIGIN` (not the contents of `data/`); most
login issues are an origin mismatch.

## Contributor License Agreement

Before your first pull request is merged, you sign the [Contributor License Agreement](CLA.md) once,
by commenting the sentence the CLA check asks for on your pull request. It covers all your past and
future contributions. You keep the copyright in your work; openGym may use and relicense it, which
is what keeps the app possible in the App Store and Google Play long term. Every version released
under the [GNU AGPL v3.0](LICENSE) stays available under it.
