import asyncio
from typing import Callable
from dataclasses import dataclass
from fasthtml.common import *
import fastcore.all as fc
from meme_games.user import *
from meme_games.utils import *
from meme_games.init import *
from meme_games.lobby import *
from fastlite import *


db = init_db('data.db')
user_manager, lobby_manager = init_services(db)
lobby_manager = LobbyManager()
bwares = [user_beforeware(user_manager)]
hdrs = [
    Script(src="https://unpkg.com/hyperscript.org@0.9.13"),
    Link(rel="stylesheet", href="https://fonts.googleapis.com/icon?family=Material+Icons"),
    Style('''
          .settings:hover {
              background-color: lightgreen;
              cursor: pointer;
          }'''),
    Link(rel="stylesheet", href="/styles.css")
]
app, rt = fast_app(pico=False, before=bwares, hdrs=hdrs, exts='ws', bodykw={'hx-boost': 'true'}, static_path='./static')


async def send(u: BaseLobbyMember, fn, *args):
    try:
        await u.ws(fn(*args))
    except:
        u.ws = None


async def notify_all(lobby: BaseLobby, fn: Callable, *args):
    tasks = [send(u, fn, lobby, *args) for u in lobby.members.values() if u.is_connected]
    await asyncio.gather(*tasks)


def ws_fn(connected=True, render_fn_on_join: Callable = fc.noop):
    async def user_joined(sess, send):
        u = user_manager.get_or_create(sess)
        lobby: Lobby = lobby_manager.get_lobby(sess.get('lobby_id'))
        if not lobby:
            return
        ws = send if connected else None
        if m := lobby.get_member(u.uid):
            m.ws = ws
            def update(lobby): return UserName(m.user, is_connected=connected)
        else:
            if ws is None:
                return  # user not found in the lobby and not connecting
            m = lobby.add_member(u, ws=ws)
            def update(lobby): return render_fn_on_join(m)

        await notify_all(lobby, update)

    return user_joined


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

    def update(lobby): return UserName(u)
    await notify_all(lobby, update)


def Settings():
    styles = Style('''
          .settings-block {
              position: fixed;
              bottom: 0;
              right: 0;
              display: flex;
              flex-direction: row-reverse;
          }''')
    return Div(
        styles,
        I('settings', cls="material-icons settings"),
        NameSetting(),
        cls='settings-block panel'
    )


@dataclass
class WhoAmIPlayer(BaseLobbyMember):
    label: str = ''
    notes: str = ''

    def set_note(self, notes: str): self.notes = notes
    def set_label(self, label: str): self.label = label


@dataclass
class WhoAmILobby(BaseLobby[WhoAmIPlayer]):
    @classmethod
    def create_member(cls, user: User, ws=None):
        return WhoAmIPlayer(user, ws=ws)


def PlayerCard(p: WhoAmIPlayer):
    return Div(
        UserName(p.user, cls='username' + ('' if p.is_connected else ' muted')),
        Div(f"ID: {p.uid}"),
        Img(src=('/user-content/'+p.filename) if p.filename else None),
        Form(Input(type='file', name='file', accept="image/*"),
             Input(type="submit"), hx_post='/picture', hx_swap='none'),
        cls='panel', hx_swap_oob='beforeend:#players'
    )


def Game(lobby: WhoAmILobby):
    return Div(
        *[PlayerCard(p) for p in lobby.members.values()],
        id='players'
    )


@rt("/whoami/{lobby_id}")
def get(req: Request, lobby_id: str = None):
    if not lobby_id: return Redirect(f"/whoami/{random_id()}")
    u: User = req.state.user
    lobby: WhoAmILobby
    lobby, _ = lobby_manager.get_or_create(u, lobby_id, WhoAmILobby)
    req.session['lobby_id'] = lobby.id
    return Titled(f'Lobby {lobby.id}',
                  Game(lobby),
                  Div(hx_ext='ws', ws_connect='/ws/whoami'),
                  Div(id='background'), Settings())


@app.ws('/ws/whoami', conn=ws_fn(render_fn_on_join=PlayerCard), disconn=ws_fn(connected=False, render_fn_on_join=PlayerCard))
async def ws(send): pass


@rt('/picture')
async def post(req: Request, file: UploadFile):
    u: User = req.state.user
    await u.set_picture(file)
    user_manager.update(u)
    lobby = lobby_manager.get_lobby(req.session.get("lobby_id"))
    if not lobby: return
    lobby.get_member(u.uid).sync_user(u)
    await notify_all(lobby, Game)


serve(port=8000)
