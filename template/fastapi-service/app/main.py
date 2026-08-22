"""EDS FastAPI template service (baseline).

The Worker starts from this baseline and grows the service toward the
work-order requirement. `/healthz` is the contract the EDS deployment
health check probes.
"""

from fastapi import FastAPI

app = FastAPI(title="Template Service")


@app.get("/")
def root() -> dict:
    """Service root: identify the service and its status."""
    return {"service": "template", "status": "ok"}


@app.get("/healthz")
def healthz() -> dict:
    """Liveness probe consumed by the EDS deployment health check."""
    return {"status": "ok"}
