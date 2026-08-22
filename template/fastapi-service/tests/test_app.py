"""Baseline tests for the template service."""

from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_root() -> None:
    assert client.get("/").status_code == 200


def test_healthz() -> None:
    assert client.get("/healthz").json() == {"status": "ok"}
