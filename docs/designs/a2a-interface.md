# A2A Interface

**Status:** Current · **Component:** `a2a_api/`

## 1. Contract

EDS is exposed as one Engineering Delivery Agent. The unit of interaction:

```
A2A Task ≈ Engineering Work Order        (not: a Codex turn)
```

The caller says **"build and deploy this API"** and never needs to know about
worker threads, inspector threads, sandboxes, retries, or inspection loops.
All of that is internal to EDS and observable only through task state and
artifacts.

## 2. Task State Mapping

| A2A Task State | EDS meaning |
|---|---|
| `submitted` | Work Order created (durable row exists) |
| `working` | Supervisor autonomously advancing the work order |
| `input-required` | External confirmation needed (requirement ambiguity — from v0.4) |
| `auth-required` | Additional permission/approval needed |
| `completed` | Deployed and final acceptance verified |
| `failed` | Cannot continue (terminal, reason persisted) |
| `canceled` | Canceled by the caller |

`input-required` / `auth-required` transitions are resumed by the caller
answering through the same task; EDS maps the answer onto the work order and
the Supervisor continues.

## 3. Task Payload (MVP)

MVP input is the [MVP delivery protocol](mvp-delivery-protocol.md) document:
a structured API requirement (endpoint, input, output, business logic,
acceptance criteria). The Supervisor is responsible for turning an
underspecified request into a confirmed requirement before development starts
(v0.4); until then, requirements must arrive complete.

## 4. Completion Artifacts

A `completed` task carries at least:

```
repository / commit        candidate commit delivered
deployment URL             base URL of the running service
/docs URL                  Swagger UI for human acceptance
test result                pytest evidence (persisted)
inspection result          verdict + criteria evidence (from v0.3)
delivery summary           what was built, changed, and how verified
```

## 5. Server Design Notes

- Implemented in `a2a_api/server.py` on `a2a-sdk`; the package is named
  `a2a_api` (not `a2a`) because a top-level `a2a` package would shadow the
  SDK's import root for every process run from the repo root.
- Task handlers create/read work orders exclusively through
  [Delivery Control tools](delivery-control.md) — the endpoint is a thin
  protocol adapter, not a controller.
- One ADK session per work order; task state derives from
  `overall_status` in [work order state](work-order-state.md), never from
  in-memory session state.

## 6. Out of Scope (MVP)

- Authentication/authorization between caller and EDS (trusted network).
- Push notifications/webhooks (callers poll task state).
- Multi-project routing (single template repository until v0.5).
- A graphical EDS console — the reference external caller is the `eds` CLI
  (v0.1.5); a web UI would be post-M1 scope.
