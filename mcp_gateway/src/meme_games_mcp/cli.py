import argparse
import os

import uvicorn

from .client import Settings
from .server import build_gateway


def csv_env(name: str, default: str):
    return tuple(value.strip() for value in os.environ.get(name, default).split(',') if value.strip())


def main(argv=None):
    parser = argparse.ArgumentParser(prog='meme-games-mcp', description='Run the Meme Games MCP gateway')
    parser.add_argument('--host', default=os.environ.get('MCP_HOST', '127.0.0.1'))
    parser.add_argument('--port', type=int, default=int(os.environ.get('MCP_PORT', '8001')))
    args = parser.parse_args(argv)
    secret = os.environ.get('MCP_GATEWAY_SECRET', '')
    if not secret: parser.error('MCP_GATEWAY_SECRET is required')
    settings = Settings(
        app_url=os.environ.get('MEME_GAMES_AGENT_API', 'http://127.0.0.1:8000/internal/agents'),
        gateway_secret=secret,
        allowed_hosts=csv_env('MCP_ALLOWED_HOSTS', '127.0.0.1:*,localhost:*'),
        allowed_origins=csv_env('MCP_ALLOWED_ORIGINS', 'http://127.0.0.1:8001,http://localhost:8001'))
    app, *_ = build_gateway(settings)
    uvicorn.run(app, host=args.host, port=args.port, proxy_headers=True)
