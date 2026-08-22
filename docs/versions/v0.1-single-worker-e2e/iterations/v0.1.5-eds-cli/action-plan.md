# v0.1.5 Action Plan — EDS CLI

- [ ] T1 — Test-First: CLI tests against a fake A2A server (submit/status/
      watch/open, exit codes) — red
- [ ] T2 — Implement `cli.py` + A2A client module; declare httpx; T1 green
- [ ] T3 — Implement `serve` (uvicorn factory on the a2a_api app) and
      verify against the real v0.1.4 endpoint (marked live test or manual)
- [ ] T4 — Packaging: console script `eds` if the flat layout allows;
      otherwise document `uv run python -m cli`; update README quickstart
- [ ] T5 — Dogfood the full user loop end-to-end: `serve` → `submit
      "/hello requirement"` → `status --watch` → `open` → Swagger UI
      verification; record evidence and notes

Acceptance: a user can test EDS in four commands without knowing A2A
exists; README quickstart documents the loop.
