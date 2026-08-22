# v0.1.5 Implementation Notes — EDS CLI

## Key Decisions

- 2026-08-22 (planning): CLI over UI — the CLI is an external A2A client,
  so dogfooding doubles as a contract test; a web UI is deferred per the
  no-frontend-in-MVP principle.
- 2026-08-22 (T2): `cli.py` speaks only the A2A protocol (httpx);
  the single exception is `serve`, which imports the endpoint. The
  client seam is `_http_client(base_url)` — tests inject a TestClient
  over a fake A2A app, so CLI tests need no EDS backend at all.
- 2026-08-22 (T4): the console script works with the flat layout —
  hatchling build-system with an explicit include list (cli.py + the
  nine production packages), `[project.scripts] eds = "cli:main"`;
  `uv run eds` is the documented interface, `python -m cli` equally.
- 2026-08-22 (T5): added `agent/deterministic.py` — a rule-based
  fallback Supervisor model (`EDS_SUPERVISOR_BACKEND=deterministic`,
  paired with `EDS_WORKER_SCRIPT` for a scripted worker) so `eds serve`
  runs the full delivery loop in demos without LLM credentials. Every
  stage decision derives from durable facts (work-order fields, audit
  events, evidence rows); it replays the canonical order and never
  reasons — the ADK LlmAgent remains the default Supervisor. This went
  beyond the planned scope because the T5 dogfood (four-command user
  loop to `completed`) is impossible in this credential-free
  environment with the real model.

## Deviations from Design

- Design sketched `cli/a2a_client.py` "or a section within cli.py if it
  stays small" — it stayed small: `A2AClient` is ~40 lines inside
  `cli.py`; a separate module would be ceremony.
- The deterministic supervisor backend (see Key Decisions) is an
  unplanned addition required to dogfood the acceptance criterion.

## Bugs Encountered

- The first deterministic backend polled `get_worker_status` forever:
  `create_worker_runtime` already sets worker status "starting", so the
  `start_worker_turn` stage (status None/unknown) was unreachable and
  ADK's internal loop has no step bound of its own — pytest spun at
  95% CPU until killed. Two fixes: stage detection via the durable
  `worker.turn_started` audit event, and a self-imposed MAX_STEPS=200
  after which the model yields plain text, handing control back to the
  supervise loop's turn budget.
- Same incident, second bug: a test re-issued `configure_supervisor`
  with partial kwargs, silently wiping the scripted worker and pointing
  the delivery at a real Codex driver — the exact config-replacement
  trap v0.1.4 fixed in the launcher, re-committed in a test. Tests now
  configure once, fully.
- pydantic v2 rejects non-annotated class attributes on models
  (`MAX_STEPS = 200`) — needs `ClassVar[int]`.

## Lessons Learned

- ADK's run loop only ends when the model emits a final text response;
  any custom `BaseLlm` that always emits tool calls can loop forever.
  Custom model doubles need their own step budget.
- The `eds` four-command loop is a genuinely effective dogfood: it
  exercised the endpoint, the durable state, docker deploy and the CLI
  in one pass, and the recorded `human_acceptance_check` evidence
  (wo-ffffe93012fc) is the M1 exit-criteria demo.
