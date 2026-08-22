# v0.1.5 Design — EDS CLI

A thin external caller over the [A2A interface](../../../designs/a2a-interface.md).
It never imports EDS internals — only the A2A protocol — so using it is
itself a contract test of the endpoint.

## Commands (`uv run python -m cli`, or `uv run eds` if packaged)

```
eds serve [--host 127.0.0.1] [--port 8080]     # start EDS (uvicorn factory)
eds submit "<requirement text>"                # tasks/send → prints task id + state
eds status <task-id> [--watch] [--interval 2]  # tasks/get, pretty-printed
eds open <task-id>                             # open docs_url in the browser
```

- `status` renders: task state, timestamps, artifacts (commit, deployment
  URL, `/docs` URL, test evidence summary, delivery summary), and the most
  recent status lines while `--watch` polls until a terminal state.
- Exit codes for scripting: 0 completed, 1 failed, 2 still running.

## Layout

- `cli.py` — argparse subcommands, rendering, `main()` entrypoint.
- `cli/a2a_client.py` (or section within `cli.py` if it stays small) — the
  only module touching the A2A protocol (httpx); base URL from
  `EDS_A2A_URL` (default `http://127.0.0.1:8080`).
- Packaging: add `httpx` as an explicit dependency; add `[project.scripts]
  eds = "cli:main"` plus the minimal build-system config if it works with
  the flat layout — otherwise document `uv run python -m cli` as the
  interface and keep the console script as a follow-up.

## Testing

Unit tests against a fake A2A app (FastAPI TestClient or httpx mock):
submit → status transitions → watch terminates on terminal state → open
resolves docs_url. No real EDS, Codex, or docker needed.
