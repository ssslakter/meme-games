from ..init import *


@rt('/name')
async def put(req: Request, name: str):
    u: User = req.state.user
    u.name = name
    user_manager.update(u)
    lobby = lobby_manager.get_lobby(req.session.get("lobby_id"))
    if not lobby:
        return
    m = lobby.members.get(u.uid)
    if m:
        m.user.name = name

    def update(*_): return UserName(u)
    await notify_all(lobby, update)


def Settings():
    return Div(
        I('settings', cls="material-icons controls"),
        NameSetting(),
        cls='controls-block panel'
    )