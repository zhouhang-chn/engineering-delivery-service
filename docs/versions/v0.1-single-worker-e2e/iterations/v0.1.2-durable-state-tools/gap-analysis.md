# v0.1.2 Gap Analysis — Durable State & Tools

**Goal:** make the v0.1.1 flow durable and tool-driven: work orders,
events, evidence and deployment facts live in PostgreSQL; the M1 tool
subset is implemented and unit-tested; the runner calls tools instead of
modules directly.

**Current state:** models exist but nothing persists; tools raise
`NotImplementedError`; no alembic; worker status is in-memory.

**Gaps:** alembic init + initial migration · session/engine plumbing
(`control/state.py`) · implement 9 M1 tools · audit events on every
state-changing call · retry policy applied to runtime/deploy calls ·
runner rewired onto tools.
