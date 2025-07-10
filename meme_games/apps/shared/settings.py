import urllib
from meme_games.core import *
from meme_games.domain import *
from .general import *


rt = APIRouter()

lobby_service = DI.get(LobbyService)
user_manager = DI.get(UserManager)


# --- Class Constants ---
BASE_SETTING_ROW_CLS = "space-x-2 p-2 bg-white/60 rounded-md dark:bg-gray-800/60"
SETTING_ROW_CLS = f"{BASE_SETTING_ROW_CLS} hover:bg-green-300 cursor-pointer dark:hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"

def Avatar(u: User):
    filename = u.filename
    filename = ('/user-content/' + filename) if filename else '/media/default-avatar.jpg'
    return Div(style=f'background-image: url({filename})', cls="w-full h-full bg-cover bg-center bg-no-repeat dark:brightness-75", data_avatar=u.uid)


def Setting(icon: str, title: str = None, hx_swap='none', **kwargs):
    return DivLAligned(
        UkIcon(icon, cls="text-3xl"),
        P(title, cls="text-lg"),
        cls=SETTING_ROW_CLS,
        hx_swap=hx_swap,
        **kwargs
    )


def NameSetting(): return Setting('pencil', title='Edit name', hx_put=edit_name.to(), hx_prompt='Enter your name')

def AvatarRemoval(): return Setting('trash', title='Remove avatar', hx_delete=reset_avatar.to(),
                                    hx_confirm="Confirm that you want to remove your avatar?")

def LockLobby(l: Lobby): 
    args = ('lock-open', 'Lock lobby') if not l.locked else ('lock', 'Unlock lobby')
    return Setting(*args, hx_post=lock_lobby.to(), hx_swap=None)(hx_swap_oob='outerHTML', id='lock-lobby')

def SetBackground(l: Lobby):
    return Setting('image', title='Background', hx_post=change_background.to(), hx_prompt='Enter the URL of the background image')


def Settings(reciever: User|LobbyMember, lobby: Lobby):
    card_header_content = DivLAligned(
        UkIcon('cog', width=25, height=25),
        H4('Settings', cls="text-xl font-bold ml-2")
    )

    settings_items = [
        NameSetting(),
        AvatarRemoval(),
        SetBackground(lobby),
    ]
    if isinstance(reciever, LobbyMember) and reciever.is_host:
        settings_items.extend(HostSettings(lobby))
    
    return Card(
        *settings_items,
        header=card_header_content,
        cls = 'space-y-2'
    )
    

def HostSettings(lobby: Lobby):
    return tuple(f(lobby) for f in (LockLobby,))


def SettingsPopover(reciever: User|LobbyMember, lobby: Lobby):
    button = Panel(
        UkIcon('cog', width=45, height=45),
        _ = "on mouseenter or focus remove .hidden from #settings-panel-wrapper then add .hidden to me",
        cls="cursor-pointer rounded-full focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500",
        hoverable=True,
        tabindex="0",
        id="settings-popover-button"
    )

    settings_card = Settings(reciever, lobby)
    panel_wrapper = Div(
        settings_card,
        cls="absolute bottom-0 right-0 p-4 mt-2 max-w-3xl w-80 z-10 hidden",
        id="settings-panel-wrapper"
    )

    return Div(
        button,
        panel_wrapper,
        cls="fixed bottom-0 right-0 p-4 z-50"
    )


#-----------------------------------#
#------------- Routes --------------#
#-----------------------------------#


@rt('/name', methods=['put'])
async def edit_name(req: Request, hdrs: HtmxHeaders):
    u: User = req.state.user
    name = ' '.join(urllib.parse.unquote(hdrs.prompt).split())
    u.name = name
    user_manager.update(u)
    lobby_service.sync_active_lobbies_user(u)
    lobby = lobby_service.get_lobby(req.session.get("lobby_id"))
    if not lobby: return
    def update(r, *_): return UserName(r, u)(hx_swap_oob=f"outerHTML:span[data-username='{u.uid}']")
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
    def update(*_): return Avatar(u)(hx_swap_oob=f"outerHTML:[data-avatar='{u.uid}']")
    await notify_all(lobby, update)


@rt('/avatar', methods=['post'])
async def edit_avatar(req: Request, file: UploadFile): await modify_avatar(req, file)


@rt('/avatar', methods=['delete'])
async def reset_avatar(req: Request): await modify_avatar(req, None)


@rt('/lock', methods=['post'])
async def lock_lobby(req: Request):
    lobby: Lobby[LobbyMember] = req.state.lobby
    p = lobby.get_member(req.state.user.uid)
    if not p.is_host: return
    if lobby.locked: lobby.unlock()
    else: lobby.lock()
    lobby_service.update(lobby)
    def update(*_): return LockLobby(lobby)
    return await notify(p, update)


@rt('/background', methods=['post'])
async def change_background(req: Request, hdrs: HtmxHeaders):
    lobby: Lobby[LobbyMember] = req.state.lobby
    lobby.background_url = urllib.parse.unquote(hdrs.prompt)
    lobby_service.update(lobby)
    def update(*_): return Background(lobby.background_url)
    return await notify_all(lobby, update)
