from ..common.components import *
from ..init import *
from fasthtml.common import *
from .domain import *
from ..common import *


def Avatar(filename: Optional[str] = None):
    filename = ('/user-content/'+filename) if filename else '/media/default-avatar.jpg'
    return Div(style=f'background-image: url({filename})', cls='avatar')


def PlayerCard(reciever: WhoAmIPlayer, p: WhoAmIPlayer):
    edit =  I('edit', cls='controls material-icons', _='on click set x to next <form input/> then x.click()') if reciever.uid == p.uid else None
    return Div(edit,
               Form(Input(type='file', name='file', accept="image/*"), style='display: none;',
                    hx_trigger='change', hx_post='/picture', hx_swap='none'),
        Avatar(p.user.filename),
        Div(UserName(p.user, is_connected=p.is_connected)),
        cls='player-card')


def NewPlayerCard():
    return Div(Div('+', cls='add-user-icon'),
               cls='new-user-card')


def Game(reciever: WhoAmIPlayer, lobby: WhoAmILobby):
    return Div(
        *[PlayerCard(reciever, p) for p in lobby.members.values()],
        id='players')


# Routes


def ws_fn(connected=True, render_fn_on_join: Callable = fc.noop):
    '''Returns a function that will be called when a user joins the lobby websocket'''
    async def user_joined(sess, send):
        u = user_manager.get_or_create(sess)
        lobby: Lobby = lobby_manager.get_lobby(sess.get('lobby_id'))
        if not lobby: return
        if m := lobby.get_member(u.uid):
            if connected: m.connect(send)
            else: m.disconnect()
            def update(*_): return UserName(m.user, is_connected=connected)
        else:
            if not connected: return  # user not found in the lobby and not connecting
            m = lobby.add_member(u, ws=send)
            def update(u, *_): return render_fn_on_join(u, m)
        await notify_all(lobby, update)

    return user_joined


@rt("/whoami/{lobby_id}")
def get(req: Request, lobby_id: str = None):
    if not lobby_id:
        return Redirect(f"/whoami/{random_id()}")
    u: User = req.state.user
    lobby: WhoAmILobby
    lobby, _ = lobby_manager.get_or_create(u, lobby_id, WhoAmILobby)
    req.session['lobby_id'] = lobby.id
    return Titled(f'Lobby {lobby.id}',
                  Game(u, lobby),
                  Div(hx_ext='ws', ws_connect='/ws/whoami'),
                  Settings())

def on_join(reciever: WhoAmIPlayer, p: WhoAmIPlayer):
    return Div(PlayerCard(reciever, p), hx_swap_oob='beforeend:#players')

@app.ws('/ws/whoami', conn=ws_fn(render_fn_on_join=on_join), disconn=ws_fn(connected=False, render_fn_on_join=on_join))
async def ws(send): pass


@rt('/picture')
async def post(req: Request, file: UploadFile):
    u: User = req.state.user
    await u.set_picture(file)
    user_manager.update(u)
    lobby = lobby_manager.get_lobby(req.session.get("lobby_id"))
    if not lobby:
        return
    lobby.get_member(u.uid).sync_user(u)
    await notify_all(lobby, Game)
