from ..shared.ws_route import lobby_ws
from ..shared.utils import register_route
from ..shared.spectators import *
from meme_games.domain import *
from meme_games.apps.shared import register_page
from meme_games.core import *
from ..shared import *
from .components import *

rt = APIRouter('/video')
register_route(rt)

VIDEO = 'video'
register_game(VIDEO)
register_game_page(VIDEO, "Videos 🚧", lambda lobby_id: index.to(lobby_id=lobby_id))

logger = logging.getLogger(__name__)

lobby_service = DI.get(LobbyService)


@rt('/{lobby_id}', methods=['get'])
def index(req: Request, lobby_id: str = None):
    if not lobby_id: return redirect(random_id())
    u: User = req.state.user
    lobby, was_created = lobby_service.get_or_create(u, lobby_id, VIDEO, persistent=True)
    if was_created: lobby_service.update(lobby)
    req.session['lobby_id'] = lobby.id

    return LobbyPage(
        H1("Videos"),
        StreamingMain(),
        Spectators(u, lobby, cls='right-0 bottom-1/3 -translate-y-1/2'),
        SettingsPopover(lobby=lobby, member=lobby.get_member(u.uid)),
        title=f"Watch together lobby: {lobby.id}",
        no_image=True, page='video')

def redirect(lobby_id: str): return Redirect(index.to(lobby_id=lobby_id))

async def relay(ws, sess, data):
    '''Video playback events are echoed to everyone else as-is.'''
    lobby = lobby_service.get_lobby(sess.get("lobby_id"))
    if not lobby: return
    await notify_all(lobby, lambda *_: data, but=lobby.get_member(sess['uid']), json=True)

ws_url = lobby_ws('/video', relay)
