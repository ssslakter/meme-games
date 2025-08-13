from meme_games.core import *
from typing import Type, get_args
from meme_games.domain import LobbyMember, User, Lobby, LobbyService
from meme_games.domain.notify import notify_all, notify
from meme_games.apps.user.components import MemberName
from ..shared.utils import register_route
from .settings import logger


rt = APIRouter('/lobby')
register_route(rt)

def prep_data(req: Request) -> tuple[Lobby, LobbyMember]:
    try: lobby = req.state.lobby
    except AttributeError as e:
        logger.error(f"Lobby not found in request state: {req.state}")
        raise HTTPException(status_code=400, detail="Incorrect client state. Please refresh the page.")
    return lobby, lobby.get_member(req.state.user.uid)


def SpectatorsList(reciever: LobbyMember | User, lobby: Lobby):
    return Div(
            *[
                MemberName(reciever, p)
                for p in lobby.sorted_members()
                if not p.is_player
            ],
            id="spectators",
            cls="flex flex-col gap-1",
        )

def Spectators(reciever: LobbyMember | User, lobby: Lobby, cls = 'right-0 top-1/3 -translate-y-1/2'):
    return Card(
        "Spectators: ",
        SpectatorsList(reciever, lobby),
        body_cls='p-2',
        hx_post=spectate,
        hx_swap='none',
        tabindex="0",
        cls=f"fixed rounded-r-none p-2 cursor-pointer {cls}"
    )


def JoinSpectators(r: LobbyMember, p: LobbyMember):
    return Div(MemberName(r.user, p), hx_swap_oob="beforeend:#spectators")


@rt
async def spectate(req: Request):
    lobby, p = prep_data(req)
    if not p.is_player: return
    if lobby.locked: return add_toast(req.session, "Game is locked", "error")
    DI.get(LobbyService).spectate(p, lobby)

    upd, send = SPECTATORS_NOTIFY_REGISTRY[lobby.current_type]
    def update(r: LobbyMember, *_):
        return JoinSpectators(r, p), upd(r, lobby, p)
    await notify_all(lobby, update)
    if send: await notify(p, send, lobby)


SPECTATORS_NOTIFY_REGISTRY: dict[str, tuple[Callable, Callable]] = {}

def register_lobby_spectators_update[T: LobbyMember, State: Any](
        target_type: Type['Lobby[T,State]'],
        update_fn: Callable[[LobbyMember, Lobby, LobbyMember], Any],
        update_sender: Callable[[LobbyMember, Lobby], Any] = None):
    name = target_type.__name__.lower() + '_' + get_args(target_type)[0].__name__.lower()
    SPECTATORS_NOTIFY_REGISTRY[name] = (update_fn, update_sender)
