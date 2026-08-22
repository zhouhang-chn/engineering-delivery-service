# v0.1 Action Plan — Single Worker End-to-End

Work happens iteration by iteration (see [iterations.md](iterations.md));
each iteration's own `action-plan.md` carries its checked tasks. This plan
tracks version-level tasks only.

- [x] T1 — Write version-level gap analysis, design, and iteration split
- [ ] T2 — Complete **v0.1.1-worker-engine** (all iteration tasks checked, tests green)
- [ ] T3 — Complete **v0.1.2-durable-state-tools**
- [ ] T4 — Complete **v0.1.3-react-supervisor**
- [ ] T5 — Complete **v0.1.4-a2a-endpoint** (includes full-chain e2e + dogfooding)
- [ ] T6 — Complete **v0.1.5-eds-cli** (user test loop: serve / submit / status --watch / open)
- [ ] T7 — Conduct retrospective, finalize `retrospect.md`, update `CHANGELOG.md`/`README.md`
- [ ] T8 — Mark version COMPLETE — run `uv run python .agents/scripts/verify_version.py v0.1-single-worker-e2e`, update `docs/milestones.md` to COMPLETE with date, merge version branch via PR
