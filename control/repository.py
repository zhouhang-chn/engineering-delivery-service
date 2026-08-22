"""Git operations: clone/checkout, baseline, candidate commits.

M1 scope: single fixed FastAPI template repository; M5 adds project
registry, worktrees, branches and PR delivery.

All commands run through the ``git`` CLI. The workspace layout is owned
by :mod:`sandbox.manager`: a work order's worker repository lives at
``<work-dir>/<work-order>/worker/repo``. Pass ``repo_dir`` to operate on
an explicit location (tests, future inspector checkouts).
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from sandbox.manager import work_dir

COMMIT_AUTHOR_NAME = "eds-worker"
COMMIT_AUTHOR_EMAIL = "eds-worker@eds.local"


def _git(repo_dir: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    """Run a git command inside repo_dir and return the completed process."""
    return subprocess.run(
        ["git", "-C", str(repo_dir), *args],
        check=check,
        capture_output=True,
        text=True,
    )


def worker_repo_dir(work_order_id: str, base_dir: str | Path | None = None) -> Path:
    """Return the default worker git-workspace path for a work order."""
    return work_dir(base_dir) / work_order_id / "worker" / "repo"


def checkout(
    work_order_id: str,
    repo_url: str,
    baseline_commit: str | None = None,
    *,
    repo_dir: Path | None = None,
    base_dir: str | Path | None = None,
) -> str:
    """Clone the repository at the baseline commit into the workspace.

    Returns the resolved baseline sha (HEAD after checkout).
    """
    target = repo_dir or worker_repo_dir(work_order_id, base_dir)
    if target.exists() and any(target.iterdir()):
        raise FileExistsError(f"workspace already populated: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "clone", repo_url, str(target)],
        check=True,
        capture_output=True,
        text=True,
    )
    if baseline_commit:
        _git(target, "checkout", baseline_commit)
    proc = _git(target, "rev-parse", "HEAD")
    return proc.stdout.strip()


def commit_candidate(
    work_order_id: str,
    message: str,
    *,
    repo_dir: Path | None = None,
    base_dir: str | Path | None = None,
) -> str:
    """Commit the Worker's changes on branch ``eds/<work-order>``.

    Idempotent: when nothing changed, returns the current HEAD sha.
    """
    target = repo_dir or worker_repo_dir(work_order_id, base_dir)
    branch = f"eds/{work_order_id}"
    existing = _git(target, "branch", "--list", branch, check=False)
    if existing.stdout.strip():
        _git(target, "checkout", branch)
    else:
        _git(target, "checkout", "-b", branch)
    _git(target, "add", "-A")
    status = _git(target, "status", "--porcelain")
    if status.stdout.strip():
        _git(
            target,
            "-c",
            f"user.name={COMMIT_AUTHOR_NAME}",
            "-c",
            f"user.email={COMMIT_AUTHOR_EMAIL}",
            "commit",
            "-m",
            message,
        )
    proc = _git(target, "rev-parse", "HEAD")
    return proc.stdout.strip()


def ensure_bare_repo(source_dir: Path, bare_dir: Path) -> Path:
    """Materialize a plain source tree into a bare git repository.

    The in-repo template has no ``.git``; the runner clones real
    repositories, so the template is published once into a local bare
    repo that then acts as ``EDS_TEMPLATE_REPO_URL``. Idempotent.
    """
    if (bare_dir / "HEAD").exists():
        return bare_dir
    bare_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "init", "--bare", "-b", "main", str(bare_dir)],
        check=True,
        capture_output=True,
        text=True,
    )
    staging = Path(tempfile.mkdtemp(prefix="eds-template-"))
    try:
        shutil.copytree(source_dir, staging, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns(".git"))
        _git(staging, "init", "-b", "main")
        _git(staging, "add", "-A")
        _git(
            staging,
            "-c",
            f"user.name={COMMIT_AUTHOR_NAME}",
            "-c",
            f"user.email={COMMIT_AUTHOR_EMAIL}",
            "commit",
            "-m",
            "template baseline",
        )
        _git(staging, "push", str(bare_dir), "main")
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return bare_dir
