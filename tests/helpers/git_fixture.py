"""Local git template repository fixture for contract/integration tests.

The fixture commits the real in-repo template (template/fastapi-service)
into a throwaway git repository, so tests exercise the exact baseline
the runner publishes via ``ensure_bare_repo``.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_SOURCE = PROJECT_ROOT / "template" / "fastapi-service"


def _git(repo: Path, *args: str) -> str:
    """Run a git command inside the fixture repo and return stdout."""
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return proc.stdout.strip()


def make_template_repo(dest: Path, source: Path = TEMPLATE_SOURCE) -> Path:
    """Create a committed local template repo at dest; return its path."""
    shutil.copytree(source, dest)
    _git(dest, "init", "-b", "main")
    _git(dest, "config", "user.name", "eds-fixture")
    _git(dest, "config", "user.email", "eds-fixture@localhost")
    _git(dest, "add", "-A")
    _git(dest, "commit", "-m", "template baseline")
    return dest
