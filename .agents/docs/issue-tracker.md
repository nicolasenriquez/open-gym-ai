# Issue tracker: Local Markdown

Local issues for workflows that explicitly use this tracker live in `.scratch/`.
OpenSpec changes keep their authoritative proposal, specs, design and tasks in
`openspec/`. A local ticket for such a change links to those artifacts; it does not
create a second authoritative specification.

## Conventions

- One feature per directory: `.scratch/<feature-slug>/`
- For a standalone local workflow, the spec is `.scratch/<feature-slug>/spec.md`; for an OpenSpec change, link to its artifacts instead
- Implementation issues are one file per ticket at `.scratch/<feature-slug>/issues/<NN>-<slug>.md`, numbered from `01`, never a single combined tickets file
- Triage state is recorded as a `Status:` line near the top of each issue file (see `triage-labels.md` for the role strings)
- Comments and conversation history append to the bottom of the file under a `## Comments` heading

## Scratch lifecycle

Keep task artifacts in `.scratch/<feature-slug>/`. Tickets under `issues/*.md`
are versioned; working specs, maps, logs, captures, exports and helper scripts stay
local under the existing Git ignore policy.

At task closeout:

1. Record the necessary result, limits and unresolved work in the existing ticket
   or OpenSpec task. Keep only sanitized evidence needed for an open review or an
   explicit acceptance requirement; record its purpose and removal condition there.
2. After confirming the task's writers have stopped, remove its obsolete logs,
   duplicate captures, exports, copied dependencies and temporary scripts. Verify
   exact paths remain inside that task's directory, including through links;
   preserve tickets, ongoing work, user data and protected evidence. Use the owning
   verifier for container cleanup; deleting files does not clean Docker resources.
3. Review `git diff --cached --name-only -- .scratch` before committing. Only
   intended tickets belong there. Unstage accidental artifacts without deleting
   their local copies; keep reusable tests in the normal test directories.

Closeout is complete when obsolete owned artifacts are removed, retained evidence
has a stated purpose and removal condition, and staging contains no temporaries.
Remove retained artifacts when that condition is met; avoid a separate cleanup report.

## When a skill says "publish to the issue tracker"

Create a local ticket under `.scratch/<feature-slug>/` (creating the directory if needed). Preserve OpenSpec authority when the task belongs to an OpenSpec change.

## When a skill says "fetch the relevant ticket"

Read the file at the referenced path. The user will normally pass the path or the issue number directly.

## Wayfinding operations

Used by `/wayfinder`. The **map** is a file with one **child** file per ticket.

- **Map**: `.scratch/<effort>/map.md` (the Notes / Decisions-so-far / Fog body).
- **Child ticket**: `.scratch/<effort>/issues/NN-<slug>.md`, numbered from `01`, with the question in the body. A `Type:` line records the ticket type (`research`/`prototype`/`grilling`/`task`); a `Status:` line records `claimed`/`resolved`.
- **Blocking**: a `Blocked by: NN, NN` line near the top. A ticket is unblocked when every file it lists is `resolved`.
- **Frontier**: scan `.scratch/<effort>/issues/` for files that are open, unblocked, and unclaimed; first by number wins.
- **Claim**: set `Status: claimed` and save before any work.
- **Resolve**: append the answer under an `## Answer` heading, set `Status: resolved`, then append a context pointer (gist + link) to the map's Decisions-so-far in `map.md`.
