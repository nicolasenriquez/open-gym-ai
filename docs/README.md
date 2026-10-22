---
type: Guide
title: openGym documentation
description: Documentation entry point and ownership of guidance, requirements and supporting research.
---
# openGym documentation

Start at the [documentation index](index.md), grouped by use, current operation,
development and planned evolution. For a quick product question, try the [FAQ](FAQ.md).

## Using the app

The index links the current phone, import and coach guides. The
[live demo](https://opengym.ch/demo/) runs with example data.

## Hosting it

Read [self-hosting](SELF_HOSTING.md) before operating an instance. Deployment
settings remain documented in [the environment example](../.env.example).

## Working on the code

Read [contributing](../CONTRIBUTING.md) and [AGENTS.md](../AGENTS.md).
For documentation changes, follow the [authoring guide](operations/okf-authoring-guide.md).

## Documentation authority

| Question | Source of truth |
| --- | --- |
| Shared repository rules | [AGENTS.md](../AGENTS.md) |
| Where to find a document | [Documentation index](index.md) |
| Current runtime and hosting | [Root README](../README.md), [self-hosting](SELF_HOSTING.md) and current source |
| HTTP API contract | [OpenAPI](../api/openapi.yaml); [API guide](API.md) explains it |
| Platform outcomes and priority | [Evolution PRD](open-gym-evolution.prd.md) |
| Transition, mechanisms and technical gates | [Architecture](open-gym-evolution.architecture.md) and its linked references |
| Recovery functional requirements | [Recovery PRD](open-gym-recovery.prd.md) |
| Product evidence and decision sources | [Discovery](dev/personal-recovery-discovery.md) and [research](research/index.md), only within their stated scope |
| A selected change and its tasks | [OpenSpec artifacts](../openspec/changes/); archives preserve their original scope |
| Documentation rules and maintenance | [Local OKF profile](standards/okf-profile.md) and [authoring guide](operations/okf-authoring-guide.md) |

Current runtime remains Node/JSON. The Evolution PRD governs the order of future
delivery; reformatting these documents does not satisfy platform acceptance.
The [roadmap](../ROADMAP.md) summarizes direction and preserves upstream context;
it does not override the PRDs or architecture. Research supports decisions; it is not current implementation guidance or proof of acceptance.

Keep reusable knowledge in its owning page. Git/PRs preserve change history;
execution logs and screenshots remain temporary artifacts. Follow the
[retention policy](operations/okf-authoring-guide.md#qué-pertenece-a-docs) before adding or retiring a document.

## Still stuck?

Ask in [Discussions](https://github.com/DuarteSantos8/openGym/discussions)
or [Discord](https://discord.gg/e62jY6fwVb).
