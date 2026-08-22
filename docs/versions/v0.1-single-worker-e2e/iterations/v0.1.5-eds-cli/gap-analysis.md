# v0.1.5 Gap Analysis — EDS CLI (user test loop)

**Goal:** give the human user a one-command way to test EDS exactly as an
external caller would: start the service, submit a requirement, watch it
progress, and open the delivered `/docs`.

**Current state:** after v0.1.4 the only test paths are raw A2A protocol
calls (curl/httpx) or `runner.py`, which bypasses the A2A surface and thus
does not exercise the real external contract.

**Gaps:** `eds` CLI (serve / submit / status --watch / open) · httpx as an
explicit dependency · optional console-script packaging · CLI tests against
a fake A2A server.

**Risks:** a2a-sdk client API churn (isolate protocol calls in one module);
none blocking.

UI (web status page) is explicitly **deferred**: the MVP acceptance surface
is the delivered API's `/docs` (see
[system architecture](../../../designs/system-architecture.md)); everything
a UI would display is already durable state the CLI renders.
