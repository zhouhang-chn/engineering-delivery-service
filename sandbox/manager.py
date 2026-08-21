"""Sandbox lifecycle management.

Creates and tears down isolated workspaces (git workspace, Python env,
Codex App Server) for Worker (writable) and Inspector (clean checkout).
"""


def create_sandbox(work_order_id: str, role: str) -> str:
    raise NotImplementedError


def destroy_sandbox(sandbox_id: str) -> None:
    raise NotImplementedError
