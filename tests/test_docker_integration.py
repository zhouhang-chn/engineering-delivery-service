"""Integration test (marked 'docker'): real build/run/health of the template.

Run explicitly: uv run pytest -m docker
"""

from __future__ import annotations

from pathlib import Path

import docker.errors
import pytest

from deployment import docker as deploy
from tests.helpers.git_fixture import make_template_repo

pytestmark = pytest.mark.docker


def test_template_builds_runs_and_serves_docs(tmp_path: Path) -> None:
    template = make_template_repo(tmp_path / "template")
    record = deploy.deploy(
        template,
        port=18999,
        image_tag="eds-integration:template",
        container_name="eds-integration-template",
    )
    try:
        assert deploy.health_check(record.base_url, timeout_s=120, interval_s=1.0)
        import httpx

        health = httpx.get(f"{record.base_url}/healthz", timeout=10)
        assert health.status_code == 200
        assert health.json() == {"status": "ok"}
        docs = httpx.get(record.docs_url, timeout=10, follow_redirects=True)
        assert docs.status_code == 200
    finally:
        client = deploy.default_client()
        try:
            client.containers.get(record.container_name).remove(force=True)
        except docker.errors.NotFound:
            pass


def test_runner_scripted_delivery_with_real_docker(tmp_path: Path) -> None:
    """The full runner loop against real docker (scripted worker)."""
    from codex.worker_driver import ScriptedWorker
    from runner import run_delivery
    from tests.test_runner_contract import SCRIPT

    template = make_template_repo(tmp_path / "template")
    result = run_delivery(
        "Add a GET /hello endpoint returning {'hello': 'world'}",
        worker=ScriptedWorker(SCRIPT),
        repo_url=str(template),
        work_dir=tmp_path / "work",
        test_command=_eds_python_pytest(),
    )
    try:
        assert result.overall_status == "delivered"
        assert result.deployment_health == "healthy"
        import httpx

        response = httpx.get(f"{result.base_url}/hello", timeout=10)
        assert response.status_code == 200
        assert response.json() == {"hello": "world"}
    finally:
        client = deploy.default_client()
        try:
            client.containers.get(f"eds-{result.work_order_id}").remove(force=True)
        except docker.errors.NotFound:
            pass


def _eds_python_pytest() -> str:
    """Run the workspace tests with the EDS venv interpreter (no network)."""
    import sys

    return f"{sys.executable} -m pytest -q"
