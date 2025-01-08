import logging
from ..common.components import *
from ..init import *
from fasthtml.common import *
from .domain import *
from ..common import *

logger = logging.getLogger(__name__)


def Spectators(reciever: WhoAmIPlayer | User, lobby: WhoAmILobby):
    spectate_controls = dict(hx_post='/spectate', hx_swap='beforeend', hx_target='#players', cls='spectators-controls')
    return Div(
        "Spectators: ",
        Div(*[UserName(reciever, p.user, is_connected=p.is_connected)
              for p in lobby.sorted_members() if not p.is_player], id='spectators'), **spectate_controls)


def Avatar(u: User):
    filename = u.filename
    filename = ('/user-content/' + filename) if filename else '/media/default-avatar.jpg'
    return Div(style=f'background-image: url({filename})', cls='avatar', hx_swap_oob=f"outerHTML:[dt-avatar='{u.uid}']", dt_avatar=u.uid)


def PlayerLabelText(r: WhoAmIPlayer | User, owner: WhoAmIPlayer):
    return (Textarea(owner.label, placeholder='enter label', ws_send=True, name='label', dt_label=owner.uid,
                     _="on change set my.value to me.innerHTML", hx_vals={'owner_uid': owner.uid},
                     hx_trigger="input changed delay:500ms", hx_swap_oob=f"innerHTML:[dt-label='{owner.uid}']")
            if r.uid != owner.uid
            else Textarea(readonly=True))


def PlayerLabel(r: WhoAmIPlayer | User, owner: WhoAmIPlayer):
    return Div(PlayerLabelText(r, owner),
               Div(hx_trigger='moved', ws_send=True,
                   hx_vals='js:{x: event.detail.x, y: event.detail.y, width: event.detail.width, height: event.detail.height, owner_uid: event.detail.owner_uid}'),
               cls='draggable label' + (' label-hidden' if r == owner else ''),
               _=f'''
            on mousedown
                if not me.isClicked
                    set me.isClicked to true
                    if event.target != first <textarea/> in me
                        set me.isDragging to true
                        set {{offsetX: event.clientX - me.offsetLeft, offsetY: event.clientY - me.offsetTop}} on me
                        set *user-select of body to 'none'
                    end
                end
            end
            on mousemove from document
                if me.isDragging
                    set *left to (event.clientX - me.offsetX) px
                    set *top to (event.clientY - me.offsetY) px
                end
            on mouseup from document
                if me.isClicked then
                    set me.isDragging to false
                    set *user-select of body to ''
                    set scale to getStyleScale(me) then set pos to getStylePosition(me)
                    set params to getTransformParams(me, me.parentElement, pos, scale)
                    trigger moved (x: pos.x, y: pos.y, width: scale.width, height: scale.height, \
                                   owner_uid: '{owner.uid}') on first <div/> in me
                    call applyTransform(me, params)
                end
            on htmx:wsBeforeMessage from document
                set msg to event.detail.message
                if isJSON(msg) then set msg to JSON.parse(msg)
                    if msg.owner_uid == '{owner.uid}' then
                        set params to getTransformParams(me, me.parentElement, {{x: msg.x, y: msg.y}}, {{width: msg.width, height: msg.height}})
                        call applyTransform(me, params)
                        set txt to first <textarea/> in me
                    end
                end
            '''
               )


def PlayerCard(reciever: WhoAmIPlayer | User, p: WhoAmIPlayer, lobby: WhoAmILobby):
    if not p.is_player: return
    if reciever == p:
        edit = I('edit', cls='controls material-icons',
                 _='on click set x to next <form input/> then x.click()')
    else: edit = (I('description', cls='material-icons controls',
                    _='on mouseover send mouseover to next <.notes/>'),
                  Notes(reciever, p))
    return Div(edit,
               PlayerLabel(reciever, p),
               Form(Input(type='file', name='file', accept="image/*"), style='display: none;',
                    hx_trigger='change', hx_post='/picture', hx_swap='none'),
               Avatar(p.user),
               Div(UserName(reciever, p.user, is_connected=p.is_connected), " ✪" if lobby.host == p else None),
               cls='player-card', dt_user=p.uid, _='on mouseleave remove .hover from .hover in me')


def NewPlayerCard():
    return Div(Div('+', cls='join-icon'), cls='new-player-card', hx_post='/play', hx_swap='delete')


def Notes(reciever: WhoAmIPlayer | User, author: WhoAmIPlayer, **kwargs):
    notes_kwargs = (dict(hx_post='/notes',
                         hx_trigger="input changed delay:500ms, load",
                         hx_swap='none',
                         placeholder="Your notes")
                    if reciever == author
                    else dict(readonly=True,
                              dt_notes=author.uid,
                              hx_swap_oob=f"outerHTML:[dt-notes='{author.uid}']"))

    return Textarea(author.notes, name='text', cls='notes', **notes_kwargs,
                    _='''on mouseover add .hover on me''')


def NotesBlock(r: WhoAmIPlayer | User):
    return Div(Notes(r, r) if is_player(r) else None, id='notes-block', hx_swap_oob='true')


def Game(reciever: WhoAmIPlayer | User, lobby: WhoAmILobby):
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

def JoinSpectators(r: WhoAmIPlayer, p: WhoAmIPlayer):
    return Div(UserName(r.user, p.user), hx_swap_oob='beforeend:#spectators')


def ActiveGameState(r: WhoAmIPlayer | User, lobby: WhoAmILobby): return Spectators(r, lobby), Game(r, lobby)


def ws_fn(connected=True, render_fn: Callable = JoinSpectators):
    '''Returns a function that will be called when a user joins the lobby websocket'''
    async def user_joined(sess, send, ws):
        u = user_manager.get_or_create(sess)
        lobby: Lobby = lobby_manager.get_lobby(sess.get('lobby_id'))
        if not lobby: return
        if m := lobby.get_member(u.uid):
            if connected: m.connect(send, ws)
            else: m.disconnect()

            def update(r, *_):
                if r == u: return ActiveGameState(r, lobby), UserName(r.user, m.user, is_connected=connected)
                return UserName(r.user, m.user, is_connected=connected)
        else:
            if not connected: return  # user not found in the lobby and not connecting
            m = lobby.add_member(u, send=send, ws=ws)

            def update(r, *_):
                if r == u: return ActiveGameState(r, lobby), render_fn(r, m)
                return render_fn(r, m)
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


async def edit_label_text(sess, label: str, owner_uid: str):
    lobby: WhoAmILobby = lobby_manager.get_lobby(sess.get("lobby_id"))
    p = lobby.get_member(user_manager.get(sess.get('uid')).uid)
    owner = lobby.get_member(owner_uid)
    if not (owner and p and p.is_player) or p == owner: return
    owner.set_label(label)
    def update(r, *_): return PlayerLabelText(r, owner)
    await notify_all(lobby, update, filter_fn=lambda m: m != owner)


async def edit_label_position(sess, owner_uid: str,
                              x: int, y: int,
                              width: int, height: int):
    lobby: WhoAmILobby = lobby_manager.get_lobby(sess.get("lobby_id"))
    p = lobby.get_member(user_manager.get(sess.get('uid')).uid)
    owner = lobby.get_member(owner_uid)
    if not (p and owner): return
    def update(*_): return dict(x=x, y=y, width=width, height=height, owner_uid=owner.uid)
    await notify_all(lobby, update, json=True, filter_fn=lambda m: m != p)


@app.ws('/ws/whoami', conn=ws_fn(), disconn=ws_fn(connected=False))
async def ws(sess, data):
    try:
        if 'label' in data: await edit_label_text(sess, **data)
        elif 'x' in data: await edit_label_position(sess, **data)
    except Exception as e: logger.error(e)
