from meme_games.core import *

static_dir = Path(__file__).parent.parent / 'static'
# Script(src='/' + f.relative_to(static_dir.parent).as_posix())
#                 for f in (static_dir / 'live2d').rglob("*.js")


def not_found(req: Request, exc):
    if req.method.lower() != 'get': return Response('Not found', status_code=404)
    model_path = '/media/shizuku/shizuku.model.json'
    return (Title("Not Found"), Body(H1("404😭! Sorry, this page does not exist."),
                                     Canvas(id="canvas", cls='live2d-canvas',
                                            width=1000, height=900, style='opacity: 0;',
                                            _=f'''
                            init call initLive2D(me, @width, @height, "{model_path}")
                            then wait 10ms then transition my opacity to 1 over 500ms end
                            on resize from window call resizeCanvas(me)'''),
                                     hx_boost='true', cls='live2d'))
