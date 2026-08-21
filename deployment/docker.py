"""Docker deployment runtime.

docker build + docker run of the candidate; health check; expose
`<base_url>/docs` for human acceptance.
"""


def deploy(image_tag: str, port: int) -> str:
    raise NotImplementedError


def health_check(base_url: str) -> bool:
    raise NotImplementedError
