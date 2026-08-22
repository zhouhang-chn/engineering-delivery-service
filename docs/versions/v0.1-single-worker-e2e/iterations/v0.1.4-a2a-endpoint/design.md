# v0.1.4 Design — A2A Endpoint & Close-out

Implements version design D6 and the
[a2a-interface design](../../../designs/a2a-interface.md).

## Endpoint

`a2a_api/server.py: create_app()` builds an a2a-sdk application:

- agent card: Engineering Delivery Agent, skill = FastAPI API delivery
- `tasks/send` (and `sendSync` if supported cheaply): parse requirement
  text → create work order (`submitted`) → launch supervisor run-loop in
  background → return task in `working`
- `tasks/get`: map `overall_status` → task state per the design table;
  on `completed`, attach artifacts: repository/commit, deployment URL,
  `/docs` URL, pytest evidence summary, delivery summary
- error mapping: invalid requirement → task `failed` with reason

The endpoint never touches modules directly — only tools (thin adapter,
per [system architecture](../../../designs/system-architecture.md)).

## Close-out

Full-chain e2e test (marked `e2e`: real A2A call → real Codex → docker →
assert artifacts + `/docs` reachable). Dogfooding checklist: submit the
`/hello` requirement as an external caller would; open `/docs`; Try it
out; Execute. Then CHANGELOG.md, README updates, gate, retrospect, PR
merge.
