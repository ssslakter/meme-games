from ..shared import *
from ..shared.spectators import register_game_view
from ..shared.ws_route import lobby_ws
from ..shared.utils import register_route, lobby_state
from meme_games.core import *
from meme_games.domain import *
from meme_games.domain import Lobby as _Lobby
from .domain import *
from .actions import *
from .components import *

Lobby = _Lobby[HiveMindState]

#---------------------------------#
#------------- Routes ------------#
#---------------------------------#

rt = APIRouter('/hivemind')
register_route(rt)

lobby_service = DI.get(LobbyService)


def rejected(req, error): return add_toast(req.session, str(error), 'error')


def pre_init(req: Request) -> tuple[Lobby, HiveMindState, LobbyMember]:
    return lobby_state(req, HIVEMIND)


@rt('/{lobby_id}', methods=['get'])
def index(req: Request, lobby_id: str = None):
    if not lobby_id: return fresh_lobby_redirect(index.to(lobby_id=random_id()), req)
    u: User = req.state.user
    lobby, was_created = lobby_service.get_or_create(u, lobby_id, HIVEMIND, **new_lobby_options(req))
    if was_created:
        lobby_service.update(lobby)
        if 'allow_agents' in req.query_params: return Redirect(index.to(lobby_id=lobby.id))
    m = lobby.get_member(u.uid)
    req.session['lobby_id'] = lobby.id
    return (Title(f'Hive Mind lobby: {lobby.id}'),
            MainBlock(m or u, lobby))


@rt
async def play(req: Request):
    lobby, _, p = pre_init(req)
    try: await hivemind_actions.join(lobby, p)
    except ActionRejected as error: return rejected(req, error)


@rt
async def set_word(req: Request, index: int, text: str):
    lobby, _, p = pre_init(req)
    try: await hivemind_actions.set_word(lobby, p, index, text)
    except ActionRejected as error: return rejected(req, error)


@rt
async def set_ready(req: Request, is_ready: bool = True):
    lobby, _, p = pre_init(req)
    try: await hivemind_actions.set_ready(lobby, p, is_ready)
    except ActionRejected as error: return rejected(req, error)


@rt
async def edit_word(req: Request, uid: str, index: int, text: str):
    """Rewriting a word on the revealed round, to settle a near miss by hand."""
    lobby, _, p = pre_init(req)
    try: await hivemind_actions.edit_word(lobby, p, uid, index, text)
    except ActionRejected as error: return rejected(req, error)


@rt
async def advance(req: Request):
    lobby, _, p = pre_init(req)
    try: await hivemind_actions.advance(lobby, p)
    except ActionRejected as error: return rejected(req, error)


@rt
async def start_game(req: Request):
    lobby, _, p = pre_init(req)
    try: await hivemind_actions.start(lobby, p)
    except ActionRejected as error: return rejected(req, error)


@rt
async def restart_game(req: Request):
    lobby, _, p = pre_init(req)
    try: await hivemind_actions.restart(lobby, p)
    except ActionRejected as error: return rejected(req, error)


@rt
async def update_settings(req: Request, total_rounds: int = DEFAULT_ROUNDS,
                          seconds: int = DEFAULT_SECONDS):
    lobby, _, p = pre_init(req)
    try: await hivemind_actions.update_settings(lobby, p, total_rounds, seconds)
    except ActionRejected as error: return rejected(req, error)


@rt
def editor_readonly(req: Request, id: str):
    _, state, member = pre_init(req)
    return SelectEditor(member, wordpack_manager.get_by_id(id), state)


@rt
def pack_select(req: Request):
    _, state, member = pre_init(req)
    return PackSelectContents(member, state)


@rt
async def select_pack(req: Request, id: str):
    lobby, _, p = pre_init(req)
    try: await hivemind_actions.select_pack(lobby, p, id)
    except ActionRejected as error: return rejected(req, error)


#------------------------------#
#------------ Events ----------#
#------------------------------#

def HiveMindView(reciever: LobbyMember | User, lobby: Lobby, **kwargs):
    return Game(reciever, lobby, **kwargs)


register_game_view(HIVEMIND, HiveMindView)


def _render_hivemind_event(event: LobbyChanged, lobby: Lobby):
    if event.game != HIVEMIND or 'game' not in event.topics: return
    return notify_all(lobby, lambda r, *_: (
        Game(r, lobby, hx_swap_oob='true'),
        HiveMindSettings(r, lobby, hx_swap_oob='outerHTML') if is_host(r) else None))


lobby_events.subscribe(_render_hivemind_event)

ws_url = lobby_ws('/hivemind')

register_game_page(HIVEMIND, 'Hive Mind', lambda lobby_id: index.to(lobby_id=lobby_id))
