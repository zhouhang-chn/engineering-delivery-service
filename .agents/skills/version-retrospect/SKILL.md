---
name: version-retrospect
description: Standardized Scrum/Agile milestone retrospective skill for Engineering Delivery Service. Use when conducting end-of-version retrospectives, analyzing development velocity, conducting 5-Whys root cause analysis on Day-2 bug surges, optimizing agent configurations/prompts/tools, and propagating continuous improvement (Kaizen) action items.
---

# Version Retrospective Skill (Agile / Kaizen Edition)

This skill guides coding agents through conducting an evidence-based, **Scrum Agile Retrospective** at the conclusion of any development version (`vX.Y`) or major iteration in the `engineering-delivery-service` repository.

In Scrum, the retrospective is the single most critical ceremony for **Continuous Improvement (Kaizen)** — inspecting people, processes, tools, and definitions of done (DoD) to adapt and increase team velocity and quality in the next sprint. For an AI coding agent, the retrospective systematically inspects:
1. **Engineering Velocity & Quality**: Test coverage, delivery-loop reliability, cycle time, and escaped defects.
2. **Process Flow & Bureaucracy**: Removing developer friction, minimizing unnecessary steps, and streamlining iteration lifecycles.
3. **Agent Configurations, Prompts & Tool Ergonomics**: Hardening agent instructions, optimizing Supervisor prompts and Delivery Control tool schemas, eliminating multi-turn loops.
4. **Escaped Defect 5-Whys Root Cause Analysis**: Investigating every post-completion bug surge to eliminate root causes rather than patching symptoms.

---

## 1. When to Trigger

Activate this skill whenever:
1. A version/milestone reaches Phase 4 of the [development-workflow skill](file:///.agents/skills/development-workflow/SKILL.md).
2. The user requests a retrospective (e.g. *"do version retrospect of v0.1"*, *"review sprint friction and improvements"*).
3. Transitioning from a completed milestone (`vX.Y`) to the next planned milestone (`vX.Y+1`).

---

## 2. The 5-Step Agile Retrospective Workflow

```
Step 1: Quantitative Telemetry & Sprint Metrics
   ↓
Step 2: 4-Quadrant Agile Inspection (Keep, Stop, 5-Whys, Try)
   ↓
Step 3: Agent Configuration & Prompt/Tool Kaizen
   ↓
Step 4: 4-Category Action Item Formulation & Immediate Execution
   ↓
Step 5: Quality Gate Verification & Commit/Push Protocol
```

---

### Step 1: Quantitative Telemetry & Sprint Metrics

Gather objective, measurable data from the codebase before drawing qualitative conclusions:

```bash
# 1. Test Suite Pass Count & Execution Time
uv run pytest tests/ -q

# 2. Lint Compliance
uv run ruff check .

# 3. Git Commit History & Day-2 Escaped Defect Audit
git log --oneline $(git merge-base main HEAD)..HEAD

# 4. Version Completeness Gate Status
uv run python .agents/scripts/verify_version.py <version-dir>
```

Compile telemetry metrics into a standardized summary scorecard:
- **Total Passing Tests**: (e.g. 18 unit/integration tests across 4 test modules)
- **Escaped Defect Count (Day-2 Bug Surge)**: Number of fix/refactor commits created after initial iteration completion.
- **Delivery-Loop Metrics** (from Work Order events once M1+ runs real work orders): worker→inspector cycle count, REJECT→fix turnaround, Supervisor turns per delivery.
- **Lint Compliance**: 0 ruff errors across all source files.
- **Quality Gate Score**: (e.g. 12/12 automated checks passed in `verify_version.py`).

---

### Step 2: 4-Quadrant Agile Inspection

Structure qualitative reflection into the standard 4 Agile Retrospective Quadrants:

#### 1. What Went Well (Keep / Amplify)
- **Architectural Wins**: Which abstractions, models, or design patterns accelerated implementation and remained durable?
- **Process & Tooling Wins**: Which scripts, gates, or sandbox/deployment primitives delivered rapid feedback loops?
- **Delivery Capability Unlocks**: What concrete, end-to-end capability was delivered (e.g. a work order going from A2A request to a live `/docs` the user can verify)?

#### 2. What Went Wrong & Friction Points (Stop / Drop)
- **Development Friction**: Where did the coding agent get stuck, loop needlessly, or generate excessive token overhead?
- **Process Waste**: Were there administrative documentation burdens that provided low signal relative to effort?
- **Tool / Schema Mismatches**: Did Delivery Control tool signatures, Work Order state shapes, or Codex App Server events cause runtime errors or confusion?

#### 3. Escaped Defect Analysis via 5 Whys (Root Cause Investigation)
Analyze every commit with a `fix(...)` prefix or changes made *after* a version was initially thought complete:
- **Why 1**: What was the immediate defect/symptom?
- **Why 2**: Why was it not caught during initial design and task execution?
- **Why 3**: Why did the test suite or quality gate not catch it prior to completion?
- **Why 4**: Was there a missing architectural principle, state validation rule, or dogfooding check?
- **Why 5**: What systemic change (rule, gate check, fixture, tool schema) guarantees this class of defect never recurs?

#### 4. Experiments & Kaizen Proposals (Start / Try)
- What new architectural pattern, automated check, prompt instruction, or tooling experiment should be piloted in the next milestone?

---

### Step 3: Agent Configuration & Prompt/Tool Kaizen

Examine the human-agent collaboration and agent runtime configuration to optimize efficiency:

1. **Agent Instructions & Behavioral Guidelines** (`AGENTS.md` when present, plus the skills themselves):
   - Did the agent require repeated manual steering or reminders?
   - Update instructions with explicit positive guidelines and negative anti-patterns.
2. **Supervisor Prompt & Delivery Control Tool Economy**:
   - Are Supervisor system prompts concise and structured around Goal / Current State / Open Gaps / Next Action?
   - Are tool schemas typed, descriptive, and error-tolerant (returning actionable resolution hints rather than leaking Python stack traces)?
3. **Automated Quality Gates (`.agents/scripts/`)**:
   - Can manual checklist items from this sprint be automated as AST or runtime checks in `verify_version.py` or `.agents/scripts/githooks/`?

---

### Step 4: 4-Category Action Plan & Immediate Operationalization

All retrospective learnings must be formulated into actionable items across four categories:

| Category | Purpose | Typical Target Locations |
| :--- | :--- | :--- |
| **Category 1: Core Design Principles** | Codify permanent architectural rules so future agents never repeat mistakes. | `docs/refer/engineering-delivery-service-architecture.md`, `AGENTS.md`, `README.md` |
| **Category 2: Quality Gates & Verification** | Add automated AST/runtime checks to prevent regressions. | `.agents/scripts/verify_version.py`, `.agents/scripts/githooks/` |
| **Category 3: Tooling, Defaults & Infrastructure** | Provide reusable utilities, fixtures, and sensible defaults. | `.agents/scripts/`, `pyproject.toml`, `docker-compose.yml` |
| **Category 4: Next Milestone Propagation** | Update future version designs and action plans to adopt lessons learned. | `docs/versions/vX.Y+1/design.md`, `action-plan.md`, `docs/milestones.md` |

#### The Operationalization Rule: Execute Now, Don't Defer
Retrospective action items are **not a passive wishlist**. In accordance with Agile Kaizen:
- **Category 1, 2, 3 Action Items MUST be implemented and tested immediately** during the retrospective turn (updating instructions, adding checks to `verify_version.py`, updating tooling).
- **Category 4 Action Items MUST be written directly** into the next milestone's `gap-analysis.md`, `design.md`, and `action-plan.md`.

---

### Step 5: Authoring `retrospect.md`

Create or finalize `docs/versions/vX.Y-<name>/retrospect.md` using this compact, high-density template:

```markdown
# Version X.Y Retrospective: <Version Title>

**Milestone**: `vX.Y-<name>`  
**Status**: ✅ COMPLETE  
**Completion Date**: YYYY-MM-DD  
**Quality Gate Result**: PASSED (X/X checks passed)

---

## 1. Executive Summary & Value Delivered
<1-2 concise paragraphs summarizing capabilities delivered, user value unlocked, and system evolution>

---

## 2. Quantitative Scorecard & Sprint Velocity
| Metric | Target | Actual | Status |
| :--- | :--- | :--- | :--- |
| **Total Automated Tests** | ≥ X | **Y passed** (Z test modules) | ✅ Exceeded |
| **Lint Check Errors** | 0 errors | **0 errors** (`ruff`) | ✅ Met |
| **Docstring AST Coverage** | 100% public symbols | **100%** | ✅ Met |
| **Escaped Defect Rate (Day-2)**| 0 critical bugs | **X non-critical post-fixes** | ✅ Audited |
| **Delivery-Loop Health** | worker→inspector cycles within budget | **X cycles, Y REJECT→fix turnarounds** | ✅ Met |
| **Completeness Gate** | All checks pass | **X/X checks passed** (`verify_version.py`) | ✅ Met |

---

## 3. 4-Quadrant Agile Retrospective

### 1. What Went Well (Keep / Amplify)
- **<Win 1 Title>**: <Explanation of why it worked and why we keep it>
- **<Win 2 Title>**: <Explanation of why it worked and why we keep it>

### 2. What Went Wrong & Friction Points (Stop / Drop)
- **<Friction 1 Title>**: <Root cause, wasted effort, and what we drop>
- **<Friction 2 Title>**: <Root cause, wasted effort, and what we drop>

### 3. Escaped Defect 5-Whys Root Cause Analysis
- **Defect A (<Commit / Area>)**:
  - *Why 1*: <Immediate symptom>
  - *Why 2*: <Why missed during implementation>
  - *Why 3*: <Why missed by tests/gates>
  - *Why 4*: <Systemic gap>
  - *Why 5 & Permanent Fix*: <Root cause eliminated via rule/gate>

### 4. Kaizen Proposals & Experiments (Start / Try)
- **<Experiment 1>**: <Hypothesis and expected efficiency benefit>

---

## 4. Action Items & System Evolution
| ID | Action Item | Category | Target Location | Status |
| :--- | :--- | :--- | :--- | :--- |
| **A1** | <Description> | Category 1 (Principles) | docs/refer/engineering-delivery-service-architecture.md | ✅ Done |
| **A2** | <Description> | Category 2 (Gates) | .agents/scripts/verify_version.py | ✅ Done |
| **A3** | <Description> | Category 3 (Tooling) | .agents/scripts/ | ✅ Done |
| **A4** | <Description> | Category 4 (Next Version) | docs/versions/vX.Y+1/design.md | ✅ Done |

---

## 5. Next Version Scope (vX.Y+1 — <Next Milestone Title>)
<Bullet points summarizing the next milestone focus and how retrospective learnings are incorporated>
```

---

### Step 6: Gate Verification & Mandatory Commit/Push Protocol

In accordance with [Section 6 of the development-workflow skill](file:///.agents/skills/development-workflow/SKILL.md):

1. **Run Full Verification**:
   ```bash
   uv run python .agents/scripts/verify_version.py <version-dir>
   uv run pytest tests/
   uv run ruff check .
   ```
2. **Stage All Changes**:
   ```bash
   git add -A
   ```
3. **Commit with Conventional Multi-part Structure**:
   ```bash
   git commit -m "retrospect(vX.Y): conduct milestone retrospective and codify architectural principles" \
     -m "Document vX.Y sprint metrics, conduct 4-quadrant agile inspection and 5-Whys root cause analysis on Day-2 defects, optimize agent configurations, and propagate Kaizen action items." \
     -m "Key Changes:
   - docs/versions/vX.Y/retrospect.md: Finalize agile retrospective analysis and scorecard.
   - .agents/skills/: Codify new behavioral guidelines.
   - .agents/scripts/verify_version.py: Add automated quality gate enhancements.
   - docs/versions/vX.Y+1/: Update gap analysis, design, and action plan." \
     -m "Verification:
   - verify_version.py passed X/X checks.
   - pytest passed all tests.
   - ruff reported 0 errors."
   ```
4. **Push to Remote Branch**:
   ```bash
   git push origin <branch-name>
   ```
5. **Return Confirmation to User**: Deliver a concise summary including verified metrics, action items executed, and commit hash.

---

## 3. Retrospective Antipatterns to Avoid

- ❌ **Passive Wishlists**: Listing action items in markdown without actually updating instructions, `verify_version.py`, or future design docs during the turn.
- ❌ **Superficial Blame ("LLM hallucinated")**: Blaming the model instead of analyzing missing prompt constraints, loose tool schemas, or weak validation gates.
- ❌ **Ignoring Escaped Defect Surges**: Declaring a milestone successful while ignoring 5+ emergency bug fix commits made post-completion.
- ❌ **Administrative Bloat**: Writing multi-page generic essays instead of high-density, actionable tables and 5-Whys root-cause analyses.
- ❌ **Leaving Dirty Working Trees**: Completing the turn without committing and pushing all verified retrospective artifacts.
