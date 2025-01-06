from ..init import *


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


def Settings():
    return Div(
        I('settings', cls="material-icons controls"),
        NameSetting(),
        cls='controls-block'
    )