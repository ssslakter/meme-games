from .utils import *
import urllib
from meme_games.core import *
from meme_games.domain import *
from meme_games.apps.user import *
from .general import *


__all__ = ['Settings', 'SettingsPopover',
           'lock_lobby', 'change_background', 'switch_game', 'SwitchGame', 'GoTo']


rt = APIRouter()
register_route(rt)

lobby_service = DI.get(LobbyService)


def Setting(icon: str, title: str = None, hx_swap='none', cls=('uk-btn cursor-pointer', ButtonT.default), **kwargs):
    return DivLAligned(
        UkIcon(icon, cls="text-3xl"),
        P(title, cls="text-lg pl-2"),
        cls=cls,
        hx_swap=hx_swap,
        **kwargs
    )


def LockLobby(l: Lobby, cls=('uk-btn cursor-pointer', ButtonT.default)): 
    args = ('lock-open', 'Lock lobby') if not l.locked else ('lock', 'Unlock lobby')
    return Setting(*args, hx_post=lock_lobby, cls=cls)(hx_swap_oob='outerHTML', id='lock-lobby')

def SetBackground():
    return Setting('image', title='Background', hx_post=change_background, hx_prompt='Enter the URL of the background image')

def LeaveLobby():
    return Setting('log-out', title='Leave Lobby', hx_post=leave_lobby, hx_swap="none")


def GoTo(url: str):
    '''Sends a websocket-connected member to `url` - used when the host changes the game.'''
    return Div(hx_swap_oob="beforeend:body", _=f'init go to url "{url}"')


def SwitchGame(lobby: Lobby):
    '''Host-only: moves the whole lobby to another game, keeping everyone in it.'''
    others = [(game, name) for game, (name, _) in GAME_PAGES.items() if game != lobby.current_game]
    if not others: return None
    return Div(
        DivLAligned(UkIcon('gamepad-2', cls="text-3xl"), P('Switch game', cls="text-lg pl-2"), cls='py-2'),
        DivHStacked(*[Button(name, cls=ButtonT.default, hx_post=switch_game.to(game=game), hx_swap='none')
                      for game, name in others], cls='gap-1 flex flex-wrap'),
        cls='w-full')


def Settings(*lobby_settings, lobby: Lobby = None, member: LobbyMember = None):
    def ico(txt): return UkIcon(txt, width=25, height=25)
    lobby_settings = tuple(lobby_settings or ())
    if lobby and is_host(member): lobby_settings += (SwitchGame(lobby),)
    card_header_content = DivLAligned(
        ico('cog'),
        H4('Settings', cls="text-xl font-bold ml-2")
    )

    lobby_actions = [
        SetBackground(),
        LeaveLobby(),
    ]
    container = lambda o, x: Div(o, DivHStacked(*x,cls='gap-1 flex flex-wrap'))
    head = lambda i, txt: DivLAligned(ico(i), H5(txt), cls='space-x-4 py-2')
    
    return Card(
        Div(
            container(head('layout-dashboard', "Lobby settings"), lobby_settings) if any(lobby_settings) else None,
            container(head('settings', "Lobby actions"), lobby_actions),
            cls='flex flex-col items-right space-y-4'),
        header=card_header_content,
        cls='mg-lobby-settings space-y-2', data_ui='lobby-settings',
    )



def SettingsPopover(*lobby_settings, lobby: Lobby = None, member: LobbyMember = None):
    button = Card(
        UkIcon('cog', width=45, height=45),
        # TODO on mobile the focus is still on the button, not the card
        _ = "on mouseenter trigger mouseenter on #settings-panel-wrapper",
        cls="cursor-pointer rounded-full focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500",
        tabindex="0",
        id="settings-popover-button"
    )

    settings_card = Settings(*lobby_settings, lobby=lobby, member=member)
    panel_wrapper = Div(
        settings_card,
        cls="absolute bottom-0 right-0 w-[28rem] z-10 opacity-0 scale-75 pointer-events-none transition-all duration-200 ease-out",
        _ = """on mouseenter or focus
        remove .opacity-0 .scale-75 .pointer-events-none
        add .opacity-100 .scale-100 .pointer-events-auto
        settle
      on mouseleave or blur
        remove .opacity-100 .scale-100 .pointer-events-auto
        add .opacity-0 .scale-75 .pointer-events-none
        settle""",
        id="settings-panel-wrapper"
    )

    return Div(
        button,
        panel_wrapper,
        cls="mg-settings-popover fixed bottom-0 right-0 p-4 z-50 sm:block hidden",
        data_ui='settings-popover'
    )


#-----------------------------------#
#------------- Routes --------------#
#-----------------------------------#

@rt('/switch_game', methods=['post'])
async def switch_game(req: Request, game: str):
    lobby, _, p = lobby_state(req)
    if not is_host(p): return add_toast(req.session, "Only the host can switch the game", "error")
    url = game_url(game, lobby.id)
    if not url: return add_toast(req.session, "Unknown game", "error")
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


@rt('/background', methods=['post'])
async def change_background(req: Request, hdrs: HtmxHeaders):
    lobby: Lobby = req.state.lobby
    lobby.background_url = urllib.parse.unquote(hdrs.prompt)
    lobby_service.update(lobby)
    def update(*_): return Background(lobby.background_url, no_image=not lobby.background_url)
    return await notify_all(lobby, update)

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
