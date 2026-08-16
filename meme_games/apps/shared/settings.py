from .utils import *
from meme_games.core import *
from meme_games.domain import *
from meme_games.apps.user import *
from .general import *
from .rules import game_rules


__all__ = ['Settings', 'SettingsPanel', 'LobbyTools', 'Section', 'GameRules',
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
    # MonsterUI's Input also carries `uk-input`, which sizes it like a text field and
    # squashes the box into a pill; CheckboxX is the plain `uk-checkbox` input.
    return Div(
        Div(
            CheckboxX(id='allow-agents-checkbox', checked=lobby.allow_agents,
                      cls='shrink-0', hx_post=toggle_agents, hx_trigger='change',
                      hx_target='#allow-agents', hx_swap='outerHTML'),
            FormLabel('Allow agents to join', fr='allow-agents-checkbox', cls='m-0 cursor-pointer'),
            cls='mg-settings-check flex items-center gap-2'),
        Script(f"localStorage.setItem('meme-games.allow-agents', '{str(lobby.allow_agents).lower()}')")
            if save_preference else None,
        id='allow-agents', data_ui='allow-agents')

def GoTo(url: str):
    '''Sends a websocket-connected member to `url` - used when the host changes the game.'''
    # htmx reads a selector-form OOB element as a template and inserts only its children,
    # so the childless carrier used to arrive as nothing at all and never navigated
    return Div(Div(_=f'init go to url "{url}"'), hx_swap_oob='beforeend:body')


def Section(title: str, *content, open=False, **kwargs):
    '''A collapsible group inside the settings panel.'''
    return Details(
        Summary(UkIcon('chevron-right', width=16, height=16, cls='mg-section-caret shrink-0'), title,
                cls='mg-settings-section-title'),
        Div(*content, cls='mg-settings-section-body'),
        open=open, cls='mg-settings-section-group', **kwargs)


def SwitchGame(lobby: Lobby):
    '''Host-only: moves the whole lobby to another game, keeping everyone in it.'''
    others = [(game, name) for game, (name, _) in GAME_PAGES.items() if game != lobby.current_game]
    if not others: return None
    return Section(
        'Switch game',
        Div(*[Button(name, cls=(ButtonT.default, 'w-full'),
                     hx_post=switch_game.to(game=game), hx_swap='none')
              for game, name in others], cls='grid grid-cols-2 gap-2'),
        data_ui='switch-game')


def Settings(*lobby_settings, lobby: Lobby = None, member: LobbyMember = None):
    lobby_settings = tuple(lobby_settings or ())
    if lobby and is_host(member): lobby_settings += (AllowAgents(lobby), SwitchGame(lobby))
    if not any(lobby_settings): return None
    return Div(*lobby_settings, cls='mg-lobby-settings', data_ui='lobby-settings')


def SettingsPanel(*lobby_settings, lobby: Lobby = None, member: LobbyMember = None):
    settings = Settings(*lobby_settings, lobby=lobby, member=member)
    if settings is None: return None
    return Details(
        Summary(UkIcon('cog', width=18, height=18, cls='shrink-0'), 'Game settings',
                cls='mg-settings-summary'),
        settings,
        open=True, cls='mg-settings-panel w-full rounded-lg border bg-card shadow-sm',
        data_ui='settings-panel')


def GameRules(lobby: Lobby):
    '''The rules of whatever the lobby is playing, the same text the agents are given.'''
    rules = game_rules(lobby.current_game)
    if not rules: return None
    return Div(
        Button(UkIcon('book-open', cls='mr-2', width=20, height=20), 'Rules',
               cls=(ButtonT.default, 'inline-flex w-full items-center justify-center whitespace-nowrap px-4 py-2'),
               data_uk_toggle='target: #game-rules'),
        Modal(Div(render_md(rules), cls='mg-rules-body'),
              header=ModalTitle('How to play'), id='game-rules', data_ui='game-rules'))


def LobbyTools(reciever: LobbyMember | User, lobby: Lobby, *lobby_settings,
               cls=()):
    from .spectators import Spectators
    from .chat import ChatPanel
    return GameRail(
        Div(
            SettingsPanel(*lobby_settings, lobby=lobby, member=reciever),
            GameRules(lobby),
            Button(UkIcon('log-out', cls='mr-2', width=20, height=20), 'Leave lobby',
                   cls=(ButtonT.destructive, 'inline-flex w-full items-center justify-center whitespace-nowrap px-4 py-2'),
                   hx_post=leave_lobby, hx_swap='none', data_ui='leave-lobby'),
            cls='w-full space-y-3'),
        Div(ChatPanel(reciever, lobby), Spectators(reciever, lobby),
            cls='mg-lobby-talk flex w-full min-h-0 flex-1 flex-col gap-3'),
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
    lobby: Lobby = req.state.lobby
    uid = req.state.user.uid
    if not lobby: return
    lobby.remove_member(uid)
    # a round cannot be finished a player short, so walking out ends it for everyone
    was_playing = lobby.reset_game()
    lobby_service.update(lobby)
    def update(*_): return UserRemover(uid)
    await notify_all(lobby, update)
    # always a roster event: someone leaving can hand the host seat to whoever is left,
    # and the controls that come with it have to appear without a reload
    await lobby_events.publish(lobby, *(('roster', 'game') if was_playing else ('roster',)))
    return Redirect('/')
