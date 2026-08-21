# Deployment Runtime

**Status:** Current · **Component:** `deployment/`

## 1. Scope

MVP deployment is local Docker targeting a test environment. The deliverable
of every deployment is a running FastAPI service whose `/docs` a human can
open, "Try it out", and execute — that Swagger UI is the human acceptance
surface, which is why MVP needs no additional frontend.

## 2. Deploy Flow

```
deploy_candidate(work_order_id, candidate_commit)
   → docker build (candidate commit's Dockerfile)
   → docker run   (allocated port, isolated network)
   → health check (service answers; /docs reachable)
   → persist deployment_id, base_url, docs_url, health on the work order
```

`get_deployment_status(deployment_id)` reports phase, base URL, docs URL and
health for the Supervisor's verify-deployment step; the result is recorded as
evidence via `record_evidence`.

## 3. Lifecycle Rules

- Deployments are recreate-per-candidate: a new candidate commit produces a
  new deployment; the old one is torn down after the replacement is healthy
  (rollback posture until v0.6 adds explicit rollback).
- Teardown is idempotent and safe to retry.
- Port allocation must be recorded on the work order so restarts can rebind
  to the same deployment (v0.2).

## 4. Acceptance Contract

A deployment counts as live only when:

1. the container is running and healthy,
2. `GET <base>/docs` answers (Swagger UI loads),
3. the delivered OpenAPI schema contains the endpoints required by the
   acceptance criteria (verified by the Inspector from v0.3).

## 5. Out of Scope (until the milestone plan says otherwise)

- Non-Docker targets (K8s, cloud deploys).
- Production environments, TLS, custom domains.
- Per-project deployment configuration (v0.5).
- Zero-downtime rollout and explicit rollback automation (v0.6).
