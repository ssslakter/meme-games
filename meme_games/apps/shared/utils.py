from meme_games.core import *

ext2ft = {
        'js': lambda fname: Script(src=f'/{fname}'),
        '_hs': lambda fname: Script(src=f'/{fname}', type='text/hyperscript'),
        'css': lambda fname: Link(rel="stylesheet", href=f'/{fname}'),
    }

def Statics(ext: str ='css', static_path: str|Path = 'static', wc: str = None, **kwargs):
    '''Returns a list of static files from a directory'''
    static_path = Path(static_path)
    wc = wc or f"*.{ext}"
    return [ext2ft[ext](f.relative_to(static_path.parent).as_posix())(**kwargs) 
            for f in static_path.rglob(wc)]


def int2css(value: int, unit: str = 'px'):
    return f'{value}{unit}'

def int2px(value: int):
    return int2css(value, 'px')


ROUTES: list[APIRouter] = []
def register_route(rt):
    if rt not in ROUTES: ROUTES.append(rt)


def lobby_state(req, game: str = None):
    '''The request's lobby, the state of `game`, and the requesting member.

    Raises instead of letting a handler run against a lobby that is playing
    something else - the session lobby and the route need not agree.'''
    lobby = getattr(req.state, 'lobby', None)
    if not lobby:
        raise HTTPException(400, 'Incorrect client state. Please refresh the page.')
    if game and lobby.current_game != game:
        raise HTTPException(409, f'This lobby is playing {lobby.current_game}. Refresh the page.')
    return lobby, lobby.state, lobby.get_member(req.state.user.uid)
