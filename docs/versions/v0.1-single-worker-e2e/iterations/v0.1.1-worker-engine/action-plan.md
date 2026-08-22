# v0.1.1 Action Plan — Worker Engine

- [x] T1 — Test-First: contract test for the runner loop using
      `ScriptedWorker` + fake docker (red before implementation)
      → `tests/test_runner_contract.py`
- [x] T2 — Spike: bind `CodexAppServerClient` to the real Codex App Server;
      record protocol findings in implementation-notes; adjust interface if
      needed → newline-delimited JSON-RPC over stdio confirmed; findings in
      implementation-notes (Key Decisions)
- [x] T3 — Create the FastAPI template repository (app + pytest + Dockerfile
      + `/healthz`), register URL as `EDS_TEMPLATE_REPO_URL`
      → `template/fastapi-service/` published via `ensure_bare_repo`;
      env override honored
- [x] T4 — Implement `sandbox/manager.py` (dirs, isolation, idempotent
      destroy) with unit tests → `tests/test_sandbox.py`
- [x] T5 — Implement `control/repository.py` (checkout/commit_candidate)
      with unit tests (local fixture repo) → `tests/test_repository.py`
- [x] T6 — Implement `codex/worker_driver.py` incl. `ScriptedWorker`,
      async status registry, event capture — contract tests green
      → `tests/test_worker_driver.py` + contract suite
- [x] T7 — Implement `deployment/docker.py` (build/run/health) + docker
      integration test (marked) → `tests/test_docker_integration.py`
      (2 passed against real docker)
- [x] T8 — Implement `runner.py` CLI; contract test (T1) green; live run
      against real Codex produces a reachable `/docs` (record evidence)
      → CLI delivered a live `http://localhost:58943/docs` serving the
      requirement (scripted worker + real docker; see implementation-notes
      Deviations: real-Codex delivery blocked by account usage limit until
      Aug 27, 2026 — binding validated, failure path exercised)

Acceptance: `uv run pytest -q` green (36 passed, no docker/codex needed);
marked integration/e2e suites pass when docker/codex available
(docker: 2 passed; codex: skipped — account quota); `runner.py`
demo yields `http://localhost:<port>/docs`.
