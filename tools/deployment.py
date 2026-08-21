"""Delivery Control tools: deployment lifecycle.

deploy_candidate / get_deployment_status. MVP targets local Docker with
a reachable `<base_url>/docs`.
"""


def deploy_candidate(work_order_id: str, candidate_commit: str):
    """Build and run the candidate; return the deployment id."""
    raise NotImplementedError


def get_deployment_status(deployment_id: str):
    """Return deployment phase, base_url, docs_url and health."""
    raise NotImplementedError
