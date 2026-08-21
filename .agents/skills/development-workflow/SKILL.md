---
name: development-workflow
description: Version-driven development workflow guide for Engineering Delivery Service. Use when planning, designing, implementing, testing, dogfooding, or completing versions/iterations and quality gates.
---

# Engineering Delivery Service — Development Workflow Skill

This skill guides coding agents through the standardized version-driven engineering lifecycle for the `engineering-delivery-service` repository.

## 1. Core Principles Review (Mandatory Before Any Design)

Before writing any `gap-analysis.md`, `design.md`, or code, you MUST review the architecture doc in [docs/refer/engineering-delivery-service-architecture.md](../../../docs/refer/engineering-delivery-service-architecture.md) and these core principles:

1. **Supervisor Owns the Delivery**: The top-level controller is a free-running ReAct Supervisor. Never introduce a deterministic workflow/pipeline layer above it — flow control belongs to the Supervisor.
2. **Delivery Control Is Deterministic**: `tools/` and `control/` provide reliable state and actions (CRUD, lifecycle, retry/timeout primitives, audit). They never decide "what should happen next".
3. **Worker Produces the Candidate; Inspector Establishes the Truth**: Worker "done" only means the candidate is ready for inspection, never that the Work Order is complete. The Inspector verifies independently and never modifies the candidate. Worker and Inspector never communicate directly.
4. **Durable State over Conversation Memory**: Every decision input (current state, open gaps, evidence) is persisted in PostgreSQL Work Order state and re-read via Delivery Control tools each turn.
5. **Evidence-Based Acceptance**: Completion claims require persisted evidence — pytest results, inspection verdicts, deployment health checks — not agent assertions.
6. **End-to-End Runnable at Every Version**: Every version must keep the full chain `Requirement → Development → Testing → Deployment → /docs` working. Later versions add autonomy, reliability, and engineering quality — never a partial pipeline.
7. **MVP Scope Discipline**: FastAPI only, single Git repository, until the project milestone plan explicitly lifts the constraint.

---

## 2. Iteration Sizing & Document Structure

Every version (and iteration) must target **1,000–3,000 LOC of production code** and maintain five mandatory documents:

```
docs/versions/vX.Y-description/
├── gap-analysis.md           # 1. Goal vs. current state + risk assessment
├── design.md                 # 2. Detailed component interfaces and algorithms
├── action-plan.md            # 3. Concrete tasks with verifiable acceptance criteria
├── implementation-notes.md   # 4. Written DURING implementation (after each task)
└── retrospect.md             # 5. Milestone retrospective with metrics & action items
```

When a version is split into iterations:
- Add `iterations.md` at the version level.
- Create subdirectories under `iterations/vX.Y.Z-description/` with their own `gap-analysis.md`, `design.md`, `action-plan.md`, and `implementation-notes.md`.

---

## 3. Step-by-Step Version Lifecycle

```
PLANNED → IN-PROGRESS → COMPLETE
```

### Phase 1: Planning & Design
1. Create and checkout version branch: `git checkout -b vX.Y-description`
2. Update `docs/milestones.md` status to `IN-PROGRESS`.
3. Review the architecture doc and core design principles above.
4. Write `gap-analysis.md` and `design.md`.
5. If splitting into iterations, write `iterations.md` and iteration design docs.
6. Write `action-plan.md` with explicit task IDs (e.g. `T1`, `T2`). Ensure the LAST task is: *"Mark version COMPLETE — run `uv run python .agents/scripts/verify_version.py <version>`, update docs/milestones.md, finalize retrospect.md"*.
7. Write at least one failing test that captures the version's core behavior before writing implementation code (Test-First).

### Phase 2: Implementation & Continuous Notes
1. Implement tasks one by one.
2. **Mandatory**: Immediately after completing each task, append an entry to `implementation-notes.md` under:
   - `## Key Decisions`
   - `## Deviations from Design`
   - `## Bugs Encountered`
   - `## Lessons Learned`
3. Run tests continuously: `uv run pytest tests/ -q` and `uv run ruff check .`.
4. Ensure no `TODO|FIXME|HACK|XXX` markers or conversational thinking comments are left in production code.

### Phase 3: Verification & Dogfooding
1. Run static checks:
   - `uv run ruff check .`
2. Run automated test suite:
   - `uv run pytest tests/`
3. **Dogfood the real delivery path**: exercise the system the way a caller would — submit a real API work order through the A2A endpoint and verify the deployed service's `/docs` (open Swagger UI → Try it out → Execute → check the response against the requirement). For versions delivered before the A2A endpoint exists, dogfood whatever end-to-end surface the version provides.
4. Run the automated gate script:
   ```bash
   uv run python .agents/scripts/verify_version.py <version-dir>
   ```
   The script MUST pass with exit code 0.

### Phase 4: Version Completion & Agile Retrospective
1. Complete manual review and operational dogfooding checklist.
2. Conduct the Scrum Agile milestone retrospective using the [version-retrospect skill](file:///.agents/skills/version-retrospect/SKILL.md) and finalize `retrospect.md` (4-quadrant inspection, 5-Whys root cause analysis, sprint scorecard).
3. **Execute in-sprint action items immediately**: Update the architecture principles documentation, `AGENTS.md` (when present), and `.agents/scripts/`.
4. Propagate next milestone action items into `docs/versions/vX.Y+1-*/`.
5. Update `docs/milestones.md` to `COMPLETE` with date.
6. Update `CHANGELOG.md` and `README.md`.
7. Merge version branch into `main` via pull request.

---

## 4. Key Tooling Commands

- **Run Quality Gate**: `uv run python .agents/scripts/verify_version.py <version-dir>`
- **Run Unit Tests**: `uv run pytest tests/`
- **Lint Code**: `uv run ruff check .`
- **Bring up durable state**: `docker compose up -d postgres`

---

## 5. Git Commit Message Standards

Bare oneliner commit messages are **prohibited** for `feat`, `fix`, `refactor`, and `perf` commits. Always format commit messages with context, key changes, and verification:

```text
<type>(<scope>): <summary> (<Task-ID>)

<Context: why this change was necessary and what problem it solves>

Key Changes:
- <subsystem>: Technical details of algorithm, model, or interface updates.
- <subsystem>: Edge cases, bug resolutions, or parameter handling.

Verification:
- <Test and gate commands executed, e.g. uv run pytest tests/ -q (12 passed)>
```

Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `perf`, `retrospect`.

Enforced automatically via `.agents/scripts/githooks/commit-msg` once hooks are
installed:

```bash
git config core.hooksPath .agents/scripts/githooks
```

---

## 6. Commit & Push Protocol (Mandatory Before Turn Completion)

Coding agents **MUST commit and push all verified changes before returning their turn/response to the user**.

### Execution Rules
1. **Never leave dirty working directories**: All modified code, documentation, scripts, and tests that are verified MUST be committed and pushed to the current branch before handing the turn back to the user.
2. **Pre-Commit Verification Sequence**:
   - `uv run pytest tests/`
   - `uv run ruff check .`
   - `uv run python .agents/scripts/verify_version.py <version-dir>` (for iteration or version completion)
3. **Commit & Push Execution**:
   - `git add <files>`
   - `git commit -m "<header>" -m "<Context>" -m "<Key Changes>" -m "<Verification>"`
   - `git push origin <branch-name>`
4. **Direct pushes to `main` are blocked** by the `pre-push` hook: work happens on version branches and lands in `main` via pull request.
5. **Final Response**:
   - Include the commit hash / push confirmation in the response to the user.
