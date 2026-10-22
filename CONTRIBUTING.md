# Contributing to openGym

Thanks for taking a look. openGym is deliberately small and light on dependencies, and the aim is
to keep it that way: easy to read, easy to self-host.

## Project layout

```
frontend/  React + Vite app (src/views, src/components, src/store, src/lib). Builds to static files.
           android/ and ios/ are the Capacitor shells for the standalone app (docs/MOBILE.md).
api/       Backend: server.js on plain node:http, with dependencies listed in api/package.json.
           coach/ is the optional AI coach; openapi.yaml documents every route.
web/       Multi-stage Dockerfile (builds the frontend, serves it with nginx) and the nginx template.
mcp/       Optional read-only MCP server for compatible AI clients. Not in the
           Docker build; it only runs when a client spawns it. See mcp/README.md.
website/   The static project site at opengym.ch.
kubernetes/ Example manifests (docs/SELF_HOSTING_KUBERNETES.md).
docs/      User and operator guides (index: docs/README.md); docs/dev/ has feature design notes.
catalogue/ The exercise catalogue: one JSON file per exercise, translations in i18n/, and the
           licensed 180 px stills and animations in media/ (catalogue/README.md).
```

## Running for development

```bash
cp .env.example .env
docker compose up -d --build      # api + web on :8080

cd frontend && npm install && npm run dev   # hot reload, proxies /api to :3000
cd frontend && npm test                     # training logic, locales, components
cd api && npm test
cd mcp && npm test
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
npm.cmd test
```

API tests keep recovery, durable writes and profile deletion covered on Windows. POSIX mode
assertions are separate subtests; chmod-denied scenarios are explicitly skipped on Windows
and when running as root. Run those scenarios as a non-root Linux user as well (Ubuntu CI
does this). Windows mode bits do not validate Windows ACLs.

With API dependencies installed, this PowerShell command from the repository root runs the
POSIX cases and fixture-path regression in a disposable Node 22 container. It mounts only
API source read-only and writes a temporary copy; it never mounts the instance's `data/`:

```powershell
$apiSource = (Resolve-Path api).Path
docker run --rm --user 1000:1000 --mount "type=bind,source=$apiSource,target=/source,readonly" --entrypoint sh node:22-alpine -c 'set -eu; test "$(id -u)" != 0; cp -R /source /tmp/api; cd /tmp/api; node --test --test-concurrency=2 --test-name-pattern="a profile credential lives|atomicWrite: bytes|db.json unreadable after a sign-up|a data directory the server cannot write|folders are 0700|an unwritable ./data|a push that was delivered|the fixture provider runs from" test/credential.test.js test/durable.test.js test/server-db-unreadable.test.js test/server-health-writable.test.js test/server-media.test.js test/server-push-prune-save.test.js test/adapters.test.js'
```

## Guidelines

- **Keep it dependency-light.** The frontend uses React, React Router and Zustand; `api/` has two
  dependencies. A new dependency on either side is a hard sell.
- **Match the style.** Small components, clear names, comments only where the *why* isn't obvious.
  State lives in the Zustand store (`src/store`), pure helpers in `src/lib`. There is no linter or
  formatter config, so follow the surrounding code.
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
  language and has no file. `node scripts/check-locales.mjs` (run in CI) flags a key that is
  missing, blank or has lost a `{n}` placeholder. Portuguese (Brazil) inherits from Portuguese
  (Portugal) and has its own guard test.

## Using AI tools

[`AGENTS.md`](AGENTS.md) holds the shared project context. Agent conventions and
skills are centralized in [`.agents/`](.agents/README.md). You are welcome to use
whatever tools you like for a pull request. The bar is the same either way: you
understand the change, it is tested, and you can answer questions about it in review.

## What CI does with your pull request

<p align="center">
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/diagrams/ci-dark.png">
  <img src="docs/diagrams/ci.png" alt="CI path: pull request on GitHub, GitHub Actions tests and image builds, review and merge into main, mirror workflow pushes to GitLab, GitLab CI builds the signed APK, images and SBOMs, GHCR images on release." width="280">
</picture>
</p>

A pull request runs the three test suites and builds and boots both api image targets. The APK and
the published images come from GitLab CI on the mirror, built from `main` after the merge. If your
change needs an APK to be judged, say so in the pull request and a maintainer will run that build.
A first-time contributor's workflows wait for a maintainer to approve them, so "no checks yet"
just means nobody has pressed the button.

Merge requests still open on the GitLab mirror are reviewed too and land on `main` here. New work
should come as a GitHub pull request.

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

By contributing you agree that your work is licensed under the project's
[GNU AGPL v3.0](LICENSE).
