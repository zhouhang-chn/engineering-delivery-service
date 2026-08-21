"""Docker deployment runtime.

docker build + docker run of the candidate; health check; expose
`<base_url>/docs` for human acceptance.
"""


def deploy(image_tag: str, port: int) -> str:
    """Build and run the image; return the deployment's base URL."""
    raise NotImplementedError


def health_check(base_url: str) -> bool:
    """Return True once the service answers (and /docs is reachable)."""
    raise NotImplementedError
