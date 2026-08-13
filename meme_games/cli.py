import argparse
import os

import uvicorn


def valid_port(value: str) -> int:
    port = int(value)
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError('port must be between 1 and 65535')
    return port


def main(argv=None):
    parser = argparse.ArgumentParser(prog='meme-games', description='Run the Meme Games server')
    parser.add_argument('--host', default='0.0.0.0', help='address to bind (default: %(default)s)')
    parser.add_argument('--port', type=valid_port, default=8000, help='port to bind (default: %(default)s)')
    args = parser.parse_args(argv)
    reload = bool(os.environ.get('DEV'))
    uvicorn.run('meme_games.main:app', host=args.host, port=args.port,
                proxy_headers=True,
                forwarded_allow_ips=os.environ.get('FORWARDED_ALLOW_IPS', '127.0.0.1'),
                reload=reload, reload_includes='meme_games/**' if reload else None)
