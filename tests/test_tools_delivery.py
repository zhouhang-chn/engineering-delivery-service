"""Runtime / deployment / evidence / status tool tests (v0.1.2 T1, T5).

Docker and the health probe are monkeypatched: these tests pin the tool
contracts (durable writes + audit events + retry policy), while the
docker-marked suites cover the real external calls.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers.db import event_types, evidence_kinds, new_id


def _make_work_order(durable_db, **fields) -> str:
    from tools.work_order import update_work_order

    wo = new_id()
    update_work_order(wo, original_request="req", **fields)
    return wo


def test_resolve_project_returns_repository_and_baseline(durable_db) -> None:
    from tools.project import resolve_project

    wo = _make_work_order(durable_db, repository="/repos/tpl.git", baseline_commit="base1")
    assert resolve_project(wo) == {
        "work_order_id": wo,
        "repository": "/repos/tpl.git",
        "baseline_commit": "base1",
    }
    with pytest.raises(LookupError, match="not found"):
        resolve_project(new_id())


def test_create_worker_runtime_provisions_sandbox_and_audits(durable_db, tmp_path) -> None:
    from tools.runtime import create_worker_runtime

    wo = _make_work_order(durable_db)
    runtime = create_worker_runtime(wo, base_dir=tmp_path)

    assert runtime["role"] == "worker"
    assert runtime["runtime_id"] == f"{wo}--worker"
    assert Path(runtime["sandbox_path"]).is_dir()
    assert runtime["worker_status"] == "starting"

    from tools.work_order import get_work_order

    record = get_work_order(wo)
    assert record["worker_runtime_id"] == f"{wo}--worker"
    assert record["worker_status"] == "starting"
    assert event_types(durable_db, wo) == ["work_order.created", "runtime.worker_created"]

    # idempotent re-issue: same runtime, no duplicate event
    again = create_worker_runtime(wo, base_dir=tmp_path)
    assert again["runtime_id"] == runtime["runtime_id"]
    assert event_types(durable_db, wo) == ["work_order.created", "runtime.worker_created"]


def test_create_inspector_runtime_tracks_inspector_fields(durable_db, tmp_path) -> None:
    from tools.runtime import create_inspector_runtime

    wo = _make_work_order(durable_db)
    runtime = create_inspector_runtime(wo, base_dir=tmp_path)
    assert runtime["role"] == "inspector"
    assert runtime["runtime_id"] == f"{wo}--inspector"
    assert Path(runtime["sandbox_path"]).is_dir()
    assert event_types(durable_db, wo) == [
        "work_order.created",
        "runtime.inspector_created",
    ]


def test_destroy_runtime_is_idempotent_and_audited(durable_db, tmp_path) -> None:
    from tools.runtime import create_worker_runtime, destroy_runtime

    wo = _make_work_order(durable_db)
    runtime = create_worker_runtime(wo, base_dir=tmp_path)
    sandbox_path = Path(runtime["sandbox_path"])

    result = destroy_runtime(runtime["runtime_id"], base_dir=tmp_path)
    assert result == {"runtime_id": runtime["runtime_id"], "destroyed": True}
    assert not sandbox_path.exists()

    from tools.work_order import get_work_order

    assert get_work_order(wo)["worker_status"] == "destroyed"
    assert "runtime.destroyed" in event_types(durable_db, wo)

    # idempotent: destroying again is a safe no-op
    assert destroy_runtime(runtime["runtime_id"], base_dir=tmp_path)["destroyed"] is True


def test_record_evidence_persists_and_audits(durable_db) -> None:
    from tools.evidence import record_evidence

    wo = _make_work_order(durable_db)
    saved = record_evidence(wo, "pytest_run", {"status": "passed", "passed": 3})

    assert saved["work_order_id"] == wo
    assert saved["kind"] == "pytest_run"
    assert saved["payload"] == {"status": "passed", "passed": 3}
    assert evidence_kinds(durable_db, wo) == ["pytest_run"]
    assert event_types(durable_db, wo) == ["work_order.created", "evidence.recorded"]

    with pytest.raises(ValueError, match="kind"):
        record_evidence(wo, "", {})
    with pytest.raises(LookupError, match="not found"):
        record_evidence(new_id(), "pytest_run", {})


def test_get_worker_status_reads_durable_state(durable_db) -> None:
    from tools.worker import get_worker_status

    wo = _make_work_order(
        durable_db,
        worker_status="done",
        worker_summary="added endpoint",
        worker_thread_id="thread-7",
        candidate_commit="c0ffee",
    )
    status = get_worker_status(wo)
    assert status["work_order_id"] == wo
    assert status["status"] == "done"
    assert status["summary"] == "added endpoint"
    assert status["thread_id"] == "thread-7"
    assert status["candidate_commit"] == "c0ffee"

    assert get_worker_status(new_id())["status"] == "unknown"


def test_get_inspector_status_reads_durable_state(durable_db) -> None:
    from tools.inspector import get_inspector_status

    wo = _make_work_order(durable_db)
    status = get_inspector_status(wo)
    assert status["status"] is None  # not provisioned yet
    assert get_inspector_status(new_id())["status"] == "unknown"


def _fake_deploy_record(wo: str, port: int = 9100):
    from deployment.docker import DeploymentRecord

    return DeploymentRecord(
        deployment_id=f"container-{wo[:8]}",
        image_tag=f"eds/{wo}:candidate",
        container_id=f"container-{wo[:8]}",
        container_name=f"eds-{wo}",
        port=port,
        base_url=f"http://localhost:{port}",
        docs_url=f"http://localhost:{port}/docs",
    )


def test_deploy_candidate_updates_state_and_audits(durable_db, tmp_path, monkeypatch) -> None:
    from deployment import docker
    from tools.deployment import deploy_candidate, get_deployment_status
    from tools.work_order import get_current_state

    wo = _make_work_order(durable_db, repository="/repos/tpl.git")
    record = _fake_deploy_record(wo)

    monkeypatch.setattr(docker, "deploy", lambda *a, **k: record)
    monkeypatch.setattr(docker, "health_check", lambda *a, **k: True)

    result = deploy_candidate(wo, "c0ffee", base_dir=tmp_path)

    assert result["work_order_id"] == wo
    assert result["status"] == "deployed"
    assert result["health"] == "healthy"
    assert result["base_url"] == record.base_url
    assert result["docs_url"] == record.docs_url

    state = get_current_state(wo)
    assert state["deployment"]["status"] == "deployed"
    assert state["deployment"]["url"] == record.base_url
    assert state["deployment"]["docs_url"] == record.docs_url
    assert state["deployment"]["health"] == "healthy"
    assert state["worker"]["candidate_commit"] == "c0ffee"
    assert "deployment.deployed" in event_types(durable_db, wo)

    by_id = get_deployment_status(result["deployment_id"])
    assert by_id["work_order_id"] == wo
    assert by_id["docs_url"] == record.docs_url
    assert by_id["health"] == "healthy"
    with pytest.raises(LookupError, match="not found"):
        get_deployment_status("no-such-deployment")


def test_deploy_candidate_validates_input(durable_db) -> None:
    from tools.deployment import deploy_candidate

    wo = _make_work_order(durable_db)
    with pytest.raises(ValueError, match="candidate_commit"):
        deploy_candidate(wo, "")
    with pytest.raises(LookupError, match="not found"):
        deploy_candidate(new_id(), "abc")


def test_deploy_candidate_retries_transient_docker_failures(
    durable_db, tmp_path, monkeypatch
) -> None:
    from deployment import docker
    from tools.deployment import deploy_candidate

    wo = _make_work_order(durable_db)
    record = _fake_deploy_record(wo, port=9101)
    calls = {"n": 0}

    def flaky_deploy(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] < 3:
            raise OSError("docker daemon is restarting")
        return record

    monkeypatch.setattr(docker, "deploy", flaky_deploy)
    monkeypatch.setattr(docker, "health_check", lambda *a, **k: True)

    result = deploy_candidate(wo, "c0ffee", base_dir=tmp_path)
    assert calls["n"] == 3
    assert result["status"] == "deployed"
