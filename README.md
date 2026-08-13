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

Set the same private secret for the application and gateway, then run both processes:

```sh
MCP_GATEWAY_SECRET=replace-me pixi run app
cd mcp_gateway
uv sync --locked
MCP_GATEWAY_SECRET=replace-me uv run meme-games-mcp --host 127.0.0.1 --port 8001
```

Alternatively, start the optional Compose profile:

```sh
MCP_GATEWAY_SECRET=replace-me docker compose --profile mcp up -d
```

A Codenames host can create an agent invite in Game settings. Its bearer token and MCP connection configuration are displayed once. The public MCP endpoint defaults to `http://127.0.0.1:8001/mcp`; set `MCP_PUBLIC_URL` when exposing it through a reverse proxy.
