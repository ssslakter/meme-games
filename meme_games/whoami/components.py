from ..common.components import *
from ..init import *
from fasthtml.common import *
from .domain import *
from ..common import *


def Spectators(reciever: WhoAmIPlayer | User, lobby: WhoAmILobby):
    spectate = (Button('Spectate', cls='controls', hx_post='/spectate', hx_swap='beforeend', hx_target='#players')
                if isinstance(reciever, WhoAmIPlayer) and reciever.is_player
                else None)
    return Div(spectate, *[UserName(p.user, is_connected=p.is_connected)
                 for p in sorted(lobby.members.values(),
                                 key=lambda x: x.joined_at) if not p.is_player],
               cls='spectators', id='spectators')


def Avatar(filename: Optional[str] = None):
    filename = ('/user-content/'+filename) if filename else '/media/default-avatar.jpg'
    return Div(style=f'background-image: url({filename})', cls='avatar')


def PlayerCard(reciever: WhoAmIPlayer|User, p: WhoAmIPlayer, lobby: WhoAmILobby):
    if not p.is_player: return
    edit =  I('edit', cls='controls material-icons', _='on click set x to next <form input/> then x.click()') if reciever.uid == p.uid else None
    return Div(edit,
               Form(Input(type='file', name='file', accept="image/*"), style='display: none;',
                    hx_trigger='change', hx_post='/picture', hx_swap='none'),
        Avatar(p.user.filename),
        Div(UserName(p.user, is_connected=p.is_connected), " ✪" if lobby.host.uid == p.uid else None),
        cls='player-card', dt_user=p.uid)


def NewPlayerCard():
    return Div(Div('+', cls='join-icon'), cls='new-player-card', hx_post='/play', hx_swap='delete')


def Game(reciever: WhoAmIPlayer|User, lobby: WhoAmILobby):
    new_player = [] if isinstance(reciever, WhoAmIPlayer) and reciever.is_player else [NewPlayerCard()]
    return Div(
        *[PlayerCard(reciever, p, lobby) for p in sorted(lobby.members.values(), key=lambda x: x.joined_at)] + new_player,
        id='players')


def Main(reciever: WhoAmIPlayer|User, lobby: WhoAmILobby):
    return Titled(f'Lobby {lobby.id}',
                  Spectators(reciever,lobby),
                  Game(reciever, lobby),
                  Div(hx_ext='ws', ws_connect='/ws/whoami'),
                  Settings())


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
    if not lobby_id: return Redirect(f"/whoami/{random_id()}")
    u: User = req.state.user
    lobby, _ = lobby_manager.get_or_create(u, lobby_id, WhoAmILobby)
    m = lobby.get_member(u.uid)
    req.session['lobby_id'] = lobby.id
    return Main(m or u, lobby)

def on_join(reciever: WhoAmIPlayer, p: WhoAmIPlayer):
    return Div(UserName(p.user), hx_swap_oob='beforeend:#spectators')

@app.ws('/ws/whoami', conn=ws_fn(render_fn_on_join=on_join), disconn=ws_fn(connected=False, render_fn_on_join=on_join))
async def ws(send): pass

@rt('/play')
async def post(req: Request):
    u: User = req.state.user
    lobby: Lobby = lobby_manager.get_lobby(req.session.get("lobby_id"))
    if not lobby: return
    p = lobby.get_member(u.uid)
    p.play()
    def update(r: WhoAmIPlayer, lobby):
        swap_position = 'beforeend:#players' if r.is_player else 'beforebegin:#players .new-player-card'
        return Spectators(r, lobby), Div(PlayerCard(r, p, lobby), hx_swap_oob=swap_position)
    await notify_all(lobby, update)
    
@rt('/spectate')
async def post(req: Request):
    u: User = req.state.user
    lobby: Lobby = lobby_manager.get_lobby(req.session.get("lobby_id"))
    if not lobby: return
    p = lobby.get_member(u.uid)
    p.spectate()
    def update(r: WhoAmIPlayer, lobby):
        return Spectators(r, lobby), Div(hx_swap_oob=f"delete:div[dt-user='{u.uid}']")
    await notify_all(lobby, update)
    return NewPlayerCard()


@rt('/picture')
async def post(req: Request, file: UploadFile):
    u: User = req.state.user
    await u.set_picture(file)
    user_manager.update(u)
    lobby = lobby_manager.get_lobby(req.session.get("lobby_id"))
    if not lobby: return
    lobby.get_member(u.uid).sync_user(u)
    await notify_all(lobby, Game)
