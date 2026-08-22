"""Fake docker SDK client for contract tests.

`containers.run` serves a real HTTP server on the mapped host port so the
deployment health check exercises its actual probing path.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import docker.errors


class FakeImage:
    """Minimal image handle returned by FakeImages.build."""

    def __init__(self, tags: list[str]) -> None:
        self.tags = tags


class FakeImages:
    """Records build calls; no real image is produced."""

    def __init__(self, client: FakeDockerClient) -> None:
        self._client = client

    def build(self, path: str, tag: str, **kwargs) -> tuple[FakeImage, list]:
        self._client.builds.append({"path": path, "tag": tag, "kwargs": kwargs})
        return FakeImage([tag]), []


class FakeContainer:
    """Container handle bound to the HTTP server started on its port."""

    def __init__(self, cid: str, name: str, port: int, server: ThreadingHTTPServer) -> None:
        self.id = cid
        self.name = name
        self.status = "running"
        self.port = port
        self._server = server

    def reload(self) -> None:
        """Keep status in sync (no-op for the fake)."""

    def stop(self) -> None:
        self._server.shutdown()
        self.status = "exited"

    def remove(self, force: bool = False) -> None:
        self._server.shutdown()
        self.status = "removed"


class FakeContainers:
    """Runs real local HTTP servers in place of containers."""

    def __init__(self, client: FakeDockerClient) -> None:
        self._client = client
        self._by_name: dict[str, FakeContainer] = {}
        self._seq = 0

    def run(self, image: str, name: str | None = None, ports: dict | None = None, **kwargs):
        host_port = (ports or {}).get("8000/tcp")
        if not host_port:
            raise ValueError("fake docker expects a ports mapping for 8000/tcp")
        self._seq += 1
        server = _serve(int(host_port))
        container = FakeContainer(f"fake-{self._seq:06d}", name or "", int(host_port), server)
        if name:
            self._by_name[name] = container
        self._client.runs.append(
            {"image": image, "name": name, "ports": ports, "kwargs": kwargs}
        )
        return container

    def get(self, name: str) -> FakeContainer:
        if name not in self._by_name:
            raise docker.errors.NotFound(f"no such container: {name}")
        return self._by_name[name]


class FakeDockerClient:
    """Drop-in stand-in for the docker SDK client surface EDS uses."""

    def __init__(self) -> None:
        self.images = FakeImages(self)
        self.containers = FakeContainers(self)
        self.builds: list[dict] = []
        self.runs: list[dict] = []


def _serve(port: int) -> ThreadingHTTPServer:
    """Serve a trivial 200-OK HTTP app on localhost:<port>."""

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            body = json.dumps(
                {"service": "fake-deployment", "path": self.path}
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args) -> None:
            """Silence request logging inside tests."""

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server
