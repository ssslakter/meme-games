from ..shared.spectators import register_game_view, notify_roster_changed
from ..shared.ws_route import lobby_ws
from ..shared.utils import register_route, lobby_state
from meme_games.core import *
from meme_games.domain import *
from ..shared import *
from .domain import *
from .components import *

#---------------------------------#
#------------- Routes ------------#
#---------------------------------#

rt = APIRouter('/whoami')
register_route(rt)
logger = logging.getLogger(__name__)

lobby_service = DI.get(LobbyService)


@rt('/{lobby_id}', methods=['get'])
def index(req: Request, lobby_id: str = None):
    if not lobby_id: return fresh_lobby_redirect(index.to(lobby_id=random_id()), req)
    u: User = req.state.user
    lobby, was_created = lobby_service.get_or_create(
        u, lobby_id, WHOAMI, persistent=True, **new_lobby_options(req))
    if was_created:
        lobby_service.update(lobby)
        if 'allow_agents' in req.query_params: return Redirect(index.to(lobby_id=lobby.id))
    m = lobby.get_member(u.uid)
    req.session['lobby_id'] = lobby.id
    return (Title(f'Who Am I lobby: {lobby.id}'),
            MainBlock(m or u, lobby))

def redirect(lobby_id: str): return Redirect(index.to(lobby_id=lobby_id))


@rt
async def play(req: Request):
    lobby, _, p = lobby_state(req, WHOAMI)
    if p.is_player: return
    if lobby.locked:
        add_toast(req.session, "Game is locked", "error")
        return NewPlayerCard()
    p.play()
    lobby_service.update(lobby)
    await notify_roster_changed(lobby)  # everyone, including p, re-renders the board


register_game_view(WHOAMI, Game)

@rt
async def notes(req: Request, text: str):
    lobby, state, p = lobby_state(req, WHOAMI)
    if not p.is_player: return
    data = state.player(p.uid)
    data.set_notes(text)
    lobby_service.update(lobby)
    if state.config.private_notes: return
    def update(r, *_): return NotesCard(r, p, data, state)(hx_swap_oob=f"outerHTML:[data-notes='{p.uid}']")
    await notify_all(lobby, update, but=p)


@rt
async def toggle_private_notes(req: Request):
    lobby, state, p = lobby_state(req, WHOAMI)
    if not is_host(p): return add_toast(req.session, "Only the host can change this", "error")
    state.config.private_notes = not state.config.private_notes
    lobby_service.update(lobby)
    def update(r, *_): return (PrivateNotesSetting(lobby) if is_host(r) else None,
                               Game(r, lobby, hx_swap_oob='true'))
    await notify_all(lobby, update)


def _board_member(sess: dict, owner_uid: str) -> tuple[Optional[Lobby], Optional[LobbyMember], Optional[LobbyMember]]:
    '''The lobby, the member acting, and the member they are acting on - or Nones if the move is not allowed.'''
    lobby = lobby_service.get_lobby(sess.get("lobby_id"))
    if not lobby or lobby.current_game != WHOAMI: return None, None, None
    p = lobby.get_member(sess.get('uid'))
    owner = lobby.get_member(owner_uid)
    if not (p and owner and p.is_player): return None, None, None
    return lobby, p, owner


async def edit_label_text(sess, label: str, owner_uid: str):
    lobby, p, owner = _board_member(sess, owner_uid)
    if not lobby or p == owner: return
    lobby.state.player(owner.uid).set_label(label)
    lobby_service.update(lobby)
    def update(*_): return dict(type='label_text', owner_uid=owner.uid, label=label)
    await notify_all(lobby, update, but=[owner, p], json=True)
    def update(r, *_): return PlayerLabelText(r, r, lobby.state.player(r.uid))[1](hx_swap_oob=f"innerHTML:[data-label-text='{owner.uid}']")
    await notify(owner, update, owner)


async def edit_label_position(sess, owner_uid: str, **kwargs):
    lobby, p, owner = _board_member(sess, owner_uid)
    if not lobby: return
    lobby.state.player(owner.uid).set_label_transform(kwargs)
    lobby_service.update(lobby)
    def update(*_): return dict(type='label_position', owner_uid=owner.uid, **kwargs)
    await notify_all(lobby, update, json=True, but=p)


async def move_card(sess, owner_uid: str, x: int, y: int):
    lobby, p, owner = _board_member(sess, owner_uid)
    if not lobby: return
    lobby.state.player(owner.uid).set_card_pos(x, y)
    lobby_service.update(lobby)
    def update(*_): return dict(type='card_position', owner_uid=owner.uid, x=x, y=y)
    await notify_all(lobby, update, json=True, but=p)


async def on_message(sess, data):
    try:
        msg_type = data.pop('type')
        if msg_type == 'label_text': await edit_label_text(sess, **data)
        elif msg_type == 'label_position': await edit_label_position(sess, **data)
        elif msg_type == 'card_position': await move_card(sess, **data)
    except Exception as e: logger.error(e)

ws_url = lobby_ws('/whoami', on_message)

register_game_page(WHOAMI, 'Who Am I', lambda lobby_id: index.to(lobby_id=lobby_id))
