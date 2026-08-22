# v0.1.5 Action Plan — EDS CLI

- [x] T1 — Test-First: CLI tests against a fake A2A server (submit/status/
      watch/open, exit codes) — red
- [x] T2 — Implement `cli.py` + A2A client module; declare httpx; T1 green
- [x] T3 — Implement `serve` (uvicorn factory on the a2a_api app) and
      verify against the real v0.1.4 endpoint (dogfooded live: real
      `eds serve` subprocess, healthz + agent card + task lifecycle)
- [x] T4 — Packaging: console script `eds` works with the flat layout
      (hatchling + explicit include list); README quickstart updated
- [x] T5 — Dogfood the full user loop end-to-end: `serve` → `submit
      "/hello requirement"` → `status --watch` → `open` → Swagger UI
      verification; evidence `human_acceptance_check` recorded
      (wo-ffffe93012fc) — offline demo backend
      (`EDS_SUPERVISOR_BACKEND=deterministic` + `EDS_WORKER_SCRIPT`)
      added to make the loop runnable without LLM credentials

Acceptance: a user can test EDS in four commands without knowing A2A
exists; README quickstart documents the loop.
