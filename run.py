import os
import uvicorn

if __name__ == '__main__':
    reload = bool(os.environ.get('DEV', False))
    uvicorn.run('meme_games.main:app', host='0.0.0.0', port=8000,
                proxy_headers=True,
                forwarded_allow_ips=os.environ.get('FORWARDED_ALLOW_IPS', '127.0.0.1'),
                reload=reload, reload_includes='meme_games/**' if reload else None)
