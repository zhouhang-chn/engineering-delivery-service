# EDS Design Docs

Top-level system design for Engineering Delivery Service. These docs are the
living source of truth for how the system is designed; the original
architecture draft is preserved unchanged under
[../refer/engineering-delivery-service-architecture.md](../refer/engineering-delivery-service-architecture.md).

| Doc | Scope |
|---|---|
| [system-architecture.md](system-architecture.md) | Positioning, core principles, component model, tech stack, code layout |
| [a2a-interface.md](a2a-interface.md) | External contract: A2A Task ≈ Engineering Work Order |
| [supervisor.md](supervisor.md) | ReAct Supervisor run model and decision space |
| [delivery-control.md](delivery-control.md) | Deterministic Delivery Control tools and policies |
| [worker-inspector-runtimes.md](worker-inspector-runtimes.md) | Codex App Server runtimes, sandboxes, the delivery loop |
| [work-order-state.md](work-order-state.md) | PostgreSQL durable state: schema and lifecycle |
| [deployment.md](deployment.md) | Docker deployment runtime and acceptance |
| [mvp-delivery-protocol.md](mvp-delivery-protocol.md) | The FastAPI work-order input/output/acceptance contract |

Version-specific designs (gap analysis, per-version design, action plans)
live under `docs/versions/vX.Y-*/` per the development workflow; see
[../milestones.md](../milestones.md) for the milestone plan (v0.1–v0.6 ↔ M1–M6).
