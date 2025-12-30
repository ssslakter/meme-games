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


ROUTES: set[APIRouter] = set()
def register_route(rt):
    ROUTES.add(rt)


def get_common_services():
    """Get commonly used services from DI container.
    
    Returns:
        tuple: (lobby_service, user_manager)
    """
    from meme_games.domain import LobbyService, UserManager
    from meme_games.core import DI
    
    return DI.get(LobbyService), DI.get(UserManager)


def create_lobby_redirect(index_route):
    """Create a redirect helper function for lobby routes.
    
    Args:
        index_route: The index route function to redirect to
        
    Returns:
        function: A redirect function that takes lobby_id and redirects to index
    """
    def redirect(lobby_id: str):
        from meme_games.core import Redirect
        return Redirect(index_route.to(lobby_id=lobby_id))
    return redirect


def create_ws_spectator_update(game_component=None):
    """Create a standard websocket update function for spectator lists.
    
    Args:
        game_component: Optional game component function to render for the connected member
        
    Returns:
        function: An update function for websocket connections
    """
    def upd(r, lobby, conn_member):
        from ..shared.spectators import SpectatorsList
        from ..shared.general import MemberName
        
        if game_component and r == conn_member:
            return game_component(r, lobby), SpectatorsList(r, lobby), MemberName(r, conn_member)
        return SpectatorsList(r, lobby), MemberName(r, conn_member)
    return upd
