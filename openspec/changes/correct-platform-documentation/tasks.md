## Implementation

- [x] 1. Correct README backup and historical installation guidance.
- [x] 2. Correct API implementation descriptions and remove duplicate generator prose; regenerate HTML.
- [x] 3. Verify documentation, generator idempotence, unchanged wire contract, frontend prefix/base tests and synthetic Python contract checks; record limits.
- [x] 4. Review the bounded diff and verify the tracking-branch target for the authorized normal commit/push.

## Evidence

Initial tree clean. Tracking branch: origin/docs/opengym-evolution-discovery on nicolasenriquez/open-gym-ai. Fetch confirmed HEAD and tracking branch equal. No remote named upstream. No deployment or real-instance operation.

- `node scripts/build-api-docs.mjs --check`: pass; 68 endpoints and 30 schemas. A second generation was byte-identical.
- Parsed YAML compared to HEAD with description fields excluded: identical; no methods, paths, schemas or other contract fields changed.
- `node scripts/docs/okf.mjs check`: pass; one non-blocking historical-link advisory in recovery-reference-benchmark.md for the retired payload.js path.
- `openspec validate correct-platform-documentation --strict`: pass.
- `pnpm --dir frontend exec vitest run src/lib/api-version.test.js src/lib/api-base.test.js`: 2 files, 33 tests passed.
- `node scripts/platform.mjs verify contracts --case python_routes`: pass on disposable project opengym-platform-test-81363756c787c038; cleanup completed. One non-blocking FastAPI duplicate media operation-ID warning.
- `git diff --check`: pass. Reviewed all five changed product/documentation files; changes match the approved proposal.

Limits: no full platform suite, browser/device verification, website publication or real-instance backup/restore/cutover. The remainder of the self-hosting guide stays explicitly historical. Commit and push success are reported by Git/session output, not claimed in advance here.
