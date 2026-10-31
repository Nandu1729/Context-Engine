# MCP server prototype (0.12.0)

`context-engine-mcp` exposes `MemoryStore` to MCP clients over stdio (JSON-RPC 2.0,
standard library only, no MCP SDK dependency). It never calls a model:
`get_context` returns budgeted messages for the client to send.

```sh
context-engine-mcp --data-dir ./context-memory --tenant local
```

Client configuration (the usual `mcpServers` JSON shape). Use the **absolute path**
of the installed `context-engine-mcp`: desktop apps start servers with a minimal
PATH. It is a Python program, not an npm package, so do not use `npx`.

```json
{"mcpServers": {"context-engine": {"command": "/absolute/path/to/.venv/bin/context-engine-mcp",
  "args": ["--data-dir", "/absolute/path/context-memory"]}}}
```

Claude Code: `claude mcp add context-engine -- /absolute/path/to/context-engine-mcp --data-dir /absolute/path/context-memory`.

| Tool | Arguments | Result |
|---|---|---|
| `add_message` | `session`, `role` (user/assistant), `content` | `turn_id` |
| `pin_fact` | `session`, `key`, `value` (re-pinning a key replaces it) | `key`, `revision` |
| `get_context` | `session`, `question`, optional `budget` (300–131072, default 900), `system` | `messages`, token estimate, kept/retrieved turn IDs |
| `forget` | `session`, `kind` (turn/pin/session), `key` | deleted target |

Behavior: one tenant per server process; sessions are isolated scopes. Deletions are
permanent tombstones (a deleted session or pin key cannot be silently recreated).
Invalid arguments and engine errors return `isError: true` with a code, never stored
content. Protocol versions negotiated: 2025-11-25 (default), 2025-06-18,
2025-03-26, 2024-11-05.

Prototype limits: stdio only (no HTTP transport or auth), text messages only, no
tool-call turns, no streaming, no resources/prompts. Tested offline in
`tests/test_mcp_server.py` (in-process and a real stdio subprocess).

Real-client check (2026-10-31): the owner registered it in Claude Code with
`claude mcp add context-engine -- <venv>/bin/context-engine-mcp --data-dir ~/context-memory`;
`claude mcp get` reports Connected. A stdio round trip with that installed binary
(throwaway data directory) listed all four tools, stored a message and pin, and
`get_context` returned both (148/900 estimated tokens). In-chat tool use by the model
is not yet observed. Note: a server launched from the repository `.venv` runs the
editable development code; for stable use install a released wheel in its own
environment.
