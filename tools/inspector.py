"""Delivery Control tools: inspector control.

Launch independent inspection of a candidate commit and read the verdict
(ACCEPT / REJECT), verified/failed criteria, evidence, gaps and risk.
Inspector never modifies the candidate.
"""


def get_inspector_status(work_order_id: str):
    """Return Inspector runtime status, verdict and findings."""
    raise NotImplementedError
