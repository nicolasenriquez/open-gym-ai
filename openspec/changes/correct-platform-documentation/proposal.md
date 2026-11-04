## Why

Current-platform documentation still contains Node/JSON backup and installation instructions, and the Python API reference includes obsolete implementation claims. These contradictions can mislead operators despite the existing cutover warnings.

## What Changes

- Correct README backup guidance and the historical self-hosting installation example.
- Correct implementation-specific API prose without changing the wire contract.
- Remove the API generator's duplicate Node architecture claim and regenerate HTML.

## Capabilities

### New Capabilities
- `platform-documentation-accuracy`: distinguish current operation from preserved Node releases and keep generated API prose consistent.

### Modified Capabilities
None.

## Impact

Only README, historical self-hosting guidance, OpenAPI descriptions, the static API generator and its generated page change. No runtime, schema, secrets, deployment, migration or cutover operation is authorized. Commit and normal push to the current tracking branch are authorized by the user.
