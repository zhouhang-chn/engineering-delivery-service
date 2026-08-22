"""Unit tests for deployment/docker.py using the fake docker client."""

from __future__ import annotations

from pathlib import Path

from deployment import docker
from tests.helpers.fake_docker import FakeDockerClient


def test_deploy_builds_and_runs_mapped_port(tmp_path: Path) -> None:
    fake = FakeDockerClient()
    record = docker.deploy(
        tmp_path, port=18401, image_tag="eds/wo-1:candidate",
        container_name="eds-wo-1", client=fake,
    )
    assert record.image_tag == "eds/wo-1:candidate"
    assert record.base_url == "http://localhost:18401"
    assert record.docs_url == "http://localhost:18401/docs"
    assert record.port == 18401
    assert len(fake.builds) == 1
    assert fake.builds[0]["path"] == str(tmp_path)
    assert fake.runs[0]["ports"] == {"8000/tcp": 18401}
    assert fake.runs[0]["name"] == "eds-wo-1"


def test_deploy_replaces_existing_container(tmp_path: Path) -> None:
    fake = FakeDockerClient()
    first = docker.deploy(tmp_path, port=18402, container_name="eds-wo-1", client=fake)
    second = docker.deploy(tmp_path, port=18403, container_name="eds-wo-1", client=fake)
    assert first.container_name == second.container_name
    assert fake.containers.get("eds-wo-1").status != "removed"


def test_health_check_probes_root_and_docs() -> None:
    fake = FakeDockerClient()
    record = docker.deploy(Path("/tmp"), port=18404, client=fake)
    assert docker.health_check(record.base_url, timeout_s=10, interval_s=0.1)


def test_health_check_times_out_when_probe_fails() -> None:
    assert not docker.health_check(
        "http://localhost:59999", timeout_s=0.3, interval_s=0.1
    )


def test_health_check_accepts_injected_probe() -> None:
    calls: list[str] = []

    def probe(url: str) -> bool:
        calls.append(url)
        return True

    assert docker.health_check("http://x", timeout_s=1, interval_s=0.0, probe=probe)
    assert calls == ["http://x/", "http://x/docs"]


def test_free_port_is_bindable() -> None:
    import socket

    port = docker.free_port()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", port))
