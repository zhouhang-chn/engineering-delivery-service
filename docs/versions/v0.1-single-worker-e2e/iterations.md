# v0.1 Iterations — Single Worker End-to-End

Four iterations, bottom-up by risk: engine first (Codex + sandbox + deploy),
then durable tools, then the Supervisor that drives them, then the A2A
surface. Each iteration ends with a runnable, demonstrable system slice;
the chain stays executable end-to-end via the CLI runner from v0.1.1 on.

| Iteration | Focus | Exit criterion |
|---|---|---|
| **v0.1.1-worker-engine** | template repo, sandbox, Codex client + worker driver, git candidate, pytest evidence, Docker deploy — driven by a CLI runner | `runner` turns a requirement into a live `<port>/docs` |
| **v0.1.2-durable-state-tools** | alembic init, PostgreSQL persistence, M1 Delivery Control tools, audit events, retry policy | same flow, but every step durable + restart-inspectable via tools |
| **v0.1.3-react-supervisor** | ADK Supervisor (prompts + function tools + session) replaces the scripted runner logic | Supervisor autonomously drives a work order to deployment |
| **v0.1.4-a2a-endpoint** | A2A endpoint, completion artifacts, full-chain e2e + dogfooding, version close-out | A2A task in → `completed` with artifacts; M1 exit criteria met |

Estimated production LOC: ~700 / ~450 / ~350 / ~350 (total ≈ 1,850, within
the 1,000–3,000 version budget).

Dependency order is strict: 1.1 → 1.2 → 1.3 → 1.4. The riskiest unknown
(Codex App Server binding) is spiked in the first tasks of v0.1.1.
