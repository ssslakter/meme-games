# Meme Games MCP

Optional MCP v2 gateway for Meme Games agent players. It is packaged and deployed separately from the web application.

```sh
uv sync --locked
MCP_GATEWAY_SECRET=replace-private MCP_AUTH_TOKEN=replace-public uv run meme-games-mcp --host 127.0.0.1 --port 8001
```

Configuration:

- `MEME_GAMES_AGENT_API`: private application API, default `http://127.0.0.1:8000/internal/agents`
- `MCP_GATEWAY_SECRET`: required secret shared with the application
- `MCP_AUTH_TOKEN`: required bearer shared by trusted MCP clients
- `MCP_HOST` / `MCP_PORT`: bind address and port
- `MCP_ALLOWED_HOSTS` / `MCP_ALLOWED_ORIGINS`: comma-separated MCP transport allowlists

Configure MCP clients with `Authorization: Bearer <MCP_AUTH_TOKEN>`. The lobby host enables agent joins in lobby settings; every `join_lobby` call creates a separate player and returns its opaque session handle.

Agent loop:

1. Call `join_lobby`, retain its `player_session`, and read `get_game_state`.
2. Pass that handle to one listed action when appropriate.
3. Call `wait_for_events` with the handle and last `next_cursor`; it waits for at most 25 seconds and returns every missed public game change in order.
4. When events arrive, read state again. Event payloads intentionally contain no game details.
5. Call `leave_lobby` to close the handle and remove that player.

The current Python MCP SDK does not yet expose the official MCP Tasks extension, so the gateway uses bounded waiting for compatibility. Once the SDK supports the extension, task-capable clients can receive a task handle instead of making that repeated bounded call.
