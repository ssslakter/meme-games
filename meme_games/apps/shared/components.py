import urllib
from meme_games.core import *
from meme_games.domain import *

ext2ft = {
        'js': lambda fname: Script(src=f'/{fname}'),
        '_hs': lambda fname: Script(src=f'/{fname}', type='text/hyperscript'),
        'css': lambda fname: Link(rel="stylesheet", href=f'/{fname}'),
    }

def Statics(ext: str ='css', static_path: str|Path = 'static', wc: str = None):
    '''Returns a list of static files from a directory'''
    static_path = Path(static_path)
    wc = wc or f"*.{ext}"
    return [ext2ft[ext](f.relative_to(static_path.parent).as_posix()) 
            for f in static_path.rglob(wc)]


rt = APIRouter()


lobby_service = DI.get(LobbyService)
user_manager = DI.get(UserManager)

def Timer(time: dt.timedelta = dt.timedelta(hours=1)):
    return Span(data_delta=time.total_seconds() * 1000, cls='timer',
                _='init immediately set @target to (Date.now()+@data-delta as Number) as Date')


def Avatar(u: User):
    filename = u.filename
    filename = ('/user-content/' + filename) if filename else '/media/default-avatar.jpg'
    return Div(style=f'background-image: url({filename})', cls='avatar', data_avatar=u.uid)


def Setting(icon: str, title: str = None, hx_swap='none', **kwargs):
    return Div(
        I(icon, title=title, cls="material-icons", hx_swap=hx_swap, **kwargs),
        cls='controls')


def NameSetting(): return Setting('edit', title='Edit name', hx_put=edit_name.to(), hx_prompt='Enter your name')

def AvatarRemoval(): return Setting('delete', title='Remove avatar', hx_delete=reset_avatar.to(),
                                    hx_confirm="Confirm that you want to remove your avatar?")

def LockLobby(l: Lobby): 
    args = ('lock_open', 'Lock lobby') if not l.locked else ('lock', 'Unlock lobby')
    return Setting(*args, hx_post=lock_lobby.to(), hx_swap=None)(hx_swap_oob='innerHTML', id='lock-lobby')

def Background(url: str = None): 
    return Div(id='background', cls='background', style=f'background-image: url({url})' if url else None, hx_swap_oob='true')


def SetBackground(l: Lobby):
    return Setting('image', title='Background', hx_post=change_background.to(), hx_prompt='Enter the URL of the background image')

def Settings(reciever: User|LobbyMember, lobby: Lobby):
    return Div(
        I('settings', cls="material-icons controls"),
        NameSetting(),
        AvatarRemoval(),
        SetBackground(lobby),
        *(HostSettings(lobby) if isinstance(reciever, LobbyMember) and reciever.is_host else []),
        cls='controls-block'
    )
    
def NightThemeToggle():
    return ThemePicker(color=False, radii=False, shadows=False, font=False, mode=True, cls='controls')


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
