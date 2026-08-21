# Supervisor

**Status:** Current · **Component:** `agent/` (Google ADK)

## 1. Role

The Supervisor is the free-running ReAct controller that owns delivery. Its
single goal:

> Keep driving the current Engineering Work Order until all acceptance
> criteria are independently verified AND the deployment is available at
> `/docs`. Both conditions — not just one — are required to finish.

Loop:

```
Observe → Reason → Choose Tool → Act → Observe Result → Reason Again
```

until the goal state is reached.

## 2. Per-Turn Context

Each turn the Supervisor receives:

```
Work Order                  requirement, criteria, baseline
Current State               durable snapshot via get_current_state()
Recent Worker/Inspector     events from runtimes
Open Questions              clarifications pending an answer
Open Gaps                   unverified criteria, known defects
Available Tools             the Delivery Control inventory
```

Context comes from durable state, never from the Supervisor's conversation
memory (Principle 4).

## 3. Decision Space

```
ask user? · call worker? · continue worker? · approve? · inspect?
fix? · deploy? · verify deployment? · finish?
```

Controlling the Worker (and Inspector) through the Codex App Server, the
Supervisor may: start/resume a thread, start a turn, answer a clarification,
approve/reject a requested operation, steer, interrupt, and continue after
completion. Questions raised by the Worker are answered by the Supervisor
first: answerable from the work order → answer directly; genuine business
ambiguity → escalate to the human via A2A `input-required` (v0.4).

## 4. Non-Responsibilities

The Supervisor never: checks out repositories, reads large amounts of code,
edits source, runs pytest, or debugs. Those belong to
[Worker and Inspector](worker-inspector-runtimes.md). The Supervisor only
maintains: goal, current state, open gaps, next action.

## 5. Implementation

- Google ADK `LlmAgent` in `agent/supervisor.py`, wired with the
  [Delivery Control tools](delivery-control.md).
- System prompt: `agent/prompts/supervisor_system.md` — kept concise and
  structured around Goal / Current State / Open Gaps / Next Action.
- One ADK session per work order; session state is a cache, PostgreSQL is
  the truth.
- Termination: `mark_complete` (both finish conditions met) or `mark_failed`
  (cannot continue, reason persisted). Recovery after restart is a v0.6
  concern: the Supervisor re-derives progress from durable state.
