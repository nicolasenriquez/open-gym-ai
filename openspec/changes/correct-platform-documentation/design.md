## Context

The selected fix is the four-part proposal approved in this conversation. The existing platform safeguards and CI remain in place.

## Decisions

- Link backup/restore instructions to backend/README.md instead of duplicating operational recipes.
- Preserve historical section anchors, but remove the instruction to build the current checkout as Node and correct its root-Compose claim.
- Change only inaccurate OpenAPI descriptions; retain paths, schemas and compatibility-shape comments.
- Remove hard-coded architecture prose from the generator rather than replacing it with another duplicate.

## Blast Radius and Risks

Readers and generated static HTML only. Historical examples remain historical, not current deployment support. Static website publication is separate. No real-instance backup, device behavior or cutover is certified. No automatic API fallback, migration, secret rotation, new deployment wrapper or CI expansion.

## Verification

Run generator/check and repeat generation for idempotence; compare parsed OpenAPI with description fields removed to HEAD; run OKF, diff whitespace, API prefix/base Vitest and the Python public-contract verifier on synthetic resources. Record actual outcomes and limitations in tasks.md before committing. Fetch and verify the tracking branch, commit only selected paths, then push without force to the same branch.
