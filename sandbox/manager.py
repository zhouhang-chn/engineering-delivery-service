"""Sandbox lifecycle management.

Creates and tears down isolated workspaces (git workspace, Python env,
Codex App Server) for Worker (writable) and Inspector (clean checkout).

v0.1: a sandbox is an isolated directory under ``EDS_WORK_DIR`` (default
``.eds/work/``), one per work order role. The interface (``Sandbox``
objects + ``create_sandbox``/``destroy_sandbox``) deliberately hides the
storage choice so container-backed isolation can replace it later.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

DEFAULT_WORK_DIR = ".eds/work"

ROLES = ("worker", "inspector")


@dataclass(frozen=True)
class Sandbox:
    """Handle for one role's isolated workspace."""

    sandbox_id: str
    path: Path


def work_dir(base_dir: str | Path | None = None) -> Path:
    """Resolve the sandbox root directory (explicit > EDS_WORK_DIR > default).

    Always returns an absolute path: sandbox paths flow into git push
    URLs and Codex cwds, which must not depend on the process cwd.
    """
    if base_dir is not None:
        return Path(base_dir).resolve()
    return Path(os.environ.get("EDS_WORK_DIR", DEFAULT_WORK_DIR)).resolve()


def sandbox_id_for(work_order_id: str, role: str) -> str:
    """Deterministic sandbox id: '<work-order>--<role>'."""
    return f"{work_order_id}--{role}"


def sandbox_path(sandbox_id: str, base_dir: str | Path | None = None) -> Path:
    """Map a sandbox id back to its directory under the work dir root."""
    work_order_id, _, role = sandbox_id.partition("--")
    return work_dir(base_dir) / work_order_id / role


def create_sandbox(work_order_id: str, role: str, base_dir: str | Path | None = None) -> Sandbox:
    """Provision an isolated workspace for a role ('worker'|'inspector').

    Idempotent: re-creating an existing sandbox returns the same path.
    """
    if role not in ROLES:
        raise ValueError(f"unknown sandbox role {role!r}; expected one of {ROLES}")
    sandbox_id = sandbox_id_for(work_order_id, role)
    path = sandbox_path(sandbox_id, base_dir)
    path.mkdir(parents=True, exist_ok=True)
    return Sandbox(sandbox_id=sandbox_id, path=path)


def destroy_sandbox(sandbox_id: str, base_dir: str | Path | None = None) -> None:
    """Tear down a sandbox and all its ephemeral state (idempotent)."""
    path = sandbox_path(sandbox_id, base_dir)
    shutil.rmtree(path, ignore_errors=True)
