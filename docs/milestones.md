# Milestones

Version-driven milestone plan. Status values: `PLANNED` → `IN-PROGRESS` → `COMPLETE`.

Source: architecture doc §14 (docs/refer/engineering-delivery-service-architecture.md).
Every milestone must keep the full chain `API Requirement → Development → Testing →
Deployment → /docs` runnable end-to-end.

| Version | Milestone | Scope Summary | Status | Date |
|---|---|---|---|---|
| v0.1 | M1 — Single Worker End-to-End | A2A → Supervisor → Worker Codex → FastAPI → pytest → Docker deploy → /docs | PLANNED | |
| v0.2 | M2 — Durable Delivery Control | PostgreSQL Work Order state + Delivery Control tools + restart recovery | PLANNED | |
| v0.3 | M3 — Independent Inspector | Worker → Inspector ACCEPT/REJECT feedback loop | PLANNED | |
| v0.4 | M4 — Requirement Confirmation + HITL | Confirmed requirement + acceptance criteria + clarification loop | PLANNED | |
| v0.5 | M5 — Project-aware API Delivery | Project registry, repository resolver, worktrees, PR delivery | PLANNED | |
| v0.6 | M6 — Recoverable Autonomous Delivery | Crash/retry/resume/rollback, bounded autonomy, escalation | PLANNED | |
