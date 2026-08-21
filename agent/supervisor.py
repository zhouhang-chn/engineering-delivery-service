"""ReAct Supervisor (Google ADK).

The free-running top-level controller. It observes Work Order state,
reasons about the next action, and calls Delivery Control / Worker /
Inspector tools until all acceptance criteria are verified and the
deployment is live. It never edits code or runs tests itself.

See architecture doc section 7 for the intended run model.
"""


def build_supervisor():  # TODO(M1): assemble ADK LlmAgent with delivery tools
    raise NotImplementedError
