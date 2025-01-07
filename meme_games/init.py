from fasthtml.common import *

from .common import *

db = init_db('data.db')
user_manager, lobby_manager = UserManager(db), LobbyManager()
lobby_manager = LobbyManager()
default_skips = [r'/static/.*', r'/user-content/.*']
bwares = [user_beforeware(user_manager, skip = default_skips),
          lobby_beforeware(lobby_manager, skip=default_skips + ['/picure', '/name', '/whoami/.*'])]
hdrs = [
    Script(src='/static/script._hs', type='text/hyperscript'),
    Script(src="https://unpkg.com/hyperscript.org@0.9.13"),
    Link(rel="stylesheet", href="https://fonts.googleapis.com/icon?family=Material+Icons"),
    Link(rel="stylesheet", href="/static/styles.css"),
    Script(src="https://unpkg.com/interactjs/dist/interact.min.js"),
]

app, rt = fast_app(pico=False, before=bwares, hdrs=hdrs, exts='ws', bodykw={'hx-boost': 'true'})
app.static_route(ext='._hs')
