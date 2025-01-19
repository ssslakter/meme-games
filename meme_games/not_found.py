from pathlib import Path
from fasthtml.common import *

static_dir = Path(__file__).parent.parent / 'static'
# Script(src='/' + f.relative_to(static_dir.parent).as_posix())
#                 for f in (static_dir / 'live2d').rglob("*.js")


def not_found(req, exc):
    model_path = '/media/shizuku/shizuku.model.json'
    return Body(H1("404! Sorry, our librarian could not find the page (she's not sorry)."),
                Canvas(id="canvas", cls='live2d-canvas',
                       width=1000, height=900, style='opacity: 0;',
                       _=f'''
                       init call initLive2D(me, @width, @height, "{model_path}") 
                       then wait 10ms then transition my opacity to 1 over 500ms end
                       on resize from window call resizeCanvas(me)'''),
                hx_boost='true', cls='live2d')
