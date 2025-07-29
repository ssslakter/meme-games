import urllib
from meme_games.core import *
from meme_games.domain import *

ext2ft = {
        'js': lambda fname: Script(src=f'/{fname}'),
        '_hs': lambda fname: Script(src=f'/{fname}', type='text/hyperscript'),
        'css': lambda fname: Link(rel="stylesheet", href=f'/{fname}'),
    }

def Statics(ext: str ='css', static_path: str|Path = 'static', wc: str = None):
    '''Returns a list of static files from a directory'''
    static_path = Path(static_path)
    wc = wc or f"*.{ext}"
    return [ext2ft[ext](f.relative_to(static_path.parent).as_posix()) 
            for f in static_path.rglob(wc)]

def Timer(time: dt.timedelta = dt.timedelta(hours=1)):
    return Span(data_delta=time.total_seconds() * 1000, cls='timer',
                _='init immediately set @target to (Date.now()+@data-delta as Number) as Date')


def int2css(value: int, unit: str = 'px'):
    return f'{value}{unit}'

def int2px(value: int):
    return int2css(value, 'px')


ROUTES: set[APIRouter] = set()
def register_route(rt):
    ROUTES.add(rt)