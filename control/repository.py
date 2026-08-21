"""Git operations: clone/checkout, baseline, candidate commits.

M1 scope: single fixed FastAPI template repository; M5 adds project
registry, worktrees, branches and PR delivery.
"""


def checkout(work_order_id: str, repo_url: str, baseline_commit: str):
    """Clone the repository at the baseline commit into the workspace."""
    raise NotImplementedError


def commit_candidate(work_order_id: str, message: str) -> str:
    """Commit the Worker's changes on a candidate branch; return the sha."""
    raise NotImplementedError
