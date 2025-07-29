from ..shared.utils import register_route
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



def ws_fn(connected=True, render_fn: Callable = JoinSpectators):
    '''Returns a function that will be called when a user joins the lobby websocket'''
    async def user_joined(sess, send, ws):
        u = user_manager.get_or_create(sess)
        lobby = lobby_service.get_lobby(sess.get('lobby_id'))
        if not lobby: return
        if m := lobby.get_member(u.uid):
            if connected: m.connect(send, ws)
            else: m.disconnect()

            def update(r, *_):
                hx=f"outerHTML:span[data-username='{u.uid}']"
                if r == u: return ActiveGameState(r, lobby), UserName(r.user, m.user, is_connected=connected, hx_swap_oob=hx)
                return UserName(r.user, m.user, is_connected=connected, hx_swap_oob=hx)
        else:
            if not connected: return  # user not found in the lobby and not connecting
            m = lobby.create_member(u, send=send, ws=ws)
            lobby_service.update(lobby)

            def update(r, *_):
                if r == u: return ActiveGameState(r, lobby), render_fn(r, m)
                return render_fn(r, m)
        await notify_all(lobby, update)

    return user_joined

@rt 
def editor_readonly(id:str):
    pack = wordpack_manager.get_by_id(id)
    return WordPackEditor(pack, readonly=True,
                          form_kwargs=dict(hx_post=select_pack, hx_swap='none'),
                          submit_button=Button("Select"),
                          hx_on__after_request="UIkit.modal('#pack-select').hide()")
    
@rt
async def select_pack(req: Request, id: str):
    lobby: AliasLobby = req.state.lobby
    p = lobby.get_member(req.state.user.uid)
    if not p.is_host: return
    pack = wordpack_manager.get_by_id(id)
    if not pack: return add_toast(req.session, "Wordpack not found", "error")
    lobby.game_state.config.wordpack = pack
    await notify_all(lobby, lambda r, *_: Game(r, lobby.game_state, hx_swap_oob='true'))

@rt
async def new_team(req: Request):
    lobby: AliasLobby = req.state.lobby
    game_state: GameState = lobby.game_state
    p = lobby.get_member(req.state.user.uid)
    if any(p in t for t in game_state.teams.values()): return
    if lobby.locked: 
        add_toast(req.session, "Game is locked", "error")
        return NewTeamCard()
    team = game_state.create_team()
    await join_team(req, team.id)

@rt
async def join_team(req: Request, team_id: str):
    lobby: AliasLobby = req.state.lobby
    game_state: GameState = lobby.game_state
    p = lobby.get_member(req.state.user.uid)
    team = game_state.teams.get(team_id)
    if not team: return
    lobby.game_state.remove_player(p)
    team.append(p); p.play()
    lobby_service.update(lobby)
    def update(r: AliasPlayer, lobby: AliasLobby):
        res = (Div(hx_swap_oob=f"delete:#spectators [data-username='{p.uid}']"),
               Game(r, lobby.game_state, hx_swap_oob='true'))
        return res
    await notify_all(lobby, update)


@rt
async def spectate(req: Request):
    lobby: AliasLobby = req.state.lobby
    p = lobby.get_member(req.state.user.uid)
    if not p.is_player: return
    if lobby.locked: return add_toast(req.session, "Game is locked", "error")
    p.spectate(); lobby.game_state.remove_player(p)
    lobby_service.update(lobby)

    def update(r: AliasPlayer, *_):
        return JoinSpectators(r, p), Game(r, lobby.game_state, hx_swap_oob='true')
    await notify_all(lobby, update)


@rt('/{lobby_id}', methods=['get'])
def index(req: Request, lobby_id: str = None):
    if not lobby_id: return redirect(random_id())
    u: User = req.state.user
    lobby, was_created = lobby_service.get_or_create(u, lobby_id, AliasLobby, persistent=False)
    lobby.set_default_game_state(GameState())
    if was_created: lobby_service.update(lobby)
    m = lobby.get_member(u.uid)
    print('set session to', lobby.id)
    req.session['lobby_id'] = lobby.id
    return (Title(f'Who Am I lobby: {lobby.id}'),
            Page(m or u, lobby))

def redirect(lobby_id: str): return Redirect(index.to(lobby_id=lobby_id))


@ws_rt.ws('/alias', conn=ws_fn(), disconn=ws_fn(connected=False))
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