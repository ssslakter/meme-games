import contextlib
from meme_games.core import *
from meme_games.services import db, data_dir
from meme_games.domain import *
from starlette.middleware.gzip import GZipMiddleware
from starlette.routing import compile_path
from starlette_prometheus import PrometheusMiddleware
from .metrics import metrics
from meme_games.apps import *

reg_re_param("xtra", "_hs|json|moc|mtn")

static_path = '.'
static_re = [compile_path("/{fname:path}.{ext:static}")[0], compile_path("/{fname:path}.{ext:xtra}")[0]]
internal_re = compile_path("/internal/{path:path}")[0]
middlware_cls = partial(ConditionalSessionMiddleware, skip=static_re)

bwares = [user_beforeware(DI.get(UserManager), skip = [*static_re, internal_re]),
          lobby_beforeware(DI.get(LobbyService), skip = [*static_re, internal_re]),
          current_game_beforeware(skip=[*static_re, internal_re]),
          ]

style = Style(
    '''
    :root {
        --uk-global-font-size: 1.3rem;
    }
    '''
)

hdrs = [
    Meta(charset="utf-8"),
    Meta(name="viewport", content="width=device-width, initial-scale=1, viewport-fit=cover"),
    Meta(name="robots", content="noindex, nofollow"),
    Script('htmx.config.allowNestedOobSwaps=false;'),
    Link(rel="icon", href="/static/images/favicon.ico"),
    Theme.yellow._create_headers({
        'franken_css': '/static/scripts/imports/franken-ui-core.css',
        'franken_js_core': '/static/scripts/imports/franken-ui-core.js',
        'franken_icons': '/static/scripts/imports/franken-ui-icon.js',
        'tailwind': '/static/scripts/imports/tailwind.js',
        'daisyui': '/static/scripts/imports/daisyui.css',
    }, radii=ThemeRadii.lg, shadows=ThemeShadows.lg),
    Script(src='/static/scripts/imports/htmx.js'),
    Script(src='/static/scripts/imports/fasthtml.js'),
    Script(src='/static/scripts/imports/surreal.js'),
    Script(src='/static/scripts/imports/css-scope-inline.js'),
    Script(src='/static/scripts/imports/htmx-ext-ws.js'),
    Script(src='/static/scripts/imports/_hyperscript.min.js'),
    Script(src='/static/scripts/imports/live2d/live2dcubismcore.min.js'),
    Script(src='/static/scripts/imports/live2d/live2d.min.js'),
    Script(src='/static/scripts/imports/live2d/pixi.min.js'),
    Script(src='/static/scripts/imports/live2d/index.min.js'),
    Statics(ext='css', static_path='static', wc='styles/*.css'),
    Statics(ext='js', static_path='static', wc='scripts/common/**/*.js'),
    Statics(ext='js', static_path='static', wc='scripts/whoami/**/*.js'),
    Statics(ext='js', static_path='static', wc='scripts/video/**/*.js', defer=True),
    style
]



exception_handlers = {404: not_found}


@contextlib.asynccontextmanager
async def lifespan(app):
    task = asyncio.create_task(DI.get(LobbyService).run_cleanup_loop())
    yield
    task.cancel()


app = FastHTML(before=bwares, hdrs=hdrs,
                   lifespan=lifespan,
                   default_hdrs=False,
                   sess_cls=middlware_cls,
                   key_fname=str(data_dir/'.sesskey'),
                   exception_handlers=exception_handlers,
                   htmlkw={'class': 'uk-custom-theme'},
                   bodykw={'hx-boost': 'true'})

app.add_middleware(NoStoreHTMLMiddleware)
app.add_middleware(PrometheusMiddleware, filter_unhandled_paths=True)
# Rate limiting is handled by nginx + crowdsec. This only stops crawlers/unfurlers
# (and serves robots.txt) before they can create lobbies nobody joins.
app.add_middleware(BotFilterMiddleware, patterns=LOBBY_PATTERNS)
app.add_middleware(GZipMiddleware, minimum_size=500)
app.route('/metrics')(metrics)

setup_app_toasts(app, duration=2500)

for rt in ROUTES:
    # `/{lobby_id}` must be matched after its siblings, or GET /alias/vote is read
    # as a lobby named "vote" and creates one
    rt.routes.sort(key=lambda r: '{' in r[1])
    rt.to_app(app)


async def file_resp(fname:str, ext:str): 
    cache_age = 60*60*24*7 if 'media' in fname else 10*60
    return FileResponse(f'{static_path}/{fname}.{ext}', headers={'Cache-Control': f'public, max-age={cache_age}'})

app.route("/{fname:path}.{ext:static}")(file_resp)
app.route("/{fname:path}.{ext:xtra}")(file_resp)
