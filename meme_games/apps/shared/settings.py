import urllib
from meme_games.core import *
from meme_games.domain import *


rt = APIRouter()

lobby_service = DI.get(LobbyService)
user_manager = DI.get(UserManager)


# --- Class Constants ---
BASE_SETTING_ROW_CLS = "space-x-2 p-2 bg-white/60 rounded-md dark:bg-gray-800/60"
SETTING_ROW_CLS = f"{BASE_SETTING_ROW_CLS} hover:bg-green-300 cursor-pointer dark:hover:bg-gray-700"
NIGHT_MODE_ROW_CLS = f"{BASE_SETTING_ROW_CLS} justify-between items-center"

BASE_THEME_BTN_CLS = "inline-flex items-center px-3 py-1.5 border border-gray-300 bg-white text-sm font-medium text-gray-700 hover:bg-gray-50 focus:z-10 focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 cursor-pointer dark:bg-gray-800 dark:border-gray-600 dark:text-white dark:hover:bg-gray-700"
CARD_CLS = "fixed bottom-0 right-0 p-4 border border-gray-400 rounded-lg shadow-lg bg-white/60 space-y-2 dark:border-gray-700 dark:bg-gray-900/60"
AVATAR_CLS = "w-72 h-72 bg-cover bg-center bg-no-repeat"
BACKGROUND_CLS = "absolute inset-0 z-[-1] bg-black bg-cover bg-center bg-no-repeat filter blur-sm brightness-50"


def Avatar(u: User):
    filename = u.filename
    filename = ('/user-content/' + filename) if filename else '/media/default-avatar.jpg'
    return Div(style=f'background-image: url({filename})', cls=AVATAR_CLS, data_avatar=u.uid)


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

def Background(url: str = None): 
    bg_style = f'background-image: url({url})' if url else ''
    return Div(
        id='background',
        cls=BACKGROUND_CLS,
        style=bg_style,
        hx_swap_oob='true'
    )


def SetBackground(l: Lobby):
    return Setting('image', title='Background', hx_post=change_background.to(), hx_prompt='Enter the URL of the background image')


def _ThemeButton(icon: str, text: str, action: str, extra_cls: str = ''):
    return Div(
        UkIcon(icon, cls="w-5 h-5 mr-2"),
        text,
        _=action,
        cls=f"{BASE_THEME_BTN_CLS} {extra_cls}"
    )

def ThemeSwitcher():
    light_btn = _ThemeButton(
        'sun', 'Light', 
        "on click remove .dark from <html/> then call setThemeMode(false)",
        "rounded-l-md"
    )
    dark_btn = _ThemeButton(
        'moon', 'Dark',
        "on click add .dark to <html/> then call setThemeMode(true)",
        "-ml-px rounded-r-md"
    )
    return Div(light_btn, dark_btn, cls="ml-auto isolate inline-flex rounded-md shadow-sm")


def Settings(reciever: User|LobbyMember, lobby: Lobby):
    card_header_content = DivLAligned(
        UkIcon('cog', cls="text-4xl"),
        H4('Settings', cls="text-xl font-bold ml-2")
    )

    settings_items = [
        NameSetting(),
        AvatarRemoval(),
        SetBackground(lobby),
    ]
    if isinstance(reciever, LobbyMember) and reciever.is_host:
        settings_items.extend(HostSettings(lobby))

    settings_items.append(
        DivLAligned(
            UkIcon('sun', cls="text-3xl"),
            P('Night Mode', cls="text-lg"),
            ThemeSwitcher(),
            cls=NIGHT_MODE_ROW_CLS
        )
    )
    
    return Card(
        *settings_items,
        header=card_header_content,
        cls=CARD_CLS
    )
    

def HostSettings(lobby: Lobby):
    return tuple(f(lobby) for f in (LockLobby,))


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


async def modify_avatar(req: Request, file: UploadFile = None):
    '''Update user avatar and if in lobby sync it'''
    u: User = req.state.user
    await u.set_picture(file)
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
