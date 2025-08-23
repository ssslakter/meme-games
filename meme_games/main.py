from meme_games.core import *
from meme_games.domain import *
from starlette.routing import compile_path
from starlette_prometheus import PrometheusMiddleware
from .metrics import metrics
from meme_games.apps import *

db = init_db('data/data.db')
DI.register_instance(db)

reg_re_param("xtra", "_hs|json|moc|mtn")

static_path = '.'
static_re = [compile_path("/{fname:path}.{ext:static}")[0], compile_path("/{fname:path}.{ext:xtra}")[0]]
middlware_cls = partial(ConditionalSessionMiddleware, skip=static_re)

bwares = [user_beforeware(DI.get(UserManager), skip = static_re),
          lobby_beforeware(DI.get(LobbyService), skip = static_re)
          ]

style = Style(
    '''
    :root {
        --uk-global-font-size: 1.3rem;
    }
    '''
)

hdrs = [
    Script('htmx.config.allowNestedOobSwaps=false;'),
    Link(rel="icon", href="/static/images/favicon.ico"),
    Script(src='/static/scripts/imports/_hyperscript.min.js'),
    Script(src='/static/scripts/imports/live2d/live2dcubismcore.min.js'),
    Script(src='/static/scripts/imports/live2d/live2d.min.js'),
    Script(src='/static/scripts/imports/live2d/pixi.min.js'),
    Script(src='/static/scripts/imports/live2d/index.min.js'),
    Statics(ext='js', static_path='static', wc='scripts/common/**/*.js'),
    Statics(ext='js', static_path='static', wc='scripts/whoami/**/*.js'),
    Statics(ext='js', static_path='static', wc='scripts/video/**/*.js', defer=True),
    Theme.yellow.headers(radii=ThemeRadii.lg, shadows=ThemeShadows.lg),
    style
]



exception_handlers = {404: not_found}

app = FastHTML(before=bwares, hdrs=hdrs,
                   exts='ws',
                   sess_cls=middlware_cls,
                   key_fname='data/.sesskey',
                   exception_handlers=exception_handlers,
                   htmlkw={'class': 'uk-custom-theme'},
                   bodykw={'hx-boost': 'true'})

app.add_middleware(PrometheusMiddleware, filter_unhandled_paths=True)
app.route('/metrics')(metrics)

setup_toasts(app, duration=1500)

for rt in ROUTES:
    rt.to_app(app)


async def file_resp(fname:str, ext:str): 
    cache_age = 60*60*24*7 if 'media' in fname else 10*60
    return FileResponse(f'{static_path}/{fname}.{ext}', headers={'Cache-Control': f'public, max-age={cache_age}'})

app.route("/{fname:path}.{ext:static}")(file_resp)
app.route("/{fname:path}.{ext:xtra}")(file_resp)

app.router.routes.append(app.router.routes.pop(0)) # change the order for static router
