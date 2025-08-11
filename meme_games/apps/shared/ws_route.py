from meme_games.core import *
from ..user import MemberName
from meme_games.domain import LobbyService, UserManager, notify_all
from .utils import register_route

ws_rt = APIRouter('/ws')
register_route(ws_rt)

lobby_service = DI.get(LobbyService)
user_manager = DI.get(UserManager)


def ws_fn(connected=True, render_fn: Callable = lambda *_: None):
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