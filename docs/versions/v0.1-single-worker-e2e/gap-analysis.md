# v0.1 Gap Analysis — Single Worker End-to-End (M1)

**Version:** v0.1-single-worker-e2e · **Status:** IN-PROGRESS · **Date:** 2026-08-22

## 1. Goal

Deliver the minimal closed loop, fully automatic for a single work order:

```
A2A Requirement → ReAct Supervisor → Worker Codex → FastAPI Code
→ pytest → Docker Deploy → /docs
```

Verifiable outcome: the caller sends `"增加 GET /hello?name=...，返回 greeting。"`
and the system autonomously develops, tests, builds, and deploys, finally
returning `http://localhost:<port>/docs` for human Swagger-UI acceptance
(reference: [MVP delivery protocol](../../designs/mvp-delivery-protocol.md)).

Fixed scope (architecture M1): one FastAPI template repository, one Worker,
one sandbox, one Codex App Server, local Docker deploy, single work order,
**no Inspector** — the Supervisor judges from Worker results.

## 2. Current State

Skeleton only: every module exists with docstrings and raises
`NotImplementedError`. Tests cover the skeleton (4 passing). No template
repository exists, no Codex integration, no alembic setup, no runner.

## 3. Capability Gaps

| Capability | Needed for v0.1 | Today |
|---|---|---|
| FastAPI template repository | cloneable baseline with app + pytest + Dockerfile | missing |
| Codex App Server client | start/resume thread, run turn, stream events, answer questions | stub |
| Worker driver | turn a requirement into candidate commit + test evidence | stub |
| Sandbox manager | isolated writable workspace per work order | stub |
| Git operations | checkout baseline, commit candidate | stub |
| Docker deployment | build, run, health-check, expose /docs | stub |
| Durable minimal state | work_order row: status, thread, candidate, deployment URL | models exist, no persistence path, no alembic |
| Delivery Control tools | the M1 subset implemented against PostgreSQL | stubs |
| ReAct Supervisor | ADK agent driving the tools autonomously | stub |
| A2A endpoint | task in → artifacts out | stub |
| CLI runner | dev entrypoint before Supervisor exists | missing |
| User test client (`eds` CLI) | serve / submit / status --watch / open as an external caller | missing |

## 4. Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Codex App Server API surface differs from assumptions | blocks worker path | **Spike first** (v0.1.1 T1); isolate behind `CodexAppServerClient` interface; `ScriptedWorker` double keeps the loop testable without Codex |
| Long Codex turns block Supervisor tool calls | supervisor stalls | driver runs turns **asynchronously**; tools poll status — never wait inside one call |
| ADK/a2a-sdk version churn | integration breakage | pin versions; thin adapters (`agent/`, `a2a_api/`) so framework code stays narrow |
| LLM keys unavailable in test env | supervisor untestable | unit/contract tests use ScriptedWorker + recorded states; live LLM only in marked e2e |
| Docker daemon unavailable/permissions | deploy fails | preflight check + clear failure evidence; e2e marked, not part of unit run |
| Scope creep toward M2 (inspector, full state, recovery) | version bloat | use existing full state model but fill only the M1 subset; no inspector; default retry policy only |

## 5. Exit Criteria

1. Full chain succeeds for the `/hello` work order: A2A task `submitted` →
   `completed` with repository/commit, deployment URL, `/docs` URL, test
   evidence, delivery summary.
2. Human opens `/docs` → Try it out → Execute → sees the greeting.
3. `uv run python .agents/scripts/verify_version.py v0.1-single-worker-e2e`
   passes.
4. Unit/contract tests green without Codex/LLM/Docker; e2e marked suite
   covers the live chain.
