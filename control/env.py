"""Environment bootstrap: EDS loads its own `.env`, exports not required.

Every process entrypoint (`eds` CLI, `a2a_api.server`, `agent.runner`,
alembic migrations) calls `load_env()` first so configuration — including
model credentials such as `GOOGLE_API_KEY` for the ADK Supervisor model —
comes from the gitignored `.env` at the repository root (next to
`.env.example`) without anyone sourcing it into the shell. Real
environment variables always win: the file only fills gaps and never
overrides exported values.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

_REPO_DOTENV = Path(__file__).resolve().parents[1] / ".env"


def load_env(
    dotenv_path: str | os.PathLike[str] | None = None,
) -> bool:
    """Populate `os.environ` from `.env`; return whether a file was loaded.

    Defaults to the repository-root `.env` — resolved from this module's
    location, not the working directory — so entrypoints work from any
    CWD. Already-exported variables keep precedence (`override=False`);
    a missing file is a silent no-op. Idempotent: repeated calls re-read
    at most the file.
    """
    return load_dotenv(dotenv_path=dotenv_path or _REPO_DOTENV, override=False)
