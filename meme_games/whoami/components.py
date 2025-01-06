from ..common.components import *
from ..init import *
from fasthtml.common import *
from .domain import *
from ..common import *


def Spectators(reciever: WhoAmIPlayer | User, lobby: WhoAmILobby):
    spectate_controls = dict(hx_post='/spectate', hx_swap='beforeend', hx_target='#players', cls='spectators-controls')
    return Div(
        "Spectators: ",
        Div(*[UserName(reciever, p.user, is_connected=p.is_connected)
              for p in lobby.sorted_members() if not p.is_player], id='spectators'), **spectate_controls)


def Avatar(u: User):
    filename = u.filename
    filename = ('/user-content/'+filename) if filename else '/media/default-avatar.jpg'
    return Div(style=f'background-image: url({filename})', cls='avatar', hx_swap_oob=f"outerHTML:[dt-avatar='{u.uid}']", dt_avatar=u.uid)


def PlayerCard(reciever: WhoAmIPlayer|User, p: WhoAmIPlayer, lobby: WhoAmILobby):
    if not p.is_player: return
    if reciever.uid == p.uid:
        edit =  I('edit', cls='controls material-icons',
              _='on click set x to next <form input/> then x.click()')
    else:  edit = (I('settings',cls='material-icons controls',
                    _='on mouseover send mouseover to next <.notes/>'),
    Notes(reciever, p))
    return Div(edit,
               Form(Input(type='file', name='file', accept="image/*"), style='display: none;',
                    hx_trigger='change', hx_post='/picture', hx_swap='none'),
               Avatar(p.user),
               Div(UserName(reciever, p.user, is_connected=p.is_connected), " ✪" if lobby.host.uid == p.uid else None),
        cls='player-card', dt_user=p.uid, _='on mouseleave remove .hover from .hover in me')


def NewPlayerCard():
    return Div(Div('+', cls='join-icon'), cls='new-player-card', hx_post='/play', hx_swap='delete')


def Notes(reciever: WhoAmIPlayer | User, author: WhoAmIPlayer, **kwargs):
    notes_kwargs = (dict(hx_post='/notes',
                         hx_trigger="input changed delay:500ms, load",
                         hx_swap='none',
                         placeholder="Your notes")
                    if reciever.uid == author.uid
                    else dict(readonly=True,
                              dt_notes=author.uid,
                              hx_swap_oob=f"outerHTML:[dt-notes='{author.uid}']"))

    return Textarea(author.notes, name='text', cls='notes', **notes_kwargs,
                    _='''on mouseover add .hover on me''')

def NotesBlock(r: WhoAmIPlayer|User):
    return Div(Notes(r, r) if is_player(r) else None, id='notes-block', hx_swap_oob='true')

def Game(reciever: WhoAmIPlayer|User, lobby: WhoAmILobby):
    new_player = [] if is_player(reciever) else [NewPlayerCard()]
    return Div(
        Div(
        *[PlayerCard(reciever, p, lobby) for p in lobby.sorted_members()] + new_player, id='players'),
        NotesBlock(reciever)
        )


def MainBlock(reciever: WhoAmIPlayer | User, lobby: WhoAmILobby):
    return (Title(f'Who Am I lobby: {lobby.id}'),
            Main(
                Div(cls='background'),
                Spectators(reciever, lobby),
                Game(reciever, lobby),
                Settings(),
                hx_ext='ws', ws_connect='/ws/whoami'))


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
            def update(r, *_): return UserName(r.user, m.user, is_connected=connected)
        else:
            if not connected: return  # user not found in the lobby and not connecting
            m = lobby.add_member(u, ws=send)
            def update(r, *_): return render_fn_on_join(r, m)
        await notify_all(lobby, update)

    return user_joined


@rt("/whoami/{lobby_id}")
def get(req: Request, lobby_id: str = None):
    if not lobby_id: return Redirect(f"/whoami/{random_id()}")
    u: User = req.state.user
    lobby, _ = lobby_manager.get_or_create(u, lobby_id, WhoAmILobby)
    m = lobby.get_member(u.uid)
    req.session['lobby_id'] = lobby.id
    return MainBlock(m or u, lobby)

def JoinSpectators(r: WhoAmIPlayer, p: WhoAmIPlayer):
    return Div(UserName(r.user, p.user), hx_swap_oob='beforeend:#spectators')

@app.ws('/ws/whoami', conn=ws_fn(render_fn_on_join=JoinSpectators), disconn=ws_fn(connected=False, render_fn_on_join=JoinSpectators))
async def ws(send): pass

@rt('/play')
async def post(req: Request):
    lobby: Lobby = req.state.lobby
    p = lobby.get_member(req.state.user.uid)
    if p.is_player: return
    p.play()
    def update(r: WhoAmIPlayer, lobby):
        swap_position = 'beforeend:#players' if r.is_player else 'beforebegin:#players .new-player-card'
        return Div(hx_swap_oob=f"delete:#spectators [dt-username='{p.uid}']"), Div(PlayerCard(r, p, lobby), hx_swap_oob=swap_position)
    await notify_all(lobby, update)
    return NotesBlock(p)


@rt('/spectate')
async def post(req: Request):
    lobby: WhoAmILobby = req.state.lobby
    p = lobby.get_member(req.state.user.uid)
    if not p.is_player: return
    p.spectate()
    def update(r: WhoAmIPlayer, *_):
        return JoinSpectators(r, p), Div(hx_swap_oob=f"delete:div[dt-user='{p.user.uid}']")
    await notify_all(lobby, update)
    return NewPlayerCard(), NotesBlock(p)


@rt('/picture')
async def post(req: Request, file: UploadFile):
    '''Update user picture and if in lobby sync it'''
    u: User = req.state.user
    await u.set_picture(file)
    user_manager.update(u)
    lobby = lobby_manager.get_lobby(req.session.get("lobby_id"))
    if not lobby: return
    lobby.get_member(u.uid).sync_user(u)
    def update(*_): return Avatar(u)
    await notify_all(lobby, update)



@rt('/notes')
async def post(req: Request, text: str):
    lobby: WhoAmILobby = req.state.lobby
    p = lobby.get_member(req.state.user.uid)
    if not p.is_player: return
    p.set_notes(text)
    def update(r, *_): return Notes(r, p)
    await notify_all(lobby, update)
    
    