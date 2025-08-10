from .utils import register_route
import urllib
from meme_games.core import *
from meme_games.domain import *
from meme_games.apps.user import *
from .general import *


__all__ = ['Settings', 'Avatar', 'SettingsPopover', 'edit_avatar', 'edit_name', 'reset_avatar', 'lock_lobby', 'change_background']


rt = APIRouter()
register_route(rt)

lobby_service = DI.get(LobbyService)
user_manager = DI.get(UserManager)


def Setting(icon: str, title: str = None, hx_swap='none', **kwargs):
    return DivLAligned(
        UkIcon(icon, cls="text-3xl"),
        P(title, cls="text-lg pl-2"),
        cls=('uk-btn cursor-pointer', ButtonT.default),
        hx_swap=hx_swap,
        **kwargs
    )


def NameSetting(): return Setting('pencil', title='Edit name', hx_put=edit_name, hx_prompt='Enter your name')

def AvatarRemoval(): return Setting('trash', title='Remove avatar', hx_delete=reset_avatar,
                                    hx_confirm="Confirm that you want to remove your avatar?")

def AvatarSet(): 
    return (Setting('user', title="Edit avatar",  _="on click set x to next <form input/> then x.click()"),
            Form(Input(type="file", name="file", accept="image/*"),
                style="display: none;",
                hx_trigger="change",
                hx_post=edit_avatar,
                hx_swap="none"))

def LockLobby(l: Lobby): 
    args = ('lock-open', 'Lock lobby') if not l.locked else ('lock', 'Unlock lobby')
    return Setting(*args, hx_post=lock_lobby, hx_swap=None)(hx_swap_oob='outerHTML', id='lock-lobby')

def SetBackground():
    return Setting('image', title='Background', hx_post=change_background, hx_prompt='Enter the URL of the background image')

def LeaveLobby():
    return Setting('log-out', title='Leave Lobby', hx_post=leave_lobby, hx_target="body", hx_swap="outerHTML")


def Settings(*lobby_settings):
    def ico(txt): return UkIcon(txt, width=25, height=25)
    lobby_settings = lobby_settings or ()
    card_header_content = DivLAligned(
        ico('cog'),
        H4('Settings', cls="text-xl font-bold ml-2")
    )

    user_settings = [
        NameSetting(),
        AvatarSet(),
        AvatarRemoval(),
        SetBackground(),
        LeaveLobby(),
    ]
    container = lambda o, x: Div(o, DivHStacked(*x,cls='gap-1 flex flex-wrap'))
    head = lambda i, txt: DivLAligned(ico(i), H5(txt), cls='space-x-4 py-2')
    
    return Card(
        Div(
            container(head('layout-dashboard', "Lobby settings"), lobby_settings) if any(lobby_settings) else None,
            container(head('user', "User settings"), user_settings),
            cls='flex flex-col items-right space-y-4'),
        header=card_header_content,
        cls = 'space-y-2',
    )



def SettingsPopover(*lobby_settings):
    button = Card(
        UkIcon('cog', width=45, height=45),
        # TODO on mobile the focus is still on the button, not the card
        _ = "on mouseenter trigger mouseenter on #settings-panel-wrapper",
        cls="cursor-pointer rounded-full focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500",
        tabindex="0",
        id="settings-popover-button"
    )

    settings_card = Settings(*lobby_settings)
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
        cls="fixed bottom-0 right-0 p-4 z-50 sm:block hidden"
    )


#-----------------------------------#
#------------- Routes --------------#
#-----------------------------------#

# TODO move to user app
@rt('/name', methods=['put'])
async def edit_name(req: Request, hdrs: HtmxHeaders):
    u: User = req.state.user
    name = ' '.join(urllib.parse.unquote(hdrs.prompt).split())
    u.name = name
    user_manager.update(u)
    lobby_service.sync_active_lobbies_user(u)
    lobby = lobby_service.get_lobby(req.session.get("lobby_id"))
    if not lobby: return
    def update(r, *_): return UserName(r, u)
    await notify_all(lobby, update)


async def modify_avatar(req: Request, file: Optional[UploadFile] = None):
    '''Update user avatar and if in lobby sync it'''
    u: User = req.state.user
    if file: await u.set_picture(file)
    else: u.reset_picture()
    user_manager.update(u)
    lobby_service.sync_active_lobbies_user(u)
    lobby = lobby_service.get_lobby(req.session.get("lobby_id"))
    if not lobby: return
    def update(*_): return (Avatar(u)(hx_swap_oob=f"outerHTML:[data-avatar='{u.uid}']"), 
                            AvatarBig(u)(hx_swap_oob=f"outerHTML:[data-avatar-big='{u.uid}']"))
    await notify_all(lobby, update)


@rt('/avatar', methods=['post'])
async def edit_avatar(req: Request, file: UploadFile): await modify_avatar(req, file)


@rt('/avatar', methods=['delete'])
async def reset_avatar(req: Request): await modify_avatar(req, None)


@rt('/lock', methods=['post'])
async def lock_lobby(req: Request):
    lobby: Lobby[LobbyMember] = req.state.lobby
    p = lobby.get_member(req.state.user.uid)
    if not is_host(p): return
    if lobby.locked: lobby.unlock()
    else: lobby.lock()
    lobby_service.update(lobby)
    def update(*_): return LockLobby(lobby)
    return await notify(p, update)


@rt('/background', methods=['post'])
async def change_background(req: Request, hdrs: HtmxHeaders):
    lobby: BasicLobby = req.state.lobby
    lobby.background_url = urllib.parse.unquote(hdrs.prompt)
    lobby_service.update(lobby)
    def update(*_): return Background(lobby.background_url, no_image=not lobby.background_url)
    return await notify_all(lobby, update)

@rt
async def leave_lobby(req: Request):
    lobby: BasicLobby = req.state.lobby
    uid = req.state.user.uid
    if not lobby: return
    lobby.remove_member(uid)
    def update(*_): return UserRemover(uid)
    asyncio.create_task(notify_all(lobby, update))
    return Redirect('/')