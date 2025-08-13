from ..shared.ws_route import ws_fn
from ..shared.utils import register_route
from ..shared.spectators import *
from meme_games.domain import *
from meme_games.apps.shared import register_page
from meme_games.core import *
from ..shared import *
from .components import *

rt = APIRouter('/video')
register_route(rt)
register_page("Videos 🚧", rt.prefix)

logger = logging.getLogger(__name__)

lobby_service = DI.get(LobbyService)
user_manager = DI.get(UserManager)


@rt('/{lobby_id}', methods=['get'])
def index(req: Request, lobby_id: str = None):
    if not lobby_id: return redirect(random_id())
    u: User = req.state.user
    lobby, was_created = lobby_service.get_or_create(u, lobby_id, BasicLobby, persistent=True)
    if was_created: lobby_service.update(lobby)
    req.session['lobby_id'] = lobby.id

    return LobbyPage(
        H1("Videos"),
        StreamingMain(),
        Spectators(u, lobby, cls='right-0 bottom-1/3 -translate-y-1/2'),
        SettingsPopover(),
        title=f"Watch together lobby: {lobby.id}",
        no_image=True)

def redirect(lobby_id: str): return Redirect(index.to(lobby_id=lobby_id))

def upd(r, lobby, conn_member):
    if r == conn_member: return SpectatorsList(r, lobby), MemberName(r, conn_member)
    return SpectatorsList(r, lobby), MemberName(r, conn_member)

@ws_rt.ws('/video', conn=ws_fn(render_fn=upd), disconn=ws_fn(False, upd))
async def ws(ws, sess, data):
    u = user_manager.get(sess['uid'])
    lobby = lobby_service.get_lobby(sess.get("lobby_id"), BasicLobby)
    m = lobby.get_member(u.uid)
    await notify_all(lobby, lambda *_: data, but=m, json=True)

ws_url = ws_rt.wss[-1][1]