from meme_games.core import *
from meme_games.domain import *
from meme_games.apps.word_packs.domain import WordPackRepo
from meme_games.apps.shared import *
from meme_games.apps.shared.spectators import Spectators
from meme_games.apps.shared.ws_route import lobby_ws

from .domain import *
from .components import *


rt = APIRouter('/codenames')
register_route(rt)

lobby_service = DI.get(LobbyService)
wordpack_manager = DI.get(WordPackRepo)


def pre_init(req: Request): return lobby_state(req, CODENAMES)


def game_update(reciever: LobbyMember, lobby: Lobby):
    return (Spectators(reciever, lobby, hx_swap_oob='true'),
            Game(reciever, lobby, hx_swap_oob='true'),
            HostSettings(reciever, lobby.state))


async def update_all(lobby):
    await notify_all(lobby, lambda reciever, *_: game_update(reciever, lobby))


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
    lobby, state, member = pre_init(req)
    try: team = TeamColor(team)
    except ValueError: return add_toast(req.session, 'Unknown team', 'error')
    if lobby.locked or not state.join(member, team):
        return add_toast(req.session, 'Teams are locked', 'error')
    member.play()
    lobby_service.update(lobby)
    await update_all(lobby)


@rt
async def toggle_spymaster(req: Request):
    lobby, state, member = pre_init(req)
    if not state.toggle_spymaster(member):
        return add_toast(req.session, 'This team already has a spymaster', 'error')
    await update_all(lobby)


@rt
async def select_pack(req: Request, pack_id: str):
    lobby, state, member = pre_init(req)
    pack = wordpack_manager.get_by_id(pack_id)
    if not is_host(member) or state.phase != GamePhase.WAITING or not pack:
        return add_toast(req.session, 'Cannot select that wordpack', 'error')
    state.wordpack = pack
    await update_all(lobby)


@rt
async def start_game(req: Request):
    lobby, state, member = pre_init(req)
    if not is_host(member) or not state.start():
        return add_toast(req.session, 'Each team needs two players and a spymaster', 'error')
    lobby.lock()
    lobby_service.update(lobby)
    await update_all(lobby)


@rt
async def submit_clue(req: Request, clue: str, number: int):
    lobby, state, member = pre_init(req)
    if not state.give_clue(member, clue, number):
        return add_toast(req.session, 'Invalid clue', 'error')
    await update_all(lobby)


@rt
async def reveal_card(req: Request, card_id: str):
    lobby, state, member = pre_init(req)
    if not state.reveal(member, card_id):
        return add_toast(req.session, 'You cannot reveal that card', 'error')
    await update_all(lobby)


@rt
async def end_turn(req: Request):
    lobby, state, member = pre_init(req)
    if (state.phase != GamePhase.GUESSING or state.team_of(member) != state.turn or
            member.uid in state.spymasters or not state.end_turn()):
        return add_toast(req.session, 'You cannot end this turn', 'error')
    await update_all(lobby)


@rt
async def restart_game(req: Request):
    lobby, state, member = pre_init(req)
    if not is_host(member): return add_toast(req.session, 'Only the host can restart', 'error')
    state.restart()
    lobby.unlock()
    lobby_service.update(lobby)
    await update_all(lobby)


ws_url = lobby_ws('/codenames')
register_game_page(CODENAMES, 'Codenames', lambda lobby_id: index.to(lobby_id=lobby_id))
