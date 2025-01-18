from starlette.routing import compile_path
from fasthtml.common import *

from meme_games.middleware import ConditionalSessionMiddleware
from .common import *
from .whoami.domain import *

db = init_db('data/data.db')
user_manager = UserManager(db)
member_manager = MemberManager(user_manager)
lobby_manager = LobbyManager(member_manager)
whoami_manger = WhoAmIManager(member_manager)
lobby_service = LobbyService(lobby_manager)

reg_re_param("xtra", "_hs|json")

static_re = [compile_path("/{fname:path}.{ext:static}")[0], compile_path("/{fname:path}.{ext:xtra}")[0]]
middlware_cls = partial(ConditionalSessionMiddleware, skip=static_re)

bwares = [user_beforeware(user_manager, skip = static_re),
          lobby_beforeware(lobby_service, skip = static_re + [r'/[\w-]*avatar', '/name', '/whoami/.*', '/monitor', '/video/.*', '/meme*'])]
hdrs = [
    Script(src='/static/movement._hs', type='text/hyperscript'),
    Script(src='/static/timer._hs', type='text/hyperscript'),
    Script(src='/static/youtube._hs', type='text/hyperscript'),
    Script(src="https://unpkg.com/hyperscript.org@0.9.13"),
    Link(rel="stylesheet", href="https://fonts.googleapis.com/icon?family=Material+Icons"),
    Link(rel="stylesheet", href="/static/styles.css"),
    Script(src="https://unpkg.com/interactjs/dist/interact.min.js")
]

yt_hdrs = [
    # Script(src="https://www.youtube.com/iframe_api"),
    # Script(src="/static/youtube.js"),
    # Script(src="https://cubism.live2d.com/sdk-web/cubismcore/live2dcubismcore.min.js"),
    # Script(src="https://cdn.jsdelivr.net/gh/dylanNew/live2d/webgl/Live2D/lib/live2d.min.js"),
    # Script(src="https://cdn.jsdelivr.net/npm/pixi.js@6.5.2/dist/browser/pixi.min.js"),
    # Script(src="https://cdn.jsdelivr.net/npm/pixi-live2d-display/dist/index.min.js")
]

bodykw = {'hx-boost': 'true'}

app, rt = fast_app(pico=False, before=bwares, hdrs=hdrs+yt_hdrs,
                   exts='ws', bodykw={**bodykw,'sess_cls': middlware_cls}, key_fname='data/.sesskey')

app.static_route_exts(prefix='/', exts='xtra')