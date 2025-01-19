from starlette.routing import compile_path
from fasthtml.common import *
from .not_found import not_found
from .middleware import ConditionalSessionMiddleware
from .common import *
from .utils import Statics
from .whoami.domain import *

db = init_db('data/data.db')
user_manager = UserManager(db)
lobby_manager = LobbyManager(db)
mm = register_manager(MemberManager(user_manager), LobbyMember)
wm = register_manager(WhoAmIManager(mm), WhoAmIPlayer)
lobby_service = LobbyService(lobby_manager)

reg_re_param("xtra", "_hs|json|moc|mtn")

static_path = '.'
static_re = [compile_path("/{fname:path}.{ext:static}")[0], compile_path("/{fname:path}.{ext:xtra}")[0]]
middlware_cls = partial(ConditionalSessionMiddleware, skip=static_re)

bwares = [user_beforeware(user_manager, skip = static_re),
          lobby_beforeware(lobby_service, skip = static_re + [r'/[\w-]*avatar', '/name', '/whoami/.*', '/monitor', '/video/.*', '/meme*'])]
hdrs = [
    Statics(ext='_hs', static_path='static'),
    Script(src="https://unpkg.com/hyperscript.org@0.9.13"),
    Statics(ext='js', static_path='static', wc='live2d/*.js'),
    Statics(ext='js', static_path='static', wc='scripts/*.js'),
    Link(rel="stylesheet", href="https://fonts.googleapis.com/icon?family=Material+Icons"),
    Statics(ext='css', static_path='static'),
]

yt_hdrs = [
    # Script(src="https://www.youtube.com/iframe_api"),
    # Script(src="/static/youtube.js"),
]

bodykw = {'hx-boost': 'true'}

exception_handlers = {404: not_found}

app: FastHTML
app, rt = fast_app(pico=False, before=bwares, hdrs=hdrs+yt_hdrs,
                   exts='ws',
                   bodykw={**bodykw,'sess_cls': middlware_cls},
                   key_fname='data/.sesskey',
                   exception_handlers=exception_handlers)

async def file_resp(fname:str, ext:str): 
    cache_age = 60*60*24*7 if 'media' in fname else 10*60
    return FileResponse(f'{static_path}/{fname}.{ext}', headers={'Cache-Control': f'public, max-age={cache_age}'})

app.route("/{fname:path}.{ext:static}")(file_resp)
app.route("/{fname:path}.{ext:xtra}")(file_resp)

app.router.routes.append(app.router.routes.pop(0)) # change the order for static router
print(app.routes)