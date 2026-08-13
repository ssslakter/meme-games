from ..shared.utils import register_route, lobby_state
from ..shared.ws_route import lobby_ws 
from ..shared.spectators import notify_roster_changed
from meme_games.core import *
from meme_games.domain import *
from meme_games.apps.word_packs.components import *
from .components import *


#---------------------------------#
#------------- Routes ------------#
#---------------------------------#

rt = APIRouter('/alias')
register_route(rt)

logger = logging.getLogger(__name__)

lobby_service = DI.get(LobbyService)


def pre_init(req: Request) -> tuple[Lobby, GameState, LobbyMember]:
    return lobby_state(req, ALIAS)


def game_update(reciever: LobbyMember, lobby: Lobby):
    return Game(reciever, lobby, hx_swap_oob='true'), HostGameActions(reciever, lobby.state)


@rt 
def editor_readonly(req: Request, id:str):
    _,_, p = pre_init(req)
    pack = wordpack_manager.get_by_id(id)
    return WordPackEditor(pack, readonly=True,
                          form_kwargs=dict(hx_post=select_pack, hx_swap='none'),
                          submit_button=Button("Select wordpack" if is_host(p) else "Must be host to select", 
                                               disabled= not is_host(p)),
                          hx_on__after_request="UIkit.modal('#pack-select').hide()")

@rt
async def select_pack(req: Request, id: str):
    lobby, _, p = pre_init(req)
    if not is_host(p): return
    pack = wordpack_manager.get_by_id(id)
    if not pack: return add_toast(req.session, "Wordpack not found", "error")
    lobby.state.config.wordpack = pack
    await notify_all(lobby, lambda r, *_: game_update(r, lobby))

@rt
async def new_team(req: Request):
    lobby, game_state, p = pre_init(req)
    if any(p in t for t in game_state.teams.values()): return
    if lobby.locked: 
        add_toast(req.session, "Game is locked", "error")
        return
    team = game_state.create_team()
    await join_team(req, team.id)

@rt
async def join_team(req: Request, team_id: str):
    lobby, game_state, p = pre_init(req)  
    team = game_state.teams.get(team_id)
    if not team: return
    game_state.remove_player(p.uid)
    team.append(p); p.play()
    lobby_service.update(lobby)
    await notify_roster_changed(lobby)


@rt
async def update_settings(req: Request, config: gm.GameConfig):
    _, game_state, p = pre_init(req)  
    if game_state.state == gm.StateMachine.ROUND_PLAYING or not is_host(p):
        return add_toast(req.session, "Cannot change lobby settings", "error")
    game_state.config = config
    return add_toast(req.session, "Config updated", 'success')

@rt('/{lobby_id}', methods=['get'])
def index(req: Request, lobby_id: str = None):
    if not lobby_id: return redirect(random_id())
    u: User = req.state.user
    lobby, was_created = lobby_service.get_or_create(u, lobby_id, ALIAS, persistent=False)
    if was_created: lobby_service.update(lobby)
    m = lobby.get_member(u.uid)
    req.session['lobby_id'] = lobby.id
    return Page(m or u, lobby)

def redirect(lobby_id: str): return Redirect(index.to(lobby_id=lobby_id))


@rt
async def start_game(req: Request):
    lobby, game, p = pre_init(req)
    if not is_host(p) or not game.can_start():
        return add_toast(req.session, "Cannot start game", "error")
    game.start_game()
    lobby.lock()
    await notify_all(lobby, lambda r, *_: game_update(r, lobby))


@rt
async def pause_game(req: Request):
    lobby, game, p = pre_init(req)
    if not is_host(p) or game.state != gm.StateMachine.ROUND_PLAYING:
        return add_toast(req.session, 'Cannot pause now', 'error')
    game.timer.resume() if game.timer.paused else game.timer.pause()
    await notify_all(lobby, lambda r, *_: game_update(r, lobby))


@rt
async def restart_game(req: Request):
    lobby, game, p = pre_init(req)
    if not is_host(p): return add_toast(req.session, 'Only the host can restart', 'error')
    game.restart()
    lobby.unlock()
    await notify_all(lobby, lambda r, *_: game_update(r, lobby))


@rt
async def shuffle_teams(req: Request):
    lobby, game, p = pre_init(req)
    if not is_host(p) or game.state != gm.StateMachine.WAITING_FOR_PLAYERS:
        return add_toast(req.session, 'Teams can only be shuffled before the game', 'error')
    game.shuffle_teams()
    await notify_all(lobby, lambda r, *_: game_update(r, lobby))


@rt
async def random_wordpack(req: Request):
    lobby, game, p = pre_init(req)
    if not is_host(p) or game.state == gm.StateMachine.ROUND_PLAYING:
        return add_toast(req.session, 'Cannot change the wordpack now', 'error')
    packs = wordpack_manager.get_all()
    if not packs: return add_toast(req.session, 'No wordpacks available', 'error')
    game.config.wordpack = random.choice(packs)
    await notify_all(lobby, lambda r, *_: game_update(r, lobby))

async def set_end_round_timer(lobby: Lobby):
    game_state: GameState = lobby.state
    await game_state.timer.sleep()
    if lobby.current_game != ALIAS or lobby.state is not game_state: return
    def update(r: LobbyMember, *_):
        return game_update(r, lobby)
    await notify_all(lobby, update)


@rt
async def vote(req: Request, voted: bool):
    lobby, game_state, p = pre_init(req)
    if not (p in game_state.active_team and
        game_state.state in [gm.StateMachine.VOTING_TO_START, 
                             gm.StateMachine.REVIEWING]):
        raise HTTPException(400, 'cannot vote now')
    if game_state.has_voted(p) == voted: return VoteButton(p, game_state)
    if voted: game_state.add_vote(p)
    else: game_state.retract_vote(p)
    if game_state.state == gm.StateMachine.REVIEWING and game_state.check_all_voted(): 
        game_state.next_state()
        await notify_all(lobby, lambda r, *_: game_update(r, lobby))

    await notify_all(lobby, lambda r, *_: game_update(r, lobby))


@rt
async def start_round(req: Request):
    lobby, game_state, p = pre_init(req)
    if not (p == game_state.active_player and game_state.state == gm.StateMachine.VOTING_TO_START):
        raise HTTPException(400, 'cannot vote now')
    game_state.next_state()
    def update(r: LobbyMember, *_):
        return game_update(r, lobby)
    await notify_all(lobby, update)
    asyncio.create_task(set_end_round_timer(lobby))



@rt
async def guess(req: Request, correct: bool):
    lobby, game_state, p = pre_init(req)
    if not (p==game_state.active_player and not game_state.timer.paused and
            game_state.state == gm.StateMachine.ROUND_PLAYING):
        return add_toast(req.session, "Cannot guess now", "error")
    game_state.guess_word(p, correct)
    if game_state.timer.finished:
        game_state.next_state()
        return await notify_all(lobby, lambda r, *_: game_update(r, lobby))
    def update(r: LobbyMember, *_):
        return RoundLog(game_state.guess_log, game_state), GuessCount(game_state)
    await notify_all(lobby, update)
    return CurrentWord(game_state)


@rt
async def change_guess_points(req: Request, guess_id: str, delta: int):
    _, game_state, p = pre_init(req)
    if not is_player(p): return add_toast(req.session, "You cannot change score", "error")
    entry = game_state.change_guess_points(guess_id, delta)
    if not entry: return add_toast(req.session, "Guess not found", "error")
    def update(r: LobbyMember, *_):
        return WordEntryScore(entry), TeamCard(r, game_state.active_team, game_state)
    await notify_all(req.state.lobby, update)


ws_url = lobby_ws('/alias')

register_game_page(ALIAS, 'Alias', lambda lobby_id: index.to(lobby_id=lobby_id))


#---------------------------------#
#------------ REST API -----------#
#---------------------------------#

rt = APIRouter('/alias/api')

@rt.get('/teams')
def get_teams(req: Request):
    _, game_state, _ = lobby_state(req, ALIAS)
    return {'team_ids':[t.id for t in game_state.teams.values()]}

register_route(rt)
