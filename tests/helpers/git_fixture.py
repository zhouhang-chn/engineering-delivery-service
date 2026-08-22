"""Local git template repository fixture for contract/integration tests."""

from __future__ import annotations

import subprocess
from pathlib import Path

APP_PY = '''\
"""Template FastAPI service (baseline)."""

from fastapi import FastAPI

app = FastAPI(title="Template Service")


@app.get("/")
def root() -> dict:
    """Service root: identify the service and its status."""
    return {"service": "template", "status": "ok"}


@app.get("/healthz")
def healthz() -> dict:
    """Liveness probe consumed by the deployment health check."""
    return {"status": "ok"}
'''

TEST_APP_PY = '''\
"""Baseline tests for the template service."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root() -> None:
    assert client.get("/").status_code == 200


def test_healthz() -> None:
    assert client.get("/healthz").json() == {"status": "ok"}
'''

DOCKERFILE = '''\
FROM python:3.12-slim

WORKDIR /srv

COPY pyproject.toml ./
COPY app ./app
RUN pip install --no-cache-dir .

COPY tests ./tests

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
'''

PYPROJECT = '''\
[project]
name = "template-fastapi-service"
version = "0.1.0"
description = "EDS FastAPI template service"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115",
    "uvicorn>=0.30",
]

[dependency-groups]
dev = [
    "pytest>=8.0",
    "httpx>=0.27",
]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools]
packages = ["app"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
'''


def _git(repo: Path, *args: str) -> str:
    """Run a git command inside the fixture repo and return stdout."""
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return proc.stdout.strip()


def make_template_repo(dest: Path) -> Path:
    """Create a committed local template repo at dest; return its path."""
    (dest / "app").mkdir(parents=True)
    (dest / "tests").mkdir(parents=True)
    (dest / "app" / "__init__.py").write_text('"""Template service package."""\n')
    (dest / "app" / "main.py").write_text(APP_PY)
    (dest / "tests" / "test_app.py").write_text(TEST_APP_PY)
    (dest / "tests" / "__init__.py").write_text("")
    (dest / "pyproject.toml").write_text(PYPROJECT)
    (dest / "Dockerfile").write_text(DOCKERFILE)
    (dest / ".dockerignore").write_text(".git\n__pycache__/\n.venv/\n.pytest_cache/\n")

    _git(dest, "init", "-b", "main")
    _git(dest, "config", "user.name", "eds-fixture")
    _git(dest, "config", "user.email", "eds-fixture@localhost")
    _git(dest, "add", "-A")
    _git(dest, "commit", "-m", "template baseline")
    return dest
