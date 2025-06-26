from meme_games.core import *
from meme_games.domain import *
from ..shared import *
from .domain import *

rt = APIRouter('/whoami')

logger = logging.getLogger(__name__)


lobby_service = DI.get(LobbyService)
user_manager = DI.get(UserManager)

def Spectators(reciever: WhoAmIPlayer | User, lobby: Lobby):
    spectate_controls = dict(hx_post=spectate, hx_swap='beforeend', hx_target='#players', cls='spectators-controls')
    return Div(
        "Spectators: ",
        Div(*[UserName(reciever, p.user, is_connected=p.is_connected)
              for p in lobby.sorted_members() if not p.is_player], id='spectators'), **spectate_controls)


def PlayerLabelText(r: WhoAmIPlayer | User, owner: WhoAmIPlayer):
    style = f'width: {owner.label_tfm.width}px; height: {owner.label_tfm.height}px;' if owner.label_tfm else ''
    return (Textarea(owner.label_text, placeholder='enter label', ws_send=True, name='label',
                     _="on wsMessage(label) set me.value to label",
                     data_label_text=owner.uid,
                     hx_vals={'owner_uid': owner.uid, "type": "label_text"},
                     style=style, value=owner.label_text, cls='label-text',
                     hx_trigger="input changed delay:100ms")
            if r.uid != owner.uid
            else (Textarea(readonly=True, style=style, cls='label-text'),
                  Div('?' if owner.label_text else '', cls='label-hidden', data_label_text=owner.uid)))


def PlayerLabelFT(r: WhoAmIPlayer | User, owner: WhoAmIPlayer):
    fields = ['x', 'y', 'width', 'height', 'owner_uid']
    event_details = ', '.join([f"{field}: event.detail.transform.{field}" for field in fields])
    return Div(PlayerLabelText(r, owner),
               Div(hx_trigger='moved', ws_send=True, hx_vals=f'js:{{{event_details}, type: "label_position"}}'),
               style=f'left: {owner.label_tfm.x}px; top: {owner.label_tfm.y}px' if owner.label_tfm else '',
               data_label=owner.uid,
               cls='draggable label',
               _=f'''
            init set me.isClicked to false
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
                    set transform to Object.assign(scale, pos)
                    set params to getTransformParams(me, me.parentElement, transform)
                    set params.new.owner_uid to '{owner.uid}'
                    trigger moved(transform: params.new) on last  <div/> in me
                    call applyTransform(me, params.old, params.new)
                end
            on wsMessage
               if not me.isDragging then
                  set params to getTransformParams(me, me.parentElement, event.detail)
                  call applyTransform(me, params.old, params.new)
               end
            end
            '''.strip()
               )


def PlayerCard(reciever: WhoAmIPlayer | User, p: WhoAmIPlayer, lobby: Lobby):
    if not p.is_player: return
    if reciever == p:
        edit = I('edit', cls='controls material-icons',
                 _='on click set x to next <form input/> then x.click()')
    else: edit = (I('description', cls='material-icons controls',
                    _='on mouseover send mouseover to next <.notes/>'),
                  Notes(reciever, p))
    return Div(PlayerLabelFT(reciever, p),
               Div(
                   edit,
                   Form(Input(type='file', name='file', accept="image/*"), style='display: none;',
                        hx_trigger='change', hx_post=edit_avatar.to(), hx_swap='none'),
                   Avatar(p.user),
                   Div(UserName(reciever, p.user, is_connected=p.is_connected), " ✪" if lobby.host == p else None),
                   cls='player-card-body'), cls='player-card', data_user=p.uid,
               _='on mouseleave remove .hover from .hover in me')


def NewPlayerCard():
    return Div(Div('+', cls='join-icon'), cls='new-player-card', hx_post=play, hx_swap='outerHTML')


def Notes(reciever: WhoAmIPlayer | User, author: WhoAmIPlayer, **kwargs):
    notes_kwargs = (dict(hx_post=notes,
                         hx_trigger="input changed delay:500ms, load",
                         hx_swap='none',
                         placeholder="Your notes")
                    if reciever == author
                    else dict(readonly=True,
                              data_notes=author.uid)
                    )

    return Textarea(author.notes, name='text', cls='notes', **notes_kwargs,
                    _='''on mouseover add .hover on me''')


def NotesBlock(r: WhoAmIPlayer | User):
    return Div(Notes(r, r) if is_player(r) else None, id='notes-block', hx_swap_oob='true')


def Game(reciever: WhoAmIPlayer | User, lobby: Lobby):
    new_player = [] if is_player(reciever) else [NewPlayerCard()]
    return Div(
        Div(
            *[PlayerCard(reciever, p, lobby) for p in lobby.sorted_members()] + new_player, id='players'),
        NotesBlock(reciever)
    )


def MainBlock(reciever: WhoAmIPlayer | User, lobby: Lobby):
    return Main(
        Div(cls='background'),
        Spectators(reciever, lobby),
        Game(reciever, lobby),
        Settings(reciever, lobby),
        hx_ext='ws', ws_connect=ws_url,
        _='on htmx:wsBeforeMessage call sendWSEvent(event)'
    )


def JoinSpectators(r: WhoAmIPlayer, p: WhoAmIPlayer):
    return Div(UserName(r.user, p.user), hx_swap_oob='beforeend:#spectators')


def ActiveGameState(r: WhoAmIPlayer | User, lobby: Lobby): return Spectators(r, lobby), Game(r, lobby)


#---------------------------------#
#------------- Routes ------------#
#---------------------------------#


def ws_fn(connected=True, render_fn: Callable = JoinSpectators):
    '''Returns a function that will be called when a user joins the lobby websocket'''
    async def user_joined(sess, send, ws):
        u = user_manager.get_or_create(sess)
        lobby: WAILobby = lobby_service.get_lobby(sess.get('lobby_id'))
        if not lobby: return
        if m := lobby.get_member(u.uid):
            if connected: m.connect(send, ws)
            else: m.disconnect()

            def update(r, *_):
                hx=f"outerHTML:span[data-username='{u.uid}']"
                if r == u: return ActiveGameState(r, lobby), UserName(r.user, m.user, is_connected=connected, hx_swap_oob=hx)
                return UserName(r.user, m.user, is_connected=connected, hx_swap_oob=hx)
        else:
            if not connected: return  # user not found in the lobby and not connecting
            m = lobby.create_member(u, send=send, ws=ws)
            lobby_service.update(lobby)

            def update(r, *_):
                if r == u: return ActiveGameState(r, lobby), render_fn(r, m)
                return render_fn(r, m)
        await notify_all(lobby, update)

    return user_joined


@rt('/{lobby_id}', methods=['get'])
def lobby(req: Request, lobby_id: str = None):
    if not lobby_id: return Redirect(req.url_for('lobby', lobby_id=random_id()))
    u: User = req.state.user
    lobby, was_created = lobby_service.get_or_create(u, lobby_id, WhoAmIPlayer)
    if was_created: lobby_service.update(lobby)
    m = lobby.get_member(u.uid)
    req.session['lobby_id'] = lobby.id
    req.bodykw['cls'] = 'who-am-i'
    return (Title(f'Who Am I lobby: {lobby.id}'),
            MainBlock(m or u, lobby))


@rt
async def play(req: Request):
    lobby: WAILobby = req.state.lobby
    p = lobby.get_member(req.state.user.uid)
    if p.is_player: return
    if lobby.locked: 
        add_toast(req.session, "Game is locked", "error")
        return NewPlayerCard()
    p.play()
    lobby_service.update(lobby)

    def update(r: WhoAmIPlayer, lobby):
        swap_position = 'beforeend:#players' if r.is_player else 'beforebegin:#players .new-player-card'
        res = (Div(hx_swap_oob=f"delete:#spectators [data-username='{p.uid}']"),)
        if r != p: res += (Div(PlayerCard(r, p, lobby), hx_swap_oob=swap_position),)
        return res
    await notify_all(lobby, update)
    return NotesBlock(p), PlayerCard(p, p, lobby)


@rt
async def spectate(req: Request):
    lobby: WAILobby = req.state.lobby
    p = lobby.get_member(req.state.user.uid)
    if not p.is_player: return
    if lobby.locked: return add_toast(req.session, "Game is locked", "error")
    p.spectate()
    lobby_service.update(lobby)

    def update(r: WhoAmIPlayer, *_):
        return JoinSpectators(r, p), Div(hx_swap_oob=f"delete:div[data-user='{p.user.uid}']")
    await notify_all(lobby, update)
    return NewPlayerCard(), NotesBlock(p)


@rt
async def notes(req: Request, text: str):
    lobby: WAILobby = req.state.lobby
    p = lobby.get_member(req.state.user.uid)
    if not p.is_player: return
    p.set_notes(text)
    lobby_service.update(lobby)

    def update(r, *_): return Notes(r, p)(hx_swap_oob=f"innerHTML:[data-notes='{p.uid}']")
    await notify_all(lobby, update, but=p)


async def edit_label_text(sess, label: str, owner_uid: str):
    lobby: WAILobby = lobby_service.get_lobby(sess.get("lobby_id"))
    p = lobby.get_member(user_manager.get(sess.get('uid')).uid)
    owner = lobby.get_member(owner_uid)
    if not (owner and p and p.is_player) or p == owner: return
    owner.set_label(label)
    lobby_service.update(lobby)
    def update(*_): return dict(type='label_text', owner_uid=owner.uid, label=label)
    await notify_all(lobby, update, but=[owner, p], json=True)
    def update(r, *_): return PlayerLabelText(r, r)[1](hx_swap_oob=f"innerHTML:[data-label-text='{owner.uid}']")
    await notify(owner, update, owner)


async def edit_label_position(sess, owner_uid: str, **kwargs):
    lobby: WAILobby = lobby_service.get_lobby(sess.get("lobby_id"))
    p = lobby.get_member(user_manager.get(sess.get('uid')).uid)
    owner = lobby.get_member(owner_uid)
    if not (p and owner): return
    owner.set_label_transform(kwargs)
    lobby_service.update(lobby)
    def update(*_): return dict(type='label_position', owner_uid=owner.uid, **kwargs)
    await notify_all(lobby, update, json=True, but=p)


@ws_rt.ws('/whoami', conn=ws_fn(), disconn=ws_fn(connected=False))
async def ws(sess, data):
    try:
        msg_type = data.pop('type')
        if msg_type == 'label_text': await edit_label_text(sess, **data)
        elif msg_type == 'label_position': await edit_label_position(sess, **data)
    except Exception as e: logger.error(e)

ws_url = ws_rt.wss[-1][1] # latest added websocket url