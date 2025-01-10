from starlette.routing import compile_path
from fasthtml.common import *

from meme_games.middleware import ConditionalSessionMiddleware

from .common import *

db = init_db('data/data.db')
user_manager, lobby_manager = UserManager(db), LobbyManager()
lobby_manager = LobbyManager()

static_re = [compile_path("/{fname:path}.{ext:static}")[0]]
middlware_cls = partial(ConditionalSessionMiddleware, skip=static_re)

bwares = [user_beforeware(user_manager, skip = static_re),
          lobby_beforeware(lobby_manager, skip=static_re + [r'/[\w-]*avatar', '/name', '/whoami/.*', '/monitor'])]
hdrs = [
    Script(src='/static/movement._hs', type='text/hyperscript'),
    Script(src='/static/timer._hs', type='text/hyperscript'),
    Script(src="https://unpkg.com/hyperscript.org@0.9.13"),
    Link(rel="stylesheet", href="https://fonts.googleapis.com/icon?family=Material+Icons"),
    Link(rel="stylesheet", href="/static/styles.css"),
    Script(src="https://unpkg.com/interactjs/dist/interact.min.js"),
]

app, rt = fast_app(pico=False, before=bwares, hdrs=hdrs,
                   exts='ws', bodykw={'hx-boost': 'true','sess_cls': middlware_cls}, key_fname='data/.sesskey')
app.static_route(ext='._hs')
