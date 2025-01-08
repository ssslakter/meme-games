from ..init import *


def Avatar(u: User):
    filename = u.filename
    filename = ('/user-content/' + filename) if filename else '/media/default-avatar.jpg'
    return Div(style=f'background-image: url({filename})', cls='avatar', hx_swap_oob=f"outerHTML:[dt-avatar='{u.uid}']", dt_avatar=u.uid)


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
    name = ' '.join(hdrs.prompt.split())
    u.name = name
    user_manager.update(u)
    lobby = lobby_manager.get_lobby(req.session.get("lobby_id"))
    if not lobby: return
    m = lobby.members.get(u.uid)
    m.sync_user(u)
    def update(r, *_): return UserName(r, u)
    await notify_all(lobby, update)


async def modify_avatar(req: Request, file: UploadFile = None):
    '''Update user avatar and if in lobby sync it'''
    u: User = req.state.user
    if file: await u.set_picture(file)
    else: u.reset_picture()
    user_manager.update(u)
    lobby = lobby_manager.get_lobby(req.session.get("lobby_id"))
    if not lobby: return
    lobby.get_member(u.uid).sync_user(u)
    def update(*_): return Avatar(u)
    await notify_all(lobby, update)


@rt('/avatar')
async def post(req: Request, file: UploadFile): await modify_avatar(req, file)


@rt('/reset-avatar')
async def delete(req: Request): await modify_avatar(req, None)
