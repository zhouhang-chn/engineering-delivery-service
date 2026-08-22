"""Scripted LLM double for supervisor contract tests.

Replays a scripted sequence of model turns through the ADK ``BaseLlm``
interface: function calls, plain text, or a reactive worker-poll step
that keeps calling ``get_worker_status`` until the durable worker
status reaches the expected terminal value (so worker-thread timing
never makes tests racy).
"""

from __future__ import annotations

import time

from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_response import LlmResponse
from google.genai import types
from pydantic import Field

POLL_INTERVAL_S = 0.02


class ScriptedLlm(BaseLlm):
    """Test double LLM: replays scripted model turns.

    Steps (list of dicts):
      {"tool": "tool_name", "args": {...}}  -> one function call
      {"text": "..."}                       -> plain text response
      {"poll_worker": "done", "work_order_id": "..."}
        -> repeatedly call ``get_worker_status`` (the real durable
           tool) until ``status_fn`` reports the expected status, then
           continue with the next step.

    ``model_requests`` records every LLM invocation for assertions.
    """

    model: str = "scripted-test"
    steps: list = Field(default_factory=list)
    status_fn: object = None  # callable(work_order_id) -> worker status str
    model_requests: list = Field(default_factory=list)

    def _next_step(self) -> dict:
        """Resolve the next model turn, expanding poll_worker steps."""
        step = self.steps[0]
        if "poll_worker" in step:
            status = self.status_fn(step["work_order_id"])
            if status == step["poll_worker"]:
                self.steps.pop(0)
                return self._next_step()
            time.sleep(POLL_INTERVAL_S)
            return {"tool": "get_worker_status", "args": {"work_order_id": step["work_order_id"]}}
        self.steps.pop(0)
        return step

    async def generate_content_async(self, llm_request, stream=False):
        """Yield exactly one scripted LlmResponse per model turn."""
        self.model_requests.append(llm_request)
        step = self._next_step()
        if "tool" in step:
            part = types.Part(
                function_call=types.FunctionCall(
                    name=step["tool"], args=step.get("args", {})
                )
            )
        else:
            part = types.Part(text=step.get("text", ""))
        yield LlmResponse(content=types.Content(role="model", parts=[part]))
