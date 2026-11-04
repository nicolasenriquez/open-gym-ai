---
type: Guide
title: Self-hosting openGym on Kubernetes
description: Retirement of the Node-only Kubernetes and Helm deployment examples.
---
# Self-hosting openGym on Kubernetes

The former `kubernetes/` manifests and `helm/` chart deployed the retired
Node/JSON backend and upstream images. They are removed, not silently redirected
to Python or a new PostgreSQL volume.

No Kubernetes deployment is supplied for the Python platform. The supported local
topology and explicit Dev/prod overlays live in
[backend/README.md](../backend/README.md#platform-images-and-compose).
Its roles, secrets, media, backup custody and recovery procedures cannot be
replaced by reusing the old JSON-volume manifests.

Existing cluster releases and their data are not operated on or removed by this
repository change. Real migration/cutover is deferred, needs separate authorization
and must preserve the original release/configuration/secrets and protected source.
Do not run historical `kubectl apply`/Helm update commands from earlier revisions
against the new platform.
