# Kairos MCP Registry entries

This directory holds `server.json` descriptors for publishing Kairos
components to the [MCP Registry](https://registry.modelcontextprotocol.io),
the directory that MCP hosts (Claude Desktop, Cursor, and others) read to
discover and install servers.

## Task Ledger (`com.kairos/task-ledger`)

A Postgres-backed MCP server exposing four tools — `create_task`,
`list_tasks`, `complete_task`, `delete_task`. It ships inside the Kairos
ambient action engine as the durable fallback destination for action items
that map to no external tool, and also runs standalone over stdio:

```bash
git clone https://github.com/sandeepbist/Kairos.git
cd Kairos/backend
POSTGRES_HOST=localhost POSTGRES_PORT=5435 \
POSTGRES_DB=kairos_db POSTGRES_USER=kairos_user POSTGRES_PASSWORD=... \
PYTHONPATH=. python -m app.mcp.servers.task_ledger
```

Point any stdio-capable MCP client at the command above. Schema migrations
apply automatically on first start when the target database is reachable.

### Publishing

Submit the descriptor to the MCP Registry per its published process
(the registry validates against
[server.schema.json](https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json));
until the PyPI package `kairos-task-ledger` is published separately, the
descriptor's `packages` entry documents the source-clone install path —
registry maintainers may require the PyPI identifier to exist first, in
which case publish the package before submitting.

The descriptor lives in-tree so the server description, version, and
environment contract stay under review next to the server implementation
(`backend/app/mcp/servers/task_ledger.py`).
