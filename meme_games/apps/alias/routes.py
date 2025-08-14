from ..shared.utils import register_route
from ..shared.spectators import SpectatorsList 
from ..shared.ws_route import ws_fn 
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
user_manager = DI.get(UserManager)


def pre_init(req: Request) -> tuple[Lobby, GameState, AliasPlayer]:
    try:
        lobby: AliasLobby = req.state.lobby
    except AttributeError as e:
        logger.error(f"Lobby not found in request state: {req.state}")
        raise HTTPException(status_code=400, detail="Incorrect client state. Please refresh the page.")
    return lobby, lobby.game_state, lobby.get_member(req.state.user.uid)


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
    lobby.game_state.config.wordpack = pack
    await notify_all(lobby, lambda r, *_: Game(r, lobby.game_state, hx_swap_oob='true'))

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
    game_state.remove_player(p)
    team.append(p); p.play()
    lobby_service.update(lobby)
    def update(r: AliasPlayer, lobby: AliasLobby):
        res = (Div(hx_swap_oob=f"delete:#spectators [data-username='{p.uid}']"),
               Game(r, lobby.game_state, hx_swap_oob='true'))
        return res
    await notify_all(lobby, update)


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
    lobby, was_created = lobby_service.get_or_create(u, lobby_id, AliasLobby, persistent=False)
    lobby.set_default_game_state(GameState())
    if was_created: lobby_service.update(lobby)
    m = lobby.get_member(u.uid)
    req.session['lobby_id'] = lobby.id
    return Page(m or u, lobby)

def redirect(lobby_id: str): return Redirect(index.to(lobby_id=lobby_id))


@rt
async def start_game(req: Request):
    lobby, game, _ = pre_init(req)
    if not game.can_start():
        return add_toast(req.session, "Cannot start game", "error")
    game.start_game()
    lobby.lock()
    await notify_all(lobby, lambda r, *_: Game(r, game, hx_swap_oob='true'))

async def set_end_round_timer(lobby: AliasLobby):
    game_state: GameState = lobby.game_state
    await game_state.timer.sleep()
    def update(r: AliasPlayer, *_):
        return Game(r, game_state, hx_swap_oob='true')
    await notify_all(lobby, update)


@rt
async def vote(req: Request, voted: bool):
    lobby, game_state, p = pre_init(req)
    if not (p in game_state.active_team and
        game_state.state in [gm.StateMachine.VOTING_TO_START, 
                             gm.StateMachine.REVIEWING]):
        raise HTTPException(400, 'cannot vote now')
    if p.voted == voted: return VoteButton(p, game_state)
    if voted: game_state.add_vote(p)
    else: game_state.retract_vote(p)
    if game_state.state == gm.StateMachine.REVIEWING and game_state.check_all_voted(): 
        game_state.next_state()
        await notify_all(lobby, lambda r, *_: Game(r, game_state, hx_swap_oob='true'))

    await notify_all(lobby, lambda r, *_: (TeamCard(r, game_state.active_team, game_state), GameControls(r, game_state)))


@rt
async def start_round(req: Request):
    lobby, game_state, p = pre_init(req)
    if not (p == game_state.active_player and game_state.state == gm.StateMachine.VOTING_TO_START):
        raise HTTPException(400, 'cannot vote now')
    game_state.next_state()
    def update(r: AliasPlayer, *_):
        return Game(r, game_state, hx_swap_oob='true')
    await notify_all(lobby, update)
    asyncio.create_task(set_end_round_timer(lobby))



@rt
async def guess(req: Request, correct: bool):
    lobby, game_state, p = pre_init(req)
    if not (p==game_state.active_player and
            game_state.state == gm.StateMachine.ROUND_PLAYING):
        return add_toast(req.session, "Cannot guess now", "error")
    game_state.guess_word(p, correct)
    if game_state.timer.finished:
        game_state.next_state()
        return await notify_all(lobby, lambda r, *_: Game(r, game_state, hx_swap_oob='true'))
    def update(r: AliasPlayer, *_):
        return RoundLog(game_state.guess_log, game_state)
    await notify_all(lobby, update)
    return CurrentWord(game_state)


@rt
async def change_guess_points(req: Request, guess_id: str, delta: int):
    _, game_state, p = pre_init(req)
    if not is_player(p): return add_toast(req.session, "You cannot change score", "error")
    entry = game_state.change_guess_points(guess_id, delta)
    if not entry: return add_toast(req.session, "Guess not found", "error")
    def update(r: AliasPlayer, *_):
        return WordEntryScore(entry), TeamCard(r, game_state.active_team, game_state)
    await notify_all(req.state.lobby, update)


def upd(r, lobby, conn_member):
    if r == conn_member: return Game(r, lobby), SpectatorsList(r, lobby), MemberName(r, conn_member)
    return SpectatorsList(r, lobby), MemberName(r, conn_member)


@ws_rt.ws('/alias', conn=ws_fn(render_fn=upd), disconn=ws_fn(False, upd))
async def ws(): pass

ws_url = ws_rt.wss[-1][1] # latest added websocket url

register_page('Alias', '/alias')


#---------------------------------#
#------------ REST API -----------#
#---------------------------------#

rt = APIRouter('/alias/api')

@rt.get('/teams')
def get_teams(req: Request):
    lobby: AliasLobby = req.state.lobby
    return {'team_ids':[t.id for t in lobby.game_state.teams.values()]}

register_route(rt)