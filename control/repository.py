"""Git operations: clone/checkout, baseline, candidate commits.

M1 scope: single fixed FastAPI template repository; M5 adds project
registry, worktrees, branches and PR delivery.
"""


def checkout(work_order_id: str, repo_url: str, baseline_commit: str):
    raise NotImplementedError


def commit_candidate(work_order_id: str, message: str) -> str:
    raise NotImplementedError
