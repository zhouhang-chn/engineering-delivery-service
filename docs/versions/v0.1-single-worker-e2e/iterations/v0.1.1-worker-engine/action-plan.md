# v0.1.1 Action Plan — Worker Engine

- [ ] T1 — Test-First: contract test for the runner loop using
      `ScriptedWorker` + fake docker (red before implementation)
- [ ] T2 — Spike: bind `CodexAppServerClient` to the real Codex App Server;
      record protocol findings in implementation-notes; adjust interface if
      needed
- [ ] T3 — Create the FastAPI template repository (app + pytest + Dockerfile
      + `/healthz`), register URL as `EDS_TEMPLATE_REPO_URL`
- [ ] T4 — Implement `sandbox/manager.py` (dirs, isolation, idempotent
      destroy) with unit tests
- [ ] T5 — Implement `control/repository.py` (checkout/commit_candidate)
      with unit tests (local fixture repo)
- [ ] T6 — Implement `codex/worker_driver.py` incl. `ScriptedWorker`,
      async status registry, event capture — contract tests green
- [ ] T7 — Implement `deployment/docker.py` (build/run/health) + docker
      integration test (marked)
- [ ] T8 — Implement `runner.py` CLI; contract test (T1) green; live run
      against real Codex produces a reachable `/docs` (record evidence)

Acceptance: `uv run pytest -q` green (no docker/codex needed); marked
integration/e2e suites pass when docker/codex available; `runner.py`
demo yields `http://localhost:<port>/docs`.
