import os
from meme_games.main import serve

if __name__ == '__main__':
    reload = os.environ.get('DEV', False)
    serve(appname='meme_games.main', port=8000, reload=reload, reload_includes='meme_games/**' if reload else None)