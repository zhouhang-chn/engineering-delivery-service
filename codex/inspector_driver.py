"""Inspector driver: drives a Codex thread inside a clean sandbox.

Independent checkout of the candidate commit. Gets requirement,
acceptance criteria, baseline/candidate commits and constraints — but not
the Worker's reasoning history. Reviews diff, runs tests, starts the
service, probes the API/OpenAPI schema, and returns ACCEPT / REJECT with
evidence. Never fixes code itself.
"""


def run_inspection(work_order_id: str, candidate_commit: str):
    """Drive one full inspection turn; return the verdict payload."""
    raise NotImplementedError
