from starlette.responses import Response

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
    return Response(status_code=204)


@rt
async def set_ready(req: Request):
    lobby, _, p = pre_init(req)
    raw = req.query_params.get('is_ready', 'true')
    is_ready = str(raw).lower() not in ('0', 'false', 'no')
    form = await req.form()
    # cells are named `text`, which is also what a single cell posts as it is typed
    key = 'text' if 'text' in form else 'words' if 'words' in form else None
    words = form.getlist(key) if is_ready and key else None
    try: await hivemind_actions.set_ready(lobby, p, is_ready, words)
    except ActionRejected as error: return rejected(req, error)
    # Still writing: hand this player their own locked list. Everyone else only
    # gets the count, so a keystroke they have not saved yet stays on screen.
    if lobby.state.phase == HivePhase.WRITING: return AnswerArea(p, lobby)
    return Response(status_code=204)


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


def _on(value: str) -> bool: return str(value).lower() in ('1', 'on', 'true')


@rt
async def update_settings(req: Request, total_rounds: int = DEFAULT_ROUNDS,
                          seconds: int = DEFAULT_SECONDS, same: str = '',
                          different: str = '', topics: str = ''):
    lobby, _, p = pre_init(req)
    try: await hivemind_actions.update_settings(
        lobby, p, total_rounds, seconds, _on(same), _on(different), _on(topics))
    except ActionRejected as error: return rejected(req, error)


@rt
def editor_readonly(req: Request, id: str, slot: str = 'prompts'):
    _, state, member = pre_init(req)
    return SelectEditor(member, wordpack_manager.get_by_id(id), state, slot)


@rt
def pack_select(req: Request, slot: str = 'prompts'):
    _, state, member = pre_init(req)
    return PackSelectContents(member, state, slot)


@rt
async def select_pack(req: Request, id: str, slot: str = 'prompts'):
    lobby, _, p = pre_init(req)
    try: await hivemind_actions.select_pack(lobby, p, id, slot)
    except ActionRejected as error: return rejected(req, error)


#------------------------------#
#------------ Events ----------#
#------------------------------#

def HiveMindView(reciever: LobbyMember | User, lobby: Lobby, **kwargs):
    return Game(reciever, lobby, **kwargs)


register_game_view(HIVEMIND, HiveMindView)


def render_hivemind(topics: set[str], reciever, lobby: Lobby):
    """What one receiver is sent. An open round's 'ready' is only the count."""
    if 'edit' in topics and 'game' not in topics: return RevealSync(lobby, oob=True)
    writing = lobby.state.phase == HivePhase.WRITING
    if 'status' in topics and 'game' not in topics and writing:
        return Status(lobby, hx_swap_oob='outerHTML')
    if topics & {'game', 'status'}:
        return (Game(reciever, lobby, hx_swap_oob='true'),
                HiveMindSettings(reciever, lobby, hx_swap_oob='outerHTML') if is_host(reciever) else None)


def _render_hivemind_event(event: LobbyChanged, lobby: Lobby):
    if event.game != HIVEMIND or not event.topics & {'game', 'status', 'edit'}: return
    return notify_all(lobby, lambda r, *_: render_hivemind(event.topics, r, lobby))


lobby_events.subscribe(_render_hivemind_event)

ws_url = lobby_ws('/hivemind')

register_game_page(HIVEMIND, 'Hive Mind', lambda lobby_id: index.to(lobby_id=lobby_id))
