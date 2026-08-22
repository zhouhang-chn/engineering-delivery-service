# Version 0.1 Retrospective: Single Worker End-to-End

**Milestone**: `v0.1-single-worker-e2e` (M1)
**Status**: ✅ COMPLETE
**Completion Date**: 2026-08-22
**Quality Gate Result**: PASSED (verify_version.py, all checks)

---

## 1. Executive Summary & Value Delivered

v0.1 delivers the complete M1 chain: an A2A task carrying an API
requirement becomes an autonomously delivered FastAPI service with a
live Swagger `/docs` a human can verify. Five iterations landed in
order — worker engine (sandbox, Codex driver, pytest evidence, Docker
deploy), durable PostgreSQL state + Delivery Control tools, an ADK
ReAct Supervisor that decides the delivery order itself, the A2A
endpoint as a thin protocol adapter, and the `eds` CLI reference
caller. Every iteration ended runnable and was dogfooded end to end
with recorded acceptance evidence (`human_acceptance_check` on
wo-c5392084ce82 and wo-ffffe93012fc). All work orders, decisions,
evidence and deployment facts are durable and restart-inspectable.

**Known caveat**: the real-LLM legs of the marked live tests
(`-m llm`) skip in credential-free environments; the loops were
proven with everything real except the model (real PostgreSQL, Docker,
HTTP, health checks) plus a deterministic fallback supervisor added
for offline demos. First run with `GOOGLE_API_KEY` set closes this
gap.

---

## 2. Quantitative Scorecard & Sprint Velocity

| Metric | Target | Actual | Status |
| :--- | :--- | :--- | :--- |
| Total automated tests | growing per iteration | **87 passed** default (+4 docker-marked, +1 codex-marked live; 21 test modules) | ✅ Exceeded |
| Lint check errors | 0 | **0** (`ruff`) | ✅ Met |
| Docstring AST coverage | 100% public symbols | **100%** (gate-checked) | ✅ Met |
| Escaped defects (Day-2 fix commits) | 0 | **0** — every defect was found and fixed inside its iteration before commit | ✅ Met |
| Delivery-loop health | delivery to healthy `/docs` | **2 dogfooded deliveries** with green pytest evidence, healthy deploy, recorded human acceptance | ✅ Met |
| Completeness gate | all checks pass | **all checks passed** (`verify_version.py`) | ✅ Met |
| Production LOC | 1,000–3,000 | ≈ 2,100 (per iterations.md estimate; engine ~700, tools ~450, agent ~350+180, a2a ~250, cli ~230) | ✅ Met |

---

## 3. 4-Quadrant Agile Retrospective

### 1. What Went Well (Keep / Amplify)

- **Durable-state-first design**: because every fact lands in
  PostgreSQL via tools, each later iteration (supervisor, endpoint,
  CLI) was a thin new reader of the same state — no rework, no
  divergence.
- **Test-first with reactive doubles**: ScriptedWorker + ScriptedLlm
  (polling durable status instead of sleeping) made agent-loop tests
  deterministic; every iteration's T1 red→green cycle caught interface
  mistakes before implementation hardened.
- **FakeDockerClient serving real HTTP**: contract tests exercised the
  actual health-check probing path without Docker.
- **Evidence-based acceptance in practice**: the human Swagger-UI
  verification was recorded as durable evidence rows — the
  architecture's Principle 5 is not just documentation.
- **Worktree-per-iteration + stacked branches**: clean isolation, one
  PR for the whole version.

### 2. What Went Wrong & Friction Points (Stop / Drop)

- **SDK assumptions vs resolved versions**: the a2a-sdk server stack
  planned in design turned out to be a proto-first 1.x rewrite; ADK
  2.x renamed `google.adk.llm`→`models` and `content=`→`new_message=`.
  Cost: exploration overhead and one design deviation. Fix: probe
  installed SDKs before designing (now workflow Phase 1, step 4).
- **No LLM credentials in the environment**: two marked live legs skip;
  forced the (useful) deterministic fallback supervisor, but the real
  Supervisor model remains unproven end-to-end.
- **Config-replacement trap** (see 5-Whys): partial re-configuration
  silently wiped pre-set fields — hit twice across iterations.

### 3. Escaped Defect 5-Whys Root Cause Analysis

- **Defect A — unbounded ADK-internal loop (v0.1.5, caught in-test)**:
  - *Why 1*: pytest spun at 95% CPU; the deterministic supervisor LLM
    issued `get_worker_status` forever.
  - *Why 2*: `create_worker_runtime` sets worker status `"starting"`,
    so the `start_worker_turn` stage (status None/unknown) was
    unreachable — the worker was never started, status never changed.
  - *Why 3*: no test covered the stage machine's reachability; the
    first test run discovered it (test-first worked, but the loop had
    no guard).
  - *Why 4*: ADK's internal run loop has no step bound; the supervise
    turn budget only bounds outer turns. A custom `BaseLlm` that always
    emits tool calls never terminates the run.
  - *Why 5 & permanent fix*: stage detection now uses the durable
    `worker.turn_started` audit event; the model self-bounds
    (MAX_STEPS → yields text, handing control to the outer budget).
    Codified as architecture Principle 10 and regression-tested
    (deterministic tests assert delivery completes and red candidates
    never deploy).
- **Defect B — partial `configure_supervisor` wiping config (v0.1.4,
  repeated in a v0.1.5 test)**:
  - *Why 1*: endpoint tests silently ran the real Gemini model; every
    turn failed "No API key"; tasks ended in budget exhaustion.
  - *Why 2*: `start_supervised_delivery` re-issued
    `configure_supervisor` with only its own kwargs — replace, not
    merge semantics.
  - *Why 3*: no assertion covered "the configured LLM is actually the
    one used"; the symptom looked like a credential problem.
  - *Why 4*: process-global config with all-or-nothing writes.
  - *Why 5 & permanent fix*: the launcher now merges with the active
    config field-by-field; tests configure once, fully. Lesson
    recorded in both iterations' notes.

### 4. Kaizen Proposals & Experiments (Start / Try)

- **Carry into v0.2**: restart recovery — the durable state already
  supports re-derivation; a `supervise --resume <wo>` path and a
  reconciliation entrypoint make the supervisor crash-tolerant.
- **Pin or gate the protocol surface**: a small contract test suite
  for the A2A wire surface (already present) should grow with each
  endpoint capability instead of relying on SDK types.
- **Prompt tuning with a real model**: first credential-bearing run
  should review `supervisor_turn` events and tighten
  `agent/prompts/supervisor_system.md` (task left explicitly open from
  v0.1.3).

---

## 4. Action Items & System Evolution

| ID | Action Item | Category | Target Location | Status |
| :--- | :--- | :--- | :--- | :--- |
| A1 | Codify principles 8–10 (durable-derived adapters, structured tool errors, bounded model loops) | 1 — Principles | docs/designs/system-architecture.md | ✅ Done |
| A2 | Gate iteration action-plans (unchecked tasks fail the version gate) | 2 — Gates | .agents/scripts/verify_version.py | ✅ Done |
| A3 | Probe installed SDK versions before designing against them | 3 — Tooling/practice | .agents/skills/development-workflow/SKILL.md (Phase 1 step 4) | ✅ Done |
| A4 | Carry restart-recovery scope + real-model prompt tuning into v0.2 planning | 4 — Next version | docs/versions/v0.2-* (at planning), docs/milestones.md | ✅ Recorded (§5) |

---

## 5. Next Version Scope (v0.2 — Durable Delivery Control)

v0.1 already absorbed much of M2 (PostgreSQL state, tools, audit,
retry policy). The v0.2 plan should therefore focus on the remaining
substance:

- **Restart recovery**: re-derive in-flight work orders after a
  process crash; `supervise --resume`; reconciliation of stuck
  `working` states (the supervise loop and durable state were built
  for this — Principle 4/10 make it mechanical).
- **Operational hardening**: background-delivery process model beyond
  daemon threads (supervisor runs inside the endpoint process today),
  delivery queueing for concurrent work orders.
- **Real-model validation**: run the credential-bearing live legs
  (`-m llm`, `-m 'llm and codex'`), tune the Supervisor prompt from
  observed `supervisor_turn` events (open task from v0.1.3).
- Incorporate retrospective learnings: contract tests for every new
  endpoint capability; config stays merge-semantics everywhere.
