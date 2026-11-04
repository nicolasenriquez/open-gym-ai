## ADDED Requirements

### Requirement: Documentation distinguishes current and preserved deployments
Current platform documentation SHALL describe PostgreSQL and external media/secrets, link to the maintained capture/restore procedures, and SHALL NOT instruct readers to install the retired Node application from the current checkout.

#### Scenario: Operator reads installation and backup guidance
- **WHEN** an operator follows the README or historical self-hosting introduction
- **THEN** current platform procedures and preserved-release instructions are distinguished without authorizing cutover

### Requirement: API implementation prose matches the current platform
The public YAML and generated API page SHALL NOT describe the Python server as Node/JSON storage or instruct operators to edit db.json. Documentation corrections SHALL preserve the public methods, paths and schemas.

#### Scenario: Static API reference is regenerated
- **WHEN** the reference is built from the corrected YAML and generator
- **THEN** no duplicate Node implementation claim is emitted and a second generation produces identical bytes
