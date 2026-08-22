# v0.1.4 Action Plan — A2A Endpoint & Close-out

- [x] T1 — Test-First: endpoint tests with a scripted supervisor backend
      (state mapping, artifact assembly, error mapping) — red
- [x] T2 — Implement `create_app()` + background supervisor launch; T1 green
- [x] T3 — Full-chain e2e test (marked): real uvicorn endpoint + raw
      httpx A2A call + real Docker → artifacts + `/docs` reachable
      (`-m docker`, green); the real-Codex+real-LLM leg exists
      (`-m 'llm and codex'`) but skips without credentials — see
      implementation notes
- [x] T4 — Dogfood: run the `/hello` requirement through a raw A2A client
      call (httpx); record the Swagger-UI verification as evidence
      (`human_acceptance_check`, work order wo-c5392084ce82) — the
      polished CLI arrives in v0.1.5
- [x] T5 — Update CHANGELOG.md + README.md (run/usage instructions)
- [x] T6 — Run version gate; fix findings; conduct retrospective and
      finalize version `retrospect.md`; check remaining version-level tasks
      (executed after v0.1.5 with the version close-out)
- [x] T7 — Merge version branch via PR; update `docs/milestones.md` to
      COMPLETE with date (PR from the stacked v0.1.5 branch carries the
      whole version; milestones updated 2026-08-22)

Acceptance: M1 exit criteria demonstrated end-to-end; gate passes;
retrospective actions executed.
