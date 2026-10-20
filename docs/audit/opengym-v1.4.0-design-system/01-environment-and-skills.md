# 01 — Environment, provenance and tooling

Audit date: 2026-10-19 (host UTC−03; evidence timestamps UTC). Discovery/proposal only. Read this provenance before interpreting any screenshot.

## Version verification

| Artifact | Verified observation | Conclusion |
|---|---|---|
| Working directory/root | `C:/Users/nenri/OneDrive/Desktop/proyectos/pry-open-gym/openGym`; `pwd` and `git rev-parse --show-toplevel` agree | Correct repository |
| Branch | `git branch --show-current` empty; `git symbolic-ref -q --short HEAD` unsuccessful | Detached HEAD |
| HEAD | `464355ef43d4c8f8a4e0bb6db9c2af7f240593b5`; `git describe --tags --always`: `v1.4.1` | **Not v1.4.0** |
| Requested tag | Local annotated tag `v1.4.0`; tag-object SHA `a00424f65a69eba2151ea16dec156c951a3ba9e9` | Present, not substituted |
| Requested commit | `git rev-parse 'v1.4.0^{commit}'`: `28b7e4dc3b9c3ac7efd32a1bb783a1e9f6d1429e` | Distinguish tag object from release commit |
| Source package versions | `frontend/package.json`: 1.4.1; `git show v1.4.0:frontend/package.json`: 1.4.0 | Separate source strata |
| Running frontend | `/assets/index-Cyfy8C1l.js` contains v1.4.1; About page visibly v1.4.1 | **Screenshots are v1.4.1 runtime observations** |
| Running API | Read-only `docker exec opengym-api-1 node -p ...package.json...version`: 1.4.1 | API package also 1.4.1 |

No branch switch, reset, fetch, pull, build, service restart or volume operation occurred. v1.4.0 was investigated with read-only `git show`, not checked out. Its original stylesheet is preserved in [evidence/index.v1.4.0.css](evidence/index.v1.4.0.css). Relevant release differences are in [evidence/release-ui-delta.diff](evidence/release-ui-delta.diff).

**Correspondence:** runtime and HEAD report the same package version and representative tokens/layout/behaviors agree. Exact source-to-image build correspondence is **not proven**: OCI revision/version are `dev`, no release commit/build fingerprint is exposed. Do not assert identical bundles merely from matching version strings. v1.4.0 → HEAD has 75 changed files. `App.jsx`, `components/ui.jsx`, `components/Modals.jsx`, `views/Login.jsx`, `views/RoutineEdit.jsx`, `views/Workout.jsx`, `store/useStore.js` are unchanged between these releases. CSS has one additional `.hdr>.hdr-actions` rule in HEAD. Picker Type row, search ranking, Plan Coach entry and populated exercise-chart range controls differ; see 02/03.

## Docker and URL

| Service | State | Configured image | Running image ID | Ports |
|---|---|---|---|---|
| api / `opengym-api-1` | Up, healthy | `ghcr.io/duartesantos8/opengym-api:latest` | `sha256:ecfa3156057b2b76231dc3d4fc598c54913098344d1062e156962a81863a1d20` | 3000/tcp internal |
| web / `opengym-web-1` | Up, healthy | `ghcr.io/duartesantos8/opengym-web:latest` | `sha256:1b7008edb7215f483af7ddd4ba8b769115cb8a88e88c0c25c6a68c5060875b5d` | host 8080 → container 80, IPv4/IPv6 |

`docker compose config --images` agrees. Repo digests match those image IDs. Both images label revision/version `dev`, creation `unknown`; image source labels point to the GitLab mirror. `http://localhost:8080/` responds; `/api/health` reports healthy/writable and zero registered users. No account database, training files, secrets, cookies or `.env` were read. Existing Compose has two services; CLAUDE.md's three-service/media-download description is stale relative to README, Compose and v1.4.0 release notes.

## Initial working-tree baseline and final safety

Initial `git status --short`:

```text
 M .gitignore
?? .agents/
?? .gitattributes
?? skills-lock.json
```

Those changes were user/environment-owned. No pre-existing audit directory, canonical DESIGN.md, AGENTS.md or PRODUCT.md was found in the searched repository locations. README.md, CLAUDE.md, CONTRIBUTING.md, relevant CHANGELOG sections, docs/dev notes and frontend implementation were read. Tests/builds were not run: this is not a behavior change or release verification.

Browser safety: fresh named `opengym-audit` isolated in-memory context, no attachment/personal profile and no persistent state export. Before entry only `gym_default_lang` existed in browser storage; login rendered and `/api/me` returned 401. Source `useStore.js:1477–1483` makes guest selection local; `pushState:1582` returns with no user. Guest mode was offered by the server and used through the UI, not by altering storage or bypassing authentication. The temporary guest contained no existing data; a disposable routine and session were created there, one set marked and theme changed. No account was created, no workout saved, no import/export/upload or account operation executed. Final inspection still showed guest=true, hasUser=false. Browser context was closed without clearing any user storage; see final verification artifact.

## Skills and tools

Project-relative paths below resolve under the verified root. Versions not declared in a SKILL.md are intentionally unspecified. Installed means readable file exists, not merely an entry in `skills-lock.json`.

| Skill/tool | Installed | Actual path/version | Capabilities | Decision |
|---|---|---|---|---|
| Playwright CLI | Yes | `C:/nvm4w/nodejs/playwright-cli` (NVM points into `C:/Users/nenri/AppData/Local/nvm/v24.14.0/node_modules/@playwright/cli`); **0.1.19** | Named isolated sessions; snapshots, screenshots, navigation, resize, eval/run-code, console/requests | Primary browser tool; actual `--help` inspected |
| Playwright CLI skill | Yes, harness-listed/read | `.agents/skills/playwright-cli/SKILL.md` | Documented CLI/reference workflows | Used; CLI installation and skill installation verified separately |
| Packaged Chromium | No usable binary | Expected `.../ms-playwright/chromium_headless_shell-1243/...exe` absent | Headless Chromium | Initial open failed; no download |
| Google Chrome | Executable exists, launch failed | `C:/Program Files/Google/Chrome/Application/chrome.exe` | Chromium channel | Isolated launch exited; not used for evidence |
| Microsoft Edge | Yes, operational | `C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe`; UA Edge **155.0.0.0** | Chromium browser engine | Used through CLI `--browser=msedge` |
| Impeccable | Yes, harness-listed/read | `.agents/skills/impeccable/SKILL.md`, **4.7.0**; shipped Windows x64 binary | `document`, `audit`, `critique`; source detector | `context` ran locally without download; scan methodology used, no canonical writes or sidecar |
| Impeccable document/audit/critique refs | Yes | `.agents/skills/impeccable/reference/{document,audit,critique}.md` | Token extraction, technical review, heuristic critique | Read; adapted to audit-only constraints. No qualitative brand invention, overlay injection or standard write workflow |
| Google Stitch extract-design-md | Yes, harness-listed/read | `.agents/skills/stitch-extract-design-md/SKILL.md`; lock provenance `google-labs-code/stitch-skills/plugins/stitch-design/skills/extract-design-md` | Source extraction; React/plain-CSS references | Used methodology only. No upload, Stitch API, `.stitch` or DESIGN.md generation |
| UI/UX Pro Max | **No readable skill found** | No project/global SKILL.md in searched roots | Independent UX recommendations | Not needed; manual/source + Impeccable critique sufficient |
| Ponytail | Yes, harness-listed/read | `.agents/skills/ponytail/SKILL.md` | Smallest-complete scope, explicit limitations | Used restraint; no application edits |
| codebase-design, code-review, ponytail-audit/review, writing-for-agents | Yes, harness-listed | `.agents/skills/<name>/SKILL.md` | Architecture, review, instructions | Available; no additional workflow needed (no instruction file edited) |
| ECC design-system | Yes, filesystem-discovered/read later | `.agents/skills/design-system/SKILL.md`; origin ECC, no version | Token/consistency assessment | Independent checklist only; competitor research and generating new tokens rejected as out of scope |
| ECC frontend-a11y | Yes, filesystem-discovered/read later | `.agents/skills/frontend-a11y/SKILL.md`; no version | Labeling, focus, semantics | Used to cross-check accessibility findings; no dependency recommendation adopted automatically |
| ECC inherit-legacy-style | Yes, filesystem-discovered/read later | `.agents/skills/inherit-legacy-style/SKILL.md`; no version | Preserve incumbent conventions | Relevant but redundant; no root rules/hook generation |
| ECC click-path-audit | Yes, filesystem-discovered/read later | `.agents/skills/click-path-audit/SKILL.md`; no version | Trace store/handler interactions | Useful later for behavior regressions; full behavioral audit not run |
| frontend-patterns, e2e-testing, react-testing | Files exist, not harness-listed | `.agents/skills/<name>/SKILL.md` | Names suggest frontend/testing workflows; bodies not audited here | Availability only; no capabilities relied on |
| Global find-skills / herdr | Yes, harness-listed | `C:/Users/nenri/.agents/skills/{find-skills,herdr}/SKILL.md` | Skill discovery / explicit Herdr terminal operations | Not invoked: no installations or Herdr request |
| Bash/read/write/edit, Git, Docker, Node | Yes | Tools exposed by harness; Node v24.14.0 | Local discovery and evidence | No new packages/services |
| Sub-agent / Stitch / axe tools | Not exposed | None | — | No subagents, uploads or claimed axe scan |

Locations checked: `.agents/skills`, `$HOME/.agents/skills`, `$HOME/.pi/agent/skills`, `$HOME/.claude/skills`, plus the harness's available-skill catalogue. The latter two global skill directories yielded no entries. Some ECC directories appeared in a later filesystem listing although absent from the first listing; their presence was rechecked/read, but they are not in the harness's initial skill catalogue. **No skill installation command was run by this audit**; this is external environment drift, not evidence of an audit installation. `skills-lock.json` is not sufficient on its own to prove availability. No claim of an exhaustive disk-wide search.

### Documentation-skills follow-up (after the original audit)

The user subsequently confirmed additional skill installations. The entries below were verified by reading their local SKILL.md files; they update current availability, not the original audit's tool-use history. Reading a skill is not evidence that its full workflow ran. Earlier harness-availability statements describe the original audit only.

| Skill | Verified local path | Appropriate use / boundary |
|---|---|---|
| writing-for-agents | `.agents/skills/writing-for-agents/SKILL.md` | Editorial hierarchy, conditional pointers, single-source facts and checkable completion criteria |
| rules-check-drift | `.agents/skills/rules-check-drift/SKILL.md` | Advisory check of CLAUDE.md/AGENTS.md against source; not a general docs audit |
| rules-create-global | `.agents/skills/rules-create-global/SKILL.md` | Optional future packaging of approved root rules; full workflow deferred, no root rewrite or backup creation |
| prime-frontend | `.agents/skills/prime-frontend/SKILL.md` | Refresh affected frontend context before drafting; read-only, no unrelated backend expansion |
| prime-codebase | `.agents/skills/prime-codebase/SKILL.md` | Broader context only when a cross-project claim needs verification |
| codebase-onboarding | `.agents/skills/codebase-onboarding/SKILL.md` | Architecture-map cross-check; starter guide/CLAUDE.md generation unnecessary for this existing audit |

These skills support editorial review; they add no runtime evidence, accessibility verification or permission to modify canonical files. No additional installation is required.

### Missing-tool recommendation (approval required)

- Exact skill: **UI/UX Pro Max**, official repository: <https://github.com/nextlevelbuilder/ui-ux-pro-max-skill>. Not necessary to finish discovery. If later requested, prefer project-local installation for reproducible team availability; generated recommendations remain secondary to openGym's own principles. Fallback: existing Impeccable/ECC checklists plus read-only browser/contrast checks. **Do not install without approval.**
- Packaged Chromium: official CLI/browser documentation <https://github.com/microsoft/playwright-cli> and <https://playwright.dev/docs/browsers>. Not necessary while Edge works. An optional user-cache browser installation would improve reproducibility but requires approval; fallback is the verified installed Edge channel.
- No other missing design skill is required. Impeccable: <https://github.com/pbakaus/impeccable>; Stitch source: <https://github.com/google-labs-code/stitch-skills>. Their presence does not require replacing the existing CSS architecture.
