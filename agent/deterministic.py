"""Deterministic fallback Supervisor model.

A rule-based ``BaseLlm`` that walks the M1 delivery order by reading
durable state — runtime → checkout → worker turn (poll) → acceptance
tests → candidate commit → deploy → mark_complete/mark_failed.

It exists so `eds serve` can run the full delivery loop in demos and
tests without LLM credentials (``EDS_SUPERVISOR_BACKEND=deterministic``).
The ADK ``LlmAgent`` with a real model remains the default Supervisor;
this backend never reasons — it replays the canonical order, so it is
NOT an autonomous controller and is never used when a model is
configured. Every stage decision is derived from durable state
(work order fields + evidence rows), never from instance memory.
"""

from __future__ import annotations

import time
from typing import ClassVar

from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_response import LlmResponse
from google.genai import types

POLL_SLEEP_S = 0.5


def deterministic_llm_factory(work_order_id: str) -> DeterministicSupervisorLlm:
    """llm_factory hook: one deterministic model per work order."""
    return DeterministicSupervisorLlm(work_order_id=work_order_id)


class DeterministicSupervisorLlm(BaseLlm):
    """Replays the canonical delivery order from durable state."""

    model: str = "eds-deterministic"
    work_order_id: str = ""
    _steps: int = 0

    MAX_STEPS: ClassVar[int] = 200

    def _next_action(self) -> dict:
        """Decide the next tool call from the durable snapshot."""
        from tools.work_order import get_current_state, get_work_order

        wo = self.work_order_id
        state = get_current_state(wo)
        worker = state["worker"]
        deployment = state["deployment"]

        if state["overall_status"] in ("complete", "failed"):
            return {"text": f"terminal: {state['overall_status']}"}
        if worker.get("runtime_id") is None:
            return {"tool": "create_worker_runtime", "args": {"work_order_id": wo}}
        if not get_work_order(wo).get("baseline_commit"):
            return {"tool": "checkout_baseline", "args": {"work_order_id": wo}}
        if not _worker_turn_started(wo):
            return {"tool": "start_worker_turn", "args": {"work_order_id": wo}}
        if worker["status"] in ("starting", "running", "waiting"):
            time.sleep(POLL_SLEEP_S)  # real worker turns take minutes
            return {"tool": "get_worker_status", "args": {"work_order_id": wo}}
        if worker["status"] == "failed":
            reason = f"worker failed: {worker.get('error') or 'unknown error'}"
            return {"tool": "mark_failed", "args": {"work_order_id": wo, "reason": reason}}
        if not _acceptance_evidence_passed(wo):
            if _has_pytest_evidence(wo):
                return {
                    "tool": "mark_failed",
                    "args": {
                        "work_order_id": wo,
                        "reason": "acceptance tests failed (see pytest_run evidence)",
                    },
                }
            return {"tool": "run_acceptance_tests", "args": {"work_order_id": wo}}
        if not worker.get("candidate_commit"):
            return {"tool": "commit_candidate", "args": {"work_order_id": wo}}
        if deployment.get("status") != "deployed":
            return {"tool": "deploy_candidate", "args": {"work_order_id": wo}}
        if deployment.get("health") != "healthy":
            return {
                "tool": "mark_failed",
                "args": {
                    "work_order_id": wo,
                    "reason": f"deployed but health={deployment.get('health')}",
                },
            }
        return {
            "tool": "mark_complete",
            "args": {
                "work_order_id": wo,
                "summary": "delivered; acceptance green; deployed healthy",
            },
        }

    async def generate_content_async(self, llm_request, stream=False):
        """Yield one tool call (or final text) per model turn.

        Self-bounded: ADK loops internally until the model yields a
        plain-text response, so a stuck delivery (e.g. a worker that
        never reaches a terminal status) must still produce one — after
        MAX_STEPS model turns this backend answers with text only,
        handing control back to the supervise loop's turn budget.
        """
        self._steps += 1
        if self._steps > self.MAX_STEPS:
            step = {"text": "deterministic step budget exhausted; yielding control"}
        else:
            step = self._next_action()
        if "tool" in step:
            part = types.Part(
                function_call=types.FunctionCall(
                    name=step["tool"], args=step.get("args", {})
                )
            )
        else:
            part = types.Part(text=step.get("text", ""))
        yield LlmResponse(content=types.Content(role="model", parts=[part]))


def _worker_turn_started(work_order_id: str) -> bool:
    """Whether a worker turn was launched (durable fact: audit event)."""
    from control.state import session_scope
    from db.models import Event

    with session_scope() as session:
        return (
            session.query(Event)
            .filter_by(work_order_id=work_order_id, type="worker.turn_started")
            .first()
            is not None
        )


def _latest_pytest_evidence(work_order_id: str):
    """The latest pytest_run evidence row, or None (durable fact)."""
    from control.state import session_scope
    from db.models import Evidence

    with session_scope() as session:
        return (
            session.query(Evidence)
            .filter_by(work_order_id=work_order_id, kind="pytest_run")
            .order_by(Evidence.id.desc())
            .first()
        )


def _has_pytest_evidence(work_order_id: str) -> bool:
    """Whether acceptance tests were recorded at all."""
    return _latest_pytest_evidence(work_order_id) is not None


def _acceptance_evidence_passed(work_order_id: str) -> bool:
    """Whether the latest recorded acceptance run passed."""
    row = _latest_pytest_evidence(work_order_id)
    return row is not None and (row.payload or {}).get("status") == "passed"
