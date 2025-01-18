import urllib.parse
from ..init import *


def Timer(time: dt.timedelta = dt.timedelta(hours=1)):
    return Span(data_delta = time.total_seconds()*1000, cls='timer',
                _ = 'init immediately set @target to (Date.now()+@data-delta as Number) as Date')


def LobbyInfo(lobby: Lobby):
    print(dt.datetime.now() - (lobby.last_active + lobby_manager.lobby_lifetime))
    return Div(f'{lobby.id}: ',
               A('join', href=f'/whoami/{lobby.id}', hx_boost='false'),
               f'Last active: {lobby.last_active.strftime("%Y-%m-%d %H:%M:%S")}',
               Div("Will be deleted in: ", Timer(lobby.last_active + lobby_manager.lobby_lifetime - dt.datetime.now())),
               style='display: flex; gap: 8px;')


def Avatar(u: User):
    filename = u.filename
    filename = ('/user-content/' + filename) if filename else '/media/default-avatar.jpg'
    return Div(style=f'background-image: url({filename})', cls='avatar', hx_swap_oob=f"outerHTML:[data-avatar='{u.uid}']", data_avatar=u.uid)


def NameSetting():
    return Div(
        I('edit', title='Edit name', cls="material-icons", hx_put='/name', hx_swap='none', hx_prompt='Enter your name'),
        cls='controls')


def AvatarSetting():
    return Div(
        I('delete', cls="material-icons", hx_delete='/reset-avatar', hx_swap='none', title="remove avatar",
          hx_confirm="Confirm that you want to remove your avatar?"),
        cls='controls')


def Settings():
    return Div(
        I('settings', cls="material-icons controls"),
        NameSetting(),
        AvatarSetting(),
        cls='controls-block'
    )


@rt('/name')
async def put(req: Request, hdrs: HtmxHeaders):
    u: User = req.state.user
    name = ' '.join(urllib.parse.unquote(hdrs.prompt).split())
    u.name = name
    user_manager.update(u)
    lobby_service.sync_active_lobbies_user(u)
    lobby = lobby_service.get_lobby(req.session.get("lobby_id"))
    if not lobby: return
    def update(r, *_): return UserName(r, u)
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
    def update(*_): return Avatar(u)
    await notify_all(lobby, update)


@rt('/avatar')
async def post(req: Request, file: UploadFile): await modify_avatar(req, file)


@rt('/reset-avatar')
async def delete(req: Request): await modify_avatar(req, None)


@rt('/monitor')
def get():
    lobbies_list = Div(H3("Who am I lobbies:"), Ul(*[Li(LobbyInfo(lobby)) for lobby in lobby_manager.lobbies.values()]),
                       _='init updateTimer() then setInterval(updateTimer, 500)')
    return Titled("Current active lobbies",
                  lobbies_list if len(lobby_manager.lobbies) else Div("No active lobbies"))
