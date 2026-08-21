"""A2A endpoint.

Exposes EDS as an Engineering Delivery Agent. An A2A Task maps to one
Engineering Work Order, not to a Codex turn. Task state maps to Work
Order progress (submitted / working / input-required / completed / ...).

See architecture doc section 5.

This package is deliberately NOT named `a2a`: a top-level `a2a` package
would shadow the a2a-sdk distribution (whose import root is `a2a`) for
every process run from the repo root.
"""


def create_app():  # TODO(M1): a2a-sdk agent card + task handlers
    raise NotImplementedError
