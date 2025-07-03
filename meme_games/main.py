from meme_games.core import *
from meme_games.domain import *
from starlette.routing import compile_path
from meme_games.apps import *

db = init_db('data/data.db')
DI.register_instance(db)
for man, member in zip([MemberManager, WhoAmIManager, CodenamesManager],
                       [LobbyMember, WhoAmIPlayer, CodenamesPlayer]):
    register_lobby_member_manager(DI.get(man), member)

reg_re_param("xtra", "_hs|json|moc|mtn")

static_path = '.'
static_re = [compile_path("/{fname:path}.{ext:static}")[0], compile_path("/{fname:path}.{ext:xtra}")[0]]
middlware_cls = partial(ConditionalSessionMiddleware, skip=static_re)

bwares = [user_beforeware(DI.get(UserManager), skip = static_re),
          lobby_beforeware(DI.get(LobbyService))
          ]
hdrs = [
    Statics(ext='_hs', static_path='static'),
    Script(src="/static/_hyperscript.min.js"),
    Statics(ext='js', static_path='static', wc='live2d/*.js'),
    Statics(ext='js', static_path='static', wc='scripts/*.js'),
    Link(rel="stylesheet", href="https://fonts.googleapis.com/icon?family=Material+Icons"),
    # Statics(ext='css', static_path='static'),
    Theme.blue.headers()
]

yt_hdrs = [
    # Script(src="https://www.youtube.com/iframe_api"),
    # Script(src="/static/youtube.js"),
]

bodykw = {'hx-boost': 'true'}

exception_handlers = {404: not_found}

app: FastHTML
app, _ = fast_app(pico=False, before=bwares, hdrs=hdrs+yt_hdrs,
                   exts='ws',
                   bodykw={**bodykw,'sess_cls': middlware_cls},
                   key_fname='data/.sesskey',
                   exception_handlers=exception_handlers)

setup_toasts(app, duration=1.5)

for rt in [shared_rt, whoami_rt, video_rt, word_packs_rt, codenames_rt, ws_rt]:
    rt.to_app(app)


async def file_resp(fname:str, ext:str): 
    cache_age = 60*60*24*7 if 'media' in fname else 10*60
    return FileResponse(f'{static_path}/{fname}.{ext}', headers={'Cache-Control': f'public, max-age={cache_age}'})

app.route("/{fname:path}.{ext:static}")(file_resp)
app.route("/{fname:path}.{ext:xtra}")(file_resp)

app.router.routes.append(app.router.routes.pop(0)) # change the order for static router
