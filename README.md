# meme-games
Random social games to have fun with friends

## How to run
1. Run locally
```sh
git clone https://github.com/ssslakter/meme-games
pixi run app
```
Choose a bind address or port with:
```sh
pixi run app --host 127.0.0.1 --port 9000
```
2. Run with docker compose
```sh
docker compose up -d
```

## Contributing

For more info on used stack read [fasthtml](https://fastht.ml/docs) docs.

Run the tests with
```sh
pixi run test
```

## Agent players (optional)

The MCP gateway is a separate package in `mcp_gateway/`; the web application does not install its dependencies unless you opt in.

Set a private app-to-gateway secret and a deployment bearer token for MCP clients, then run both processes:

```sh
MCP_GATEWAY_SECRET=replace-private pixi run app
cd mcp_gateway
uv sync --locked
MCP_GATEWAY_SECRET=replace-private MCP_AUTH_TOKEN=replace-public uv run meme-games-mcp --host 127.0.0.1 --port 8001
```

Alternatively, start the optional Compose profile:

```sh
MCP_GATEWAY_SECRET=replace-private MCP_AUTH_TOKEN=replace-public docker compose --profile mcp up --build -d
```

Configure MCP clients with the gateway URL and `Authorization: Bearer <MCP_AUTH_TOKEN>`. A host must enable **Allow agents to join** before clients call `join_lobby`; each call returns an independent opaque `player_session`. Agents use that handle for state, actions, events, and leaving. The `wait_for_events` cursor preserves ordered invalidations across reconnects.
