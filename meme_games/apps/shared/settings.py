from .utils import *
from meme_games.core import *
from meme_games.domain import *
from meme_games.apps.user import *
from .general import *


__all__ = ['Settings', 'SettingsPanel', 'LobbyTools',
           'lock_lobby', 'toggle_agents', 'switch_game', 'SwitchGame', 'GoTo']


rt = APIRouter()
register_route(rt)

lobby_service = DI.get(LobbyService)


def Setting(icon: str, title: str = None, hx_swap='none',
            cls=('uk-btn cursor-pointer', ButtonT.default, 'w-full justify-start px-3 py-2'), **kwargs):
    return DivLAligned(
        UkIcon(icon, width=20, height=20),
        Span(title, cls="pl-2"),
        cls=cls,
        hx_swap=hx_swap,
        **kwargs
    )


def LockLobby(l: Lobby, cls=('uk-btn cursor-pointer', ButtonT.default, 'w-full justify-start px-3 py-2')):
    args = ('lock-open', 'Lock lobby') if not l.locked else ('lock', 'Unlock lobby')
    return Setting(*args, hx_post=lock_lobby, cls=cls)(hx_swap_oob='outerHTML', id='lock-lobby')


def AllowAgents(lobby: Lobby, save_preference=False):
    return Div(
        Div(
            Input(type='checkbox', id='allow-agents-checkbox', checked=lobby.allow_agents,
                  cls='uk-checkbox', hx_post=toggle_agents, hx_trigger='change',
                  hx_target='#allow-agents', hx_swap='outerHTML'),
            FormLabel('Allow agents to join', fr='allow-agents-checkbox', cls='m-0 cursor-pointer pl-2'),
            cls='flex items-center px-3 py-2'),
        Script(f"localStorage.setItem('meme-games.allow-agents', '{str(lobby.allow_agents).lower()}')")
            if save_preference else None,
        id='allow-agents', data_ui='allow-agents')

def GoTo(url: str):
    '''Sends a websocket-connected member to `url` - used when the host changes the game.'''
    return Div(hx_swap_oob="beforeend:body", _=f'init go to url "{url}"')


def SwitchGame(lobby: Lobby):
    '''Host-only: moves the whole lobby to another game, keeping everyone in it.'''
    others = [(game, name) for game, (name, _) in GAME_PAGES.items() if game != lobby.current_game]
    if not others: return None
    return Div(
        H6('Switch game', cls='font-semibold'),
        DivHStacked(*[Button(name, cls=ButtonT.default, hx_post=switch_game.to(game=game), hx_swap='none')
                      for game, name in others], cls='grid grid-cols-2 gap-2'),
        cls='w-full space-y-3 border-t pt-5', data_ui='switch-game')


def Settings(*lobby_settings, lobby: Lobby = None, member: LobbyMember = None):
    lobby_settings = tuple(lobby_settings or ())
    if lobby and is_host(member): lobby_settings += (AllowAgents(lobby), SwitchGame(lobby))
    if not any(lobby_settings): return None
    return Div(
        H5('Lobby', cls='mb-4'), Div(*lobby_settings, cls='space-y-6'),
        cls='mg-lobby-settings px-5 pb-5 pt-5', data_ui='lobby-settings')



def SettingsPanel(*lobby_settings, lobby: Lobby = None, member: LobbyMember = None):
    settings = Settings(*lobby_settings, lobby=lobby, member=member)
    if settings is None: return None
    return Details(
        Summary(UkIcon('cog', cls='mr-2', width=20, height=20), 'Game settings',
                cls='cursor-pointer list-none px-4 py-3 font-semibold'),
        settings,
        open=True, cls='mg-settings-panel w-full rounded-lg border bg-card shadow-sm',
        data_ui='settings-panel')


def LobbyTools(reciever: LobbyMember | User, lobby: Lobby, *lobby_settings,
               cls=()):
    from .spectators import Spectators
    return GameRail(
        Div(
            SettingsPanel(*lobby_settings, lobby=lobby, member=reciever),
            Button(UkIcon('log-out', cls='mr-2', width=20, height=20), 'Leave lobby',
                   cls=(ButtonT.destructive, 'inline-flex w-full items-center justify-center whitespace-nowrap px-4 py-2'),
                   hx_post=leave_lobby, hx_swap='none', data_ui='leave-lobby'),
            cls='w-full space-y-3'),
        Spectators(reciever, lobby),
        cls=('mg-lobby-tools justify-between', cls),
        data_ui='lobby-tools')


#-----------------------------------#
#------------- Routes --------------#
#-----------------------------------#

@rt('/switch_game', methods=['post'])
async def switch_game(req: Request, game: str):
    lobby, _, p = lobby_state(req)
    if not is_host(p): return add_toast(req.session, "Only the host can switch the game", "error")
    url = game_url(game, lobby.id)
    if not url: return add_toast(req.session, "Unknown game", "error")
    if timer := getattr(lobby.state, 'timer', None): timer.stop()
    for member in lobby.members.values(): member.spectate()
    lobby.unlock()
    lobby.play_game(game)
    lobby_service.update(lobby)
    # everyone in the lobby follows the host into the new game
    def update(*_): return GoTo(url)
    await notify_all(lobby, update, but=p)
    return Redirect(url)


@rt('/lock', methods=['post'])
async def lock_lobby(req: Request):
    lobby: Lobby = req.state.lobby
    p = lobby.get_member(req.state.user.uid)
    if not is_host(p): return
    if lobby.locked: lobby.unlock()
    else: lobby.lock()
    lobby_service.update(lobby)
    def update(*_): return LockLobby(lobby)
    return await notify(p, update)


@rt('/agents', methods=['post'])
async def toggle_agents(req: Request):
    lobby: Lobby = req.state.lobby
    member = lobby.get_member(req.state.user.uid)
    if not is_host(member): return
    lobby.allow_agents = not lobby.allow_agents
    lobby_service.update(lobby)
    return AllowAgents(lobby, save_preference=True)


@rt
async def leave_lobby(req: Request):
    lobby: BasicLobby = req.state.lobby
    uid = req.state.user.uid
    if not lobby: return
    if lobby.locked: 
        return add_toast(req.session, "Can't leave while lobby is locked", "error")
    lobby.remove_member(uid)
    def update(*_): return UserRemover(uid)
    asyncio.create_task(notify_all(lobby, update))
    return Redirect('/')
