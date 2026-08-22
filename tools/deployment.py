"""Delivery Control tools: deployment lifecycle.

deploy_candidate / get_deployment_status. MVP targets local Docker with
a reachable `<base_url>/docs`. The docker build+run call is wrapped in a
bounded RetryPolicy (operational retries only — semantic build failures
surface immediately).
"""

from __future__ import annotations

from control.policy import RetryPolicy
from control.state import append_event, require_work_order, session_scope
from db.models import WorkOrder

# Transient infra errors worth retrying (docker daemon restarting, socket
# hiccups). Semantic failures (bad image, missing context) raise other types.
RETRYABLE_ERRORS = (OSError, RuntimeError)


def deploy_candidate(
    work_order_id: str,
    candidate_commit: str,
    *,
    port: int | None = None,
    client=None,
    base_dir=None,
) -> dict:
    """Build and run the candidate; persist the deployment facts."""
    if not isinstance(candidate_commit, str) or not candidate_commit:
        raise ValueError("candidate_commit must be a non-empty string")

    from control import repository
    from deployment import docker

    with session_scope() as session:
        require_work_order(session, work_order_id)

    repo_dir = repository.worker_repo_dir(work_order_id, base_dir=base_dir)
    image_tag = f"eds/{work_order_id}:candidate"
    container_name = f"eds-{work_order_id}"
    record = RetryPolicy().run(
        lambda: docker.deploy(
            repo_dir,
            port=port,
            image_tag=image_tag,
            container_name=container_name,
            client=client,
        ),
        retry_on=RETRYABLE_ERRORS,
    )
    healthy = docker.health_check(record.base_url)
    health = "healthy" if healthy else "unhealthy"

    with session_scope() as session:
        work_order = require_work_order(session, work_order_id)
        work_order.candidate_commit = candidate_commit
        work_order.deployment_id = container_name
        work_order.deployment_status = "deployed"
        work_order.deployment_url = record.base_url
        work_order.docs_url = record.docs_url
        work_order.deployment_health = health
        append_event(
            session,
            work_order_id,
            "deployment.deployed",
            {
                "deployment_id": container_name,
                "base_url": record.base_url,
                "docs_url": record.docs_url,
                "health": health,
                "candidate_commit": candidate_commit,
            },
        )
        session.flush()

    return {
        "work_order_id": work_order_id,
        "deployment_id": container_name,
        "status": "deployed",
        "base_url": record.base_url,
        "docs_url": record.docs_url,
        "health": health,
        "candidate_commit": candidate_commit,
        "port": record.port,
        "image_tag": image_tag,
        "container_name": container_name,
    }


def get_deployment_status(deployment_id: str) -> dict:
    """Return deployment phase, base_url, docs_url and persisted health."""
    with session_scope() as session:
        work_order = (
            session.query(WorkOrder).filter_by(deployment_id=deployment_id).first()
        )
        if work_order is None:
            raise LookupError(f"deployment {deployment_id!r} not found")
        return {
            "deployment_id": deployment_id,
            "work_order_id": work_order.id,
            "status": work_order.deployment_status,
            "base_url": work_order.deployment_url,
            "docs_url": work_order.docs_url,
            "health": work_order.deployment_health,
        }
