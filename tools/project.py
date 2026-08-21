"""Delivery Control tools: project resolution.

resolve_project maps a Work Order to a registered Git repository and
baseline commit. MVP M1 uses a single fixed FastAPI template repository.
"""


def resolve_project(work_order_id: str):
    """Return the repository URL and baseline commit for a Work Order."""
    raise NotImplementedError
