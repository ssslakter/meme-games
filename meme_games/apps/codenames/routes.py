from meme_games.core import *
from meme_games.domain import *
from meme_games.apps.word_packs.domain import WordPackRepo
from meme_games.apps.shared import *
from meme_games.apps.shared.spectators import Spectators
from meme_games.apps.shared.ws_route import lobby_ws

from .domain import *
from .actions import *
from .components import *


rt = APIRouter('/codenames')
register_route(rt)

lobby_service = DI.get(LobbyService)
wordpack_manager = DI.get(WordPackRepo)


def pre_init(req: Request): return lobby_state(req, CODENAMES)


def game_update(reciever: LobbyMember, lobby: Lobby):
    return (Spectators(reciever, lobby, hx_swap_oob='true'),
            Game(reciever, lobby, hx_swap_oob='true'),
            HostSettings(reciever, lobby))


async def update_all(lobby):
    await notify_all(lobby, lambda reciever, *_: game_update(reciever, lobby))


async def _render_game_event(event: LobbyChanged, lobby: Lobby):
    if event.game == CODENAMES and event.topics & {'game', 'settings'}:
        await update_all(lobby)


lobby_events.subscribe(_render_game_event)


def rejected(req, error): return add_toast(req.session, str(error), 'error')


@rt('/{lobby_id}', methods=['get'])
def index(req: Request, lobby_id: str = None):
    if not lobby_id: return redirect(random_id())
    user: User = req.state.user
    lobby, was_created = lobby_service.get_or_create(user, lobby_id, CODENAMES)
    # Switching games deliberately returns everyone to spectator mode. Drop any
    # Codenames seat left in the in-memory state when a lobby comes back later.
    for uid in list(lobby.state.players):
        if uid not in lobby.members or not lobby.members[uid].is_player:
            lobby.state.remove_player(uid)
    if was_created: lobby_service.update(lobby)
    req.session['lobby_id'] = lobby.id
    return Page(lobby.get_member(user.uid) or user, lobby)


def redirect(lobby_id: str): return Redirect(index.to(lobby_id=lobby_id))


@rt
async def join_team(req: Request, team: str):
    lobby, _, member = pre_init(req)
    try: await codenames_actions.join_team(lobby, member, team)
    except ActionRejected as error: return rejected(req, error)


@rt
async def toggle_spymaster(req: Request):
    lobby, state, member = pre_init(req)
    role = 'operative' if member.uid in state.spymasters else 'spymaster'
    try: await codenames_actions.set_role(lobby, member, role)
    except ActionRejected as error: return rejected(req, error)


@rt
async def select_pack(req: Request, pack_id: str):
    lobby, _, member = pre_init(req)
    try: await codenames_actions.select_pack(lobby, member, pack_id)
    except ActionRejected as error: return rejected(req, error)


@rt
async def start_game(req: Request):
    lobby, _, member = pre_init(req)
    try: await codenames_actions.start(lobby, member)
    except ActionRejected: return add_toast(req.session, 'Each team needs two players and a spymaster', 'error')


@rt
async def submit_clue(req: Request, clue: str, number: int):
    lobby, _, member = pre_init(req)
    try: await codenames_actions.give_clue(lobby, member, clue, number)
    except ActionRejected as error: return rejected(req, error)


@rt
async def reveal_card(req: Request, card_id: str):
    lobby, _, member = pre_init(req)
    try: await codenames_actions.reveal_card(lobby, member, card_id)
    except ActionRejected as error: return rejected(req, error)


@rt
async def end_turn(req: Request):
    lobby, _, member = pre_init(req)
    try: await codenames_actions.end_turn(lobby, member)
    except ActionRejected as error: return rejected(req, error)


@rt
async def restart_game(req: Request):
    lobby, _, member = pre_init(req)
    try: await codenames_actions.restart(lobby, member)
    except ActionRejected as error: return rejected(req, error)


@rt
async def create_agent_invite(req: Request, name: str):
    lobby, _, member = pre_init(req)
    if not is_host(member): return add_toast(req.session, 'Only the host can invite agents', 'error')
    try: _, token = DI.get(AgentAccessService).create(lobby.id, name)
    except ValueError as error: return rejected(req, error)
    await lobby_events.publish(lobby, 'settings')
    return InviteToken(token)


@rt
async def revoke_agent(req: Request, access_id: str):
    lobby, _, member = pre_init(req)
    if not is_host(member): return add_toast(req.session, 'Only the host can revoke agents', 'error')
    access = DI.get(AgentAccessService).revoke(access_id, lobby.id)
    if not access: return add_toast(req.session, 'Agent invite not found', 'error')
    had_member = lobby.get_member(access.user_uid) is not None
    if had_member: lobby.remove_member(access.user_uid)
    lobby_service.update(lobby)
    await lobby_events.publish(lobby, 'roster' if had_member else 'settings')


ws_url = lobby_ws('/codenames')
register_game_page(CODENAMES, 'Codenames', lambda lobby_id: index.to(lobby_id=lobby_id))
