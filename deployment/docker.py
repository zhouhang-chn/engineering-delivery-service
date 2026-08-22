"""Docker deployment runtime.

docker build + docker run of the candidate; health check; expose
``<base_url>/docs`` for human acceptance.

The docker SDK client is injectable so contract tests can substitute a
fake that implements the same narrow surface (``images.build``,
``containers.run``, ``containers.get``).
"""

from __future__ import annotations

import socket
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

CONTAINER_PORT = 8000
DEFAULT_HEALTH_TIMEOUT_S = 60.0
DEFAULT_HEALTH_INTERVAL_S = 1.0


@dataclass(frozen=True)
class DeploymentRecord:
    """One deployed candidate service."""

    deployment_id: str
    image_tag: str
    container_id: str
    container_name: str
    port: int
    base_url: str
    docs_url: str
    status: str = "deployed"
    health: str = "unknown"


def default_client():
    """Create the real docker SDK client from the environment."""
    import docker

    return docker.from_env()


def free_port() -> int:
    """Ask the OS for a currently unused TCP port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def deploy(
    build_ctx: Path | str,
    port: int | None = None,
    *,
    image_tag: str | None = None,
    container_name: str | None = None,
    client=None,
) -> DeploymentRecord:
    """Build the candidate image and run it mapped to a host port.

    Any container already running under the same name is removed first
    (re-deploys are idempotent).
    """
    active_client = client or default_client()
    port = port or free_port()
    image_tag = image_tag or f"eds/{uuid.uuid4().hex[:12]}:candidate"
    container_name = container_name or f"eds-{uuid.uuid4().hex[:12]}"

    _remove_existing(active_client, container_name)
    active_client.images.build(path=str(build_ctx), tag=image_tag)
    container = active_client.containers.run(
        image_tag,
        name=container_name,
        ports={f"{CONTAINER_PORT}/tcp": port},
        detach=True,
    )
    base_url = f"http://localhost:{port}"
    return DeploymentRecord(
        deployment_id=container.id[:12] if container.id else container_name,
        image_tag=image_tag,
        container_id=container.id or "",
        container_name=container_name,
        port=port,
        base_url=base_url,
        docs_url=f"{base_url}/docs",
    )


def _remove_existing(client, container_name: str) -> None:
    """Stop and remove a same-named container if one exists."""
    import docker.errors

    try:
        existing = client.containers.get(container_name)
    except docker.errors.NotFound:
        return
    existing.remove(force=True)


def health_check(
    base_url: str,
    *,
    timeout_s: float = DEFAULT_HEALTH_TIMEOUT_S,
    interval_s: float = DEFAULT_HEALTH_INTERVAL_S,
    probe=None,
) -> bool:
    """Poll the service until `/` and `/docs` both answer successfully.

    ``probe`` (a ``fn(url) -> bool``) is injectable for tests.
    """
    check = probe or _http_probe
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            ok = check(f"{base_url}/") and check(f"{base_url}/docs")
        except Exception:  # noqa: BLE001 - service may not be listening yet
            ok = False
        if ok:
            return True
        time.sleep(interval_s)
    return False


def _http_probe(url: str) -> bool:
    """One HTTP GET; True when the response is a non-error status."""
    import httpx

    response = httpx.get(url, timeout=5.0, follow_redirects=True)
    return response.status_code < 400
