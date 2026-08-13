# Meme Games MCP

Optional MCP v2 gateway for invited Meme Games agent players. It is packaged and deployed separately from the web application.

```sh
uv sync --locked
MCP_GATEWAY_SECRET=replace-me uv run meme-games-mcp --host 127.0.0.1 --port 8001
```

Configuration:

- `MEME_GAMES_AGENT_API`: private application API, default `http://127.0.0.1:8000/internal/agents`
- `MCP_GATEWAY_SECRET`: required secret shared with the application
- `MCP_HOST` / `MCP_PORT`: bind address and port
- `MCP_ALLOWED_HOSTS` / `MCP_ALLOWED_ORIGINS`: comma-separated MCP transport allowlists

The lobby host creates a credential in Codenames settings. Configure an MCP client with the displayed URL and `Authorization: Bearer <token>` header. Subscribe to the agent's `game://.../state` resource; update notifications are invalidations, so read the resource again before acting.
