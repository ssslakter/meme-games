from meme_games.core import *
from ..user import MemberName
from meme_games.domain import LobbyService, UserManager, notify_all
from .utils import register_route
from .spectators import SpectatorsList, GameView

ws_rt = APIRouter('/ws')
register_route(ws_rt)

lobby_service = DI.get(LobbyService)
user_manager = DI.get(UserManager)


def lobby_view(r, lobby, conn_member):
    '''What every member sees when someone connects or drops: the spectator list and
    that member's connection state. The member who just connected also gets the board.'''
    common = SpectatorsList(r, lobby), MemberName(r, conn_member)
    return (GameView(r, lobby), *common) if r == conn_member else common


def lobby_ws(path: str, recv: Callable = noop) -> str:
    '''Register a lobby websocket at `path` and return its url.'''
    ws_rt.ws(path, conn=ws_fn(), disconn=ws_fn(False))(recv)
    return f'{ws_rt.prefix}{path}'


def ws_fn(connected=True, render_fn: Callable = lobby_view):
    '''Returns a function that will be called when a user joins the lobby websocket'''
    async def user_joined(sess, send, ws):
        u = user_manager.get_or_create(sess)
        lobby = lobby_service.get_lobby(sess.get('lobby_id'))
        if not lobby: return
        if m := lobby.get_member(u.uid):
            if connected: m.connect(send, ws)
            else: m.disconnect()

        else:
            if not connected: return  # user not found in the lobby and not connecting
            m = lobby.create_member(u, send=send, ws=ws)
            lobby_service.update(lobby)

        await notify_all(lobby, render_fn, conn_member=m)

    return user_joined