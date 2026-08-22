# Worker / Inspector Runtimes

**Status:** Current · **Components:** `codex/`, `sandbox/`

## 1. Worker Runtime

The Worker is a complete engineering runtime in a **writable sandbox**:

```
Worker Sandbox
├── Git workspace (baseline checked out)
├── FastAPI project
├── Python environment
├── Codex App Server + Codex thread
└── Worker driver (codex/worker_driver.py)
```

The Worker may: check out and read code, understand the project, design the
API, modify code, add tests, run pytest, start the service, debug, and
adjust Dockerfile/deployment files. It must not write to `.git` (commit,
stage, stash): the Codex `workspace-write` sandbox denies git-metadata
writes by design, and the candidate commit is recorded by Delivery Control
(`commit_candidate`) outside the sandbox — which also keeps the worker from
planting `.git/hooks` that would execute with EDS's own privileges.

Worker output:

```
working-tree changes + engineering summary + test evidence + remaining concerns
```

**"done" semantics**: Worker done means *the candidate is ready for
inspection* — nothing more. Never the work order being complete.

## 2. Inspector Runtime

The Inspector is a second complete engineering runtime in a **clean sandbox**,
acting as reviewer + tester + acceptance engineer:

```
Inspector Sandbox
├── Independent checkout of the candidate commit
├── Python environment
├── Codex App Server + fresh Codex thread
└── Inspection driver (codex/inspector_driver.py)
```

Inspector input:

```
original requirement · acceptance criteria · baseline commit
candidate commit · project constraints · deployment contract
```

It deliberately does NOT receive the Worker's reasoning history.

Typical inspection:

```
checkout candidate → read requirement → read implementation → review diff
→ run existing tests → add temporary tests/probes → start FastAPI
→ call the API → inspect OpenAPI schema → compare with criteria
→ ACCEPT / REJECT
```

Output: `verdict · verified criteria · failed criteria · evidence · gaps · risk`.

**The Inspector never modifies the candidate.** On defect it returns
`REJECT + evidence`; the Supervisor turns that into a fix task for the Worker.

## 3. Why Codex App Server

The Supervisor needs continuous observation and control of the engineering
process — not one-shot `codex exec` calls:

```
start/resume thread · start turn · answer clarification · approve/reject
steer · interrupt · continue after completion
```

while observing: turn status, item status, agent messages, command
executions, file changes, questions, approval requests, errors, completion
events. The App Server (`codex/app_server_client.py`) is therefore the
bidirectional control interface between Supervisor and each runtime.

## 4. The Closed Loop

```
Supervisor ──task──▶ Worker ──candidate + done──▶ Supervisor
                                                     │ inspect
                                                     ▼
                                                 Inspector
                                                 ACCEPT / REJECT
       fix task ◀── feedback (REJECT) ── Supervisor ── ACCEPT ──▶ Deploy
```

Worker and Inspector never communicate directly; all coordination passes
through the Supervisor (Principle 3).

## 5. Isolation

Each runtime gets its own sandbox (`sandbox/manager.py`): separate container,
separate git workspace, separate Python environment, separate Codex App
Server instance. The Worker's sandbox is writable; the Inspector's is a clean
checkout. Neither sandbox shares state with the EDS service process beyond
explicit inputs (work order data, commits).
