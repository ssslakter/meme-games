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
    return (Game(reciever, lobby, hx_swap_oob='true'), HostGameActions(reciever, lobby.state),
            PackSelectButton(lobby.state, oob=True))


async def broadcast(lobby: Lobby):
    await notify_all(lobby, lambda r, *_: game_update(r, lobby))


def still_running(lobby: Lobby, game_state: GameState, state: gm.StateMachine) -> bool:
    '''A background timer outlives restarts and game switches; it may only act on the game that started it.'''
    return lobby.current_game == ALIAS and lobby.state is game_state and game_state.state == state


@rt
def editor_readonly(req: Request, id:str):
    _, game, p = pre_init(req)
    return SelectEditor(p, wordpack_manager.get_by_id(id), game)

@rt
def pack_select(req: Request) -> FT:
    _, game_state, player = pre_init(req)
    return PackSelectContents(player, game_state)

@rt
async def select_pack(req: Request, id: str):
    lobby, game, p = pre_init(req)
    if not is_host(p) or not game.can_change_wordpack():
        return add_toast(req.session, 'Cannot select a wordpack now', 'error')
    pack = wordpack_manager.get_by_id(id)
    if not pack: return add_toast(req.session, "Wordpack not found", "error")
    lobby.state.config.wordpack = pack
    await broadcast(lobby)

@rt
async def new_team(req: Request):
    lobby, game_state, p = pre_init(req)
    if game_state.team_by_player(p): return
    if lobby.locked or not game_state.can_add_team():
        return add_toast(req.session, "Cannot create a team now", "error")
    team = game_state.create_team()
    await join_team(req, team.id)

@rt
async def join_team(req: Request, team_id: str):
    lobby, game_state, p = pre_init(req)
    if lobby.locked or game_state.state != gm.StateMachine.WAITING_FOR_PLAYERS:
        return add_toast(req.session, "Game is locked", "error")
    team = game_state.teams.get(team_id)
    if not team: return
    game_state.remove_player(p.uid)
    team.append(p); p.play()
    lobby_service.update(lobby)
    await notify_roster_changed(lobby)


@rt
async def update_settings(req: Request, config: gm.GameConfig):
    lobby, game_state, p = pre_init(req)
    if game_state.state == gm.StateMachine.ROUND_PLAYING or not is_host(p):
        return add_toast(req.session, "Cannot change lobby settings", "error")
    game_state.change_config(config)
    def update(r: LobbyMember, *_: Any) -> tuple[Any, FT]:
        toast = Div(AppToast('Config updated', 'success'),
                    hx_swap_oob='beforeend:#mg-toast-container')
        # the picker stays mounted while the modal is open, so a checkbox change has to
        # replace it too; `shown` only reloads the next time the modal opens
        picker = Div(PackSelectContents(r, game_state), hx_swap_oob='innerHTML:#pack-select-content')
        return game_update(r, lobby), toast, picker, ConfigLobby(r, game_state, oob=True)
    await notify_all(lobby, update, but=p)
    return update(p)

@rt('/{lobby_id}', methods=['get'])
def index(req: Request, lobby_id: str = None):
    if not lobby_id: return fresh_lobby_redirect(index.to(lobby_id=random_id()), req)
    u: User = req.state.user
    lobby, was_created = lobby_service.get_or_create(
        u, lobby_id, ALIAS, persistent=False, **new_lobby_options(req))
    if was_created:
        lobby_service.update(lobby)
        if 'allow_agents' in req.query_params: return Redirect(index.to(lobby_id=lobby.id))
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
    await broadcast(lobby)
    if game.state == gm.StateMachine.COLLECTING_WORDS:
        asyncio.create_task(set_end_word_collection_timer(lobby))


@rt
async def pause_game(req: Request):
    lobby, game, p = pre_init(req)
    if not is_host(p) or not game.can_pause():
        return add_toast(req.session, 'Cannot pause now', 'error')
    game.timer.resume() if game.timer.paused else game.timer.pause()
    await broadcast(lobby)


@rt
async def restart_game(req: Request):
    lobby, game, p = pre_init(req)
    if not is_host(p): return add_toast(req.session, 'Only the host can restart', 'error')
    game.restart()
    lobby.unlock()
    await broadcast(lobby)


@rt
async def shuffle_teams(req: Request):
    lobby, game, p = pre_init(req)
    if not is_host(p) or game.state != gm.StateMachine.WAITING_FOR_PLAYERS:
        return add_toast(req.session, 'Teams can only be shuffled before the game', 'error')
    game.shuffle_teams()
    await broadcast(lobby)


@rt
async def random_wordpack(req: Request):
    lobby, game, p = pre_init(req)
    if not is_host(p) or not game.can_change_wordpack():
        return add_toast(req.session, 'Cannot change the wordpack now', 'error')
    packs = wordpack_manager.get_all()
    if not packs: return add_toast(req.session, 'No wordpacks available', 'error')
    game.config.wordpack = random.choice(packs)
    await broadcast(lobby)

async def set_end_round_timer(lobby: Lobby):
    game_state: GameState = lobby.state
    await game_state.timer.sleep()
    if not still_running(lobby, game_state, gm.StateMachine.ROUND_PLAYING): return
    game_state.end_round_on_timeout()
    await broadcast(lobby)


async def set_end_word_collection_timer(lobby: Lobby):
    game_state: GameState = lobby.state
    collecting = gm.StateMachine.COLLECTING_WORDS
    await game_state.timer.sleep()
    if not (still_running(lobby, game_state, collecting) and game_state.timer.finished): return
    # browsers submit their drafts when their own timer fires; give them a moment to arrive
    for _ in range(20):
        if game_state.all_words_submitted(): break
        await asyncio.sleep(0.25)
        if not still_running(lobby, game_state, collecting): return
    if not game_state.finish_word_collection():
        game_state.restart()
        lobby.unlock()
    await broadcast(lobby)


@rt
async def vote(req: Request, voted: bool) -> Any:
    lobby, game_state, p = pre_init(req)
    between_rounds = game_state.state == gm.StateMachine.BETWEEN_WORD_ROUNDS
    if not ((between_rounds and game_state.team_by_player(p)) or
            (p in game_state.active_team and game_state.state in [gm.StateMachine.VOTING_TO_START,
                                                                   gm.StateMachine.REVIEWING])):
        return add_toast(req.session, 'Cannot vote now', 'error')
    if game_state.has_voted(p) == voted: return VoteButton(p, game_state)
    if voted: game_state.add_vote(p)
    else: game_state.retract_vote(p)
    if game_state.state == gm.StateMachine.REVIEWING and game_state.all_voted(game_state.active_team):
        game_state.next_state(reset_votes=False)
    elif between_rounds and game_state.all_players_voted():
        game_state.next_state()
        asyncio.create_task(set_end_round_timer(lobby))

    await broadcast(lobby)


@rt
async def start_round(req: Request):
    lobby, game_state, p = pre_init(req)
    if not (p == game_state.active_player and game_state.state == gm.StateMachine.VOTING_TO_START and
            game_state.all_voted(game_state.active_team)):
        return add_toast(req.session, 'Cannot start the round now', 'error')
    game_state.next_state()
    await broadcast(lobby)
    asyncio.create_task(set_end_round_timer(lobby))



@rt
async def guess(req: Request, correct: bool):
    lobby, game_state, p = pre_init(req)
    if not game_state.can_guess(p, correct): return add_toast(req.session, "Cannot guess now", "error")
    if game_state.end_round_on_timeout(): return await broadcast(lobby)
    pool_finished = game_state.guess_word(p, correct)
    if game_state.timer.finished or pool_finished:
        game_state.next_state()
        return await broadcast(lobby)
    def update(r: LobbyMember, *_):
        return RoundLog(r, game_state), GuessCount(r, game_state)
    await notify_all(lobby, update)
    return CurrentWord(game_state)


@rt
async def submit_words(req: Request, words: str = '', finalized: bool = False) -> Any:
    lobby, game_state, p = pre_init(req)
    if game_state.state != gm.StateMachine.COLLECTING_WORDS or not is_player(p):
        return add_toast(req.session, 'Cannot add words now', 'error')
    game_state.submit_words(p, words, finalized)
    return WordCollectionPanel(p, game_state) if finalized else WordCollectionStatus(p, game_state)


@rt
async def change_guess_points(req: Request, guess_id: str, delta: int):
    lobby, game_state, p = pre_init(req)
    if not is_player(p): return add_toast(req.session, "You cannot change score", "error")
    entry = game_state.change_guess_points(guess_id, delta)
    if not entry: return add_toast(req.session, "Guess not found", "error")
    def update(r: LobbyMember, *_):
        visible = entry in visible_round_guesses(r, game_state)
        return WordEntryScore(entry) if visible else None, TeamCard(r, game_state.review_team, game_state)
    await notify_all(lobby, update)


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
