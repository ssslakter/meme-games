from ..shared.spectators import register_game_view, notify_roster_changed
from ..shared.ws_route import ws_fn
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
user_manager = DI.get(UserManager)


@rt('/{lobby_id}', methods=['get'])
def index(req: Request, lobby_id: str = None):
    if not lobby_id: return redirect(random_id())
    u: User = req.state.user
    lobby, was_created = lobby_service.get_or_create(u, lobby_id, WHOAMI, persistent=True)
    if was_created: lobby_service.update(lobby)
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
    # TODO: Remove duplication
    notes_classes = f"w-[{CARD_WIDTH}] h-[{CARD_HEIGHT}] absolute top-0 left-0 z-50 hidden p-3"

    def update(r, *_): return Notes(r, p, data, text_cls='flex-1 box-border',
                                        cls=notes_classes, _='on mouseleave add .hidden to me')(hx_swap_oob=f"innerHTML:[data-notes='{p.uid}']")
    await notify_all(lobby, update, but=p)


async def edit_label_text(sess, label: str, owner_uid: str):
    lobby = lobby_service.get_lobby(sess.get("lobby_id"))
    if not lobby or lobby.current_game != WHOAMI: return
    p = lobby.get_member(sess.get('uid'))
    owner = lobby.get_member(owner_uid)
    if not (owner and p and p.is_player) or p == owner: return
    lobby.state.player(owner.uid).set_label(label)
    lobby_service.update(lobby)
    def update(*_): return dict(type='label_text', owner_uid=owner.uid, label=label)
    await notify_all(lobby, update, but=[owner, p], json=True)
    def update(r, *_): return PlayerLabelText(r, r, lobby.state.player(r.uid))[1](hx_swap_oob=f"innerHTML:[data-label-text='{owner.uid}']")
    await notify(owner, update, owner)


async def edit_label_position(sess, owner_uid: str, **kwargs):
    lobby = lobby_service.get_lobby(sess.get("lobby_id"))
    if not lobby or lobby.current_game != WHOAMI: return
    p = lobby.get_member(sess.get('uid'))
    owner = lobby.get_member(owner_uid)
    if not (p and owner): return
    lobby.state.player(owner.uid).set_label_transform(kwargs)
    lobby_service.update(lobby)
    def update(*_): return dict(type='label_position', owner_uid=owner.uid, **kwargs)
    await notify_all(lobby, update, json=True, but=p)


@ws_rt.ws('/whoami', conn=ws_fn(), disconn=ws_fn(False))
async def ws(sess, data):
    try:
        msg_type = data.pop('type')
        if msg_type == 'label_text': await edit_label_text(sess, **data)
        elif msg_type == 'label_position': await edit_label_position(sess, **data)
    except Exception as e: logger.error(e)

ws_url = ws_rt.wss[-1][1] # latest added websocket url

register_page('Who Am I', '/whoami')