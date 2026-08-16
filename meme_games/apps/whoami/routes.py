from ..shared.spectators import register_game_view, notify_roster_changed
from ..shared.ws_route import lobby_ws
from ..shared.utils import register_route, lobby_state
from meme_games.core import *
from meme_games.domain import *
from ..shared import *
from .domain import *
from .actions import *
from .components import *

#---------------------------------#
#------------- Routes ------------#
#---------------------------------#

rt = APIRouter('/whoami')
register_route(rt)
logger = logging.getLogger(__name__)

lobby_service = DI.get(LobbyService)


def rejected(req, error): return add_toast(req.session, str(error), 'error')


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
    if lobby.locked: return add_toast(req.session, "Game is locked", "error")
    p.play()
    lobby_service.update(lobby)
    # the board re-render below removes the card this request targeted, so the notes
    # have to travel with it - an http response swapped into a gone target is dropped
    await notify_roster_changed(lobby)


def WhoAmIView(reciever, lobby: Lobby, **kwargs):
    '''The board and the receiver's own notes: joining or leaving changes both.'''
    return Game(reciever, lobby, **kwargs), NotesBlock(reciever, lobby)


register_game_view(WHOAMI, WhoAmIView)

@rt
async def notes(req: Request, text: str):
    lobby, _, p = lobby_state(req, WHOAMI)
    try: await whoami_actions.write_note(lobby, p, text)
    except ActionRejected as error: return rejected(req, error)


@rt
async def update_topic(req: Request, topic: str):
    lobby, _, member = lobby_state(req, WHOAMI)
    try: await whoami_actions.set_topic(lobby, member, topic)
    except ActionRejected as error: return rejected(req, error)


@rt
async def start_game(req: Request):
    lobby, _, member = lobby_state(req, WHOAMI)
    try: await whoami_actions.start(lobby, member)
    except ActionRejected as error: return rejected(req, error)


@rt
async def restart_game(req: Request):
    lobby, _, member = lobby_state(req, WHOAMI)
    try: await whoami_actions.restart(lobby, member)
    except ActionRejected as error: return rejected(req, error)


@rt
async def ask_question(req: Request, text: str):
    lobby, _, member = lobby_state(req, WHOAMI)
    try: await whoami_actions.ask_question(lobby, member, text)
    except ActionRejected as error: return rejected(req, error)


@rt
async def answer_question(req: Request, answer: str):
    lobby, _, member = lobby_state(req, WHOAMI)
    try: await whoami_actions.answer_question(lobby, member, answer)
    except ActionRejected as error: return rejected(req, error)


@rt
async def set_guessed(req: Request, uid: str, guessed: bool = False):
    lobby, _, member = lobby_state(req, WHOAMI)
    try: await whoami_actions.set_guessed(lobby, member, uid, guessed)
    except ActionRejected as error: return rejected(req, error)


@rt
async def toggle_private_notes(req: Request):
    lobby, state, p = lobby_state(req, WHOAMI)
    if not is_host(p): return add_toast(req.session, "Only the host can change this", "error")
    state.config.private_notes = not state.config.private_notes
    lobby_service.update(lobby)
    await lobby_events.publish(lobby, 'game')


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
    if not lobby: return
    order = (lobby.state.turn_order if lobby.state.phase == WhoAmIPhase.PLAYING
             else whoami_actions.order(lobby))
    if lobby.state.next_player(p.uid, order) != owner.uid: return
    try: await whoami_actions.write_card(lobby, p, label)
    except ActionRejected: return


async def edit_label_position(sess, owner_uid: str, **kwargs):
    lobby, p, owner = _board_member(sess, owner_uid)
    if not lobby: return
    lobby.state.player(owner.uid).set_label_transform(kwargs)
    lobby_service.update(lobby)
    def update(*_): return dict(type='label_position', owner_uid=owner.uid, **kwargs)
    await notify_all(lobby, update, json=True, but=p)


async def on_message(sess, data):
    try:
        msg_type = data.pop('type')
        if msg_type == 'label_text': await edit_label_text(sess, **data)
        elif msg_type == 'label_position': await edit_label_position(sess, **data)
    except Exception as e: logger.error(e)


async def _render_whoami_event(event: LobbyChanged, lobby: Lobby):
    if event.game != WHOAMI: return
    topics = event.topics
    if 'game' in topics:
        return await notify_all(lobby, lambda r, *_: (
            *WhoAmIView(r, lobby, hx_swap_oob='true'),
            WhoAmISettings(r, lobby, hx_swap_oob='outerHTML') if is_host(r) else None))
    if 'topic' in topics:
        await notify_all(lobby, lambda *_: TopicBanner(lobby, hx_swap_oob='outerHTML'))
    if topics & {'turn', 'question'}:
        await notify_all(lobby, lambda r, *_: (
            TurnStatus(r, lobby, hx_swap_oob='outerHTML'), *QuestionUpdates(r, lobby)))
    for topic in topics:
        if topic.startswith('notes:'):
            uid = topic.partition(':')[2]
            owner = lobby.members.get(uid)
            if owner:
                def note_update(r, *_):
                    note = NotesCard(r, owner, lobby.state.player(uid), lobby.state)
                    return note(hx_swap_oob=f"outerHTML:[data-notes='{uid}']") if note else None
                await notify_all(lobby, note_update, but=owner)
        elif topic.startswith('card:'):
            uid = topic.partition(':')[2]
            owner = lobby.members.get(uid)
            if not owner: continue
            label = lobby.state.player(uid).label_text
            await notify_all(lobby, lambda *_: dict(type='label_text', owner_uid=uid, label=label), json=True)
            await notify_all(lobby, lambda r, *_: (
                PlayerLabelText(r, owner, lobby.state.player(uid), lobby)[1](
                    hx_swap_oob=f"innerHTML:[data-label-text='{uid}']") if r == owner else None,
                GameControl(lobby, hx_swap_oob='outerHTML') if is_host(r) else None))


lobby_events.subscribe(_render_whoami_event)

ws_url = lobby_ws('/whoami', on_message)

register_game_page(WHOAMI, 'Who Am I', lambda lobby_id: index.to(lobby_id=lobby_id))
