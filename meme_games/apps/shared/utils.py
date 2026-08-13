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


# page name -> url, or a callable building one from a lobby id
PAGES_REGISTRY: dict[str, str | Callable[[str], str]] = {}
# game key -> (display name, url builder), for switching the game of an existing lobby
GAME_PAGES: dict[str, tuple[str, Callable[[str], str]]] = {}


def register_page(name: str, url: str | Callable[[str], str]):
    PAGES_REGISTRY[name] = url


def register_game_page(game: str, name: str, url: Callable[[str], str]):
    '''A game's page: listed in the navbar, and reachable for a lobby already in play.'''
    PAGES_REGISTRY[name] = url
    GAME_PAGES[game] = (name, url)


def page_url(url: str | Callable[[str], str], lobby_id: str = None) -> str:
    '''With no lobby id the game route sends you to a fresh lobby.'''
    return url(lobby_id or '') if callable(url) else url


def game_url(game: str, lobby_id: str) -> Optional[str]:
    entry = GAME_PAGES.get(game)
    return page_url(entry[1], lobby_id) if entry else None
