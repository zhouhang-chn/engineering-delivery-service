# v0.1.4 Action Plan — A2A Endpoint & Close-out

- [ ] T1 — Test-First: endpoint tests with a scripted supervisor backend
      (state mapping, artifact assembly, error mapping) — red
- [ ] T2 — Implement `create_app()` + background supervisor launch; T1 green
- [ ] T3 — Full-chain e2e test (marked): A2A → Codex → docker → artifacts
      + `/docs` reachable
- [ ] T4 — Dogfood: run the `/hello` requirement through a real A2A client;
      record the Swagger-UI verification as evidence
- [ ] T5 — Update CHANGELOG.md + README.md (run/usage instructions)
- [ ] T6 — Run version gate; fix findings; conduct retrospective and
      finalize version `retrospect.md`; check remaining version-level tasks
- [ ] T7 — Merge version branch via PR; update `docs/milestones.md` to
      COMPLETE with date

Acceptance: M1 exit criteria demonstrated end-to-end; gate passes;
retrospective actions executed.
